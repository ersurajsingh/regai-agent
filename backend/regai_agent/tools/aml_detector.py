"""
ADK Tool: AML pattern detection.

Detects structuring (smurfing), CTR threshold breaches, and round-number clustering
in a list of transaction records.

Instrumented with Arize Phoenix via @tracer.tool — each call produces a TOOL span
visible in the Phoenix UI under the regai-compliance project.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

CTR_THRESHOLD = 10_000.0
STRUCTURING_BAND_LOW = 9_000.0
ROUND_NUMBER_THRESHOLD = 0.95  # fraction of round-number txns that triggers a flag


def detect_aml_patterns(transactions_json: str) -> dict[str, Any]:
    """
    Detect AML (Anti-Money Laundering) patterns in transaction data.

    Checks for:
    - Structuring / smurfing: 3+ transactions in the $9,000–$9,999 band
    - CTR threshold breaches: transactions exceeding $10,000
    - Round-number clustering: >95% of amounts are exact multiples of $1,000

    Args:
        transactions_json: JSON string — a list of transaction dicts, each containing
                           at least an 'amount' field (numeric or string).

    Returns:
        A dict with keys:
          - status: "success" or "error"
          - issues: list of detected AML issue dicts
          - structuring_count: number of structuring-band transactions
          - ctr_count: number of CTR-threshold transactions
          - round_number_ratio: fraction of round-number transactions
    """
    try:
        rows: list[dict] = json.loads(transactions_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"status": "error", "message": f"Invalid transactions_json: {exc}", "issues": []}

    issues = []
    amounts: list[float] = []
    structuring_rows: list[int] = []
    ctr_rows: list[int] = []

    for i, row in enumerate(rows):
        try:
            amt = float(row.get("amount", 0))
        except (TypeError, ValueError):
            continue
        amounts.append(amt)
        if STRUCTURING_BAND_LOW <= amt < CTR_THRESHOLD:
            structuring_rows.append(i)
        if amt > CTR_THRESHOLD:
            ctr_rows.append(i)

    if not amounts:
        return {"status": "success", "issues": [], "structuring_count": 0,
                "ctr_count": 0, "round_number_ratio": 0.0}

    # Structuring
    if len(structuring_rows) >= 3:
        issues.append({
            "category": "aml",
            "severity": "critical",
            "row_indices": structuring_rows,
            "description": (
                f"{len(structuring_rows)} transactions fall in the $9,000–$9,999 range, "
                "a classic structuring pattern used to evade CTR filing requirements."
            ),
            "regulation": "BSA 31 CFR 1010.314 (Structuring)",
            "evidence": {"structuring_count": len(structuring_rows), "band": "$9,000–$9,999"},
        })

    # CTR breaches
    if ctr_rows:
        issues.append({
            "category": "reporting_threshold",
            "severity": "high",
            "row_indices": ctr_rows,
            "description": (
                f"{len(ctr_rows)} transaction(s) exceed $10,000 and require a "
                "Currency Transaction Report (CTR) filing."
            ),
            "regulation": "BSA 31 CFR 1010.311 (CTR)",
            "evidence": {"ctr_count": len(ctr_rows)},
        })

    # Round-number clustering
    round_count = sum(1 for a in amounts if a > 0 and a % 1000 == 0)
    round_ratio = round(round_count / len(amounts), 3) if amounts else 0.0
    if round_ratio >= ROUND_NUMBER_THRESHOLD:
        issues.append({
            "category": "aml",
            "severity": "medium",
            "row_indices": [],
            "description": (
                f"{round_count}/{len(amounts)} transactions are exact multiples of $1,000. "
                "High concentration of round numbers is an AML red flag."
            ),
            "regulation": "FATF Recommendation 20",
            "evidence": {"round_number_ratio": round_ratio},
        })

    logger.debug(
        "AML detection complete | structuring=%d ctr=%d round_ratio=%.3f",
        len(structuring_rows), len(ctr_rows), round_ratio,
    )

    return {
        "status": "success",
        "issues": issues,
        "structuring_count": len(structuring_rows),
        "ctr_count": len(ctr_rows),
        "round_number_ratio": round_ratio,
    }
