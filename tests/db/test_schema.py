import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.entities import Author, DocumentNode, Edition, IngestionRun, IngestionStatus, SourceDocument, Work


pytestmark = pytest.mark.integration


def test_duplicate_canonical_reference_current_fails(db_session):
    author = Author(canonical_name="Test Author", display_name="Test Author")
    db_session.add(author)
    db_session.flush()
    work = Work(
        author_id=author.id,
        title="Test Work",
        short_code="TW",
        genre="treatise",
        original_language="en",
    )
    db_session.add(work)
    db_session.flush()
    edition = Edition(work_id=work.id, label="Test Ed", language="en")
    db_session.add(edition)
    db_session.flush()
    source = SourceDocument(
        edition_id=edition.id,
        uri="file://test",
        format="test",
        checksum_sha256="abc",
        raw_storage_path="/tmp/x",
    )
    db_session.add(source)
    db_session.flush()
    run = IngestionRun(
        source_document_id=source.id,
        parser_name="Test",
        parser_version="0",
        corpus_version="v0",
        status=IngestionStatus.ACTIVE,
    )
    db_session.add(run)
    db_session.flush()

    n1 = DocumentNode(
        ingestion_run_id=run.id,
        edition_id=edition.id,
        node_type="chapter",
        label="One",
        canonical_reference="TW, ch. 1",
        ordinal=1,
        depth=1,
        text_language="en",
        is_current=True,
    )
    n2 = DocumentNode(
        ingestion_run_id=run.id,
        edition_id=edition.id,
        node_type="chapter",
        label="Two",
        canonical_reference="TW, ch. 1",
        ordinal=2,
        depth=1,
        text_language="en",
        is_current=True,
    )
    db_session.add(n1)
    db_session.flush()
    db_session.add(n2)
    with pytest.raises(IntegrityError):
        db_session.flush()
