"""
Evaluation endpoints.

POST /api/v1/compliance/evaluate              — run evaluation on a prior analysis
GET  /api/v1/compliance/evaluate/history      — list evaluations for an upload
GET  /api/v1/compliance/evaluate/{id}         — retrieve a specific evaluation
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.evaluation_agent import EvaluationAgent
from app.core.database import get_db
from app.schemas.evaluation import EvaluationRequest, EvaluationResult

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate_compliance(
    payload: EvaluationRequest,
    db=Depends(get_db),
):
    """
    Evaluate the quality of a prior compliance analysis.

    Scores four dimensions:
    - decision_quality    — correctness of risk level and issue categorisation
    - reasoning_quality   — regulation citations, evidence, explanation depth
    - hallucination_risk  — LLM issues not supported by deterministic rule engine
    - rule_alignment      — F1 agreement with rule engine (precision + recall)

    Returns a Phoenix-compatible EvaluationResult with per-dimension scores,
    a rule-engine comparison, and a Gemini-generated narrative summary.
    """
    agent = EvaluationAgent(db=db)
    try:
        return await agent.run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/evaluate/history")
async def get_evaluation_history(
    session_id: str = Query(...),
    upload_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db=Depends(get_db),
):
    """
    List evaluation history for a given upload, newest first.
    Returns lightweight summaries (scores + labels, no full issue lists).
    """
    cursor = db.evaluations.find(
        {"session_id": session_id, "upload_id": upload_id},
        {
            "_id": 0,
            "evaluation_id": 1,
            "analysis_trace_id": 1,
            "overall_score": 1,
            "overall_label": 1,
            "decision_quality.score": 1,
            "decision_quality.label": 1,
            "reasoning_quality.score": 1,
            "reasoning_quality.label": 1,
            "hallucination_risk.score": 1,
            "hallucination_risk.label": 1,
            "rule_alignment.score": 1,
            "rule_alignment.label": 1,
            "rule_comparison.f1_score": 1,
            "evaluation_summary": 1,
            "created_at": 1,
        },
        sort=[("created_at", -1)],
        limit=limit,
    )
    entries = await cursor.to_list(length=limit)
    return {"session_id": session_id, "upload_id": upload_id, "evaluations": entries}


@router.get("/evaluate/{evaluation_id}", response_model=EvaluationResult)
async def get_evaluation(
    evaluation_id: str,
    db=Depends(get_db),
):
    """Retrieve a specific evaluation result by its evaluation_id."""
    doc = await db.evaluations.find_one(
        {"evaluation_id": evaluation_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation '{evaluation_id}' not found.",
        )
    return doc
