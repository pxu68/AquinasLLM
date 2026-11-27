from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.ingestion.pipeline import IngestRequest, IngestionPipeline
from app.models.entities import DocumentNode, IngestionRun, IngestionStatus, RetrievalUnit

pytestmark = pytest.mark.integration

GOLDEN = Path(__file__).resolve().parents[2] / "data" / "golden" / "st_i_q9_excerpt.json"


def _summa_request(**overrides) -> IngestRequest:
    base = dict(
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
        corpus_version="test-v1",
    )
    base.update(overrides)
    return IngestRequest(**base)


def test_ingest_idempotent(db_session, tmp_path):
    pipeline = IngestionPipeline(db_session, storage_root=tmp_path / "raw")
    first = pipeline.ingest(_summa_request())
    assert not first.skipped
    second = pipeline.ingest(_summa_request())
    assert second.skipped
    active_nodes = db_session.scalar(
        select(func.count())
        .select_from(DocumentNode)
        .where(DocumentNode.is_current.is_(True))
    )
    assert active_nodes == 11


def test_reingest_supersedes_with_force(db_session, tmp_path):
    pipeline = IngestionPipeline(db_session, storage_root=tmp_path / "raw")
    pipeline.ingest(_summa_request(corpus_version="test-v1"))
    second = pipeline.ingest(_summa_request(corpus_version="test-v2", force=True))
    assert not second.skipped
    runs = db_session.scalars(select(IngestionRun)).all()
    statuses = {r.status for r in runs}
    assert IngestionStatus.ACTIVE in statuses
    assert IngestionStatus.SUPERSEDED in statuses


def test_malformed_fails_without_activation(db_session, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        '{"edition_label": "Bad edition unique", "work_short_code": "ST", "parts": []}',
        encoding="utf-8",
    )
    pipeline = IngestionPipeline(db_session, storage_root=tmp_path / "raw")
    result = pipeline.ingest(
        _summa_request(source_path=bad, edition_label="Bad edition unique")
    )
    assert result.message == "Validation failed"
    run = db_session.get(IngestionRun, result.ingestion_run_id)
    assert run.status == IngestionStatus.FAILED
    units = db_session.scalar(select(func.count()).select_from(RetrievalUnit))
    assert units == 0
