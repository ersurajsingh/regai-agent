"""
Trace memory service — retrieves historical compliance decisions from MongoDB.

This is the runtime introspection layer. It queries the same collections that
Phoenix traces are derived from, giving the agent access to:
  - Prior compliance analyses (decisions + risk scores)
  - Evaluation scores (quality metrics per analysis)
  - Reflection history (false positives, critique summaries)

Phoenix MCP is the IDE/CLI introspection tool; this service is the runtime
equivalent that the agent calls during inference.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# How many prior analyses to load as context
_DEFAULT_HISTORY_LIMIT = 5


@dataclass
class PriorAnalysis:
    trace_id: str | None
    upload_id: str
    risk_level: str
    risk_score: float
    issue_categories: list[str]
    explanation: str
    overall_eval_score: float | None        # from evaluations collection
    eval_label: str | None
    hallucination_risk_score: float | None
    reasoning_quality_score: float | None
    false_positive_count: int               # from reflection_history
    critique_summary: str


@dataclass
class TraceMemory:
    """Aggregated historical context for a session."""

    session_id: str
    prior_analyses: list[PriorAnalysis] = field(default_factory=list)

    # Derived patterns (computed by trace_memory service)
    repeated_mistake_categories: list[str] = field(default_factory=list)
    avg_eval_score: float | None = None
    avg_hallucination_score: float | None = None
    trend: str = "insufficient_data"   # "improving" | "degrading" | "stable" | "insufficient_data"


async def load_trace_memory(
    db,
    session_id: str,
    upload_id: str,
    limit: int = _DEFAULT_HISTORY_LIMIT,
) -> TraceMemory:
    """
    Load historical compliance decisions and their evaluation scores for a session.

    Joins:
      compliance_analyses  → prior decisions
      evaluations          → quality scores per analysis
      reflection_history   → false positive counts and critique summaries
    """
    memory = TraceMemory(session_id=session_id)

    # Fetch prior analyses for this session (excluding the current upload)
    cursor = db.compliance_analyses.find(
        {"session_id": session_id},
        {"_id": 0},
        sort=[("created_at", -1)],
        limit=limit,
    )
    analyses: list[dict[str, Any]] = await cursor.to_list(length=limit)

    if not analyses:
        logger.debug("No prior analyses found for session=%s", session_id)
        return memory

    # Build a lookup of evaluations keyed by trace_id
    trace_ids = [a.get("trace_id") for a in analyses if a.get("trace_id")]
    eval_cursor = db.evaluations.find(
        {"session_id": session_id, "analysis_trace_id": {"$in": trace_ids}},
        {"_id": 0, "analysis_trace_id": 1, "overall_score": 1, "overall_label": 1,
         "hallucination_risk": 1, "reasoning_quality": 1},
    )
    evals_raw: list[dict] = await eval_cursor.to_list(length=limit * 2)
    eval_by_trace: dict[str, dict] = {e["analysis_trace_id"]: e for e in evals_raw}

    # Build a lookup of reflection history keyed by upload_id
    upload_ids = [a.get("upload_id") for a in analyses if a.get("upload_id")]
    refl_cursor = db.reflection_history.find(
        {"session_id": session_id, "upload_id": {"$in": upload_ids}},
        {"_id": 0, "upload_id": 1, "false_positive_count": 1, "critique_count": 1},
        sort=[("created_at", -1)],
    )
    reflections_raw: list[dict] = await refl_cursor.to_list(length=limit * 2)
    # Keep only the most recent reflection per upload
    refl_by_upload: dict[str, dict] = {}
    for r in reflections_raw:
        uid = r.get("upload_id", "")
        if uid not in refl_by_upload:
            refl_by_upload[uid] = r

    # Assemble PriorAnalysis objects
    for a in analyses:
        tid = a.get("trace_id")
        uid = a.get("upload_id", "")
        ev = eval_by_trace.get(tid or "", {})
        rf = refl_by_upload.get(uid, {})

        issue_categories = list({
            i.get("category", "other")
            for i in a.get("issues", [])
        })

        memory.prior_analyses.append(PriorAnalysis(
            trace_id=tid,
            upload_id=uid,
            risk_level=a.get("risk_level", "unknown"),
            risk_score=float(a.get("risk_score", 0.0)),
            issue_categories=issue_categories,
            explanation=a.get("explanation", ""),
            overall_eval_score=ev.get("overall_score"),
            eval_label=ev.get("overall_label"),
            hallucination_risk_score=ev.get("hallucination_risk", {}).get("score"),
            reasoning_quality_score=ev.get("reasoning_quality", {}).get("score"),
            false_positive_count=rf.get("false_positive_count", 0),
            critique_summary="",  # lightweight — full critique in reflection_results
        ))

    # ── Derive patterns ────────────────────────────────────────────────────────
    memory.repeated_mistake_categories = _find_repeated_mistakes(memory.prior_analyses)
    memory.avg_eval_score = _avg([p.overall_eval_score for p in memory.prior_analyses])
    memory.avg_hallucination_score = _avg(
        [p.hallucination_risk_score for p in memory.prior_analyses]
    )
    memory.trend = _compute_trend(memory.prior_analyses)

    logger.info(
        "Trace memory loaded | session=%s analyses=%d repeated_mistakes=%s trend=%s",
        session_id, len(memory.prior_analyses),
        memory.repeated_mistake_categories, memory.trend,
    )

    return memory


def _find_repeated_mistakes(analyses: list[PriorAnalysis]) -> list[str]:
    """
    Identify issue categories that were flagged as false positives
    in multiple prior analyses — these are systematic mistakes.
    """
    if len(analyses) < 2:
        return []

    # Categories with high false-positive counts across analyses
    fp_heavy = [
        cat
        for p in analyses
        if p.false_positive_count >= 2
        for cat in p.issue_categories
    ]
    # Return categories that appear in ≥2 analyses with FP issues
    from collections import Counter
    counts = Counter(fp_heavy)
    return [cat for cat, n in counts.items() if n >= 2]


def _avg(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 3) if valid else None


def _compute_trend(analyses: list[PriorAnalysis]) -> str:
    scores = [p.overall_eval_score for p in analyses if p.overall_eval_score is not None]
    if len(scores) < 3:
        return "insufficient_data"
    # Compare first half vs second half (oldest → newest, list is newest-first)
    scores_asc = list(reversed(scores))
    mid = len(scores_asc) // 2
    older_avg = sum(scores_asc[:mid]) / mid
    newer_avg = sum(scores_asc[mid:]) / (len(scores_asc) - mid)
    delta = newer_avg - older_avg
    if delta > 0.05:
        return "improving"
    if delta < -0.05:
        return "degrading"
    return "stable"
