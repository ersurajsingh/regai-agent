"""
Self-reflection endpoints.

POST /api/v1/compliance/reflect          — run one reflection cycle
GET  /api/v1/compliance/reflect/history  — list reflection history for an upload
GET  /api/v1/compliance/reflect/{id}     — retrieve a specific reflection result
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.reflection_agent import ReflectionAgent
from app.core.database import get_db
from app.schemas.reflection import ReflectionRequest, ReflectionResult

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/reflect", response_model=ReflectionResult)
async def reflect_on_analysis(
    payload: ReflectionRequest,
    db=Depends(get_db),
):
    """
    Run a self-reflection cycle on a prior compliance analysis.

    The agent will:
    1. Load the most recent (or specified) analysis for the upload
    2. Critique it for false positives and weak reasoning
    3. Generate an improved analysis
    4. Return a structured diff of original vs improved outputs
    5. Persist the reflection to MongoDB
    """
    agent = ReflectionAgent(db=db)
    try:
        return await agent.run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/reflect/history")
async def get_reflection_history(
    session_id: str = Query(...),
    upload_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db=Depends(get_db),
):
    """
    List reflection history entries for a given upload, newest first.
    """
    cursor = db.reflection_history.find(
        {"session_id": session_id, "upload_id": upload_id},
        {"_id": 0},
        sort=[("created_at", -1)],
        limit=limit,
    )
    entries = await cursor.to_list(length=limit)
    return {"session_id": session_id, "upload_id": upload_id, "history": entries}


@router.get("/reflect/{reflection_id}", response_model=ReflectionResult)
async def get_reflection(
    reflection_id: str,
    db=Depends(get_db),
):
    """
    Retrieve a specific reflection result by its reflection_id.
    """
    doc = await db.reflection_results.find_one(
        {"reflection_id": reflection_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail=f"Reflection '{reflection_id}' not found.")
    return doc
