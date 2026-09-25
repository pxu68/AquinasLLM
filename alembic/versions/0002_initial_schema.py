"""Full Phase 1 schema (authors through retrieval_unit_concepts).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE ingestion_status AS ENUM (
            'discovered', 'downloaded', 'validated', 'parsed',
            'normalized', 'embedded', 'indexed', 'active', 'failed', 'superseded'
        );
        """
    )

    op.execute(
        """
        CREATE TABLE authors (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            canonical_name  TEXT NOT NULL,
            display_name    TEXT NOT NULL,
            birth_year      INTEGER,
            death_year      INTEGER,
            era             TEXT,
            notes           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (canonical_name)
        );

        CREATE TABLE works (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            author_id       UUID NOT NULL REFERENCES authors(id) ON DELETE RESTRICT,
            title           TEXT NOT NULL,
            short_code      TEXT NOT NULL,
            genre           TEXT NOT NULL,
            original_language TEXT NOT NULL,
            composed_year_start INTEGER,
            composed_year_end   INTEGER,
            notes           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (author_id, short_code)
        );
        CREATE INDEX idx_works_author ON works(author_id);
        CREATE INDEX idx_works_genre  ON works(genre);

        CREATE TABLE editions (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_id         UUID NOT NULL REFERENCES works(id) ON DELETE RESTRICT,
            label           TEXT NOT NULL,
            language        TEXT NOT NULL,
            is_translation  BOOLEAN NOT NULL DEFAULT FALSE,
            translator      TEXT,
            publisher       TEXT,
            publication_year INTEGER,
            license         TEXT,
            notes           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (work_id, label)
        );
        CREATE INDEX idx_editions_work ON editions(work_id);
        CREATE INDEX idx_editions_language ON editions(language);

        CREATE TABLE source_documents (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            edition_id      UUID NOT NULL REFERENCES editions(id) ON DELETE RESTRICT,
            uri             TEXT NOT NULL,
            format          TEXT NOT NULL,
            checksum_sha256 TEXT NOT NULL,
            fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            raw_storage_path TEXT NOT NULL,
            notes           TEXT,
            UNIQUE (edition_id, checksum_sha256)
        );
        CREATE INDEX idx_source_documents_edition ON source_documents(edition_id);

        CREATE TABLE ingestion_runs (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_document_id  UUID NOT NULL REFERENCES source_documents(id) ON DELETE RESTRICT,
            status              ingestion_status NOT NULL DEFAULT 'discovered',
            parser_name         TEXT NOT NULL,
            parser_version      TEXT NOT NULL,
            corpus_version      TEXT NOT NULL,
            started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at         TIMESTAMPTZ,
            error_message       TEXT,
            validation_report   JSONB,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_ingestion_runs_source ON ingestion_runs(source_document_id);
        CREATE INDEX idx_ingestion_runs_status ON ingestion_runs(status);
        CREATE UNIQUE INDEX uq_one_active_run_per_source
            ON ingestion_runs(source_document_id)
            WHERE status = 'active';

        CREATE TABLE document_nodes (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ingestion_run_id    UUID NOT NULL REFERENCES ingestion_runs(id) ON DELETE RESTRICT,
            edition_id          UUID NOT NULL REFERENCES editions(id) ON DELETE RESTRICT,
            parent_id           UUID REFERENCES document_nodes(id) ON DELETE CASCADE,
            node_type           TEXT NOT NULL,
            section_role        TEXT,
            label               TEXT NOT NULL,
            canonical_reference TEXT NOT NULL,
            ordinal             INTEGER NOT NULL,
            depth               INTEGER NOT NULL,
            text                TEXT,
            text_language       TEXT NOT NULL,
            is_retrievable_leaf  BOOLEAN NOT NULL DEFAULT FALSE,
            is_current          BOOLEAN NOT NULL DEFAULT FALSE,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_section_role_only_for_section
                CHECK (node_type <> 'section' OR section_role IS NOT NULL)
        );
        CREATE INDEX idx_nodes_parent ON document_nodes(parent_id);
        CREATE INDEX idx_nodes_edition_current ON document_nodes(edition_id) WHERE is_current;
        CREATE INDEX idx_nodes_ingestion_run ON document_nodes(ingestion_run_id);
        CREATE INDEX idx_nodes_type ON document_nodes(node_type);
        CREATE UNIQUE INDEX uq_node_sibling_order
            ON document_nodes(parent_id, ordinal) WHERE parent_id IS NOT NULL;
        CREATE UNIQUE INDEX uq_canonical_reference_current
            ON document_nodes(edition_id, canonical_reference) WHERE is_current;

        ALTER TABLE document_nodes ADD COLUMN fts tsvector
            GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED;
        CREATE INDEX idx_nodes_fts ON document_nodes USING GIN (fts);

        CREATE TABLE node_relationships (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_node_id    UUID NOT NULL REFERENCES document_nodes(id) ON DELETE CASCADE,
            target_node_id    UUID NOT NULL REFERENCES document_nodes(id) ON DELETE CASCADE,
            relationship_type TEXT NOT NULL,
            confidence        REAL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (source_node_id, target_node_id, relationship_type)
        );
        CREATE INDEX idx_node_rel_source ON node_relationships(source_node_id);
        CREATE INDEX idx_node_rel_target ON node_relationships(target_node_id);
        CREATE INDEX idx_node_rel_type   ON node_relationships(relationship_type);

        CREATE TABLE retrieval_units (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            edition_id      UUID NOT NULL REFERENCES editions(id) ON DELETE RESTRICT,
            unit_text       TEXT NOT NULL,
            primary_node_id UUID NOT NULL REFERENCES document_nodes(id) ON DELETE RESTRICT,
            is_current      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_retrieval_units_edition ON retrieval_units(edition_id);
        CREATE INDEX idx_retrieval_units_primary_node ON retrieval_units(primary_node_id);

        CREATE TABLE retrieval_unit_members (
            retrieval_unit_id UUID NOT NULL REFERENCES retrieval_units(id) ON DELETE CASCADE,
            document_node_id  UUID NOT NULL REFERENCES document_nodes(id) ON DELETE RESTRICT,
            member_order      INTEGER NOT NULL,
            PRIMARY KEY (retrieval_unit_id, document_node_id)
        );
        CREATE INDEX idx_run_members_node ON retrieval_unit_members(document_node_id);

        ALTER TABLE retrieval_units ADD COLUMN fts tsvector
            GENERATED ALWAYS AS (to_tsvector('english', coalesce(unit_text, ''))) STORED;
        CREATE INDEX idx_retrieval_units_fts ON retrieval_units USING GIN (fts);

        CREATE TABLE embeddings (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            retrieval_unit_id UUID NOT NULL REFERENCES retrieval_units(id) ON DELETE CASCADE,
            embedding_model   TEXT NOT NULL,
            embedding_version TEXT NOT NULL,
            vector            vector(1536) NOT NULL,
            is_current        BOOLEAN NOT NULL DEFAULT TRUE,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (retrieval_unit_id, embedding_model, embedding_version)
        );
        CREATE INDEX idx_embeddings_unit ON embeddings(retrieval_unit_id);
        CREATE INDEX idx_embeddings_vector_hnsw ON embeddings
            USING hnsw (vector vector_cosine_ops)
            WHERE is_current;

        CREATE TABLE concepts (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug         TEXT NOT NULL UNIQUE,
            label        TEXT NOT NULL,
            parent_id    UUID REFERENCES concepts(id) ON DELETE SET NULL,
            description  TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_concepts_parent ON concepts(parent_id);

        CREATE TABLE retrieval_unit_concepts (
            retrieval_unit_id UUID NOT NULL REFERENCES retrieval_units(id) ON DELETE CASCADE,
            concept_id        UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            source            TEXT NOT NULL DEFAULT 'manual',
            confidence        REAL,
            PRIMARY KEY (retrieval_unit_id, concept_id, source)
        );
        CREATE INDEX idx_ru_concepts_concept ON retrieval_unit_concepts(concept_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS retrieval_unit_concepts;
        DROP TABLE IF EXISTS concepts;
        DROP TABLE IF EXISTS embeddings;
        DROP TABLE IF EXISTS retrieval_unit_members;
        DROP TABLE IF EXISTS retrieval_units;
        DROP TABLE IF EXISTS node_relationships;
        DROP TABLE IF EXISTS document_nodes;
        DROP TABLE IF EXISTS ingestion_runs;
        DROP TABLE IF EXISTS source_documents;
        DROP TABLE IF EXISTS editions;
        DROP TABLE IF EXISTS works;
        DROP TABLE IF EXISTS authors;
        DROP TYPE IF EXISTS ingestion_status;
        """
    )
