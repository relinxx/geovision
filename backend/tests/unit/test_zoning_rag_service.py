"""
Unit tests for the Zoning RAG model/service layer.

These tests intentionally avoid starting ChromaDB, sentence-transformers,
or OpenAI. The goal is to test the RAG service's own logic in isolation:

1. zoning/jurisdiction detection
2. query construction
3. retrieval post-filtering behavior
4. fallback answer formatting
5. chat session memory
"""

import importlib.util
import sys
import time
import types

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Optional dependency guard
# ---------------------------------------------------------------------------
# rag_service.py imports ChromaDB and pypdf at module import time.
# These unit tests do not use the real ChromaDB client or real PDFs.
#
# So if those heavy RAG dependencies are missing in your local test environment,
# we install tiny fake modules so the pure unit tests can still run.
#
# If your virtual environment already has the real packages installed,
# these stubs are not used.
if importlib.util.find_spec("chromadb") is None:
    fake_chromadb = types.ModuleType("chromadb")
    fake_chromadb.PersistentClient = lambda *args, **kwargs: None

    fake_chromadb_utils = types.ModuleType("chromadb.utils")
    fake_embedding_functions = types.ModuleType("chromadb.utils.embedding_functions")
    fake_embedding_functions.SentenceTransformerEmbeddingFunction = lambda *args, **kwargs: None

    fake_chromadb_config = types.ModuleType("chromadb.config")
    fake_chromadb_config.Settings = lambda *args, **kwargs: None

    sys.modules["chromadb"] = fake_chromadb
    sys.modules["chromadb.utils"] = fake_chromadb_utils
    sys.modules["chromadb.utils.embedding_functions"] = fake_embedding_functions
    sys.modules["chromadb.config"] = fake_chromadb_config

if importlib.util.find_spec("pypdf") is None:
    fake_pypdf = types.ModuleType("pypdf")
    fake_pypdf.PdfReader = lambda *args, **kwargs: None
    sys.modules["pypdf"] = fake_pypdf


from agent.zoning_agent.rag_service import ChatSessionStore, RagService, RetrievedChunk


def make_rag_service_without_external_dependencies() -> RagService:
    """
    Create a RagService object without calling RagService.__init__().

    Why:
    - __init__ creates a persistent Chroma client.
    - __init__ may load sentence-transformer embeddings.
    - Unit tests should not depend on external vector databases or model downloads.

    This is safe for testing pure methods because methods like construct_query(),
    get_zone_filter(), _extract_section_number(), etc. do not need Chroma.
    """
    service = RagService.__new__(RagService)
    service._openai_client = None
    service.openai_model = "test-model"
    return service


def test_make_chunk_id_is_deterministic_and_changes_when_text_changes():
    """
    Chunk IDs should be deterministic.

    This matters because ingestion uses chunk IDs to avoid adding duplicate
    chunks when the same PDF is ingested again.
    """
    first_id = RagService._make_chunk_id(
        source_name="city-code",
        start_page=1,
        end_page=2,
        text="Residential zoning rules",
    )
    second_id = RagService._make_chunk_id(
        source_name="city-code",
        start_page=1,
        end_page=2,
        text="Residential zoning rules",
    )
    changed_text_id = RagService._make_chunk_id(
        source_name="city-code",
        start_page=1,
        end_page=2,
        text="Commercial zoning rules",
    )

    assert first_id == second_id
    assert first_id != changed_text_id
    assert first_id.startswith("city-code:1-2:")


def test_detect_jurisdiction_from_file_name_and_text_sample(tmp_path):
    """
    Jurisdiction detection is used during ingestion metadata creation.

    The service should detect County/City docs from either filename or text.
    """
    service = make_rag_service_without_external_dependencies()

    county_pdf = tmp_path / "county-zoning-ordinance.pdf"
    city_pdf = tmp_path / "municipal-code-chapter-13.pdf"
    unknown_pdf = tmp_path / "planning-rules.pdf"

    assert service._detect_jurisdiction(county_pdf, "") == "San Diego County"
    assert service._detect_jurisdiction(city_pdf, "") == "City of San Diego"

    assert (
        service._detect_jurisdiction(
            unknown_pdf,
            "This text discusses the County of San Diego and unincorporated zoning.",
        )
        == "San Diego County"
    )
    assert (
        service._detect_jurisdiction(
            unknown_pdf,
            "This text discusses the City of San Diego municipal code chapter 13.",
        )
        == "City of San Diego"
    )
    assert service._detect_jurisdiction(unknown_pdf, "generic planning document") == "Unknown"


@pytest.mark.parametrize(
    "text, expected_categories",
    [
        ("The parcel is in zone RS-1-7.", ["Residential"]),
        ("The property is in commercial zone C12.", ["Commercial"]),
        ("Industrial activity is allowed in M20.", ["Industrial"]),
        ("Agricultural regulations for A70 apply.", ["Agricultural"]),
        ("Special purpose rules for S88 apply.", ["Special"]),
        ("RS-1-7 and C12 are both mentioned.", ["Residential", "Commercial"]),
    ],
)
def test_extract_zone_categories(text, expected_categories):
    """
    The RAG service stores zone category metadata on chunks.

    Later, retrieval can use this metadata to prefer chunks related to the
    selected parcel's zoning category.
    """
    service = make_rag_service_without_external_dependencies()

    categories = service._extract_zone_categories(text)

    assert categories == expected_categories


@pytest.mark.parametrize(
    "text, expected_section",
    [
        ("See §131.0431 for development regulations.", "131.0431"),
        ("County rules are listed in §1000.", "1000"),
        ("Section 2000 explains permit rules.", "2000"),
        ("No section appears here.", None),
    ],
)
def test_extract_section_number(text, expected_section):
    """
    Section extraction should capture legal citations when available.
    """
    service = make_rag_service_without_external_dependencies()

    assert service._extract_section_number(text) == expected_section


@pytest.mark.parametrize(
    "zoning_code, expected_category",
    [
        ("RS-1-7", "Residential"),
        ("RM-3-7", "Residential"),
        ("C12", "Commercial"),
        ("M20", "Industrial"),
        ("A70", "Agricultural"),
        ("S88", "Special"),
        ("", "Unknown"),
        ("UNKNOWN-ZONE", "Unknown"),
    ],
)
def test_get_zone_category(zoning_code, expected_category):
    """
    A zoning code should map to a broad zone category.

    This category is later used as a retrieval filter.
    """
    service = make_rag_service_without_external_dependencies()

    assert service._get_zone_category(zoning_code) == expected_category


def test_split_with_sections_keeps_section_markers_with_text():
    """
    Section-aware splitting helps avoid losing section numbers during ingestion.

    This test checks that text with legal section markers is split into chunks
    that still include those markers.
    """
    service = make_rag_service_without_external_dependencies()

    text = "Intro text\n\n§1000 County zone rules\n\nSection 2000 Permit requirements"

    parts = service._split_with_sections(text)

    assert any("§1000" in part for part in parts)
    assert any("Section 2000" in part for part in parts)


def test_construct_query_adds_jurisdiction_zone_and_general_plan_hints():
    """
    The constructed query should include useful hints from the selected parcel.

    This improves retrieval because the user may ask a short question such as
    'What can I build here?' while the parcel context contains the important
    zoning information.
    """
    service = make_rag_service_without_external_dependencies()

    query = service.construct_query(
        "What can I build here?",
        {
            "JURISDICTION": "City of San Diego",
            "ZONING_CODE": "RS-1-7",
            "GP_LAND_USE": "Residential",
        },
    )

    assert "What can I build here?" in query
    assert "municipal code" in query
    assert "RS-1-7 zone" in query
    assert "residential use" in query
    assert "general plan: Residential" in query


def test_construct_query_handles_county_context():
    """
    County parcels should add a county zoning ordinance hint.
    """
    service = make_rag_service_without_external_dependencies()

    query = service.construct_query(
        "What are the height limits?",
        {
            "JURISDICTION": "San Diego County",
            "ZONING_CODE": "A70",
        },
    )

    assert "county zoning ordinance" in query
    assert "A70 zone" in query
    assert "agricultural use" in query


def test_get_jurisdiction_filter_returns_chroma_metadata_value():
    """
    Jurisdiction filter should return the exact metadata value used in Chroma.
    """
    service = make_rag_service_without_external_dependencies()

    assert (
        service.get_jurisdiction_filter({"JURISDICTION": "San Diego County"})
        == "San Diego County"
    )
    assert (
        service.get_jurisdiction_filter({"JURISDICTION": "City of San Diego"})
        == "City of San Diego"
    )
    assert service.get_jurisdiction_filter({"JURISDICTION": "Unknown"}) is None
    assert service.get_jurisdiction_filter(None) is None


def test_get_zone_filter_returns_category_for_known_zone():
    """
    Zone filter should convert detailed zoning code into broad category.
    """
    service = make_rag_service_without_external_dependencies()

    assert service.get_zone_filter({"ZONING_CODE": "RS-1-7"}) == "Residential"
    assert service.get_zone_filter({"ZONING_CODE": "C12"}) == "Commercial"
    assert service.get_zone_filter({"ZONING_CODE": "UNKNOWN"}) is None
    assert service.get_zone_filter(None) is None


def test_mmr_vectorized_selects_relevant_and_diverse_documents():
    """
    MMR should select the most relevant document first, then avoid choosing
    only near-duplicate documents when alternatives exist.
    """
    service = make_rag_service_without_external_dependencies()

    sim_to_query = np.array([0.95, 0.90, 0.70])

    # doc 0 and doc 1 are very similar.
    # doc 2 is different, so MMR should prefer it after choosing doc 0.
    doc_vecs = np.array(
        [
            [1.00, 0.00],
            [0.99, 0.01],
            [0.00, 1.00],
        ]
    )

    selected = service._mmr_vectorized(
        sim_to_query=sim_to_query,
        doc_vecs=doc_vecs,
        top_k=2,
        lambda_mult=0.4,
    )

    assert selected == [0, 2]


class FakeCollection:
    """
    Minimal fake Chroma collection used to test retrieve() without ChromaDB.
    """

    def __init__(self):
        self.last_query_kwargs = None

    def query(self, **kwargs):
        self.last_query_kwargs = kwargs
        return {
            "ids": [["residential-chunk", "commercial-chunk", "general-chunk"]],
            "documents": [[
                "Residential rules for RS zones.",
                "Commercial rules for C zones.",
                "General zoning introduction.",
            ]],
            "metadatas": [[
                {
                    "jurisdiction": "City of San Diego",
                    "zone_categories": "Residential",
                    "source": "city.pdf",
                    "start_page": 1,
                    "end_page": 2,
                },
                {
                    "jurisdiction": "City of San Diego",
                    "zone_categories": "Commercial",
                    "source": "city.pdf",
                    "start_page": 3,
                    "end_page": 4,
                },
                {
                    "jurisdiction": "City of San Diego",
                    "zone_categories": "",
                    "source": "city.pdf",
                    "start_page": 5,
                    "end_page": 6,
                },
            ]],
            "distances": [[0.10, 0.20, 0.30]],
        }


def test_retrieve_passes_jurisdiction_filter_to_collection_and_post_filters_by_zone():
    """
    retrieve() should pass jurisdiction filtering to Chroma and then apply
    zone-category filtering after results come back.
    """
    service = make_rag_service_without_external_dependencies()
    service.collection = FakeCollection()

    chunks = service.retrieve(
        query="What can I build?",
        top_k=2,
        mmr=False,
        jurisdiction_filter="City of San Diego",
        zone_filter="Residential",
    )

    assert service.collection.last_query_kwargs["where"] == {
        "jurisdiction": "City of San Diego"
    }
    assert len(chunks) == 1
    assert chunks[0].id == "residential-chunk"
    assert chunks[0].score == pytest.approx(0.90)
    assert chunks[0].metadata["zone_categories"] == "Residential"


def test_retrieve_falls_back_to_unfiltered_results_when_zone_has_no_match():
    """
    If zone filtering finds no matching chunks, retrieve() should still return
    general results instead of returning nothing.

    This is useful for demo reliability because partial zoning metadata should
    not completely break answers.
    """
    service = make_rag_service_without_external_dependencies()
    service.collection = FakeCollection()

    chunks = service.retrieve(
        query="What can I build?",
        top_k=2,
        mmr=False,
        zone_filter="Industrial",
    )

    assert len(chunks) == 2
    assert [chunk.id for chunk in chunks] == ["residential-chunk", "commercial-chunk"]


def test_answer_without_openai_returns_cited_plaintext_from_retrieved_chunks():
    """
    Unit tests should not call OpenAI.

    When no OpenAI client is configured, answer() should produce a simple,
    readable response from retrieved chunks.
    """
    service = make_rag_service_without_external_dependencies()

    retrieved = [
        RetrievedChunk(
            id="chunk-1",
            text="Residential zones allow single-family residential development subject to limits.",
            score=0.9,
            metadata={
                "jurisdiction": "City of San Diego",
                "section": "131.0431",
                "source": "city-code.pdf",
            },
        )
    ]

    answer = service.answer(
        question="What can I build?",
        parcel_ctx={"ZONING_CODE": "RS-1-7"},
        retrieved=retrieved,
    )

    assert "City of San Diego §131.0431" in answer
    assert "city-code.pdf" in answer
    assert "Residential zones allow" in answer


def test_answer_without_openai_returns_clear_empty_result_message():
    """
    If retrieval finds nothing and no OpenAI client is available, the user
    should receive a clear empty-result message.
    """
    service = make_rag_service_without_external_dependencies()

    answer = service.answer(
        question="Unknown zoning question",
        parcel_ctx=None,
        retrieved=[],
    )

    assert answer == "No zoning information found for this query."


def test_chat_session_store_generates_and_reuses_session_id():
    """
    ChatSessionStore should create a session ID when one is not provided,
    then reuse the same session ID on follow-up messages.
    """
    store = ChatSessionStore(max_sessions=10, ttl_seconds=60)

    session_id = store.ensure(None)
    reused_id = store.ensure(session_id)

    assert isinstance(session_id, str)
    assert len(session_id) > 0
    assert reused_id == session_id


def test_chat_session_store_persists_parcel_context_and_history():
    """
    The RAG endpoint relies on session memory so the frontend does not need to
    send full parcel context with every follow-up question.
    """
    store = ChatSessionStore(max_sessions=10, ttl_seconds=60)
    session_id = store.ensure(None)

    parcel_context = {
        "APN": "123-456",
        "JURISDICTION": "City of San Diego",
        "ZONING_CODE": "RS-1-7",
    }

    store.set_parcel(session_id, "123-456", parcel_context)
    apn, stored_context = store.get_parcel(session_id)

    assert apn == "123-456"
    assert stored_context == parcel_context

    store.add_turn(session_id, "What can I build?", "Single-family residential may be allowed.")
    history = store.get_history(session_id)

    assert history == [
        {
            "question": "What can I build?",
            "answer": "Single-family residential may be allowed.",
        }
    ]


def test_chat_session_store_trims_history_to_max_turns():
    """
    History should be capped so old conversations do not grow forever.
    """
    store = ChatSessionStore(max_sessions=10, ttl_seconds=60)
    session_id = store.ensure(None)

    for i in range(ChatSessionStore.MAX_HISTORY_TURNS + 5):
        store.add_turn(session_id, f"question-{i}", f"answer-{i}")

    history = store.get_history(session_id)

    assert len(history) == ChatSessionStore.MAX_HISTORY_TURNS
    assert history[0]["question"] == "question-5"
    assert history[-1]["question"] == f"question-{ChatSessionStore.MAX_HISTORY_TURNS + 4}"


def test_chat_session_store_prunes_expired_sessions():
    """
    Expired sessions should be pruned when ensure() is called.

    The class enforces a minimum ttl_seconds of 60, so this test manually makes
    one session old by editing the internal timestamp.
    """
    store = ChatSessionStore(max_sessions=10, ttl_seconds=60)
    old_session_id = store.ensure("old-session")

    # Make the session older than the TTL.
    store._store[old_session_id]["ts"] = time.time() - 120

    new_session_id = store.ensure(None)

    assert new_session_id != old_session_id
    assert old_session_id not in store._store