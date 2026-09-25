from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    ContextNode,
    PassageContextResponse,
    PassageResponse,
    ProvenanceInfo,
)
from app.db.deps import get_db
from app.repositories.corpus import CorpusRepository

router = APIRouter(prefix="/v1", tags=["passages"])


@router.get("/passages/{passage_id}", response_model=PassageResponse)
def get_passage(passage_id: UUID, db: Session = Depends(get_db)) -> PassageResponse:
    repo = CorpusRepository(db)
    row = repo.get_retrieval_unit(passage_id)
    if not row:
        raise HTTPException(status_code=404, detail="Passage not found")
    return PassageResponse(
        retrieval_unit_id=row["id"],
        text=row["unit_text"],
        canonical_reference=row["canonical_reference"],
        author=row["author"],
        work=row["work"],
        node_type=row["node_type"],
        section_role=row.get("section_role"),
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


@router.get("/passages/{passage_id}/context", response_model=PassageContextResponse)
def get_passage_context(
    passage_id: UUID, db: Session = Depends(get_db)
) -> PassageContextResponse:
    repo = CorpusRepository(db)
    if not repo.get_retrieval_unit(passage_id):
        raise HTTPException(status_code=404, detail="Passage not found")
    chain = repo.get_node_context(passage_id)
    return PassageContextResponse(
        retrieval_unit_id=passage_id,
        ancestors=[ContextNode(**node) for node in chain],
    )
