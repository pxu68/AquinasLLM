from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    authors: list[str] | None = None
    works: list[str] | None = None
    node_types: list[str] | None = None
    limit: int = Field(default=10, ge=1, le=50)


class RetrievalMethodInfo(BaseModel):
    vector_rank: int | None = None
    vector_distance: float | None = None
    lexical_rank: int | None = None
    lexical_score: float | None = None
    fused_score: float


class ProvenanceInfo(BaseModel):
    edition_label: str
    source_document_uri: str
    ingestion_run_id: UUID
    parser_name: str
    parser_version: str
    corpus_version: str | None = None
    embedding_model: str | None = None
    embedding_version: str | None = None


class SearchResultItem(BaseModel):
    retrieval_unit_id: UUID
    text: str
    canonical_reference: str
    author: str
    work: str
    node_type: str
    section_role: str | None = None
    retrieval: RetrievalMethodInfo
    provenance: ProvenanceInfo


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]


class PassageResponse(BaseModel):
    retrieval_unit_id: UUID
    text: str
    canonical_reference: str
    author: str
    work: str
    node_type: str
    section_role: str | None = None
    provenance: ProvenanceInfo


class ContextNode(BaseModel):
    label: str
    node_type: str
    canonical_reference: str
    depth: int
    ordinal: int


class PassageContextResponse(BaseModel):
    retrieval_unit_id: UUID
    ancestors: list[ContextNode]


class WorkSummary(BaseModel):
    id: UUID
    title: str
    short_code: str
    genre: str
    author: str
    edition_count: int


class EditionSummary(BaseModel):
    id: UUID
    label: str
    language: str
    is_translation: bool


class WorkDetailResponse(BaseModel):
    id: UUID
    title: str
    short_code: str
    genre: str
    author: str
    editions: list[EditionSummary]


class IngestionRunResponse(BaseModel):
    id: UUID
    status: str
    parser_name: str
    parser_version: str
    corpus_version: str
    error_message: str | None = None
    validation_report: dict | None = None
