# RegAI Architecture Overview

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                         │
│                  Next.js + Tailwind (3000)                   │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST / JSON
┌───────────────────────────▼─────────────────────────────────┐
│                    FastAPI Backend (8000)                    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  /query      │  │  /documents  │  │  /sessions       │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────┘  │
│         │                 │                                  │
│  ┌──────▼───────────────────────────────────────────────┐   │
│  │              ComplianceAgent (agents/)               │   │
│  │         + Tools (tools/regulation_search, ...)       │   │
│  └──────┬───────────────────────────────────────────────┘   │
│         │                                                    │
│  ┌──────▼──────────┐   ┌──────────────────────────────┐     │
│  │  Gemini API     │   │  Arize Phoenix (OTLP :4317)  │     │
│  │  (Google AI)    │   │  Phoenix UI (:6006)           │     │
│  └─────────────────┘   └──────────────────────────────┘     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              MongoDB Atlas (motor async)             │   │
│  │   collections: sessions, queries, documents          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

1. User opens the app → Frontend calls `POST /api/v1/sessions/` → gets `session_id`
2. User types a question → `POST /api/v1/query/` with `session_id` + `query`
3. Backend loads session context from MongoDB
4. `ComplianceAgent` calls Gemini API (instrumented by OpenInference)
5. Trace is exported to Arize Phoenix via OTLP
6. Answer is persisted to MongoDB and returned to the Frontend

## Adding a New Agent

1. Create `backend/app/agents/my_new_agent.py`
2. Implement a class with an async `run(payload)` method
3. Add a new endpoint in `backend/app/api/v1/endpoints/`
4. Register the route in `backend/app/api/v1/router.py`

## Adding a New Tool

1. Create `backend/app/tools/my_tool.py`
2. Export an async function or a class with a `run` method
3. Import and call it from any agent

## Deployment

See `deployment.md` for Cloud Run setup.
