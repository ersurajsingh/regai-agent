# RegAI Demo Datasets

Three CSV files for demonstrating RegAI compliance detection. Upload any of them
to `POST /api/v1/transactions/upload` or drag into the `/observe` page.

---

## suspicious_transactions.csv — 40 rows, all red flags

| Pattern | Rows | What to look for |
|---|---|---|
| AML structuring (smurfing) | TXN-S001–S007 | 7 transactions $9,100–$9,900 to same vendor same day |
| CTR threshold breaches | TXN-S008–S011 | 4 transactions $15k–$31k, all `kyc_status=failed` |
| Velocity spike (duplicates) | TXN-S012–S016 | Same vendor, same amount ($1,200), 5 times in 20 minutes |
| Exact duplicate invoices | TXN-S017–S019 | 3 transaction IDs each appear twice |
| Large round-number CTR | TXN-S020–S021 | $75k and $120k, `kyc_status=failed` |
| AML structuring (second cluster) | TXN-S022–S025 | 4 transactions $9,300–$9,800 to Nexus Trade Co |
| Velocity spike (round amounts) | TXN-S026–S030 | $2,000 × 5 in 8 minutes |
| Duplicate + failed KYC | TXN-S031–S032 | Same ID, same amount, `kyc_status=failed` |
| AML structuring (third cluster) | TXN-S033–S037 | 5 transactions $9,100–$9,800 to Dark Matter Trading |
| Large round-number triples | TXN-S038–S040 | $50,000 × 3 in 10 minutes, `kyc_status=failed` |

Expected detections: **CRITICAL** risk, all four detectors fire.

---

## normal_transactions.csv — 40 rows, clean

All transactions:
- `kyc_status=verified`
- Unique transaction IDs
- Diverse vendors (SaaS tools, cloud services)
- Amounts $290–$8,500 (no CTR triggers)
- No repeated vendor patterns

Expected detections: **LOW** risk, no issues flagged.

---

## mixed_transactions.csv — 50 rows, realistic enterprise mix

~60% clean SaaS/cloud transactions interspersed with deliberate red flags:

| Pattern | Rows | Severity |
|---|---|---|
| AML structuring | TXN-M006–M009 | CRITICAL |
| Velocity spike (unknown KYC) | TXN-M013–M016 | MEDIUM |
| Duplicate invoices | TXN-M020–M021 | HIGH |
| CTR breaches + failed KYC | TXN-M024–M025 | HIGH |
| AML structuring (second) | TXN-M028–M030 | CRITICAL |
| Duplicate + failed KYC | TXN-M033 | HIGH |
| Large CTR + failed KYC | TXN-M036–M037 | HIGH |
| Velocity spike (pending KYC) | TXN-M040–M043 | MEDIUM |
| AML structuring (third) | TXN-M046–M048 | CRITICAL |

Expected detections: **HIGH** risk, mixed findings across all four detectors.

---

## Column Reference

| Column | Type | Notes |
|---|---|---|
| `transaction_id` | string | Duplicates intentional in suspicious/mixed files |
| `amount` | float | USD |
| `vendor` | string | |
| `timestamp` | datetime | `YYYY-MM-DD HH:MM:SS` |
| `customer_name` | string | |
| `kyc_status` | string | `verified` / `pending` / `failed` / `unknown` |
