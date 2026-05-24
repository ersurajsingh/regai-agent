from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Upload ─────────────────────────────────────────────────────────────────────

class TransactionSummary(BaseModel):
    """Computed statistics returned with every upload."""

    row_count: int
    total_amount: float
    avg_amount: float
    min_amount: float
    max_amount: float
    earliest_timestamp: str | None
    latest_timestamp: str | None
    kyc_breakdown: dict[str, int]   # e.g. {"verified": 80, "pending": 15, "failed": 5}
    high_value_count: int           # transactions > $10,000 (CTR threshold)
    missing_fields_count: int       # rows with any None value in required columns


class TransactionUploadResponse(BaseModel):
    upload_id: str
    session_id: str
    filename: str
    columns: list[str]
    row_count: int
    summary: TransactionSummary
    warnings: list[str] = Field(default_factory=list)


# ── Analysis ───────────────────────────────────────────────────────────────────

class ComplianceAnalysisRequest(BaseModel):
    session_id: str
    upload_id: str
    query: str = Field(
        default="Analyze these transactions for compliance issues.",
        max_length=4000,
    )


class ComplianceFlag(BaseModel):
    row_index: int
    issue: str
    severity: str           # "high" | "medium" | "low"
    regulation: str | None = None


class ComplianceAnalysisResponse(BaseModel):
    session_id: str
    upload_id: str
    summary: str
    flags: list[ComplianceFlag]
    trace_id: str | None = None


# ── Internal record (used by service layer) ────────────────────────────────────

class TransactionRecord(BaseModel):
    """Single typed row stored in MongoDB."""

    row_index: int
    data: dict[str, Any]
