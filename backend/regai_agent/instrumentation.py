"""
RegAI — Arize Phoenix tracing instrumentation.

Follows the official Arize Gemini hackathon starter architecture:
  https://arize.com/docs/phoenix/sdk-api-reference/python/arize-phoenix-otel

Usage
-----
Call init_tracing() once at application startup (FastAPI lifespan or ADK agent
module load). All subsequent Gemini API calls and compliance tool calls are
captured automatically via auto_instrument=True.

For manual span decoration, import `tracer` and use:
  @tracer.chain   — multi-step reasoning / orchestration workflows
  @tracer.tool    — individual compliance tool calls
  @tracer.llm     — direct LLM invocations

For session-scoped traces, use the `using_session` context manager:
  with using_session(session_id="abc-123"):
      ...

Environment Variables (never hardcoded)
---------------------------------------
  PHOENIX_COLLECTOR_ENDPOINT  — OTLP collector URL (default: http://localhost:4317)
  PHOENIX_API_KEY             — API key for Phoenix Cloud (adds auth header automatically)
  PHOENIX_PROJECT_NAME        — Project name shown in Phoenix UI (default: regai-compliance)
"""

import logging
import os

from phoenix.otel import register, using_session  # noqa: F401 — re-exported for callers

logger = logging.getLogger(__name__)

# ── Module-level tracer — import this in agent/tool files for decorators ───────
# Initialised lazily on first call to init_tracing(); safe to import before that.
tracer = None  # type: ignore[assignment]


def init_tracing() -> None:
    """
    Initialise Arize Phoenix tracing.

    Reads configuration exclusively from environment variables:
      PHOENIX_COLLECTOR_ENDPOINT  (default: http://localhost:4317)
      PHOENIX_API_KEY             (optional — enables Phoenix Cloud auth)
      PHOENIX_PROJECT_NAME        (default: regai-compliance)

    auto_instrument=True automatically instruments:
      - google-generativeai (Gemini API calls)
      - Any other installed OpenInference-compatible library

    batch=True uses BatchSpanProcessor for production-safe async export.
    """
    global tracer

    project_name = os.environ.get("PHOENIX_PROJECT_NAME", "regai-compliance")
    endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:4317")

    try:
        tracer_provider = register(
            project_name=project_name,
            # endpoint and api_key are read from env vars automatically by register():
            #   PHOENIX_COLLECTOR_ENDPOINT → endpoint
            #   PHOENIX_API_KEY            → Authorization header
            batch=True,           # BatchSpanProcessor — non-blocking export
            auto_instrument=True, # instruments all installed OpenInference libraries
        )

        # Expose a module-level tracer for manual span decoration
        tracer = tracer_provider.get_tracer(__name__)

        logger.info(
            "Phoenix tracing initialised | project=%s endpoint=%s",
            project_name,
            endpoint,
        )
    except Exception as exc:
        # Tracing is non-fatal — the agent must still work without Phoenix
        logger.warning("Phoenix tracing init failed (non-fatal): %s", exc)


def get_tracer():
    """
    Return the module-level tracer.
    Raises RuntimeError if init_tracing() has not been called.
    """
    if tracer is None:
        raise RuntimeError(
            "Tracer not initialised. Call regai_agent.instrumentation.init_tracing() first."
        )
    return tracer
