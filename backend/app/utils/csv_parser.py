"""
CSV parsing and validation for transaction uploads.
Uses pandas for parsing; validates required columns and value types.
"""

import io
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ── Required schema ────────────────────────────────────────────────────────────
REQUIRED_COLUMNS: set[str] = {
    "transaction_id",
    "amount",
    "vendor",
    "timestamp",
    "customer_name",
    "kyc_status",
}

VALID_KYC_STATUSES: set[str] = {"verified", "pending", "failed", "unknown"}

MAX_ROWS = 5_000


class CSVParseError(ValueError):
    """Raised when a CSV cannot be decoded, is structurally invalid, or fails schema validation."""


@dataclass
class ParsedCSV:
    columns: list[str]
    rows: list[dict[str, Any]]          # raw string dicts for storage
    typed_rows: list[dict[str, Any]]    # coerced types for summary computation
    row_count: int
    warnings: list[str]                 # non-fatal issues (e.g. unknown KYC values)


def parse_transaction_csv(content: bytes, filename: str = "upload.csv") -> ParsedCSV:
    """
    Decode, parse, and validate a transaction CSV.

    Raises:
        CSVParseError: on unrecoverable errors (bad encoding, missing columns, empty file).

    Returns:
        ParsedCSV with raw rows, typed rows, and any non-fatal warnings.
    """
    text = _decode(content, filename)

    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except pd.errors.ParserError as exc:
        raise CSVParseError(f"Could not parse '{filename}' as CSV: {exc}") from exc
    except pd.errors.EmptyDataError:
        raise CSVParseError(f"'{filename}' is empty.")

    # Normalise column names
    df.columns = [c.strip().lower() for c in df.columns]

    _validate_columns(df, filename)

    if len(df) == 0:
        raise CSVParseError(f"'{filename}' has a header but no data rows.")

    if len(df) > MAX_ROWS:
        logger.warning("'%s' has %d rows; truncating to %d", filename, len(df), MAX_ROWS)
        df = df.head(MAX_ROWS)

    # Strip whitespace from all string cells
    df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)

    warnings: list[str] = []
    typed_rows = _coerce_types(df, warnings)
    raw_rows = df.to_dict(orient="records")

    logger.info("Parsed '%s': %d rows, %d columns", filename, len(df), len(df.columns))
    return ParsedCSV(
        columns=list(df.columns),
        rows=raw_rows,
        typed_rows=typed_rows,
        row_count=len(df),
        warnings=warnings,
    )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _decode(content: bytes, filename: str) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CSVParseError(f"Cannot decode '{filename}': unsupported character encoding.")


def _validate_columns(df: pd.DataFrame, filename: str) -> None:
    present = set(df.columns)
    missing = REQUIRED_COLUMNS - present
    if missing:
        raise CSVParseError(
            f"'{filename}' is missing required columns: {sorted(missing)}. "
            f"Expected: {sorted(REQUIRED_COLUMNS)}."
        )


def _coerce_types(df: pd.DataFrame, warnings: list[str]) -> list[dict[str, Any]]:
    """Return rows with amount as float, timestamp as ISO string, kyc_status validated."""
    typed: list[dict[str, Any]] = []

    for i, row in df.iterrows():
        record: dict[str, Any] = dict(row)

        # amount → float
        try:
            record["amount"] = float(str(row["amount"]).replace(",", ""))
        except ValueError:
            warnings.append(f"Row {i}: invalid amount '{row['amount']}'; stored as None.")
            record["amount"] = None

        # timestamp → ISO string (best-effort)
        try:
            record["timestamp"] = pd.to_datetime(row["timestamp"]).isoformat()
        except Exception:
            warnings.append(f"Row {i}: could not parse timestamp '{row['timestamp']}'.")

        # kyc_status → normalise case, warn on unknown values
        kyc = str(row["kyc_status"]).lower()
        record["kyc_status"] = kyc
        if kyc not in VALID_KYC_STATUSES:
            warnings.append(
                f"Row {i}: unexpected kyc_status '{kyc}'. "
                f"Expected one of {sorted(VALID_KYC_STATUSES)}."
            )

        typed.append(record)

    return typed
