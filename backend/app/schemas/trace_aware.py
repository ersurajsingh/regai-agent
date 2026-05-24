"""
Schemas for trace-aware compliance analysis.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.compliance import (
    ComplianceAnalysisRequest,
    ComplianceIssue,
    ComplianceRecommendation,
    RiskLevel,
)


class TraceAwareRequest(BaseModel):
    session_id: str
    upload_id: str
    additional_context: str = Field(default="", max_length=2000)
    # How many prior analyses to load as context (default 5, max 10)
    history_limit: int = Field(default=5, ge=1, le=10)


class HistoricalPattern(BaseModel):
    """A pattern identified across prior analyses."""

    pattern_type: str           # "repeated_mistake" | "consistent_strength" | "score_trend"
    description: str
    affected_categories: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ReasoningChange(BaseModel):
    """Explains why the current analysis differs from prior ones."""

    dimension: str              # e.g. "risk_score", "issue_category", "recommendation"
    previous_value: str
    current_value: str
    reason: str                 # why the agent changed its reasoning


class TraceAwareAnalysisResult(BaseModel):
    """
    Full output of a trace-aware compliance analysis.
    Extends the standard ComplianceAnalysisResult with historical context.
    """

    # Standard compliance output
    risk_level: RiskLevel
    risk_score: float = Field(ge=0.0, le=100.0)
    issues: list[ComplianceIssue]
    recommendations: list[ComplianceRecommendation]
    explanation: str
    trace_id: str | None = None
    upload_id: str
    session_id: str

    # Trace-aware additions
    historical_patterns: list[HistoricalPattern]
    reasoning_changes: list[ReasoningChange]
    history_summary: str        # narrative of what the agent learned from prior traces
    prior_analyses_used: int
    session_trend: str          # "improving" | "degrading" | "stable" | "insufficient_data"
    repeated_mistakes_avoided: list[str]  # categories the agent consciously avoided over-flagging
