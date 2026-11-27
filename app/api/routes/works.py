from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import EditionSummary, WorkDetailResponse, WorkSummary
from app.db.deps import get_db
from app.repositories.corpus import CorpusRepository

router = APIRouter(prefix="/v1", tags=["works"])


@router.get("/works", response_model=list[WorkSummary])
def list_works(db: Session = Depends(get_db)) -> list[WorkSummary]:
    repo = CorpusRepository(db)
    rows = repo.list_works()
    return [
        WorkSummary(
            id=r["id"],
            title=r["title"],
            short_code=r["short_code"],
            genre=r["genre"],
            author=r["author"],
            edition_count=int(r["edition_count"]),
        )
        for r in rows
    ]


@router.get("/works/{work_id}", response_model=WorkDetailResponse)
def get_work(work_id: UUID, db: Session = Depends(get_db)) -> WorkDetailResponse:
    repo = CorpusRepository(db)
    detail = repo.get_work_detail(work_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Work not found")
    return WorkDetailResponse(
        id=detail["id"],
        title=detail["title"],
        short_code=detail["short_code"],
        genre=detail["genre"],
        author=detail["author"],
        editions=[EditionSummary(**e) for e in detail["editions"]],
    )
