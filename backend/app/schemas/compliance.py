"""
Schemas for the compliance analysis agent output.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(str, Enum):
    AML = "aml"
    DUPLICATE = "duplicate_invoice"
    KYC = "missing_kyc"
    SUSPICIOUS = "suspicious_activity"
    THRESHOLD = "reporting_threshold"
    OTHER = "other"


class ComplianceIssue(BaseModel):
    """A single detected compliance issue."""

    category: IssueCategory
    severity: IssueSeverity
    row_indices: list[int] = Field(default_factory=list)  # affected rows (empty = dataset-level)
    description: str
    regulation: str | None = None          # e.g. "BSA 31 CFR 1010.311"
    evidence: dict[str, Any] = Field(default_factory=dict)  # supporting data points


class ComplianceRecommendation(BaseModel):
    priority: int = Field(ge=1, le=5, description="1 = highest priority")
    action: str
    rationale: str


class ComplianceAnalysisResult(BaseModel):
    """
    Structured output returned by the compliance analysis agent.
    Shape matches the requested contract:
      { risk_level, issues, recommendations, explanation }
    """

    risk_level: RiskLevel
    risk_score: float = Field(ge=0.0, le=100.0, description="Numeric score 0–100")
    issues: list[ComplianceIssue]
    recommendations: list[ComplianceRecommendation]
    explanation: str
    trace_id: str | None = None
    upload_id: str
    session_id: str
    gemini_prompt: str | None = None
    gemini_raw_response: str | None = None


class ComplianceAnalysisRequest(BaseModel):
    session_id: str
    upload_id: str
    additional_context: str = Field(
        default="",
        max_length=2000,
        description="Optional extra instructions for the analysis.",
    )
