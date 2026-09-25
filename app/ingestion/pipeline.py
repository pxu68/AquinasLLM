from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.embeddings.client import DeterministicEmbeddingClient, EmbeddingClient
from app.embeddings.service import EmbeddingService
from app.ingestion.retrieval_units import build_retrieval_unit_candidates
from app.ingestion.validation import validate_structured_document
from app.models.entities import IngestionStatus
from app.parsing.base import Parser
from app.parsing.models import StructuredDocument
from app.parsing.summa import SummaParser
from app.parsing.treatise import TreatiseParser
from app.repositories.corpus import CorpusRepository

PARSERS: dict[str, Parser] = {
    "summa": SummaParser(),
    "treatise": TreatiseParser(),
}


@dataclass
class IngestRequest:
    source_path: Path
    parser_key: str
    author_canonical_name: str
    author_display_name: str
    work_title: str
    work_short_code: str
    work_genre: str
    original_language: str
    edition_label: str
    edition_language: str
    corpus_version: str
    is_translation: bool = False
    force: bool = False


@dataclass
class IngestResult:
    skipped: bool
    ingestion_run_id: uuid.UUID | None
    message: str


class IngestionPipeline:
    def __init__(
        self,
        session: Session,
        embedding_client: EmbeddingClient | None = None,
        storage_root: Path | None = None,
    ):
        self.session = session
        self.repo = CorpusRepository(session)
        self.embedding_client = embedding_client or DeterministicEmbeddingClient()
        self.storage_root = storage_root or Path("data/raw")

    def ingest(self, req: IngestRequest) -> IngestResult:
        raw_bytes = req.source_path.read_bytes()
        checksum = hashlib.sha256(raw_bytes).hexdigest()
        parser = PARSERS.get(req.parser_key)
        if not parser:
            raise ValueError(f"Unknown parser: {req.parser_key}")

        author = self.repo.get_author_by_name(req.author_canonical_name)
        if not author:
            author = self.repo.create_author(
                req.author_canonical_name, req.author_display_name
            )

        work = self.repo.get_work(author.id, req.work_short_code)
        if not work:
            work = self.repo.create_work(
                author.id,
                req.work_title,
                req.work_short_code,
                req.work_genre,
                req.original_language,
            )

        edition = self.repo.get_edition(work.id, req.edition_label)
        if not edition:
            edition = self.repo.create_edition(
                work.id,
                req.edition_label,
                req.edition_language,
                is_translation=req.is_translation,
            )

        source = self.repo.get_source_by_checksum(edition.id, checksum)
        if not source:
            self.storage_root.mkdir(parents=True, exist_ok=True)
            archive = self.storage_root / f"{checksum}.bin"
            if not archive.exists():
                shutil.copy(req.source_path, archive)
            source = self.repo.create_source_document(
                edition.id,
                str(req.source_path),
                req.parser_key + "-json",
                checksum,
                str(archive),
            )
            self.session.commit()

        active = self.repo.get_active_run(source.id)
        if active and not req.force:
            return IngestResult(
                skipped=True,
                ingestion_run_id=active.id,
                message="Active ingestion already exists for this source checksum",
            )

        run = self.repo.create_ingestion_run(
            source.id,
            parser.name,
            parser.version,
            req.corpus_version,
        )
        self.session.commit()

        try:
            doc = parser.parse(raw_bytes)
            if doc.edition_label != req.edition_label:
                doc.edition_label = req.edition_label

            report = validate_structured_document(doc)
            self.repo.update_run_status(
                run.id,
                IngestionStatus.VALIDATED,
                validation_report=report.to_dict(),
            )
            if not report.passed:
                self.repo.update_run_status(
                    run.id,
                    IngestionStatus.FAILED,
                    error_message="Validation failed",
                    finished=True,
                )
                self.session.commit()
                return IngestResult(
                    skipped=False,
                    ingestion_run_id=run.id,
                    message="Validation failed",
                )

            node_payloads = [
                {
                    "local_id": n.local_id,
                    "parent_local_id": n.parent_local_id,
                    "node_type": n.node_type.value,
                    "section_role": n.section_role.value if n.section_role else None,
                    "label": n.label,
                    "canonical_reference": n.canonical_reference,
                    "ordinal": n.ordinal,
                    "depth": n.depth,
                    "text": n.text,
                    "is_retrievable_leaf": n.is_retrievable_leaf,
                }
                for n in doc.nodes
            ]
            rel_payloads = [
                {
                    "source_local_id": r.source_local_id,
                    "target_local_id": r.target_local_id,
                    "relationship_type": r.relationship_type,
                }
                for r in doc.relationships
            ]

            self.repo.update_run_status(run.id, IngestionStatus.PARSED)
            local_to_uuid = self.repo.persist_tree(
                run,
                edition.id,
                doc.text_language,
                node_payloads,
                rel_payloads,
            )
            self.repo.update_run_status(run.id, IngestionStatus.NORMALIZED)

            units = build_retrieval_unit_candidates(doc, local_to_uuid)
            unit_ids = self.repo.persist_retrieval_units(edition.id, units)

            embed_svc = EmbeddingService(self.repo, self.embedding_client)
            texts = [u["unit_text"] for u in units]
            embed_svc.embed_retrieval_units(unit_ids, texts)
            self.repo.update_run_status(run.id, IngestionStatus.EMBEDDED)

            self.repo.activate_run(run.id, edition.id)
            self.repo.update_run_status(run.id, IngestionStatus.ACTIVE, finished=True)
            self.session.commit()
            return IngestResult(
                skipped=False,
                ingestion_run_id=run.id,
                message=f"Ingestion active with {len(doc.nodes)} nodes",
            )
        except Exception as exc:
            self.session.rollback()
            self.repo.update_run_status(
                run.id,
                IngestionStatus.FAILED,
                error_message=str(exc),
                finished=True,
            )
            self.session.commit()
            raise
