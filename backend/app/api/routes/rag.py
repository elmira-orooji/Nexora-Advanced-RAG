from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.rate_limit import rag_limiter, rate_limit
from app.db.database import get_db
from app.models.user import User
from app.schemas.rag import RagRequest, RagResponse
from app.services.providers.provider_factory import get_provider_factory
from app.services.retrieval.rag_service import RagService

router = APIRouter(prefix="/rag", tags=["rag"])


def get_rag_service(db: Session) -> RagService:
    return RagService(db, providers=get_provider_factory())


@router.post("/answer", response_model=RagResponse, dependencies=[Depends(rate_limit(rag_limiter))])
def answer_question(payload: RagRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_rag_service(db).answer(payload, user)
