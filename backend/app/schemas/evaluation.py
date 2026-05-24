"""
Evaluation schemas — Phoenix-compatible structure.

Phoenix stores evaluations as span annotations with a label + score + explanation.
Each EvaluationDimension maps directly to one Phoenix annotation.

Reference:
  https://arize.com/docs/phoenix/tracing/how-to-tracing/llm-evaluations
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Per-dimension score (maps to one Phoenix span annotation) ──────────────────

class EvaluationDimension(BaseModel):
    """
    A single scored evaluation dimension.
    Compatible with Phoenix annotation format:
      { name, label, score, explanation }
    """

    name: str                                   # dimension identifier
    label: str                                  # human-readable verdict
    score: float = Field(ge=0.0, le=1.0)        # 0.0 = worst, 1.0 = best
    explanation: str                            # reasoning behind the score
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Rule-engine comparison ─────────────────────────────────────────────────────

class RuleEngineComparison(BaseModel):
    """Structured diff between deterministic rule findings and LLM output."""

    rule_issue_count: int
    llm_issue_count: int

    # Issues the rule engine found that the LLM missed
    missed_issues: list[str] = Field(default_factory=list)

    # Issues the LLM reported that the rule engine did NOT find (potential hallucinations)
    extra_issues: list[str] = Field(default_factory=list)

    # Issues present in both (confirmed findings)
    confirmed_issues: list[str] = Field(default_factory=list)

    # Precision: confirmed / llm_total  (how much of LLM output is correct)
    precision: float = Field(ge=0.0, le=1.0)

    # Recall: confirmed / rule_total  (how much of ground truth LLM captured)
    recall: float = Field(ge=0.0, le=1.0)

    # F1 harmonic mean
    f1_score: float = Field(ge=0.0, le=1.0)


# ── Full evaluation result ─────────────────────────────────────────────────────

class EvaluationResult(BaseModel):
    """
    Complete evaluation of one compliance analysis.

    Dimensions evaluated:
      decision_quality    — correctness of risk level and issue categorisation
      reasoning_quality   — clarity, specificity, and citation of regulations
      hallucination_risk  — issues claimed without rule-engine support
      rule_alignment      — F1 agreement with deterministic rule engine
    """

    evaluation_id: str
    session_id: str
    upload_id: str
    analysis_trace_id: str | None

    # Four scored dimensions
    decision_quality: EvaluationDimension
    reasoning_quality: EvaluationDimension
    hallucination_risk: EvaluationDimension     # lower score = higher hallucination risk
    rule_alignment: EvaluationDimension

    # Aggregate
    overall_score: float = Field(ge=0.0, le=1.0)
    overall_label: str                          # "excellent" | "good" | "fair" | "poor"

    # Rule-engine comparison detail
    rule_comparison: RuleEngineComparison

    # Gemini-generated narrative summary
    evaluation_summary: str

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(__import__("datetime").timezone.utc)
    )
    evaluation_trace_id: str | None = None


# ── Request ────────────────────────────────────────────────────────────────────

class EvaluationRequest(BaseModel):
    session_id: str
    upload_id: str
    analysis_trace_id: str | None = Field(
        default=None,
        description="Specific analysis to evaluate. Defaults to most recent.",
    )
