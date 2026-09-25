from pathlib import Path

import pytest

from app.ingestion.pipeline import IngestRequest, IngestionPipeline
from app.parsing.models import SectionRole
from app.parsing.summa import SummaParser
from app.retrieval.service import RetrievalService

pytestmark = pytest.mark.integration

GOLDEN = Path(__file__).resolve().parents[2] / "data" / "golden" / "st_i_q9_excerpt.json"
DEE = Path(__file__).resolve().parents[2] / "data" / "golden" / "dee_excerpt.json"


@pytest.fixture
def ingested_corpus(db_session, tmp_path):
    pipeline = IngestionPipeline(db_session, storage_root=tmp_path / "raw")
    pipeline.ingest(
        IngestRequest(
            source_path=GOLDEN,
            parser_key="summa",
            author_canonical_name="Thomas Aquinas",
            author_display_name="St. Thomas Aquinas",
            work_title="Summa Theologiae",
            work_short_code="ST",
            work_genre="summa",
            original_language="la",
            edition_label="Golden English (test)",
            edition_language="en",
            corpus_version="search-test",
        )
    )
    pipeline.ingest(
        IngestRequest(
            source_path=DEE,
            parser_key="treatise",
            author_canonical_name="Thomas Aquinas",
            author_display_name="St. Thomas Aquinas",
            work_title="De Ente et Essentia",
            work_short_code="DEE",
            work_genre="treatise",
            original_language="la",
            edition_label="Golden Latin (test)",
            edition_language="la",
            corpus_version="search-test",
        )
    )


def test_search_finds_immutability_respondeo(ingested_corpus, db_session):
    service = RetrievalService(db_session)
    response = service.search(
        "God altogether immutable pure act cannot change",
        limit=10,
    )
    assert response.results
    hits = [
        r
        for r in response.results
        if "q.9, a.1, respondeo" in r.canonical_reference
        or "immutable" in r.text.lower()
    ]
    assert hits, "Expected ST I q.9 a.1 respondeo (or immutability text) in results"


def test_work_filter_excludes_other_work(ingested_corpus, db_session):
    service = RetrievalService(db_session)
    response = service.search(
        "ens et essentia",
        works=["Summa Theologiae"],
        limit=10,
    )
    assert all(r.work == "Summa Theologiae" for r in response.results)
