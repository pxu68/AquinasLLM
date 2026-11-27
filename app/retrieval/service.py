from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    ProvenanceInfo,
    RetrievalMethodInfo,
    SearchResponse,
    SearchResultItem,
)
from app.embeddings.registry import build_embedding_service
from app.embeddings.service import EmbeddingService
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.lexical_search import lexical_search
from app.retrieval.vector_search import vector_search


class RetrievalService:
    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService | None = None,
    ):
        self.session = session
        self.embedding_service = embedding_service or build_embedding_service()

    def search(
        self,
        query: str,
        *,
        authors: list[str] | None = None,
        works: list[str] | None = None,
        node_types: list[str] | None = None,
        limit: int = 10,
        fusion: bool = True,
    ) -> SearchResponse:
        qv = self.embedding_service.embed_query(query)
        vector_hits = vector_search(
            self.session,
            qv,
            limit=50,
            work_titles=works,
            author_names=authors,
            node_types=node_types,
        )
        lexical_hits = lexical_search(
            self.session,
            query,
            limit=50,
            work_titles=works,
            author_names=authors,
            node_types=node_types,
        )

        if fusion:
            fused = reciprocal_rank_fusion(vector_hits, lexical_hits, limit=limit)
        else:
            fused = reciprocal_rank_fusion(vector_hits, [], limit=limit)

        if not fused:
            return SearchResponse(query=query, results=[])

        ids = [str(h.retrieval_unit_id) for h in fused]
        rows = self.session.execute(
            text(
                """
                SELECT ru.id, ru.unit_text, dn.canonical_reference, dn.node_type,
                       dn.section_role, w.title AS work, a.display_name AS author,
                       e.label AS edition_label, sd.uri AS source_uri,
                       ir.id AS ingestion_run_id, ir.parser_name, ir.parser_version,
                       ir.corpus_version AS corpus_version,
                       emb.embedding_model, emb.embedding_version
                FROM retrieval_units ru
                JOIN document_nodes dn ON dn.id = ru.primary_node_id
                JOIN editions e ON e.id = ru.edition_id
                JOIN works w ON w.id = e.work_id
                JOIN authors a ON a.id = w.author_id
                JOIN ingestion_runs ir ON ir.id = dn.ingestion_run_id
                JOIN source_documents sd ON sd.id = ir.source_document_id
                LEFT JOIN embeddings emb ON emb.retrieval_unit_id = ru.id AND emb.is_current
                WHERE ru.id::text = ANY(:ids)
                """
            ),
            {"ids": ids},
        ).mappings()

        by_id = {str(r["id"]): dict(r) for r in rows}
        results: list[SearchResultItem] = []
        for hit in fused:
            row = by_id.get(str(hit.retrieval_unit_id))
            if not row:
                continue
            results.append(
                SearchResultItem(
                    retrieval_unit_id=hit.retrieval_unit_id,
                    text=row["unit_text"],
                    canonical_reference=row["canonical_reference"],
                    author=row["author"],
                    work=row["work"],
                    node_type=row["node_type"],
                    section_role=row["section_role"],
                    retrieval=RetrievalMethodInfo(
                        vector_rank=hit.vector_rank,
                        vector_distance=hit.vector_distance,
                        lexical_rank=hit.lexical_rank,
                        lexical_score=hit.lexical_score,
                        fused_score=hit.fused_score,
                    ),
                    provenance=ProvenanceInfo(
                        edition_label=row["edition_label"],
                        source_document_uri=row["source_uri"],
                        ingestion_run_id=row["ingestion_run_id"],
                        parser_name=row["parser_name"],
                        parser_version=row["parser_version"],
                        corpus_version=row.get("corpus_version"),
                        embedding_model=row.get("embedding_model"),
                        embedding_version=row.get("embedding_version"),
                    ),
                )
            )
        return SearchResponse(query=query, results=results)
