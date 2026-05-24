"""
Vercel serverless entry point for the RegAI FastAPI backend.
Vercel's @vercel/python runtime calls this file.
"""
import sys
import os

# Add backend root to path so app.* imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app  # noqa: F401 — Vercel picks up the `app` ASGI object
