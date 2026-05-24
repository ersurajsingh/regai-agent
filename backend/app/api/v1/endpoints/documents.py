from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.document_processor import DocumentProcessor
from app.core.database import get_db

router = APIRouter()

ALLOWED_TYPES = {"application/pdf", "text/plain"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported file type. Use PDF or plain text.")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="File exceeds 10 MB limit.")

    processor = DocumentProcessor(db=db)
    doc_id = await processor.process(
        session_id=session_id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        content=content,
    )
    return {"document_id": doc_id, "filename": file.filename}
