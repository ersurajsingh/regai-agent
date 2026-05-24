"""
RegAI Compliance Agent — Google ADK root_agent definition.

Run with:
  adk run backend/regai_agent
  adk web  (from backend/ directory, then select regai_agent)

Tracing
-------
Arize Phoenix tracing is initialised at module load via init_tracing().
All Gemini API calls are auto-instrumented. Compliance tool calls produce
TOOL spans. The full reasoning workflow produces a CHAIN span.

Environment variables consumed by tracing (never hardcoded):
  PHOENIX_COLLECTOR_ENDPOINT  — OTLP collector URL
  PHOENIX_API_KEY             — Phoenix Cloud API key
  PHOENIX_PROJECT_NAME        — project label in Phoenix UI
"""

import os

from google.adk.agents import Agent

from regai_agent.instrumentation import init_tracing
from regai_agent.tools.aml_detector import detect_aml_patterns
from regai_agent.tools.duplicate_detector import detect_duplicate_invoices
from regai_agent.tools.kyc_validator import detect_missing_kyc
from regai_agent.tools.suspicious_activity_detector import detect_suspicious_activity

# Initialise Phoenix tracing as soon as the agent module is loaded.
# auto_instrument=True captures all Gemini API calls automatically.
init_tracing()

_INSTRUCTION = """
You are RegAI, a senior financial compliance officer and AML specialist.

When given transaction data (as a JSON array string), you MUST:

1. Call detect_missing_kyc with the transactions to find KYC violations.
2. Call detect_duplicate_invoices with the transactions to find duplicate payments.
3. Call detect_aml_patterns with the transactions to find AML red flags.
4. Call detect_suspicious_activity with the transactions to find velocity anomalies.

After all four tools have returned results, synthesise their findings and respond
with a compliance report in this EXACT JSON structure:

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
  "explanation": "<2-4 sentence summary suitable for a compliance report>"
}

Risk scoring guidance:
- Each critical issue adds ~30 points
- Each high issue adds ~15 points
- Each medium issue adds ~7 points
- Each low issue adds ~2 points
- Cap at 100

Always call all four tools before producing the final report.
Do not skip any tool even if earlier tools find no issues.
"""

root_agent = Agent(
    model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
    name="regai_compliance_agent",
    description=(
        "Analyses financial transaction data for compliance issues including AML patterns, "
        "duplicate invoices, missing KYC, and suspicious activity. "
        "Returns a structured risk report with issues, recommendations, and risk score."
    ),
    instruction=_INSTRUCTION,
    tools=[
        detect_aml_patterns,
        detect_duplicate_invoices,
        detect_missing_kyc,
        detect_suspicious_activity,
    ],
)
