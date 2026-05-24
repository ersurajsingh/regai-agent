"""
Transaction upload and compliance analysis endpoints.

POST /api/v1/transactions/upload  — parse + validate CSV, store, return summary
POST /api/v1/transactions/analyze — run Gemini compliance analysis on stored upload
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.core.database import get_db
from app.schemas.transaction import (
    ComplianceAnalysisRequest,
    ComplianceAnalysisResponse,
    TransactionUploadResponse,
)
from app.services.transaction_service import TransactionService
from app.utils.csv_parser import CSVParseError, parse_transaction_csv

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=TransactionUploadResponse)
async def upload_transactions(
    session_id: str,
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    """
    Upload a CSV of transaction data.

    Required columns: transaction_id, amount, vendor, timestamp, customer_name, kyc_status

    Returns upload_id + parsed summary. Use upload_id in /analyze.
    """
    filename = file.filename or "upload.csv"
    content_type = file.content_type or ""

    if content_type not in ALLOWED_CONTENT_TYPES and not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=422,
            detail="Unsupported file type. Please upload a CSV file.",
        )

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="File exceeds 10 MB limit.")
    if not content.strip():
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    try:
        parsed = parse_transaction_csv(content, filename=filename)
    except CSVParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    service = TransactionService(db=db)
    return await service.store_upload(
        session_id=session_id,
        filename=filename,
        parsed=parsed,
    )


@router.post("/analyze", response_model=ComplianceAnalysisResponse)
async def analyze_transactions(
    payload: ComplianceAnalysisRequest,
    db=Depends(get_db),
):
    """
    Run Gemini compliance analysis on a previously uploaded CSV.
    """
    service = TransactionService(db=db)
    try:
        return await service.analyze(
            session_id=payload.session_id,
            upload_id=payload.upload_id,
            query=payload.query,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
