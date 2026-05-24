"""
ADK Tool: Duplicate invoice detection.

Detects exact duplicate transaction IDs and near-duplicate (same vendor + amount) pairs.
"""

import json
from collections import defaultdict
from typing import Any


def detect_duplicate_invoices(transactions_json: str) -> dict[str, Any]:
    """
    Detect duplicate invoices in transaction data.

    Checks for:
    - Exact duplicate transaction_id values across rows
    - Near-duplicate pairs: same vendor + same amount (potential double-payments)

    Args:
        transactions_json: JSON string — a list of transaction dicts, each containing
                           'transaction_id', 'vendor', and 'amount' fields.

    Returns:
        A dict with keys:
          - status: "success" or "error"
          - issues: list of detected duplicate issue dicts
          - exact_duplicate_count: number of rows with duplicate transaction IDs
          - near_duplicate_count: number of rows with matching vendor+amount pairs
    """
    try:
        rows: list[dict] = json.loads(transactions_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"status": "error", "message": f"Invalid transactions_json: {exc}", "issues": []}

    issues = []

    # ── Exact duplicate transaction_id ─────────────────────────────────────────
    id_index: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        tid = str(row.get("transaction_id", "")).strip()
        if tid:
            id_index[tid].append(i)

    dup_rows = sorted({idx for indices in id_index.values() if len(indices) > 1 for idx in indices})
    dup_ids = [k for k, v in id_index.items() if len(v) > 1]

    if dup_rows:
        issues.append({
            "category": "duplicate_invoice",
            "severity": "high",
            "row_indices": dup_rows,
            "description": (
                f"{len(dup_rows)} rows share duplicate transaction IDs. "
                "Duplicate invoices may indicate double-billing or payment fraud."
            ),
            "regulation": "GAAP / Internal Controls",
            "evidence": {"duplicate_ids": dup_ids[:10]},
        })

    # ── Near-duplicate: same vendor + same amount ──────────────────────────────
    pair_index: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        vendor = str(row.get("vendor", "")).strip().lower()
        try:
            amount = round(float(row.get("amount", 0)), 2)
        except (TypeError, ValueError):
            continue
        if vendor:
            pair_index[(vendor, amount)].append(i)

    near_dup_rows = sorted({
        idx for indices in pair_index.values() if len(indices) > 1 for idx in indices
    })
    near_dup_pair_count = sum(1 for v in pair_index.values() if len(v) > 1)

    if near_dup_rows:
        issues.append({
            "category": "duplicate_invoice",
            "severity": "medium",
            "row_indices": near_dup_rows,
            "description": (
                f"{len(near_dup_rows)} rows have identical vendor + amount combinations. "
                "These may represent duplicate payments or split transactions."
            ),
            "regulation": "GAAP / Internal Controls",
            "evidence": {"affected_pairs": near_dup_pair_count},
        })

    return {
        "status": "success",
        "issues": issues,
        "exact_duplicate_count": len(dup_rows),
        "near_duplicate_count": len(near_dup_rows),
    }
