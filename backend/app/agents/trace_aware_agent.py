"""
Trace-Aware Compliance Agent.

Upgrades the standard compliance analysis with historical self-awareness:

Workflow
--------
1. LOAD MEMORY   — fetch prior analyses, evaluations, and reflections from MongoDB
                   via TraceMemory (the runtime equivalent of Phoenix MCP introspection)
2. DETECT PATTERNS — identify repeated mistakes, score trends, consistent weaknesses
3. ANALYSE        — run the four ADK detectors (same as ComplianceAnalysisAgent)
4. REASON         — call Gemini with historical context injected into the prompt:
                     - prior risk levels and scores
                     - categories that were repeatedly false-positived
                     - evaluation score trend
                     - critique summaries from reflections
5. EXPLAIN CHANGES — Gemini explains why its reasoning differs from prior analyses
6. PERSIST        — store result in compliance_analyses + trace_aware_analyses

Phoenix tracing
---------------
  trace_aware_workflow  [CHAIN]
    trace_memory_load   [TOOL]
    detect_*            [TOOL] × 4
    trace_aware_reasoning [CHAIN]  → Gemini LLM [auto-instrumented]
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

from app.schemas.compliance import (
    ComplianceIssue,
    ComplianceRecommendation,
    IssueSeverity,
    RiskLevel,
)
from app.schemas.trace_aware import (
    HistoricalPattern,
    ReasoningChange,
    TraceAwareAnalysisResult,
    TraceAwareRequest,
)
from app.services.gemini_service import GeminiService
from app.services.trace_memory import TraceMemory, load_trace_memory
from phoenix.otel import using_session
from regai_agent.tools.aml_detector import detect_aml_patterns
from regai_agent.tools.duplicate_detector import detect_duplicate_invoices
from regai_agent.tools.kyc_validator import detect_missing_kyc
from regai_agent.tools.suspicious_activity_detector import detect_suspicious_activity

logger = logging.getLogger(__name__)
_otel_tracer = otel_trace.get_tracer("regai.trace_aware_agent")

_SYSTEM_PROMPT = """You are RegAI, a senior financial compliance officer with memory of your prior decisions.

You will receive:
1. Current transaction data and pre-detected issues from automated rules
2. A summary of your PRIOR compliance analyses for this session, including:
   - Historical risk levels and scores
   - Categories you previously over-flagged (false positives)
   - Your evaluation score trend (improving / degrading / stable)
   - Critique summaries from prior reflection cycles

Your task:
- Produce a compliance analysis that LEARNS from prior mistakes
- Avoid repeating false positives in categories marked as over-flagged
- Recalibrate risk scores if your prior scores were consistently too high or too low
- Strengthen reasoning in areas where prior evaluations scored you poorly
- Explain in the "reasoning_changes" field why your current analysis differs from prior ones

Respond ONLY with valid JSON:
{
  "risk_level": "<low|medium|high|critical>",
  "risk_score": <float 0-100>,
  "issues": [
    {
      "category": "<aml|duplicate_invoice|missing_kyc|suspicious_activity|reporting_threshold|other>",
      "severity": "<low|medium|high|critical>",
      "row_indices": [<int>, ...],
      "description": "<string>",
      "regulation": "<string or null>",
      "evidence": {}
    }
  ],
  "recommendations": [
    {
      "priority": <1-5>,
      "action": "<string>",
      "rationale": "<string>"
    }
  ],
  "explanation": "<string>",
  "reasoning_changes": [
    {
      "dimension": "<string>",
      "previous_value": "<string>",
      "current_value": "<string>",
      "reason": "<string>"
    }
  ],
  "history_summary": "<2-3 sentences summarising what you learned from prior traces>"
}"""


class TraceAwareAgent:
    """
    Compliance agent that retrieves and reasons over prior trace history.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.gemini = GeminiService(system_instruction=_SYSTEM_PROMPT)

    async def run(self, request: TraceAwareRequest) -> TraceAwareAnalysisResult:
        trace_id = str(uuid.uuid4())

        upload = await self.db.transaction_uploads.find_one(
            {"upload_id": request.upload_id, "session_id": request.session_id}
        )
        if not upload:
            raise ValueError(
                f"Upload '{request.upload_id}' not found for session '{request.session_id}'."
            )

        rows: list[dict[str, Any]] = upload.get("typed_rows") or upload.get("rows", [])

        with using_session(session_id=request.session_id):
            with _otel_tracer.start_as_current_span(
                "trace_aware_workflow",
                attributes={
                    "openinference.span.kind": "CHAIN",
                    "regai.upload_id": request.upload_id,
                    "regai.session_id": request.session_id,
                    "regai.trace_id": trace_id,
                    "regai.row_count": len(rows),
                },
            ) as outer_span:
                try:
                    result = await self._run(request, rows, trace_id)
                    outer_span.set_attribute("regai.risk_level", result.risk_level.value)
                    outer_span.set_attribute("regai.risk_score", result.risk_score)
                    outer_span.set_attribute("regai.prior_analyses_used", result.prior_analyses_used)
                    outer_span.set_attribute("regai.session_trend", result.session_trend)
                    outer_span.set_attribute("regai.reasoning_changes", len(result.reasoning_changes))
                    outer_span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    outer_span.record_exception(exc)
                    outer_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

    async def _run(
        self,
        request: TraceAwareRequest,
        rows: list[dict[str, Any]],
        trace_id: str,
    ) -> TraceAwareAnalysisResult:

        # ── 1. Load trace memory ───────────────────────────────────────────────
        with _otel_tracer.start_as_current_span(
            "trace_memory_load",
            attributes={"openinference.span.kind": "TOOL",
                        "regai.session_id": request.session_id},
        ) as mem_span:
            memory = await load_trace_memory(
                self.db, request.session_id, request.upload_id,
                limit=request.history_limit,
            )
            mem_span.set_attribute("trace_memory.analyses_loaded", len(memory.prior_analyses))
            mem_span.set_attribute("trace_memory.trend", memory.trend)
            mem_span.set_attribute("trace_memory.repeated_mistakes",
                                   str(memory.repeated_mistake_categories))
            mem_span.set_status(Status(StatusCode.OK))

        # ── 2. Detect patterns from memory ────────────────────────────────────
        patterns = _extract_patterns(memory)

        # ── 3. Run detectors ───────────────────────────────────────────────────
        rows_json = json.dumps(rows)
        pre_issues_raw: list[dict] = []

        for tool_fn, tool_name in [
            (detect_missing_kyc,         "detect_missing_kyc"),
            (detect_duplicate_invoices,  "detect_duplicate_invoices"),
            (detect_aml_patterns,        "detect_aml_patterns"),
            (detect_suspicious_activity, "detect_suspicious_activity"),
        ]:
            with _otel_tracer.start_as_current_span(
                tool_name,
                attributes={"openinference.span.kind": "TOOL", "tool.name": tool_name},
            ) as tool_span:
                try:
                    res = tool_fn(rows_json)
                    issues = res.get("issues", [])
                    pre_issues_raw.extend(issues)
                    tool_span.set_attribute("tool.issue_count", len(issues))
                    tool_span.set_status(Status(StatusCode.OK))
                except Exception as exc:
                    tool_span.record_exception(exc)
                    tool_span.set_status(Status(StatusCode.ERROR, str(exc)))

        pre_issues = _raw_to_issues(pre_issues_raw)

        # ── 4. Trace-aware Gemini reasoning ───────────────────────────────────
        with _otel_tracer.start_as_current_span(
            "trace_aware_reasoning",
            attributes={"openinference.span.kind": "CHAIN",
                        "regai.prior_analyses": len(memory.prior_analyses)},
        ) as reasoning_span:
            prompt = _build_trace_aware_prompt(
                rows, pre_issues, memory, request.additional_context
            )
            raw = self.gemini.generate(prompt, trace_id=trace_id)
            gemini_result = _parse_json(raw, trace_id)
            reasoning_span.set_attribute("regai.reasoning_changes",
                                         len(gemini_result.get("reasoning_changes", [])))
            reasoning_span.set_status(Status(StatusCode.OK))

        # ── 5. Build result ────────────────────────────────────────────────────
        merged_issues = _merge_issues(pre_issues, gemini_result.get("issues", []))
        risk_level = RiskLevel(gemini_result.get("risk_level", _infer_risk_level(pre_issues)))
        risk_score = float(gemini_result.get("risk_score", _infer_risk_score(pre_issues)))

        reasoning_changes = [
            ReasoningChange(**rc)
            for rc in gemini_result.get("reasoning_changes", [])
            if _valid_reasoning_change(rc)
        ]

        result = TraceAwareAnalysisResult(
            risk_level=risk_level,
            risk_score=round(risk_score, 1),
            issues=merged_issues,
            recommendations=[
                ComplianceRecommendation(**r)
                for r in gemini_result.get("recommendations", [])
            ],
            explanation=gemini_result.get("explanation", ""),
            trace_id=trace_id,
            upload_id=request.upload_id,
            session_id=request.session_id,
            historical_patterns=patterns,
            reasoning_changes=reasoning_changes,
            history_summary=gemini_result.get("history_summary", ""),
            prior_analyses_used=len(memory.prior_analyses),
            session_trend=memory.trend,
            repeated_mistakes_avoided=memory.repeated_mistake_categories,
        )

        # ── 6. Persist ─────────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        # Store as a standard compliance analysis so evaluation/reflection can use it
        await self.db.compliance_analyses.insert_one({
            "session_id": request.session_id,
            "upload_id": request.upload_id,
            "trace_id": trace_id,
            "risk_level": risk_level.value,
            "risk_score": result.risk_score,
            "issues": [i.model_dump() for i in merged_issues],
            "recommendations": [r.model_dump() for r in result.recommendations],
            "explanation": result.explanation,
            "created_at": now,
        })
        # Also store the full trace-aware result
        await self.db.trace_aware_analyses.insert_one({
            **result.model_dump(),
            "created_at": now,
        })

        logger.info(
            "Trace-aware analysis complete | upload=%s risk=%s score=%.1f "
            "prior=%d changes=%d trend=%s",
            request.upload_id, risk_level, risk_score,
            len(memory.prior_analyses), len(reasoning_changes), memory.trend,
        )

        return result


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_patterns(memory: TraceMemory) -> list[HistoricalPattern]:
    patterns: list[HistoricalPattern] = []

    if memory.repeated_mistake_categories:
        patterns.append(HistoricalPattern(
            pattern_type="repeated_mistake",
            description=(
                f"Categories {memory.repeated_mistake_categories} were repeatedly "
                "flagged as false positives in prior analyses."
            ),
            affected_categories=memory.repeated_mistake_categories,
            evidence={"false_positive_analyses": len(memory.prior_analyses)},
        ))

    if memory.trend in ("improving", "degrading"):
        patterns.append(HistoricalPattern(
            pattern_type="score_trend",
            description=f"Evaluation scores are {memory.trend} over recent analyses.",
            evidence={
                "trend": memory.trend,
                "avg_eval_score": memory.avg_eval_score,
            },
        ))

    if memory.avg_hallucination_score is not None and memory.avg_hallucination_score < 0.6:
        patterns.append(HistoricalPattern(
            pattern_type="consistent_weakness",
            description=(
                f"Hallucination risk score averages {memory.avg_hallucination_score:.2f} — "
                "the agent consistently reports issues not confirmed by the rule engine."
            ),
            evidence={"avg_hallucination_score": memory.avg_hallucination_score},
        ))

    return patterns


def _build_trace_aware_prompt(
    rows: list[dict[str, Any]],
    pre_issues: list[ComplianceIssue],
    memory: TraceMemory,
    additional_context: str,
    max_rows: int = 60,
) -> str:
    lines: list[str] = []

    # Historical context block
    if memory.prior_analyses:
        lines += ["PRIOR ANALYSIS HISTORY (newest first):"]
        for i, p in enumerate(memory.prior_analyses[:5]):
            eval_info = (
                f"eval={p.overall_eval_score:.2f} ({p.eval_label})"
                if p.overall_eval_score is not None else "not evaluated"
            )
            lines.append(
                f"  [{i+1}] risk={p.risk_level} score={p.risk_score:.0f} "
                f"categories={p.issue_categories} {eval_info} "
                f"false_positives={p.false_positive_count}"
            )

        lines += [
            "",
            f"SESSION TREND: {memory.trend}",
            f"AVG EVAL SCORE: {memory.avg_eval_score or 'n/a'}",
            f"AVG HALLUCINATION SCORE: {memory.avg_hallucination_score or 'n/a'}",
        ]

        if memory.repeated_mistake_categories:
            lines += [
                "",
                "⚠ REPEATED FALSE POSITIVE CATEGORIES (avoid over-flagging these):",
                f"  {memory.repeated_mistake_categories}",
            ]
    else:
        lines += ["PRIOR ANALYSIS HISTORY: None — this is the first analysis for this session."]

    # Current transaction data
    sample = rows[:max_rows]
    lines += [
        "",
        f"CURRENT TRANSACTION DATA ({len(rows)} total rows, showing {len(sample)}):",
    ]
    for i, row in enumerate(sample):
        lines.append(f"  Row {i}: " + " | ".join(f"{k}={v}" for k, v in row.items()))

    # Pre-detected issues
    lines += ["", "PRE-DETECTED ISSUES (from automated rules):"]
    if pre_issues:
        for issue in pre_issues:
            lines.append(
                f"  [{issue.severity.upper()}] {issue.category}: {issue.description}"
                + (f" (rows: {issue.row_indices[:5]})" if issue.row_indices else "")
            )
    else:
        lines.append("  None detected.")

    if additional_context:
        lines += ["", f"ADDITIONAL CONTEXT: {additional_context}"]

    return "\n".join(lines)


def _parse_json(raw: str, trace_id: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Gemini non-JSON in trace-aware agent | trace=%s", trace_id)
        return {
            "risk_level": "medium", "risk_score": 50.0,
            "issues": [], "recommendations": [],
            "explanation": raw, "reasoning_changes": [], "history_summary": "",
        }


def _raw_to_issues(raw_list: list[dict]) -> list[ComplianceIssue]:
    issues = []
    for raw in raw_list:
        try:
            issues.append(ComplianceIssue(**raw))
        except Exception:
            pass
    return issues


def _merge_issues(
    pre: list[ComplianceIssue],
    gemini_raw: list[dict],
) -> list[ComplianceIssue]:
    pre_categories = {i.category for i in pre}
    merged = list(pre)
    for raw in gemini_raw:
        try:
            issue = ComplianceIssue(**raw)
            if issue.category not in pre_categories:
                merged.append(issue)
        except Exception:
            pass
    order = {IssueSeverity.CRITICAL: 0, IssueSeverity.HIGH: 1,
             IssueSeverity.MEDIUM: 2, IssueSeverity.LOW: 3}
    merged.sort(key=lambda i: order.get(i.severity, 99))
    return merged


def _valid_reasoning_change(rc: dict) -> bool:
    return all(rc.get(k) for k in ("dimension", "previous_value", "current_value", "reason"))


def _infer_risk_level(issues: list[ComplianceIssue]) -> str:
    severities = {i.severity for i in issues}
    if IssueSeverity.CRITICAL in severities:
        return "critical"
    if IssueSeverity.HIGH in severities:
        return "high"
    if IssueSeverity.MEDIUM in severities:
        return "medium"
    return "low"


def _infer_risk_score(issues: list[ComplianceIssue]) -> float:
    weights = {IssueSeverity.CRITICAL: 30, IssueSeverity.HIGH: 15,
               IssueSeverity.MEDIUM: 7, IssueSeverity.LOW: 2}
    return min(100.0, sum(weights.get(i.severity, 0) for i in issues))
