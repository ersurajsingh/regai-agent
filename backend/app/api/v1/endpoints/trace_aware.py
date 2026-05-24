"""
Trace-aware compliance analysis endpoint.

POST /api/v1/compliance/analyze/trace-aware
GET  /api/v1/compliance/analyze/trace-aware/history
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.trace_aware_agent import TraceAwareAgent
from app.core.database import get_db
from app.schemas.trace_aware import TraceAwareAnalysisResult, TraceAwareRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze/trace-aware", response_model=TraceAwareAnalysisResult)
async def analyze_trace_aware(
    payload: TraceAwareRequest,
    db=Depends(get_db),
):
    """
    Run a trace-aware compliance analysis.

    Unlike the standard analysis, this agent:
    - Retrieves prior analyses, evaluations, and reflections for the session
    - Identifies repeated mistakes and score trends
    - Injects historical context into the Gemini prompt
    - Explains why its reasoning changed compared to prior analyses
    - Avoids repeating confirmed false positives

    The result is stored in both compliance_analyses (for downstream
    evaluation/reflection) and trace_aware_analyses (full detail).
    """
    agent = TraceAwareAgent(db=db)
    try:
        return await agent.run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/analyze/trace-aware/history")
async def get_trace_aware_history(
    session_id: str = Query(...),
    upload_id: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    db=Depends(get_db),
):
    """
    List trace-aware analysis results for a session, newest first.
    Returns lightweight summaries including reasoning changes and trend.
    """
    cursor = db.trace_aware_analyses.find(
        {"session_id": session_id, "upload_id": upload_id},
        {
            "_id": 0,
            "trace_id": 1,
            "risk_level": 1,
            "risk_score": 1,
            "session_trend": 1,
            "prior_analyses_used": 1,
            "repeated_mistakes_avoided": 1,
            "reasoning_changes": 1,
            "history_summary": 1,
            "created_at": 1,
        },
        sort=[("created_at", -1)],
        limit=limit,
    )
    entries = await cursor.to_list(length=limit)
    return {"session_id": session_id, "upload_id": upload_id, "analyses": entries}
