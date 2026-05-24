"""
Deterministic rule engine — ground-truth baseline for evaluation.

Runs the four ADK detector tools and produces a canonical set of
issue category+severity pairs. This is the "reference answer" that
the LLM output is compared against during evaluation.

No LLM calls are made here — results are fully deterministic.
"""

import json
import logging
from typing import Any

from regai_agent.tools.aml_detector import detect_aml_patterns
from regai_agent.tools.duplicate_detector import detect_duplicate_invoices
from regai_agent.tools.kyc_validator import detect_missing_kyc
from regai_agent.tools.suspicious_activity_detector import detect_suspicious_activity

logger = logging.getLogger(__name__)


class RuleEngineResult:
    """Canonical findings from the deterministic rule engine."""

    def __init__(self, issues: list[dict[str, Any]]) -> None:
        self.issues = issues
        # Normalised fingerprints: "category:severity" strings for set comparison
        self.fingerprints: set[str] = {
            f"{i.get('category', 'other')}:{i.get('severity', 'low')}"
            for i in issues
        }
        # Category-level set for coarser matching
        self.categories: set[str] = {i.get("category", "other") for i in issues}

    def __len__(self) -> int:
        return len(self.issues)


def run_rule_engine(rows: list[dict[str, Any]]) -> RuleEngineResult:
    """
    Run all four deterministic detectors against the transaction rows.

    Args:
        rows: typed transaction rows (list of dicts)

    Returns:
        RuleEngineResult with all detected issues and normalised fingerprints
    """
    rows_json = json.dumps(rows)
    all_issues: list[dict] = []

    for detector_fn, name in [
        (detect_missing_kyc,         "kyc"),
        (detect_duplicate_invoices,  "duplicates"),
        (detect_aml_patterns,        "aml"),
        (detect_suspicious_activity, "suspicious"),
    ]:
        try:
            result = detector_fn(rows_json)
            issues = result.get("issues", [])
            all_issues.extend(issues)
            logger.debug("Rule engine %s: %d issues", name, len(issues))
        except Exception as exc:
            logger.warning("Rule engine detector '%s' failed: %s", name, exc)

    logger.info("Rule engine complete: %d total issues", len(all_issues))
    return RuleEngineResult(all_issues)
