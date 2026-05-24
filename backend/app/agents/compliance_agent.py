import logging
import uuid
from datetime import datetime, timezone

from app.schemas.query import QueryRequest, QueryResponse
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are RegAI, an expert AI compliance agent.
Your role is to help compliance officers understand regulatory requirements clearly and accurately.
Always cite the relevant regulation or section when possible.
If you are unsure, say so rather than guessing."""


class ComplianceAgent:
    """Core compliance agent powered by Gemini."""

    def __init__(self, db) -> None:
        self.db = db
        self.gemini = GeminiService(system_instruction=_SYSTEM_PROMPT)

    async def run(self, payload: QueryRequest) -> QueryResponse:
        trace_id = str(uuid.uuid4())

        session = await self.db.sessions.find_one({"session_id": payload.session_id})
        context = self._build_context(session)
        prompt = f"{context}\n\nUser question: {payload.query}" if context else payload.query

        answer = self.gemini.generate(prompt, trace_id=trace_id)

        await self.db.queries.insert_one({
            "session_id": payload.session_id,
            "query": payload.query,
            "answer": answer,
            "trace_id": trace_id,
            "created_at": datetime.now(timezone.utc),
        })

        logger.info("Query processed | session=%s trace=%s", payload.session_id, trace_id)

        return QueryResponse(
            session_id=payload.session_id,
            query=payload.query,
            answer=answer,
            trace_id=trace_id,
        )

    def _build_context(self, session: dict | None) -> str:
        if not session or not session.get("documents"):
            return ""
        excerpts = [doc.get("text_excerpt", "") for doc in session["documents"]]
        return "Relevant document context:\n" + "\n---\n".join(excerpts)
