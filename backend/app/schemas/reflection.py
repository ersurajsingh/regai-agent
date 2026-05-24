"""
Schemas for the self-reflection workflow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.compliance import ComplianceIssue, ComplianceRecommendation, RiskLevel


class ReflectionRequest(BaseModel):
    session_id: str
    upload_id: str
    # Optionally target a specific prior analysis; defaults to the most recent one
    analysis_trace_id: str | None = Field(
        default=None,
        description="trace_id of the prior analysis to reflect on. "
                    "Defaults to the most recent analysis for this upload.",
    )
    reflection_context: str = Field(
        default="",
        max_length=2000,
        description="Optional human feedback or additional context for the reflection.",
    )


class FalsePositiveAssessment(BaseModel):
    issue_index: int                    # index into the original issues list
    original_description: str
    verdict: str                        # "confirmed" | "likely_false_positive" | "uncertain"
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReasoningCritique(BaseModel):
    aspect: str                         # e.g. "risk_score_calibration", "missing_context"
    critique: str
    severity: str                       # "minor" | "moderate" | "significant"


class ImprovementDelta(BaseModel):
    """Diff between original and improved outputs."""

    risk_level_changed: bool
    original_risk_level: str
    improved_risk_level: str
    risk_score_delta: float             # improved - original
    issues_added: list[ComplianceIssue] = Field(default_factory=list)
    issues_removed_indices: list[int] = Field(default_factory=list)
    recommendations_changed: bool


class ReflectionResult(BaseModel):
    """Full output of one self-reflection cycle."""

    reflection_id: str
    session_id: str
    upload_id: str
    original_trace_id: str | None

    # Critique of the original analysis
    false_positive_assessments: list[FalsePositiveAssessment]
    reasoning_critiques: list[ReasoningCritique]
    critique_summary: str

    # Improved output
    improved_risk_level: RiskLevel
    improved_risk_score: float = Field(ge=0.0, le=100.0)
    improved_issues: list[ComplianceIssue]
    improved_recommendations: list[ComplianceRecommendation]
    improved_explanation: str

    # Delta
    delta: ImprovementDelta

    created_at: datetime = Field(default_factory=lambda: datetime.now(__import__("datetime").timezone.utc))
    reflection_trace_id: str | None = None


class ReflectionHistoryEntry(BaseModel):
    """Lightweight summary stored in MongoDB reflection_history collection."""

    reflection_id: str
    session_id: str
    upload_id: str
    original_trace_id: str | None
    original_risk_level: str
    improved_risk_level: str
    risk_score_delta: float
    false_positive_count: int
    critique_count: int
    created_at: datetime
