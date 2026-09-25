from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import IngestionRunResponse
from app.db.deps import get_db
from app.repositories.corpus import CorpusRepository

router = APIRouter(prefix="/v1", tags=["ingestion"])


@router.get("/ingestion-runs/{run_id}", response_model=IngestionRunResponse)
def get_ingestion_run(
    run_id: UUID, db: Session = Depends(get_db)
) -> IngestionRunResponse:
    repo = CorpusRepository(db)
    run = repo.get_ingestion_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return IngestionRunResponse(
        id=run.id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        parser_name=run.parser_name,
        parser_version=run.parser_version,
        corpus_version=run.corpus_version,
        error_message=run.error_message,
        validation_report=run.validation_report,
    )
