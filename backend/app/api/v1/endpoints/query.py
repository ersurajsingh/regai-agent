from fastapi import APIRouter, Depends, HTTPException
from app.schemas.query import QueryRequest, QueryResponse
from app.agents.compliance_agent import ComplianceAgent
from app.core.database import get_db

router = APIRouter()


@router.post("/", response_model=QueryResponse)
async def run_query(payload: QueryRequest, db=Depends(get_db)):
    agent = ComplianceAgent(db=db)
    try:
        result = await agent.run(payload)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI backend error: {e}")
    return result
