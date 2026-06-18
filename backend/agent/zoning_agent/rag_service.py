from __future__ import annotations

import os
import re
import uuid
import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader
from chromadb.config import Settings

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from openai import OpenAI as _OpenAI  # type: ignore
    _OPENAI_AVAILABLE = True
except ImportError:
    _OpenAI = None  # type: ignore
    _OPENAI_AVAILABLE = False


@dataclass
class RetrievedChunk:
    id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class RagService:
    """
    Jurisdiction-aware RAG for San Diego zoning regulations.

    Pipeline:
      ingest_dir() → PDF chunks stored in ChromaDB with rich metadata
      retrieve()   → semantic search + optional MMR reranking (no extra embedding API call)
      answer()     → GPT-4o-mini with conversation history + citations

    Changes from original (see CHANGELOG.md):
      - Chunk size raised 1000→1500 chars, overlap 200→300 (better legal-text context)
      - _mmr() fully vectorized with NumPy; query re-embedding eliminated
      - Conversation history stored per session and passed to GPT
      - init_rag.py (conflicting LangChain pipeline) replaced; this is the single ingest path
    """

    ZONE_PATTERNS = {
        "Agricultural": re.compile(r'\bA\d{2}\b'),
        "Residential":  re.compile(r'\b(RS|RD|RM|RV|RU|RMH|RR|RRO|RC)[-\s]?\d*\b'),
        "Commercial":   re.compile(r'\bC\d{2}\b'),
        "Industrial":   re.compile(r'\bM\d{2}\b'),
        "Special":      re.compile(r'\bS\d{2}\b'),
    }

    @staticmethod
    def _make_chunk_id(source_name: str, start_page: int, end_page: int, text: str) -> str:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"{source_name}:{start_page}-{end_page}:{content_hash}"

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "zoning_docs",
        openai_model: str = "gpt-4o",
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        if load_dotenv is not None:
            zoning_agent_dir = Path(__file__).resolve().parent
            for env_path in (zoning_agent_dir / ".env", zoning_agent_dir / "src" / ".env"):
                if env_path.exists():
                    load_dotenv(dotenv_path=env_path, override=False)
                    break
            else:
                load_dotenv()

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )

        # Local sentence-transformers embeddings — no API key required
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model,
        )
        try:
            self.collection = self.client.get_collection(
                name=collection_name, embedding_function=self.embedding_fn
            )
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name, embedding_function=self.embedding_fn
            )

        self.openai_model = openai_model
        openai_key = os.environ.get("OPENAI_API_KEY")
        if _OPENAI_AVAILABLE and openai_key:
            self._openai_client = _OpenAI(api_key=openai_key)
        else:
            self._openai_client = None

    # -----------------------
    # Jurisdiction & Zone Detection
    # -----------------------

    def _detect_jurisdiction(self, pdf_path: Path, text_sample: str) -> str:
        filename = pdf_path.name.lower()
        text_lower = text_sample.lower()

        if "county" in filename or "unincorporated" in filename:
            return "San Diego County"
        if "municipal" in filename or "city" in filename or "chapter" in filename:
            return "City of San Diego"

        county_markers = ["unincorporated", "county of san diego", "county zoning ordinance"]
        city_markers   = ["municipal code", "city of san diego", "chapter 13"]
        county_score = sum(1 for m in county_markers if m in text_lower)
        city_score   = sum(1 for m in city_markers   if m in text_lower)

        if county_score > city_score:
            return "San Diego County"
        if city_score > county_score:
            return "City of San Diego"
        return "Unknown"

    def _extract_zone_categories(self, text: str) -> List[str]:
        return [cat for cat, pat in self.ZONE_PATTERNS.items() if pat.search(text)]

    def _extract_section_number(self, text: str) -> Optional[str]:
        for pattern in (r'§(131\.\d{4})', r'§(\d{4})', r'\bSection\s+(\d{4})\b'):
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _get_zone_category(self, zoning_code: str) -> str:
        if not zoning_code:
            return "Unknown"
        for cat, pat in self.ZONE_PATTERNS.items():
            if pat.search(zoning_code):
                return cat
        return "Unknown"

    # -----------------------
    # Ingestion  (single pipeline — init_rag.py delegates here)
    # -----------------------

    def ingest_dir(self, data_dir: Path) -> int:
        data_dir = Path(data_dir)
        if not data_dir.exists():
            return 0
        total = 0
        for pdf_path in sorted(data_dir.glob("*.pdf")):
            total += self._ingest_pdf(pdf_path)
        return total

    def _ingest_pdf(self, pdf_path: Path, chunk_chars: int = 1500, overlap: int = 300) -> int:
        """
        Ingest one PDF.

        chunk_chars raised 1000→1500, overlap 200→300 so legal clauses aren't
        split mid-sentence.  Chunk IDs are deterministic (SHA256) so re-runs are
        idempotent — duplicate chunks are never added.
        """
        reader = PdfReader(str(pdf_path))
        pages = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append((i + 1, text))

        sample_text = "\n".join(t for _, t in pages[:3])
        jurisdiction = self._detect_jurisdiction(pdf_path, sample_text)

        docs: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []

        buf = ""
        start_page = 1

        for page_num, text in pages:
            if not text:
                continue
            for para in self._split_with_sections(text):
                para = para.strip()
                if not para or len(para) < 50:
                    continue
                buf = (buf + "\n\n" + para) if buf else para

                if len(buf) >= chunk_chars:
                    zone_cats  = self._extract_zone_categories(buf)
                    section    = self._extract_section_number(buf)
                    chunk_id   = self._make_chunk_id(pdf_path.stem, start_page, page_num, buf)
                    docs.append(buf)
                    metadatas.append({
                        "source":          str(pdf_path.name),
                        "jurisdiction":    jurisdiction,
                        "zone_categories": ",".join(zone_cats) if zone_cats else "",
                        "section":         section or "",
                        "start_page":      start_page,
                        "end_page":        page_num,
                        "ingested_ts":     int(time.time()),
                    })
                    ids.append(chunk_id)
                    buf = buf[-overlap:]
                    start_page = page_num

        if buf and len(buf) >= 100:
            zone_cats = self._extract_zone_categories(buf)
            section   = self._extract_section_number(buf)
            chunk_id  = self._make_chunk_id(pdf_path.stem, start_page, pages[-1][0], buf)
            docs.append(buf)
            metadatas.append({
                "source":          str(pdf_path.name),
                "jurisdiction":    jurisdiction,
                "zone_categories": ",".join(zone_cats) if zone_cats else "",
                "section":         section or "",
                "start_page":      start_page,
                "end_page":        pages[-1][0],
                "ingested_ts":     int(time.time()),
            })
            ids.append(chunk_id)

        if not docs:
            return 0

        # Idempotent: skip chunks already in the collection
        existing: set = set()
        try:
            for i in range(0, len(ids), 100):
                got = self.collection.get(ids=ids[i:i + 100])
                existing.update(got.get("ids") or [])
        except Exception:
            pass

        to_add = [i for i, cid in enumerate(ids) if cid not in existing]
        if not to_add:
            return 0

        self.collection.add(
            ids       =[ids[i]       for i in to_add],
            documents =[docs[i]      for i in to_add],
            metadatas =[metadatas[i] for i in to_add],
        )
        return len(to_add)

    def _split_with_sections(self, text: str) -> List[str]:
        section_pattern = re.compile(r'(§\d{4}|Section\s+\d{4})', re.IGNORECASE)
        if not section_pattern.search(text):
            return text.split("\n\n")
        parts = section_pattern.split(text)
        paragraphs = []
        for i in range(0, len(parts), 2):
            paragraphs.append(parts[i] + (parts[i + 1] if i + 1 < len(parts) else ""))
        return paragraphs

    # -----------------------
    # Retrieval
    # -----------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        mmr: bool = True,
        jurisdiction_filter: Optional[str] = None,
        zone_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        where_filter = {}
        if jurisdiction_filter:
            where_filter["jurisdiction"] = jurisdiction_filter

        over_k = max(top_k * 3, 12)

        q = self.collection.query(
            query_texts=[query],
            n_results=over_k,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )

        ids   = (q.get("ids")       or [[]])[0]
        docs  = (q.get("documents") or [[]])[0]
        metas = (q.get("metadatas") or [[]])[0]
        dists = (q.get("distances") or [[]])[0]

        if not ids:
            return []

        # Post-filter by zone category; fall back to unfiltered if no matches
        if zone_filter:
            zone_idx = [i for i, m in enumerate(metas) if zone_filter in (m or {}).get("zone_categories", "")]
            if zone_idx:
                ids   = [ids[i]   for i in zone_idx]
                docs  = [docs[i]  for i in zone_idx]
                metas = [metas[i] for i in zone_idx]
                dists = [dists[i] for i in zone_idx]
            # If no zone match, keep all — better to return something than nothing

        if not mmr or len(ids) <= top_k:
            return [
                RetrievedChunk(
                    id=_id, text=doc,
                    score=float(1.0 - (d or 0.0)),
                    metadata=meta or {},
                )
                for _id, doc, meta, d in zip(ids[:top_k], docs[:top_k], metas[:top_k], dists[:top_k])
            ]

        # MMR using Chroma distances as relevance (no extra embedding API call)
        got      = self.collection.get(ids=ids, include=["embeddings", "metadatas", "documents"])
        emb_raw  = got.get("embeddings")
        if emb_raw is None:
            emb_list = []
        elif hasattr(emb_raw, "tolist"):
            emb_list = emb_raw.tolist()
        else:
            emb_list = list(emb_raw)

        if not emb_list:
            return [
                RetrievedChunk(id=ids[i], text=docs[i], score=1.0 - dists[i], metadata=metas[i] or {})
                for i in range(min(top_k, len(ids)))
            ]

        # sim_to_query derived directly from Chroma distances — avoids a second embedding call
        sim_to_query = 1.0 - np.clip(np.array(dists[:len(emb_list)], dtype=float), 0.0, 1.0)
        doc_vecs     = np.array(emb_list, dtype=float)

        order = self._mmr_vectorized(sim_to_query, doc_vecs, top_k=top_k, lambda_mult=0.4)

        return [
            RetrievedChunk(
                id=ids[i], text=docs[i],
                score=float(sim_to_query[i]) if i < len(sim_to_query) else 0.0,
                metadata=metas[i] or {},
            )
            for i in order
        ]

    def _mmr_vectorized(
        self,
        sim_to_query: np.ndarray,
        doc_vecs: np.ndarray,
        top_k: int,
        lambda_mult: float = 0.5,
    ) -> List[int]:
        """
        Fully vectorized MMR selection.

        Replaces the original O(n²) Python-loop implementation.  After each pick
        we update max_sim_to_selected with a single np.maximum() call instead of
        re-computing all pairwise sims from scratch.

        No query re-embedding needed — sim_to_query comes from Chroma distances.
        """
        n = len(sim_to_query)
        if n == 0:
            return []

        # Normalize doc vectors once; pairwise sims via matrix multiply
        norms    = np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-12
        D        = doc_vecs / norms                  # (n, dim)
        sim_mat  = D @ D.T                           # (n, n)  pairwise

        selected:              List[int]  = []
        selected_mask:         np.ndarray = np.zeros(n, dtype=bool)
        max_sim_to_selected:   np.ndarray = np.full(n, -np.inf)

        for _ in range(min(top_k, n)):
            if not selected:
                idx = int(np.argmax(sim_to_query))
            else:
                scores = lambda_mult * sim_to_query - (1.0 - lambda_mult) * max_sim_to_selected
                scores[selected_mask] = -np.inf
                idx = int(np.argmax(scores))

            selected.append(idx)
            selected_mask[idx] = True
            # Incremental update — O(n) per iteration instead of O(n²)
            max_sim_to_selected = np.maximum(max_sim_to_selected, sim_mat[:, idx])

        return selected

    # -----------------------
    # Answer Generation
    # -----------------------

    def answer(
        self,
        question: str,
        parcel_ctx: Optional[Dict[str, Any]],
        retrieved: List[RetrievedChunk],
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Generate an answer using GPT-4o-mini with full conversation history.

        history: list of {"question": str, "answer": str} dicts, oldest first.
                 The last 8 turns (4 Q&A pairs) are included to stay within
                 token budget.
        """
        if not self._openai_client:
            # No API key — return structured plaintext from retrieved chunks
            lines = []
            for r in retrieved[:4]:
                juris = r.metadata.get("jurisdiction", "Unknown")
                sect  = r.metadata.get("section", "")
                src   = r.metadata.get("source", "")
                lines.append(f"[{juris}{(' §' + sect) if sect else ''}, {src}]\n{r.text[:300]}")
            return "\n\n".join(lines) if lines else "No zoning information found for this query."

        jurisdiction  = (parcel_ctx or {}).get("JURISDICTION", "")
        zoning_code   = (parcel_ctx or {}).get("ZONING_CODE", "")
        zone_category = self._get_zone_category(zoning_code)

        system = f"""You are a San Diego zoning compliance expert.

CRITICAL RULES:
1. This parcel is in {jurisdiction or 'San Diego'}.
   - If County: cite County Zoning Ordinance sections (§1000-9999)
   - If City: cite San Diego Municipal Code Chapter 13 (§131.xxxx)
2. For {zoning_code or 'the'} zone ({zone_category} category):
   - Explain allowed uses from the use table
   - State minimum lot size, maximum height, setbacks
   - Mention any special requirements or permits needed
3. Always cite specific section numbers when available.
4. For suitability/feasibility questions discuss development requirements and
   practical site constraints. Avoid financial advice.
5. If information is not in the provided context, say so and suggest consulting County/City Planning.

Answer based ONLY on the provided parcel context and retrieved excerpts."""

        # Build context block
        ctx_lines: List[str] = []
        if parcel_ctx:
            ctx_lines.append("**Parcel Context:**")
            for k in ["APN", "JURISDICTION", "ZONING_CODE", "GP_LAND_USE", "MAX_HEIGHT", "MIN_LOT_SIZE", "MAX_FAR"]:
                v = parcel_ctx.get(k)
                if v is not None:
                    ctx_lines.append(f"- {k}: {v}")

        if retrieved:
            ctx_lines.append("\n**Relevant Zoning Regulations:**")
            for r in retrieved[:6]:
                juris = r.metadata.get("jurisdiction", "")
                sect  = r.metadata.get("section", "")
                src   = r.metadata.get("source", "")
                sp    = r.metadata.get("start_page", "")
                ep    = r.metadata.get("end_page", "")
                cite  = f"[{juris}{(' §' + sect) if sect else ''}, {src} p.{sp}-{ep}]"
                ctx_lines.append(f"{cite}\n{r.text}\n")

        user_prompt = (
            "\n".join(ctx_lines)
            + f"\n\n**Question:** {question}"
            + "\n\nProvide a clear, accurate answer with proper citations."
        )

        # Build messages with conversation history (OpenAI format)
        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
        for turn in (history or [])[-8:]:      # last 4 Q&A pairs
            messages.append({"role": "user",      "content": turn["question"]})
            messages.append({"role": "assistant", "content": turn["answer"]})
        messages.append({"role": "user", "content": user_prompt})

        try:
            resp = self._openai_client.chat.completions.create(
                model=self.openai_model,
                messages=messages,
                temperature=0.2,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            # API unavailable — return clean plaintext from retrieved chunks
            lines = []
            for r in retrieved[:4]:
                juris = r.metadata.get("jurisdiction", "Unknown")
                sect  = r.metadata.get("section", "")
                src   = r.metadata.get("source", "")
                lines.append(f"[{juris}{(' §' + sect) if sect else ''}, {src}]\n{r.text[:300]}")
            return "\n\n".join(lines) if lines else f"OpenAI API error: {exc}"

    # -----------------------
    # Query Construction & Filters
    # -----------------------

    def construct_query(self, question: str, parcel_ctx: Optional[Dict[str, Any]]) -> str:
        parts = [question]
        if parcel_ctx:
            hints = []
            j  = parcel_ctx.get("JURISDICTION") or parcel_ctx.get("Name", "")
            z  = parcel_ctx.get("ZONING_CODE", "")
            gp = parcel_ctx.get("GP_LAND_USE") or parcel_ctx.get("GP_LU_DESC", "")

            if j:
                if "COUNTY" in j.upper():
                    hints.append("county zoning ordinance")
                elif "CITY" in j.upper() or "SAN DIEGO" in j.upper():
                    hints.append("municipal code")
                else:
                    hints.append(f"jurisdiction: {j}")

            if z:
                hints.append(f"{z} zone")
                cat = self._get_zone_category(z)
                if cat != "Unknown":
                    hints.append(f"{cat.lower()} use")

            if gp:
                hints.append(f"general plan: {gp}")

            if hints:
                parts.append("(" + ", ".join(hints) + ")")
        return " ".join(parts)

    def get_jurisdiction_filter(self, parcel_ctx: Optional[Dict[str, Any]]) -> Optional[str]:
        if not parcel_ctx:
            return None
        j = parcel_ctx.get("JURISDICTION", "")
        if "COUNTY" in j.upper():
            return "San Diego County"
        if "CITY" in j.upper() or "SAN DIEGO" in j.upper():
            return "City of San Diego"
        return None

    def get_zone_filter(self, parcel_ctx: Optional[Dict[str, Any]]) -> Optional[str]:
        if not parcel_ctx:
            return None
        cat = self._get_zone_category(parcel_ctx.get("ZONING_CODE", ""))
        return cat if cat != "Unknown" else None


# -----------------------
# Session Store
# -----------------------

class ChatSessionStore:
    """
    In-memory session store.

    Stores per-session:
      - apn / parcel_ctx  (set on first message or parcel change)
      - history           (list of {"question", "answer"} dicts, capped at max_history)
    """

    MAX_HISTORY_TURNS = 20  # store up to 20 Q&A pairs; only last 4 sent to GPT

    def __init__(self, max_sessions: int = 5000, ttl_seconds: int = 86400) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._max_sessions = max(1, int(max_sessions))
        self._ttl_seconds  = max(60, int(ttl_seconds))
        self._lock = Lock()

    def _prune_locked(self) -> None:
        now    = time.time()
        cutoff = now - float(self._ttl_seconds)
        stale  = [sid for sid, p in self._store.items() if float(p.get("ts", 0)) < cutoff]
        for sid in stale:
            self._store.pop(sid, None)
        overflow = len(self._store) - self._max_sessions
        if overflow > 0:
            oldest = sorted(self._store.items(), key=lambda x: float(x[1].get("ts", 0)))
            for sid, _ in oldest[:overflow]:
                self._store.pop(sid, None)

    def _get_entry(self, session_id: str) -> Dict[str, Any]:
        return self._store.setdefault(session_id, {
            "apn": None, "parcel_ctx": None, "history": [], "ts": time.time()
        })

    def ensure(self, session_id: Optional[str]) -> str:
        with self._lock:
            self._prune_locked()
            if session_id and session_id in self._store:
                self._store[session_id]["ts"] = time.time()
                return session_id
            sid = session_id or uuid.uuid4().hex
            self._get_entry(sid)
            return sid

    def set_parcel(self, session_id: str, apn: Optional[str], ctx: Optional[Dict[str, Any]]) -> None:
        with self._lock:
            self._prune_locked()
            entry = self._get_entry(session_id)
            entry["apn"]        = apn
            entry["parcel_ctx"] = ctx
            entry["ts"]         = time.time()

    def get_parcel(self, session_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        with self._lock:
            self._prune_locked()
            entry = self._store.get(session_id) or {}
            if entry:
                entry["ts"] = time.time()
            return entry.get("apn"), entry.get("parcel_ctx")

    def add_turn(self, session_id: str, question: str, answer: str) -> None:
        """Append a Q&A pair to this session's conversation history."""
        with self._lock:
            entry = self._get_entry(session_id)
            history: List[Dict[str, str]] = entry.setdefault("history", [])
            history.append({"question": question, "answer": answer})
            # Trim to cap — keep the most recent turns
            if len(history) > self.MAX_HISTORY_TURNS:
                entry["history"] = history[-self.MAX_HISTORY_TURNS:]
            entry["ts"] = time.time()

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Return the full stored history for this session (oldest first)."""
        with self._lock:
            entry = self._store.get(session_id) or {}
            return list(entry.get("history", []))
