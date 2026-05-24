from fastapi import APIRouter

from app.api.v1.endpoints import (
    query, documents, sessions, transactions,
    compliance, reflection, evaluation, trace_aware,
)

api_router = APIRouter()

api_router.include_router(query.router, prefix="/query", tags=["Query"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["Compliance"])
api_router.include_router(reflection.router, prefix="/compliance", tags=["Reflection"])
api_router.include_router(evaluation.router, prefix="/compliance", tags=["Evaluation"])
api_router.include_router(trace_aware.router, prefix="/compliance", tags=["Trace-Aware"])
