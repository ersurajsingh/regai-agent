"""
Compliance analysis endpoint.
POST /api/v1/compliance/analyze — run full compliance analysis on an uploaded CSV
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.agents.compliance_analysis_agent import ComplianceAnalysisAgent
from app.core.database import get_db
from app.schemas.compliance import ComplianceAnalysisRequest, ComplianceAnalysisResult

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze", response_model=ComplianceAnalysisResult)
async def analyze_compliance(
    payload: ComplianceAnalysisRequest,
    db=Depends(get_db),
):
    """
    Run the full compliance analysis pipeline on a previously uploaded CSV.

    Steps:
    1. Deterministic pre-checks (KYC, duplicates, AML patterns, velocity)
    2. Gemini 2.0 Flash enrichment and risk scoring
    3. Merged structured result persisted to MongoDB

    Requires a valid upload_id from POST /api/v1/transactions/upload.
    """
    agent = ComplianceAnalysisAgent(db=db)
    try:
        return await agent.run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
