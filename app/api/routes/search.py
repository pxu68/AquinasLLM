from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import SearchRequest, SearchResponse
from app.db.deps import get_db
from app.retrieval.service import RetrievalService

router = APIRouter(prefix="/v1", tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(body: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    service = RetrievalService(db)
    return service.search(
        body.query,
        authors=body.authors,
        works=body.works,
        node_types=body.node_types,
        limit=body.limit,
    )
