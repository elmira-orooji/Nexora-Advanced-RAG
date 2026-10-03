from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.research_service import ResearchService

router = APIRouter(prefix="/research", tags=["deep-research"])


@router.post("/run", response_model=ResearchResponse)
def run_research(
    payload: ResearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResearchResponse:
    return ResearchService(db).run(payload, user)
