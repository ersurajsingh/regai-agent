"""
Evaluation Agent for RegAI compliance outputs.

Workflow
--------
1. LOAD     — fetch prior compliance analysis + transaction rows from MongoDB
2. RULE     — run deterministic rule engine to get ground-truth findings
3. SCORE    — compute four evaluation dimensions:
               decision_quality    (rule-based + heuristic)
               reasoning_quality   (heuristic: regulation citations, specificity)
               hallucination_risk  (extra LLM issues not in rule engine)
               rule_alignment      (precision / recall / F1 vs rule engine)
4. SUMMARISE — Gemini generates a narrative evaluation summary
5. PERSIST  — store EvaluationResult in MongoDB + annotate Phoenix span

Phoenix compatibility
---------------------
Each EvaluationDimension maps to a Phoenix span annotation:
  { name, label, score, explanation }
The evaluation_workflow CHAIN span carries all four annotations as attributes,
making them queryable in the Phoenix UI under the regai-compliance project.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

from app.schemas.evaluation import (
    EvaluationDimension,
    EvaluationRequest,
    EvaluationResult,
    RuleEngineComparison,
)
from app.services.gemini_service import GeminiService
from app.services.rule_engine import RuleEngineResult, run_rule_engine
from phoenix.otel import using_session

logger = logging.getLogger(__name__)
_otel_tracer = otel_trace.get_tracer("regai.evaluation_agent")

_SUMMARY_SYSTEM_PROMPT = """You are a compliance AI quality auditor.

You will receive a structured evaluation of an AI compliance analysis, including:
- Scores for decision quality, reasoning quality, hallucination risk, and rule alignment
- A comparison between the AI output and a deterministic rule engine
- The original analysis explanation

Write a concise evaluation summary (3–5 sentences) that:
1. States the overall quality verdict
2. Highlights the strongest and weakest dimensions
3. Notes any hallucination concerns
4. Gives one concrete improvement suggestion

Be direct and specific. Do not repeat the scores verbatim."""


class EvaluationAgent:
    """
    Evaluates compliance analysis quality across four dimensions.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.gemini = GeminiService(system_instruction=_SUMMARY_SYSTEM_PROMPT)

    async def run(self, request: EvaluationRequest) -> EvaluationResult:
        evaluation_id = str(uuid.uuid4())
        eval_trace_id = str(uuid.uuid4())

        with using_session(session_id=request.session_id):
            with _otel_tracer.start_as_current_span(
                "evaluation_workflow",
                attributes={
                    "openinference.span.kind": "CHAIN",
                    "regai.evaluation_id": evaluation_id,
                    "regai.upload_id": request.upload_id,
                    "regai.session_id": request.session_id,
                },
            ) as outer_span:
                try:
                    result = await self._run_evaluation(request, evaluation_id, eval_trace_id)

                    # Attach Phoenix-compatible annotation attributes to the span
                    for dim in [
                        result.decision_quality,
                        result.reasoning_quality,
                        result.hallucination_risk,
                        result.rule_alignment,
                    ]:
                        outer_span.set_attribute(f"eval.{dim.name}.score", dim.score)
                        outer_span.set_attribute(f"eval.{dim.name}.label", dim.label)

                    outer_span.set_attribute("eval.overall_score", result.overall_score)
                    outer_span.set_attribute("eval.overall_label", result.overall_label)
                    outer_span.set_attribute("eval.f1_score", result.rule_comparison.f1_score)
                    outer_span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    outer_span.record_exception(exc)
                    outer_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

    async def _run_evaluation(
        self,
        request: EvaluationRequest,
        evaluation_id: str,
        eval_trace_id: str,
    ) -> EvaluationResult:

        # ── 1. Load prior analysis ─────────────────────────────────────────────
        query: dict[str, Any] = {
            "upload_id": request.upload_id,
            "session_id": request.session_id,
        }
        if request.analysis_trace_id:
            query["trace_id"] = request.analysis_trace_id

        analysis = await self.db.compliance_analyses.find_one(
            query, sort=[("created_at", -1)]
        )
        if not analysis:
            raise ValueError(
                f"No compliance analysis found for upload '{request.upload_id}'."
            )

        upload = await self.db.transaction_uploads.find_one(
            {"upload_id": request.upload_id, "session_id": request.session_id}
        )
        rows: list[dict[str, Any]] = (upload or {}).get("typed_rows") or []

        llm_issues: list[dict] = analysis.get("issues", [])
        llm_risk_level: str = analysis.get("risk_level", "medium")
        llm_risk_score: float = float(analysis.get("risk_score", 50.0))
        llm_explanation: str = analysis.get("explanation", "")
        analysis_trace_id: str | None = analysis.get("trace_id")

        # ── 2. Run rule engine ─────────────────────────────────────────────────
        with _otel_tracer.start_as_current_span(
            "rule_engine_baseline",
            attributes={"openinference.span.kind": "TOOL", "regai.upload_id": request.upload_id},
        ) as rule_span:
            rule_result = run_rule_engine(rows)
            rule_span.set_attribute("rule_engine.issue_count", len(rule_result))
            rule_span.set_status(Status(StatusCode.OK))

        # ── 3. Score dimensions ────────────────────────────────────────────────
        rule_comparison = _compute_rule_comparison(llm_issues, rule_result)

        decision_quality = _score_decision_quality(
            llm_issues, llm_risk_level, llm_risk_score, rule_result
        )
        reasoning_quality = _score_reasoning_quality(llm_issues, llm_explanation)
        hallucination_risk = _score_hallucination_risk(rule_comparison)
        rule_alignment = _score_rule_alignment(rule_comparison)

        overall_score = round(
            (decision_quality.score * 0.35)
            + (reasoning_quality.score * 0.25)
            + (hallucination_risk.score * 0.20)
            + (rule_alignment.score * 0.20),
            3,
        )
        overall_label = _overall_label(overall_score)

        # ── 4. Gemini evaluation summary ───────────────────────────────────────
        with _otel_tracer.start_as_current_span(
            "evaluation_summary_generation",
            attributes={"openinference.span.kind": "CHAIN"},
        ):
            summary_prompt = _build_summary_prompt(
                decision_quality, reasoning_quality,
                hallucination_risk, rule_alignment,
                rule_comparison, llm_explanation, overall_score,
            )
            evaluation_summary = self.gemini.generate(
                summary_prompt, trace_id=eval_trace_id
            )

        # ── 5. Build & persist result ──────────────────────────────────────────
        result = EvaluationResult(
            evaluation_id=evaluation_id,
            session_id=request.session_id,
            upload_id=request.upload_id,
            analysis_trace_id=analysis_trace_id,
            decision_quality=decision_quality,
            reasoning_quality=reasoning_quality,
            hallucination_risk=hallucination_risk,
            rule_alignment=rule_alignment,
            overall_score=overall_score,
            overall_label=overall_label,
            rule_comparison=rule_comparison,
            evaluation_summary=evaluation_summary,
            evaluation_trace_id=eval_trace_id,
        )

        await self.db.evaluations.insert_one({
            **result.model_dump(),
            "created_at": datetime.now(timezone.utc),
        })

        logger.info(
            "Evaluation complete | upload=%s overall=%.3f label=%s f1=%.3f eval=%s",
            request.upload_id, overall_score, overall_label,
            rule_comparison.f1_score, evaluation_id,
        )

        return result


# ── Scoring functions ──────────────────────────────────────────────────────────

def _compute_rule_comparison(
    llm_issues: list[dict],
    rule_result: RuleEngineResult,
) -> RuleEngineComparison:
    """Compute precision/recall/F1 between LLM output and rule engine."""
    llm_categories = {i.get("category", "other") for i in llm_issues}
    rule_categories = rule_result.categories

    confirmed = llm_categories & rule_categories
    extra = llm_categories - rule_categories       # LLM-only → potential hallucinations
    missed = rule_categories - llm_categories      # rule-only → LLM missed these

    llm_total = len(llm_categories)
    rule_total = len(rule_categories)
    confirmed_count = len(confirmed)

    precision = confirmed_count / llm_total if llm_total > 0 else 1.0
    recall = confirmed_count / rule_total if rule_total > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return RuleEngineComparison(
        rule_issue_count=len(rule_result),
        llm_issue_count=len(llm_issues),
        missed_issues=sorted(missed),
        extra_issues=sorted(extra),
        confirmed_issues=sorted(confirmed),
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1_score=round(f1, 3),
    )


def _score_decision_quality(
    llm_issues: list[dict],
    llm_risk_level: str,
    llm_risk_score: float,
    rule_result: RuleEngineResult,
) -> EvaluationDimension:
    """
    Score correctness of risk level and issue categorisation.
    Combines recall (did LLM find what rules found?) with risk calibration.
    """
    rule_categories = rule_result.categories
    llm_categories = {i.get("category", "other") for i in llm_issues}
    recall = len(llm_categories & rule_categories) / len(rule_categories) if rule_categories else 1.0

    # Risk calibration: penalise if risk_score is wildly off from rule-implied score
    rule_implied_score = min(100.0, len(rule_result) * 15.0)
    calibration_error = abs(llm_risk_score - rule_implied_score) / 100.0
    calibration_score = max(0.0, 1.0 - calibration_error)

    score = round((recall * 0.6) + (calibration_score * 0.4), 3)
    label = _score_label(score)

    return EvaluationDimension(
        name="decision_quality",
        label=label,
        score=score,
        explanation=(
            f"LLM captured {len(llm_categories & rule_categories)}/{len(rule_categories)} "
            f"rule-engine categories (recall={recall:.2f}). "
            f"Risk score {llm_risk_score:.0f} vs rule-implied {rule_implied_score:.0f} "
            f"(calibration={calibration_score:.2f})."
        ),
        metadata={"recall": recall, "calibration_score": calibration_score},
    )


def _score_reasoning_quality(
    llm_issues: list[dict],
    explanation: str,
) -> EvaluationDimension:
    """
    Score reasoning quality via heuristics:
    - Regulation citations present in issues
    - Explanation length and specificity
    - Evidence dicts populated
    """
    if not llm_issues:
        return EvaluationDimension(
            name="reasoning_quality",
            label="n/a",
            score=0.5,
            explanation="No issues to evaluate reasoning quality against.",
        )

    citation_rate = sum(
        1 for i in llm_issues if i.get("regulation")
    ) / len(llm_issues)

    evidence_rate = sum(
        1 for i in llm_issues if i.get("evidence")
    ) / len(llm_issues)

    # Explanation quality: penalise very short or very generic explanations
    explanation_words = len(explanation.split())
    explanation_score = min(1.0, explanation_words / 40.0)  # 40 words = full score

    score = round(
        (citation_rate * 0.40)
        + (evidence_rate * 0.30)
        + (explanation_score * 0.30),
        3,
    )
    label = _score_label(score)

    return EvaluationDimension(
        name="reasoning_quality",
        label=label,
        score=score,
        explanation=(
            f"Regulation citations: {citation_rate:.0%} of issues. "
            f"Evidence populated: {evidence_rate:.0%}. "
            f"Explanation length: {explanation_words} words."
        ),
        metadata={
            "citation_rate": citation_rate,
            "evidence_rate": evidence_rate,
            "explanation_words": explanation_words,
        },
    )


def _score_hallucination_risk(comparison: RuleEngineComparison) -> EvaluationDimension:
    """
    Score hallucination risk based on extra LLM issues not found by rule engine.
    Score of 1.0 = no hallucination risk; 0.0 = all LLM issues are unsupported.
    """
    if comparison.llm_issue_count == 0:
        return EvaluationDimension(
            name="hallucination_risk",
            label="n/a",
            score=1.0,
            explanation="LLM reported no issues — no hallucination risk.",
        )

    # precision = fraction of LLM issues confirmed by rule engine
    score = round(comparison.precision, 3)
    label = _score_label(score)
    extra_count = len(comparison.extra_issues)

    return EvaluationDimension(
        name="hallucination_risk",
        label=label,
        score=score,
        explanation=(
            f"{extra_count} LLM issue category/categories not found by rule engine "
            f"({comparison.extra_issues}). "
            f"Precision vs rule engine: {comparison.precision:.2f}."
        ),
        metadata={
            "extra_issues": comparison.extra_issues,
            "precision": comparison.precision,
        },
    )


def _score_rule_alignment(comparison: RuleEngineComparison) -> EvaluationDimension:
    """Score overall F1 alignment between LLM output and rule engine."""
    score = round(comparison.f1_score, 3)
    label = _score_label(score)

    return EvaluationDimension(
        name="rule_alignment",
        label=label,
        score=score,
        explanation=(
            f"F1={comparison.f1_score:.3f} "
            f"(precision={comparison.precision:.3f}, recall={comparison.recall:.3f}). "
            f"Confirmed: {comparison.confirmed_issues}. "
            f"Missed: {comparison.missed_issues}."
        ),
        metadata={
            "f1": comparison.f1_score,
            "precision": comparison.precision,
            "recall": comparison.recall,
        },
    )


# ── Prompt & label helpers ─────────────────────────────────────────────────────

def _build_summary_prompt(
    decision: EvaluationDimension,
    reasoning: EvaluationDimension,
    hallucination: EvaluationDimension,
    alignment: EvaluationDimension,
    comparison: RuleEngineComparison,
    original_explanation: str,
    overall_score: float,
) -> str:
    return "\n".join([
        "EVALUATION SCORES:",
        f"  overall_score:      {overall_score:.3f}",
        f"  decision_quality:   {decision.score:.3f} ({decision.label}) — {decision.explanation}",
        f"  reasoning_quality:  {reasoning.score:.3f} ({reasoning.label}) — {reasoning.explanation}",
        f"  hallucination_risk: {hallucination.score:.3f} ({hallucination.label}) — {hallucination.explanation}",
        f"  rule_alignment:     {alignment.score:.3f} ({alignment.label}) — {alignment.explanation}",
        "",
        "RULE ENGINE COMPARISON:",
        f"  confirmed: {comparison.confirmed_issues}",
        f"  missed:    {comparison.missed_issues}",
        f"  extra:     {comparison.extra_issues}",
        f"  F1:        {comparison.f1_score:.3f}",
        "",
        "ORIGINAL ANALYSIS EXPLANATION:",
        f"  {original_explanation}",
    ])


def _score_label(score: float) -> str:
    if score >= 0.85:
        return "excellent"
    if score >= 0.70:
        return "good"
    if score >= 0.50:
        return "fair"
    return "poor"


def _overall_label(score: float) -> str:
    return _score_label(score)
