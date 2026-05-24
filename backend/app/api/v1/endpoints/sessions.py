from fastapi import APIRouter, Depends, HTTPException
from app.services.session_service import SessionService
from app.core.database import get_db

router = APIRouter()


@router.post("/")
async def create_session(db=Depends(get_db)):
    service = SessionService(db=db)
    session = await service.create()
    return session


@router.get("/{session_id}")
async def get_session(session_id: str, db=Depends(get_db)):
    service = SessionService(db=db)
    session = await service.get(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    return session
