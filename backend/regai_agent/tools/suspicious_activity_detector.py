"""
ADK Tool: Suspicious activity detection.

Detects high-velocity vendor patterns (same vendor appearing multiple times
in a short consecutive window), which may indicate layering or fictitious invoicing.
"""

import json
from collections import Counter
from typing import Any

VELOCITY_WINDOW_SIZE = 5   # sliding window width (rows)
VELOCITY_MIN_COUNT = 3     # minimum occurrences within window to flag


def detect_suspicious_activity(transactions_json: str) -> dict[str, Any]:
    """
    Detect suspicious transaction patterns using velocity analysis.

    Applies a sliding window over the transaction sequence to identify vendors
    that appear 3 or more times within any 5-row window. This pattern may
    indicate layering, fictitious invoicing, or coordinated fraud.

    Args:
        transactions_json: JSON string — a list of transaction dicts, each containing
                           at least a 'vendor' field.

    Returns:
        A dict with keys:
          - status: "success" or "error"
          - issues: list of detected suspicious activity issue dicts
          - flagged_row_count: number of rows involved in velocity spikes
          - top_vendors: list of vendor names with the highest velocity counts
    """
    try:
        rows: list[dict] = json.loads(transactions_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"status": "error", "message": f"Invalid transactions_json: {exc}", "issues": []}

    vendor_sequence: list[tuple[str, int]] = []
    for i, row in enumerate(rows):
        vendor = str(row.get("vendor", "")).strip().lower()
        if vendor:
            vendor_sequence.append((vendor, i))

    flagged: set[int] = set()
    flagged_vendors: Counter = Counter()

    for start in range(len(vendor_sequence)):
        window = vendor_sequence[start: start + VELOCITY_WINDOW_SIZE]
        counts = Counter(v for v, _ in window)
        for vendor, count in counts.items():
            if count >= VELOCITY_MIN_COUNT:
                for v, idx in window:
                    if v == vendor:
                        flagged.add(idx)
                        flagged_vendors[vendor] += 1

    issues = []
    if flagged:
        top_vendors = [v for v, _ in flagged_vendors.most_common(5)]
        issues.append({
            "category": "suspicious_activity",
            "severity": "medium",
            "row_indices": sorted(flagged),
            "description": (
                f"{len(flagged)} transactions show high-velocity activity with the same vendor "
                "in a short sequence, which may indicate layering or fictitious invoicing."
            ),
            "regulation": "FATF Recommendation 20 (Suspicious Transaction Reporting)",
            "evidence": {
                "velocity_rows": len(flagged),
                "top_vendors": top_vendors,
            },
        })

    return {
        "status": "success",
        "issues": issues,
        "flagged_row_count": len(flagged),
        "top_vendors": [v for v, _ in flagged_vendors.most_common(5)],
    }
