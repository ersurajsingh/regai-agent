"""
ADK Tool: KYC (Know Your Customer) validation.

Flags transactions where the customer's KYC status is not 'verified'.
"""

import json
from typing import Any

VALID_KYC_STATUS = "verified"


def detect_missing_kyc(transactions_json: str) -> dict[str, Any]:
    """
    Identify transactions with missing or incomplete KYC verification.

    Flags any row where kyc_status is not 'verified'. Unverified customers
    must not be processed under FATF Recommendation 10 and BSA CIP rules.

    Args:
        transactions_json: JSON string — a list of transaction dicts, each containing
                           at least 'kyc_status' and optionally 'customer_name'.

    Returns:
        A dict with keys:
          - status: "success" or "error"
          - issues: list of detected KYC issue dicts (empty if all verified)
          - non_verified_count: number of rows with non-verified KYC
          - kyc_breakdown: dict mapping each kyc_status value to its row count
    """
    try:
        rows: list[dict] = json.loads(transactions_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"status": "error", "message": f"Invalid transactions_json: {exc}", "issues": []}

    non_verified: list[int] = []
    kyc_breakdown: dict[str, int] = {}

    for i, row in enumerate(rows):
        status = str(row.get("kyc_status", "unknown")).strip().lower()
        kyc_breakdown[status] = kyc_breakdown.get(status, 0) + 1
        if status != VALID_KYC_STATUS:
            non_verified.append(i)

    issues = []
    if non_verified:
        issues.append({
            "category": "missing_kyc",
            "severity": "high",
            "row_indices": non_verified,
            "description": (
                f"{len(non_verified)} transaction(s) involve customers whose KYC is not verified. "
                "Unverified customers must not be processed under FATF Recommendation 10."
            ),
            "regulation": "FATF Recommendation 10 / BSA CIP Rule (31 CFR 1020.220)",
            "evidence": {
                "affected_rows": len(non_verified),
                "kyc_breakdown": kyc_breakdown,
            },
        })

    return {
        "status": "success",
        "issues": issues,
        "non_verified_count": len(non_verified),
        "kyc_breakdown": kyc_breakdown,
    }
