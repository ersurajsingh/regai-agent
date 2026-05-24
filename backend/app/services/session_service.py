import uuid
import secrets
from datetime import datetime, timezone, timedelta

from app.core.config import settings


class SessionService:
    def __init__(self, db):
        self.db = db

    async def create(self) -> dict:
        session_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRE_HOURS)

        doc = {
            "session_id": session_id,
            "token": token,
            "documents": [],
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
        }
        await self.db.sessions.insert_one(doc)
        return {"session_id": session_id, "token": token, "expires_at": expires_at.isoformat()}

    async def get(self, session_id: str) -> dict | None:
        session = await self.db.sessions.find_one(
            {"session_id": session_id, "expires_at": {"$gt": datetime.now(timezone.utc)}},
            {"_id": 0, "token": 0},
        )
        return session
