from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Enum as SAEnum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class IngestionStatus(str, Enum):
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    VALIDATED = "validated"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    ACTIVE = "active"
    FAILED = "failed"
    SUPERSEDED = "superseded"


INGESTION_STATUS_ENUM = SAEnum(
    IngestionStatus,
    name="ingestion_status",
    values_callable=lambda enum: [member.value for member in enum],
    create_constraint=True,
)


class Author(SQLModel, table=True):
    __tablename__ = "authors"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    canonical_name: str
    display_name: str
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    era: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Work(SQLModel, table=True):
    __tablename__ = "works"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    author_id: uuid.UUID = Field(foreign_key="authors.id")
    title: str
    short_code: str
    genre: str
    original_language: str
    composed_year_start: Optional[int] = None
    composed_year_end: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Edition(SQLModel, table=True):
    __tablename__ = "editions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    work_id: uuid.UUID = Field(foreign_key="works.id")
    label: str
    language: str
    is_translation: bool = False
    translator: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    license: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SourceDocument(SQLModel, table=True):
    __tablename__ = "source_documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    edition_id: uuid.UUID = Field(foreign_key="editions.id")
    uri: str
    format: str
    checksum_sha256: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    raw_storage_path: str
    notes: Optional[str] = None


class IngestionRun(SQLModel, table=True):
    __tablename__ = "ingestion_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_document_id: uuid.UUID = Field(foreign_key="source_documents.id")
    status: IngestionStatus = Field(
        default=IngestionStatus.DISCOVERED,
        sa_column=Column(INGESTION_STATUS_ENUM, nullable=False),
    )
    parser_name: str
    parser_version: str
    corpus_version: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    validation_report: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentNode(SQLModel, table=True):
    __tablename__ = "document_nodes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ingestion_run_id: uuid.UUID = Field(foreign_key="ingestion_runs.id")
    edition_id: uuid.UUID = Field(foreign_key="editions.id")
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="document_nodes.id")
    node_type: str
    section_role: Optional[str] = None
    label: str
    canonical_reference: str
    ordinal: int
    depth: int
    text: Optional[str] = None
    text_language: str
    is_retrievable_leaf: bool = False
    is_current: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NodeRelationship(SQLModel, table=True):
    __tablename__ = "node_relationships"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_node_id: uuid.UUID = Field(foreign_key="document_nodes.id")
    target_node_id: uuid.UUID = Field(foreign_key="document_nodes.id")
    relationship_type: str
    confidence: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RetrievalUnit(SQLModel, table=True):
    __tablename__ = "retrieval_units"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    edition_id: uuid.UUID = Field(foreign_key="editions.id")
    unit_text: str
    primary_node_id: uuid.UUID = Field(foreign_key="document_nodes.id")
    is_current: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RetrievalUnitMember(SQLModel, table=True):
    __tablename__ = "retrieval_unit_members"

    retrieval_unit_id: uuid.UUID = Field(
        foreign_key="retrieval_units.id", primary_key=True
    )
    document_node_id: uuid.UUID = Field(
        foreign_key="document_nodes.id", primary_key=True
    )
    member_order: int


class Embedding(SQLModel, table=True):
    __tablename__ = "embeddings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    retrieval_unit_id: uuid.UUID = Field(foreign_key="retrieval_units.id")
    embedding_model: str
    embedding_version: str
    vector: list[float] = Field(sa_column=Column(Vector(1536)))
    is_current: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Concept(SQLModel, table=True):
    __tablename__ = "concepts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    slug: str
    label: str
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="concepts.id")
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RetrievalUnitConcept(SQLModel, table=True):
    __tablename__ = "retrieval_unit_concepts"

    retrieval_unit_id: uuid.UUID = Field(
        foreign_key="retrieval_units.id", primary_key=True
    )
    concept_id: uuid.UUID = Field(foreign_key="concepts.id", primary_key=True)
    source: str = "manual"
    confidence: Optional[float] = None
