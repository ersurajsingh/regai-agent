"""
Compliance Analysis Agent — FastAPI integration layer.

Delegates all detector logic to the ADK tool functions in regai_agent/tools/,
then calls Gemini for enrichment and risk scoring.

Tracing
-------
Manual Phoenix spans are added at three levels:
  CHAIN  — full compliance_analysis_workflow (orchestration)
  TOOL   — each of the four detector calls
  LLM    — Gemini enrichment call (auto-instrumented; chain span provides context)

Session context is propagated via using_session() so all spans for a given
upload are grouped under the same session in the Phoenix UI.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

from app.schemas.compliance import (
    ComplianceAnalysisRequest,
    ComplianceAnalysisResult,
    ComplianceIssue,
    ComplianceRecommendation,
    IssueSeverity,
    RiskLevel,
)
from app.services.gemini_service import GeminiService

# ── Re-use ADK tool functions directly ────────────────────────────────────────
from regai_agent.tools.aml_detector import detect_aml_patterns
from regai_agent.tools.duplicate_detector import detect_duplicate_invoices
from regai_agent.tools.kyc_validator import detect_missing_kyc
from regai_agent.tools.suspicious_activity_detector import detect_suspicious_activity

# ── Phoenix tracing helpers ───────────────────────────────────────────────────
from phoenix.otel import using_session

logger = logging.getLogger(__name__)

# Module-level OTel tracer — spans appear under the regai-compliance project
_otel_tracer = otel_trace.get_tracer("regai.compliance_agent")

_SYSTEM_PROMPT = """You are RegAI, a senior financial compliance officer and AML specialist.

You will receive:
1. A structured summary of transaction data
2. Pre-detected compliance issues found by automated rules

Your job:
- Validate and enrich the pre-detected issues
- Identify any additional risks the rules may have missed
- Assign an overall risk_level (low / medium / high / critical) and numeric risk_score (0–100)
- Write a concise explanation (2–4 sentences) suitable for a compliance report
- Provide 3–5 prioritised recommendations

Respond ONLY with valid JSON matching this exact schema:
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
  "explanation": "<string>"
}"""


class ComplianceAnalysisAgent:
    """
    FastAPI compliance agent.
    Runs ADK tool functions for pre-analysis, then calls Gemini for enrichment.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.gemini = GeminiService(system_instruction=_SYSTEM_PROMPT)

    async def run(self, request: ComplianceAnalysisRequest) -> ComplianceAnalysisResult:
        trace_id = str(uuid.uuid4())

        upload = await self.db.transaction_uploads.find_one(
            {"upload_id": request.upload_id, "session_id": request.session_id}
        )
        if not upload:
            raise ValueError(
                f"Upload '{request.upload_id}' not found for session '{request.session_id}'."
            )

        rows: list[dict[str, Any]] = upload.get("typed_rows") or upload.get("rows", [])
        rows_json = json.dumps(rows)

        # Wrap the full reasoning workflow in a CHAIN span, scoped to the session
        with using_session(session_id=request.session_id):
            with _otel_tracer.start_as_current_span(
                "compliance_analysis_workflow",
                attributes={
                    "openinference.span.kind": "CHAIN",
                    "regai.upload_id": request.upload_id,
                    "regai.session_id": request.session_id,
                    "regai.trace_id": trace_id,
                    "regai.row_count": len(rows),
                },
            ) as chain_span:
                try:
                    result = await self._run_analysis(
                        request, rows, rows_json, trace_id
                    )
                    chain_span.set_attribute("regai.risk_level", result.risk_level.value)
                    chain_span.set_attribute("regai.risk_score", result.risk_score)
                    chain_span.set_attribute("regai.issue_count", len(result.issues))
                    chain_span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    chain_span.record_exception(exc)
                    chain_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

    async def _run_analysis(
        self,
        request: ComplianceAnalysisRequest,
        rows: list[dict[str, Any]],
        rows_json: str,
        trace_id: str,
    ) -> ComplianceAnalysisResult:
        # ── 1. Detector tool spans ─────────────────────────────────────────────
        pre_issues_raw: list[dict] = []

        for tool_fn, tool_name in [
            (detect_missing_kyc,         "detect_missing_kyc"),
            (detect_duplicate_invoices,  "detect_duplicate_invoices"),
            (detect_aml_patterns,        "detect_aml_patterns"),
            (detect_suspicious_activity, "detect_suspicious_activity"),
        ]:
            with _otel_tracer.start_as_current_span(
                tool_name,
                attributes={
                    "openinference.span.kind": "TOOL",
                    "tool.name": tool_name,
                    "regai.upload_id": request.upload_id,
                },
            ) as tool_span:
                try:
                    result_dict = tool_fn(rows_json)
                    issues = result_dict.get("issues", [])
                    pre_issues_raw.extend(issues)
                    tool_span.set_attribute("tool.issue_count", len(issues))
                    tool_span.set_attribute("tool.status", result_dict.get("status", "unknown"))
                    tool_span.set_status(Status(StatusCode.OK))
                except Exception as exc:
                    tool_span.record_exception(exc)
                    tool_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    logger.warning("Tool %s failed: %s", tool_name, exc)

        pre_issues = _raw_to_issues(pre_issues_raw)

        logger.info(
            "Pre-analysis complete | upload=%s pre_issues=%d trace=%s",
            request.upload_id, len(pre_issues), trace_id,
        )

        # ── 2. Gemini enrichment (auto-instrumented as LLM span) ───────────────
        prompt = _build_prompt(rows, pre_issues, request.additional_context)
        raw = self.gemini.generate(prompt, trace_id=trace_id)
        gemini_result = _parse_gemini_response(raw, trace_id)

        # ── 3. Merge & persist ─────────────────────────────────────────────────
        merged_issues = _merge_issues(pre_issues, gemini_result.get("issues", []))
        risk_level = RiskLevel(gemini_result.get("risk_level", _infer_risk_level(pre_issues)))
        risk_score = float(gemini_result.get("risk_score", _infer_risk_score(pre_issues)))
        recommendations = [
            ComplianceRecommendation(**r) for r in gemini_result.get("recommendations", [])
        ]
        explanation = gemini_result.get("explanation", "Analysis complete.")

        result = ComplianceAnalysisResult(
            risk_level=risk_level,
            risk_score=round(risk_score, 1),
            issues=merged_issues,
            recommendations=recommendations,
            explanation=explanation,
            trace_id=trace_id,
            upload_id=request.upload_id,
            session_id=request.session_id,
        )

        await self.db.compliance_analyses.insert_one({
            **result.model_dump(),
            "created_at": datetime.now(timezone.utc),
        })

        logger.info(
            "Compliance analysis stored | upload=%s risk=%s score=%.1f issues=%d trace=%s",
            request.upload_id, risk_level, risk_score, len(merged_issues), trace_id,
        )

        return result


# ── Helpers ────────────────────────────────────────────────────────────────────

def _raw_to_issues(raw_list: list[dict]) -> list[ComplianceIssue]:
    issues = []
    for raw in raw_list:
        try:
            issues.append(ComplianceIssue(**raw))
        except Exception:
            pass
    return issues


def _build_prompt(
    rows: list[dict[str, Any]],
    pre_issues: list[ComplianceIssue],
    additional_context: str,
    max_rows: int = 80,
) -> str:
    sample = rows[:max_rows]
    lines = [f"TRANSACTION DATA ({len(rows)} total rows, showing first {len(sample)}):", ""]
    for i, row in enumerate(sample):
        lines.append(f"  Row {i}: " + " | ".join(f"{k}={v}" for k, v in row.items()))

    lines += ["", "PRE-DETECTED ISSUES (from automated rules):"]
    if pre_issues:
        for issue in pre_issues:
            lines.append(
                f"  [{issue.severity.upper()}] {issue.category}: {issue.description}"
                + (f" (rows: {issue.row_indices[:5]})" if issue.row_indices else "")
            )
    else:
        lines.append("  None detected by automated rules.")

    if additional_context:
        lines += ["", f"ADDITIONAL CONTEXT: {additional_context}"]

    return "\n".join(lines)


def _parse_gemini_response(raw: str, trace_id: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON | trace=%s — using fallback", trace_id)
        return {
            "risk_level": "medium",
            "risk_score": 50.0,
            "issues": [],
            "recommendations": [],
            "explanation": raw,
        }


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
    severity_order = {IssueSeverity.CRITICAL: 0, IssueSeverity.HIGH: 1,
                      IssueSeverity.MEDIUM: 2, IssueSeverity.LOW: 3}
    merged.sort(key=lambda i: severity_order.get(i.severity, 99))
    return merged


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
