from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.search import PipelineTraceResponse, PlaygroundResponse, RetrieverComparisonRequest, RetrieverComparisonResponse, SearchRequest, SearchResponse
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def semantic_search(payload: SearchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return search_service.semantic_search(payload=payload, db=db, user=user)


@router.post("/playground", response_model=PlaygroundResponse)
def retrieval_playground(payload: SearchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return search_service.retrieval_playground(payload=payload, db=db, user=user)


@router.post("/trace", response_model=PipelineTraceResponse)
def pipeline_trace(payload: SearchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return search_service.pipeline_trace(payload=payload, db=db, user=user)


@router.post("/compare", response_model=RetrieverComparisonResponse)
def compare_retrievers(payload: RetrieverComparisonRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return search_service.compare_retrievers(payload=payload, db=db, user=user)
