"""
Initialize the RAG vector store by ingesting all PDFs from src/data/.

This is now a thin wrapper around RagService.ingest_dir() — the single,
authoritative ingestion pipeline.  The previous LangChain-based implementation
(chunk_size=400, no metadata) has been replaced because:
  - 400-char chunks are too small for legal clauses (split mid-sentence)
  - No metadata meant jurisdiction/zone filtering silently returned nothing
  - Two pipelines creating the same collection caused duplicate/mixed chunks

Run:
    python -m agent.zoning_agent.init_rag
"""
import logging
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path, override=False)
    else:
        load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def init_rag_database() -> bool:

    base_dir     = Path(__file__).resolve().parent
    data_dir     = base_dir / "src" / "data"
    chroma_dir   = base_dir / "src" / "chroma_db"

    if not data_dir.exists() or not list(data_dir.glob("*.pdf")):
        logger.error("No PDF files found in %s", data_dir)
        return False

    try:
        from agent.zoning_agent.rag_service import RagService
    except ImportError:
        from rag_service import RagService

    logger.info("Initializing RagService at %s", chroma_dir)
    svc = RagService(persist_dir=chroma_dir)

    pdf_files = sorted(data_dir.glob("*.pdf"))
    logger.info("Found %d PDF files — starting ingestion...", len(pdf_files))

    total = svc.ingest_dir(data_dir)
    logger.info("Ingestion complete. %d new chunks added to collection '%s'.",
                total, "zoning_docs")
    logger.info("Collection now has %d total chunks.", svc.collection.count())
    return True


if __name__ == "__main__":
    success = init_rag_database()
    if success:
        print("\nRAG system initialized successfully.")
    else:
        print("\nFailed to initialize RAG system. Check logs above.")
