"""
FastAPI observability — delegates to regai_agent.instrumentation.

Calls init_tracing() which uses phoenix.otel.register() with auto_instrument=True.
All Gemini API calls are captured automatically. Manual CHAIN and TOOL spans
are added in the compliance agent and service layers.
"""

import logging

from regai_agent.instrumentation import init_tracing

logger = logging.getLogger(__name__)


def init_observability() -> None:
    """Initialise Arize Phoenix tracing for the FastAPI application."""
    init_tracing()
