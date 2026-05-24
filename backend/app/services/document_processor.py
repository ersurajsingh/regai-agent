import io
import uuid
from datetime import datetime, timezone

from pypdf import PdfReader


class DocumentProcessor:
    def __init__(self, db):
        self.db = db

    async def process(
        self,
        session_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> str:
        text = self._extract_text(content_type, content)
        doc_id = str(uuid.uuid4())

        await self.db.sessions.update_one(
            {"session_id": session_id},
            {
                "$push": {
                    "documents": {
                        "document_id": doc_id,
                        "filename": filename,
                        "text_excerpt": text[:8000],  # store first 8k chars as context
                        "uploaded_at": datetime.now(timezone.utc),
                    }
                }
            },
            upsert=True,
        )
        return doc_id

    def _extract_text(self, content_type: str, content: bytes) -> str:
        if content_type == "application/pdf":
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        return content.decode("utf-8", errors="replace")
