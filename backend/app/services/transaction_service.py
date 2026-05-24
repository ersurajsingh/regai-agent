"""
Transaction pipeline service.
- Parses and validates CSV uploads with pandas
- Stores typed transaction documents in MongoDB
- Computes a data summary on upload
- Runs Gemini compliance analysis on demand
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.transaction import (
    ComplianceAnalysisResponse,
    ComplianceFlag,
    TransactionSummary,
    TransactionUploadResponse,
)
from app.services.gemini_service import GeminiService
from app.utils.csv_parser import ParsedCSV

logger = logging.getLogger(__name__)

_COMPLIANCE_SYSTEM_PROMPT = """You are RegAI, an expert financial compliance analyst.
Given a set of transaction records, identify potential compliance issues such as:
- AML (Anti-Money Laundering) red flags
- Unusual transaction patterns or amounts
- Missing required fields (e.g. counterparty, purpose)
- Sanctions screening concerns
- Regulatory reporting thresholds (e.g. CTR > $10,000)

Respond ONLY with valid JSON in this exact structure:
{
  "summary": "<one paragraph summary of findings>",
  "flags": [
    {
      "row_index": <int>,
      "issue": "<description>",
      "severity": "<high|medium|low>",
      "regulation": "<regulation name or null>"
    }
  ]
}"""

CTR_THRESHOLD = 10_000.0


class TransactionService:
    def __init__(self, db) -> None:
        self.db = db
        self.gemini = GeminiService(system_instruction=_COMPLIANCE_SYSTEM_PROMPT)

    # ── Upload ─────────────────────────────────────────────────────────────────

    async def store_upload(
        self,
        session_id: str,
        filename: str,
        parsed: ParsedCSV,
    ) -> TransactionUploadResponse:
        upload_id = str(uuid.uuid4())
        summary = _compute_summary(parsed.typed_rows)

        await self.db.transaction_uploads.insert_one({
            "upload_id": upload_id,
            "session_id": session_id,
            "filename": filename,
            "columns": parsed.columns,
            "rows": parsed.rows,           # raw strings — safe for re-display
            "typed_rows": parsed.typed_rows,
            "row_count": parsed.row_count,
            "summary": summary.model_dump(),
            "warnings": parsed.warnings,
            "uploaded_at": datetime.now(timezone.utc),
        })

        logger.info(
            "Transaction upload stored | session=%s upload=%s rows=%d warnings=%d",
            session_id, upload_id, parsed.row_count, len(parsed.warnings),
        )

        return TransactionUploadResponse(
            upload_id=upload_id,
            session_id=session_id,
            filename=filename,
            columns=parsed.columns,
            row_count=parsed.row_count,
            summary=summary,
            warnings=parsed.warnings,
        )

    # ── Analysis ───────────────────────────────────────────────────────────────

    async def analyze(
        self,
        session_id: str,
        upload_id: str,
        query: str,
    ) -> ComplianceAnalysisResponse:
        trace_id = str(uuid.uuid4())

        upload = await self.db.transaction_uploads.find_one(
            {"upload_id": upload_id, "session_id": session_id}
        )
        if not upload:
            raise ValueError(f"Upload '{upload_id}' not found for session '{session_id}'.")

        prompt = _build_analysis_prompt(upload["typed_rows"], upload["columns"], query)
        raw = self.gemini.generate(prompt, trace_id=trace_id)
        result = _parse_gemini_json(raw, trace_id)

        await self.db.compliance_analyses.insert_one({
            "trace_id": trace_id,
            "session_id": session_id,
            "upload_id": upload_id,
            "summary": result["summary"],
            "flags": result["flags"],
            "created_at": datetime.now(timezone.utc),
        })

        logger.info(
            "Compliance analysis complete | session=%s upload=%s flags=%d trace=%s",
            session_id, upload_id, len(result["flags"]), trace_id,
        )

        return ComplianceAnalysisResponse(
            session_id=session_id,
            upload_id=upload_id,
            summary=result["summary"],
            flags=[ComplianceFlag(**f) for f in result["flags"]],
            trace_id=trace_id,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_summary(typed_rows: list[dict[str, Any]]) -> TransactionSummary:
    amounts = [r["amount"] for r in typed_rows if isinstance(r.get("amount"), (int, float))]
    timestamps = [r["timestamp"] for r in typed_rows if isinstance(r.get("timestamp"), str)]

    kyc_breakdown: dict[str, int] = {}
    for row in typed_rows:
        status = str(row.get("kyc_status", "unknown"))
        kyc_breakdown[status] = kyc_breakdown.get(status, 0) + 1

    missing_fields_count = sum(
        1 for row in typed_rows
        if any(row.get(col) in (None, "", "nan") for col in ("transaction_id", "amount", "vendor", "customer_name"))
    )

    return TransactionSummary(
        row_count=len(typed_rows),
        total_amount=round(sum(amounts), 2) if amounts else 0.0,
        avg_amount=round(sum(amounts) / len(amounts), 2) if amounts else 0.0,
        min_amount=round(min(amounts), 2) if amounts else 0.0,
        max_amount=round(max(amounts), 2) if amounts else 0.0,
        earliest_timestamp=min(timestamps) if timestamps else None,
        latest_timestamp=max(timestamps) if timestamps else None,
        kyc_breakdown=kyc_breakdown,
        high_value_count=sum(1 for a in amounts if a > CTR_THRESHOLD),
        missing_fields_count=missing_fields_count,
    )


def _build_analysis_prompt(
    typed_rows: list[dict[str, Any]],
    columns: list[str],
    query: str,
    max_rows: int = 100,
) -> str:
    sample = typed_rows[:max_rows]
    header = ", ".join(columns)
    lines = [
        f"Columns: {header}",
        f"Total rows: {len(typed_rows)} (showing first {len(sample)})",
        "",
    ]
    for i, row in enumerate(sample):
        lines.append(f"Row {i}: " + " | ".join(f"{k}={v}" for k, v in row.items()))
    lines += ["", f"Instruction: {query}"]
    return "\n".join(lines)


def _parse_gemini_json(raw: str, trace_id: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON | trace=%s", trace_id)
        return {"summary": raw, "flags": []}
