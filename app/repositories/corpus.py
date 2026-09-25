from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import (
    Author,
    DocumentNode,
    Edition,
    Embedding,
    IngestionRun,
    IngestionStatus,
    NodeRelationship,
    RetrievalUnit,
    RetrievalUnitMember,
    SourceDocument,
    Work,
)


class CorpusRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_author_by_name(self, canonical_name: str) -> Author | None:
        return self.session.query(Author).filter_by(canonical_name=canonical_name).one_or_none()

    def create_author(self, canonical_name: str, display_name: str) -> Author:
        author = Author(canonical_name=canonical_name, display_name=display_name)
        self.session.add(author)
        self.session.flush()
        return author

    def get_work(self, author_id: uuid.UUID, short_code: str) -> Work | None:
        return (
            self.session.query(Work)
            .filter_by(author_id=author_id, short_code=short_code)
            .one_or_none()
        )

    def create_work(
        self,
        author_id: uuid.UUID,
        title: str,
        short_code: str,
        genre: str,
        original_language: str,
    ) -> Work:
        work = Work(
            author_id=author_id,
            title=title,
            short_code=short_code,
            genre=genre,
            original_language=original_language,
        )
        self.session.add(work)
        self.session.flush()
        return work

    def get_edition(self, work_id: uuid.UUID, label: str) -> Edition | None:
        return (
            self.session.query(Edition)
            .filter_by(work_id=work_id, label=label)
            .one_or_none()
        )

    def create_edition(
        self,
        work_id: uuid.UUID,
        label: str,
        language: str,
        is_translation: bool = False,
    ) -> Edition:
        edition = Edition(
            work_id=work_id,
            label=label,
            language=language,
            is_translation=is_translation,
        )
        self.session.add(edition)
        self.session.flush()
        return edition

    def get_source_by_checksum(
        self, edition_id: uuid.UUID, checksum: str
    ) -> SourceDocument | None:
        return (
            self.session.query(SourceDocument)
            .filter_by(edition_id=edition_id, checksum_sha256=checksum)
            .one_or_none()
        )

    def create_source_document(
        self,
        edition_id: uuid.UUID,
        uri: str,
        fmt: str,
        checksum: str,
        raw_storage_path: str,
    ) -> SourceDocument:
        doc = SourceDocument(
            edition_id=edition_id,
            uri=uri,
            format=fmt,
            checksum_sha256=checksum,
            raw_storage_path=raw_storage_path,
        )
        self.session.add(doc)
        self.session.flush()
        return doc

    def get_active_run(self, source_document_id: uuid.UUID) -> IngestionRun | None:
        return (
            self.session.query(IngestionRun)
            .filter_by(source_document_id=source_document_id, status=IngestionStatus.ACTIVE)
            .one_or_none()
        )

    def create_ingestion_run(
        self,
        source_document_id: uuid.UUID,
        parser_name: str,
        parser_version: str,
        corpus_version: str,
    ) -> IngestionRun:
        run = IngestionRun(
            source_document_id=source_document_id,
            parser_name=parser_name,
            parser_version=parser_version,
            corpus_version=corpus_version,
            status=IngestionStatus.DISCOVERED,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def update_run_status(
        self,
        run_id: uuid.UUID,
        status: IngestionStatus,
        *,
        error_message: str | None = None,
        validation_report: dict | None = None,
        finished: bool = False,
    ) -> None:
        run = self.session.get(IngestionRun, run_id)
        if not run:
            return
        run.status = status
        if error_message is not None:
            run.error_message = error_message
        if validation_report is not None:
            run.validation_report = validation_report
        if finished:
            run.finished_at = datetime.utcnow()
        self.session.flush()

    def persist_tree(
        self,
        run: IngestionRun,
        edition_id: uuid.UUID,
        text_language: str,
        nodes: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> dict[str, uuid.UUID]:
        local_to_uuid: dict[str, uuid.UUID] = {}
        for n in nodes:
            node = DocumentNode(
                ingestion_run_id=run.id,
                edition_id=edition_id,
                parent_id=None,
                node_type=n["node_type"],
                section_role=n.get("section_role"),
                label=n["label"],
                canonical_reference=n["canonical_reference"],
                ordinal=n["ordinal"],
                depth=n["depth"],
                text=n.get("text"),
                text_language=text_language,
                is_retrievable_leaf=n.get("is_retrievable_leaf", False),
                is_current=False,
            )
            self.session.add(node)
            self.session.flush()
            local_to_uuid[n["local_id"]] = node.id

        for n in nodes:
            pid = n.get("parent_local_id")
            if pid:
                db_node = self.session.get(DocumentNode, local_to_uuid[n["local_id"]])
                if db_node:
                    db_node.parent_id = local_to_uuid[pid]
        self.session.flush()

        for rel in relationships:
            self.session.add(
                NodeRelationship(
                    source_node_id=local_to_uuid[rel["source_local_id"]],
                    target_node_id=local_to_uuid[rel["target_local_id"]],
                    relationship_type=rel["relationship_type"],
                )
            )
        self.session.flush()
        return local_to_uuid

    def persist_retrieval_units(
        self,
        edition_id: uuid.UUID,
        units: list[dict[str, Any]],
    ) -> list[uuid.UUID]:
        ids: list[uuid.UUID] = []
        for u in units:
            ru = RetrievalUnit(
                edition_id=edition_id,
                unit_text=u["unit_text"],
                primary_node_id=u["primary_node_id"],
                is_current=False,
            )
            self.session.add(ru)
            self.session.flush()
            for order, member_id in enumerate(u["member_node_ids"]):
                self.session.add(
                    RetrievalUnitMember(
                        retrieval_unit_id=ru.id,
                        document_node_id=member_id,
                        member_order=order,
                    )
                )
            ids.append(ru.id)
        self.session.flush()
        return ids

    def upsert_embedding(
        self,
        retrieval_unit_id: uuid.UUID,
        model: str,
        version: str,
        vector: list[float],
    ) -> None:
        existing = (
            self.session.query(Embedding)
            .filter_by(
                retrieval_unit_id=retrieval_unit_id,
                embedding_model=model,
                embedding_version=version,
            )
            .one_or_none()
        )
        if existing:
            return
        self.session.add(
            Embedding(
                retrieval_unit_id=retrieval_unit_id,
                embedding_model=model,
                embedding_version=version,
                vector=vector,
                is_current=False,
            )
        )
        self.session.flush()

    def activate_run(self, run_id: uuid.UUID, edition_id: uuid.UUID) -> None:
        old_runs = (
            self.session.query(IngestionRun)
            .join(SourceDocument, SourceDocument.id == IngestionRun.source_document_id)
            .join(Edition, Edition.id == SourceDocument.edition_id)
            .filter(Edition.id == edition_id, IngestionRun.status == IngestionStatus.ACTIVE)
            .all()
        )
        for old in old_runs:
            if old.id != run_id:
                old.status = IngestionStatus.SUPERSEDED
                old.finished_at = datetime.utcnow()
        self.session.flush()

        self.session.query(DocumentNode).filter_by(edition_id=edition_id, is_current=True).update(
            {"is_current": False}
        )
        self.session.query(RetrievalUnit).filter_by(edition_id=edition_id, is_current=True).update(
            {"is_current": False}
        )

        self.session.query(DocumentNode).filter_by(ingestion_run_id=run_id).update(
            {"is_current": True}
        )
        run = self.session.get(IngestionRun, run_id)
        if not run:
            return
        ru_ids = [
            ru.id
            for ru in self.session.query(RetrievalUnit)
            .join(DocumentNode, DocumentNode.id == RetrievalUnit.primary_node_id)
            .filter(DocumentNode.ingestion_run_id == run_id)
            .all()
        ]
        if ru_ids:
            self.session.query(RetrievalUnit).filter(RetrievalUnit.id.in_(ru_ids)).update(
                {"is_current": True}, synchronize_session=False
            )
            self.session.query(Embedding).filter(
                Embedding.retrieval_unit_id.in_(ru_ids)
            ).update({"is_current": True}, synchronize_session=False)

        run.status = IngestionStatus.ACTIVE
        run.finished_at = datetime.utcnow()
        self.session.flush()

    def list_works(self) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT w.id, w.title, w.short_code, w.genre, a.display_name AS author,
                       COUNT(DISTINCT e.id) AS edition_count
                FROM works w
                JOIN authors a ON a.id = w.author_id
                LEFT JOIN editions e ON e.work_id = w.id
                GROUP BY w.id, a.display_name
                ORDER BY w.title
                """
            )
        ).mappings()
        return [dict(r) for r in rows]

    def get_work_detail(self, work_id: uuid.UUID) -> dict[str, Any] | None:
        work = self.session.get(Work, work_id)
        if not work:
            return None
        author = self.session.get(Author, work.author_id)
        editions = self.session.query(Edition).filter_by(work_id=work_id).all()
        return {
            "id": work.id,
            "title": work.title,
            "short_code": work.short_code,
            "genre": work.genre,
            "author": author.display_name if author else "",
            "editions": [
                {
                    "id": e.id,
                    "label": e.label,
                    "language": e.language,
                    "is_translation": e.is_translation,
                }
                for e in editions
            ],
        }

    def get_retrieval_unit(self, unit_id: uuid.UUID) -> dict[str, Any] | None:
        row = self.session.execute(
            text(
                """
                SELECT ru.id, ru.unit_text, dn.canonical_reference, dn.node_type,
                       dn.section_role, w.title AS work, a.display_name AS author,
                       e.label AS edition_label, sd.uri AS source_uri,
                       ir.id AS ingestion_run_id, ir.parser_name, ir.parser_version,
                       ir.corpus_version, ir.started_at AS ingested_at,
                       emb.embedding_model, emb.embedding_version
                FROM retrieval_units ru
                JOIN document_nodes dn ON dn.id = ru.primary_node_id
                JOIN editions e ON e.id = ru.edition_id
                JOIN works w ON w.id = e.work_id
                JOIN authors a ON a.id = w.author_id
                JOIN ingestion_runs ir ON ir.id = dn.ingestion_run_id
                JOIN source_documents sd ON sd.id = ir.source_document_id
                LEFT JOIN embeddings emb ON emb.retrieval_unit_id = ru.id AND emb.is_current
                WHERE ru.id = :uid AND ru.is_current
                """
            ),
            {"uid": unit_id},
        ).mappings().first()
        return dict(row) if row else None

    def get_node_context(self, unit_id: uuid.UUID) -> list[dict[str, Any]]:
        primary = self.session.execute(
            text(
                "SELECT primary_node_id FROM retrieval_units WHERE id = :uid"
            ),
            {"uid": unit_id},
        ).scalar_one_or_none()
        if not primary:
            return []
        rows = self.session.execute(
            text(
                """
                WITH RECURSIVE chain AS (
                    SELECT id, parent_id, label, node_type, canonical_reference, depth, ordinal
                    FROM document_nodes WHERE id = :nid
                    UNION ALL
                    SELECT dn.id, dn.parent_id, dn.label, dn.node_type,
                           dn.canonical_reference, dn.depth, dn.ordinal
                    FROM document_nodes dn
                    JOIN chain c ON dn.id = c.parent_id
                )
                SELECT label, node_type, canonical_reference, depth, ordinal
                FROM chain ORDER BY depth ASC
                """
            ),
            {"nid": primary},
        ).mappings()
        return [dict(r) for r in rows]

    def get_ingestion_run(self, run_id: uuid.UUID) -> IngestionRun | None:
        return self.session.get(IngestionRun, run_id)
