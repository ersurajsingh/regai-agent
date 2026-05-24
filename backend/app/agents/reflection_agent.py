"""
Self-Reflection Agent for RegAI.

Workflow
--------
1. FETCH    — load the prior compliance analysis from MongoDB
2. CRITIQUE — Gemini critiques the original output for false positives
              and weak reasoning (CHAIN span: reflection_critique)
3. IMPROVE  — Gemini re-runs analysis with critique context injected
              (CHAIN span: reflection_improvement)
4. DIFF     — compute structured delta between original and improved outputs
5. PERSIST  — store full ReflectionResult + lightweight history entry in MongoDB

Phoenix tracing
---------------
Each reflection cycle produces:
  reflection_workflow  [CHAIN]  — outer span for the full cycle
    reflection_critique  [CHAIN]  — critique phase
    reflection_improvement [CHAIN] — improvement phase

All spans are scoped to the session via using_session().
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
    RiskLevel,
)
from app.schemas.reflection import (
    FalsePositiveAssessment,
    ImprovementDelta,
    ReasoningCritique,
    ReflectionRequest,
    ReflectionResult,
)
from app.services.gemini_service import GeminiService
from phoenix.otel import using_session

logger = logging.getLogger(__name__)
_otel_tracer = otel_trace.get_tracer("regai.reflection_agent")

# ── System prompts ─────────────────────────────────────────────────────────────

_CRITIQUE_PROMPT = """You are a senior compliance auditor reviewing an AI-generated compliance analysis.

Your task is to critically evaluate the analysis for:
1. FALSE POSITIVES — issues that are likely incorrect or over-flagged
2. WEAK REASONING — conclusions that lack sufficient evidence or context
3. CALIBRATION ERRORS — risk scores that seem too high or too low
4. MISSING CONTEXT — important factors the original analysis overlooked

Respond ONLY with valid JSON:
{
  "false_positive_assessments": [
    {
      "issue_index": <int>,
      "original_description": "<string>",
      "verdict": "<confirmed|likely_false_positive|uncertain>",
      "reasoning": "<string>",
      "confidence": <float 0-1>
    }
  ],
  "reasoning_critiques": [
    {
      "aspect": "<string>",
      "critique": "<string>",
      "severity": "<minor|moderate|significant>"
    }
  ],
  "critique_summary": "<2-3 sentence overall assessment>"
}"""

_IMPROVEMENT_PROMPT = """You are RegAI, a senior financial compliance officer.

You are re-analysing a set of transactions. You have been given:
1. The original compliance analysis
2. A critique identifying false positives and weak reasoning
3. The original transaction data

Your task: produce an IMPROVED compliance analysis that:
- Removes or downgrades confirmed false positives
- Strengthens reasoning where the critique identified weaknesses
- Recalibrates the risk score based on the critique
- Adds any issues the original analysis missed

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
  "explanation": "<string>"
}"""


class ReflectionAgent:
    """
    Self-reflection agent that critiques and improves prior compliance analyses.
    """

    def __init__(self, db) -> None:
        self.db = db
        self._critique_gemini = GeminiService(system_instruction=_CRITIQUE_PROMPT)
        self._improve_gemini = GeminiService(system_instruction=_IMPROVEMENT_PROMPT)

    async def run(self, request: ReflectionRequest) -> ReflectionResult:
        reflection_id = str(uuid.uuid4())
        reflection_trace_id = str(uuid.uuid4())

        with using_session(session_id=request.session_id):
            with _otel_tracer.start_as_current_span(
                "reflection_workflow",
                attributes={
                    "openinference.span.kind": "CHAIN",
                    "regai.reflection_id": reflection_id,
                    "regai.upload_id": request.upload_id,
                    "regai.session_id": request.session_id,
                },
            ) as outer_span:
                try:
                    result = await self._run_reflection(
                        request, reflection_id, reflection_trace_id
                    )
                    outer_span.set_attribute("regai.false_positive_count",
                                             len(result.false_positive_assessments))
                    outer_span.set_attribute("regai.risk_score_delta", result.delta.risk_score_delta)
                    outer_span.set_attribute("regai.improved_risk_level",
                                             result.improved_risk_level.value)
                    outer_span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    outer_span.record_exception(exc)
                    outer_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

    async def _run_reflection(
        self,
        request: ReflectionRequest,
        reflection_id: str,
        reflection_trace_id: str,
    ) -> ReflectionResult:

        # ── 1. Fetch prior analysis ────────────────────────────────────────────
        prior = await self._fetch_prior_analysis(request)
        if not prior:
            raise ValueError(
                f"No prior compliance analysis found for upload '{request.upload_id}'."
            )

        upload = await self.db.transaction_uploads.find_one(
            {"upload_id": request.upload_id, "session_id": request.session_id}
        )
        rows: list[dict[str, Any]] = (upload or {}).get("typed_rows") or []

        original_issues: list[dict] = prior.get("issues", [])
        original_risk_level = prior.get("risk_level", "medium")
        original_risk_score = float(prior.get("risk_score", 50.0))
        original_trace_id = prior.get("trace_id")

        logger.info(
            "Reflection started | upload=%s prior_trace=%s issues=%d",
            request.upload_id, original_trace_id, len(original_issues),
        )

        # ── 2. Critique phase ──────────────────────────────────────────────────
        critique_result = await self._run_critique(
            original_issues, original_risk_level, original_risk_score,
            rows, request.reflection_context, reflection_trace_id,
        )

        # ── 3. Improvement phase ───────────────────────────────────────────────
        improved = await self._run_improvement(
            prior, critique_result, rows, reflection_trace_id,
        )

        # ── 4. Compute delta ───────────────────────────────────────────────────
        improved_issues = _raw_to_issues(improved.get("issues", []))
        improved_risk_level = RiskLevel(improved.get("risk_level", original_risk_level))
        improved_risk_score = float(improved.get("risk_score", original_risk_score))

        delta = _compute_delta(
            original_issues, original_risk_level, original_risk_score,
            improved_issues, improved_risk_level, improved_risk_score,
            prior.get("recommendations", []), improved.get("recommendations", []),
        )

        # ── 5. Build result ────────────────────────────────────────────────────
        false_positives = [
            FalsePositiveAssessment(**fp)
            for fp in critique_result.get("false_positive_assessments", [])
        ]
        critiques = [
            ReasoningCritique(**c)
            for c in critique_result.get("reasoning_critiques", [])
        ]

        result = ReflectionResult(
            reflection_id=reflection_id,
            session_id=request.session_id,
            upload_id=request.upload_id,
            original_trace_id=original_trace_id,
            false_positive_assessments=false_positives,
            reasoning_critiques=critiques,
            critique_summary=critique_result.get("critique_summary", ""),
            improved_risk_level=improved_risk_level,
            improved_risk_score=round(improved_risk_score, 1),
            improved_issues=improved_issues,
            improved_recommendations=[
                ComplianceRecommendation(**r)
                for r in improved.get("recommendations", [])
            ],
            improved_explanation=improved.get("explanation", ""),
            delta=delta,
            reflection_trace_id=reflection_trace_id,
        )

        # ── 6. Persist ─────────────────────────────────────────────────────────
        await self._persist(result)

        logger.info(
            "Reflection complete | upload=%s reflection=%s fp=%d delta=%.1f",
            request.upload_id, reflection_id,
            len(false_positives), delta.risk_score_delta,
        )

        return result

    async def _fetch_prior_analysis(self, request: ReflectionRequest) -> dict | None:
        query: dict[str, Any] = {
            "upload_id": request.upload_id,
            "session_id": request.session_id,
        }
        if request.analysis_trace_id:
            query["trace_id"] = request.analysis_trace_id

        return await self.db.compliance_analyses.find_one(
            query,
            sort=[("created_at", -1)],  # most recent if no trace_id specified
        )

    async def _run_critique(
        self,
        original_issues: list[dict],
        original_risk_level: str,
        original_risk_score: float,
        rows: list[dict],
        reflection_context: str,
        trace_id: str,
    ) -> dict:
        with _otel_tracer.start_as_current_span(
            "reflection_critique",
            attributes={
                "openinference.span.kind": "CHAIN",
                "regai.phase": "critique",
                "regai.original_issue_count": len(original_issues),
            },
        ) as span:
            prompt = _build_critique_prompt(
                original_issues, original_risk_level, original_risk_score,
                rows, reflection_context,
            )
            raw = self._critique_gemini.generate(prompt, trace_id=f"{trace_id}-critique")
            result = _parse_json(raw, trace_id, phase="critique")
            span.set_attribute("regai.false_positive_count",
                               len(result.get("false_positive_assessments", [])))
            span.set_status(Status(StatusCode.OK))
            return result

    async def _run_improvement(
        self,
        prior: dict,
        critique: dict,
        rows: list[dict],
        trace_id: str,
    ) -> dict:
        with _otel_tracer.start_as_current_span(
            "reflection_improvement",
            attributes={
                "openinference.span.kind": "CHAIN",
                "regai.phase": "improvement",
            },
        ) as span:
            prompt = _build_improvement_prompt(prior, critique, rows)
            raw = self._improve_gemini.generate(prompt, trace_id=f"{trace_id}-improve")
            result = _parse_json(raw, trace_id, phase="improvement")
            span.set_attribute("regai.improved_risk_level",
                               result.get("risk_level", "unknown"))
            span.set_status(Status(StatusCode.OK))
            return result

    async def _persist(self, result: ReflectionResult) -> None:
        doc = result.model_dump()
        doc["created_at"] = datetime.now(timezone.utc)
        await self.db.reflection_results.insert_one(doc)

        # Lightweight history entry for quick queries
        await self.db.reflection_history.insert_one({
            "reflection_id": result.reflection_id,
            "session_id": result.session_id,
            "upload_id": result.upload_id,
            "original_trace_id": result.original_trace_id,
            "original_risk_level": result.delta.original_risk_level,
            "improved_risk_level": result.improved_risk_level.value,
            "risk_score_delta": result.delta.risk_score_delta,
            "false_positive_count": len(result.false_positive_assessments),
            "critique_count": len(result.reasoning_critiques),
            "created_at": datetime.now(timezone.utc),
        })


# ── Prompt builders ────────────────────────────────────────────────────────────

def _build_critique_prompt(
    issues: list[dict],
    risk_level: str,
    risk_score: float,
    rows: list[dict],
    reflection_context: str,
    max_rows: int = 50,
) -> str:
    lines = [
        "ORIGINAL COMPLIANCE ANALYSIS:",
        f"  risk_level: {risk_level}",
        f"  risk_score: {risk_score}",
        "",
        "ORIGINAL ISSUES:",
    ]
    for i, issue in enumerate(issues):
        lines.append(
            f"  [{i}] [{issue.get('severity','?').upper()}] "
            f"{issue.get('category','?')}: {issue.get('description','')}"
        )

    sample = rows[:max_rows]
    lines += ["", f"TRANSACTION SAMPLE ({len(rows)} total, showing {len(sample)}):"]
    for i, row in enumerate(sample):
        lines.append(f"  Row {i}: " + " | ".join(f"{k}={v}" for k, v in row.items()))

    if reflection_context:
        lines += ["", f"HUMAN FEEDBACK: {reflection_context}"]

    return "\n".join(lines)


def _build_improvement_prompt(
    prior: dict,
    critique: dict,
    rows: list[dict],
    max_rows: int = 50,
) -> str:
    sample = rows[:max_rows]
    lines = [
        "ORIGINAL ANALYSIS:",
        f"  risk_level: {prior.get('risk_level')}",
        f"  risk_score: {prior.get('risk_score')}",
        f"  explanation: {prior.get('explanation', '')}",
        "",
        "CRITIQUE FINDINGS:",
        f"  {critique.get('critique_summary', '')}",
        "",
        "FALSE POSITIVE ASSESSMENTS:",
    ]
    for fp in critique.get("false_positive_assessments", []):
        lines.append(
            f"  Issue #{fp.get('issue_index')}: {fp.get('verdict')} "
            f"(confidence={fp.get('confidence', 0):.2f}) — {fp.get('reasoning', '')}"
        )

    lines += ["", "REASONING CRITIQUES:"]
    for c in critique.get("reasoning_critiques", []):
        lines.append(f"  [{c.get('severity','?').upper()}] {c.get('aspect')}: {c.get('critique')}")

    lines += ["", f"TRANSACTION DATA ({len(rows)} total, showing {len(sample)}):"]
    for i, row in enumerate(sample):
        lines.append(f"  Row {i}: " + " | ".join(f"{k}={v}" for k, v in row.items()))

    return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_json(raw: str, trace_id: str, phase: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Gemini non-JSON in %s phase | trace=%s", phase, trace_id)
        return {}


def _raw_to_issues(raw_list: list[dict]) -> list[ComplianceIssue]:
    issues = []
    for raw in raw_list:
        try:
            issues.append(ComplianceIssue(**raw))
        except Exception:
            pass
    return issues


def _compute_delta(
    original_issues: list[dict],
    original_risk_level: str,
    original_risk_score: float,
    improved_issues: list[ComplianceIssue],
    improved_risk_level: RiskLevel,
    improved_risk_score: float,
    original_recs: list[dict],
    improved_recs: list[dict],
) -> ImprovementDelta:
    original_descriptions = {i.get("description", "") for i in original_issues}
    improved_descriptions = {i.description for i in improved_issues}

    added = [i for i in improved_issues if i.description not in original_descriptions]
    removed_indices = [
        idx for idx, issue in enumerate(original_issues)
        if issue.get("description", "") not in improved_descriptions
    ]

    original_rec_actions = {r.get("action", "") for r in original_recs}
    improved_rec_actions = {r.get("action", "") for r in improved_recs}

    return ImprovementDelta(
        risk_level_changed=(original_risk_level != improved_risk_level.value),
        original_risk_level=original_risk_level,
        improved_risk_level=improved_risk_level.value,
        risk_score_delta=round(improved_risk_score - original_risk_score, 1),
        issues_added=added,
        issues_removed_indices=removed_indices,
        recommendations_changed=(original_rec_actions != improved_rec_actions),
    )
