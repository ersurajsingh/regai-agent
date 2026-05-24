# RegAI — Observability-Driven AI Compliance Agent

> **Google Cloud Agent Hackathon 2025 · Arize Track Submission**
> Built with Gemini 2.0 · Google ADK · Arize Phoenix · MongoDB Atlas · Google Cloud Run

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![Arize Phoenix](https://img.shields.io/badge/Arize-Phoenix-purple)](https://phoenix.arize.com)

---

## The Problem

Financial institutions process millions of transactions daily. Compliance teams manually review flagged transactions for AML (Anti-Money Laundering), KYC violations, duplicate invoices, and suspicious patterns. This process is:

- **Slow** — manual review takes days, not seconds
- **Inconsistent** — human reviewers miss patterns across large datasets
- **Opaque** — no visibility into *why* an AI flagged a transaction
- **Static** — AI models don't learn from their own mistakes over time

**RegAI solves all four.**

---

## What RegAI Does

RegAI is a **self-improving AI compliance agent** that:

1. **Analyzes** transaction CSVs for AML patterns, KYC gaps, duplicate invoices, and suspicious activity
2. **Explains** every decision with regulation citations (BSA, FATF, GAAP)
3. **Evaluates** its own output quality against a deterministic rule engine
4. **Reflects** on prior decisions to identify false positives and weak reasoning
5. **Improves** future analyses using trace memory from prior sessions
6. **Exposes** every reasoning step through Arize Phoenix traces

---

## Why Observability-Driven AI Governance Matters

Traditional AI compliance tools are black boxes. When an AI flags a transaction, compliance officers can't see:
- Which rules fired and why
- Whether the AI hallucinated an issue
- How confident the model was
- Whether the same mistake was made before

RegAI treats **observability as a first-class feature**, not an afterthought. Every Gemini call, every detector execution, every reasoning step is a traced span in Phoenix — queryable, auditable, and improvable.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Browser                                │
│              Next.js + Tailwind — Observability Timeline            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST / JSON
┌──────────────────────────────▼──────────────────────────────────────┐
│                      FastAPI Backend (:8000)                        │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Agent Pipeline                           │    │
│  │                                                             │    │
│  │  CSV Upload → Compliance Analysis → Evaluation →            │    │
│  │  Self-Reflection → Trace-Aware Analysis                     │    │
│  └──────────────────────┬──────────────────────────────────────┘    │
│                         │                                           │
│  ┌──────────────────────▼──────────────────────────────────────┐    │
│  │              Google ADK root_agent                          │    │
│  │                                                             │    │
│  │  Tools:                                                     │    │
│  │  ├── detect_aml_patterns      (structuring, CTR, round #s)  │    │
│  │  ├── detect_duplicate_invoices (exact + near-duplicate)     │    │
│  │  ├── detect_missing_kyc       (FATF Rec 10 / BSA CIP)       │    │
│  │  └── detect_suspicious_activity (velocity spikes)           │    │
│  └──────────────────────┬──────────────────────────────────────┘    │
│                         │                                           │
│  ┌──────────┐  ┌────────▼────────┐  ┌──────────────────────────┐    │
│  │ MongoDB  │  │  Gemini 2.0     │  │  Arize Phoenix           │    │
│  │  Atlas   │  │  Flash API      │  │  (OTLP traces)           │    │
│  │          │  │  (Reasoning +   │  │  Phoenix MCP Server      │    │
│  │  Memory  │  │   Risk Scoring) │  │  (IDE introspection)     │    │
│  └──────────┘  └─────────────────┘  └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Self-Improving Agent Loop

```
Upload CSV
    │
    ▼
[1] Deterministic Detectors (rule engine — no LLM cost)
    ├── AML patterns
    ├── Duplicate invoices
    ├── Missing KYC
    └── Suspicious velocity
    │
    ▼
[2] Gemini 2.0 Flash (enrichment + risk scoring)
    └── Prompt includes: transaction data + pre-detected issues
    │
    ▼
[3] Evaluation (quality scoring vs rule engine)
    ├── Decision quality (recall + calibration)
    ├── Reasoning quality (citations + evidence)
    ├── Hallucination risk (precision vs rules)
    └── Rule alignment (F1 score)
    │
    ▼
[4] Self-Reflection (critique + improvement)
    ├── Identify false positives
    ├── Critique weak reasoning
    └── Generate improved analysis
    │
    ▼
[5] Trace-Aware Analysis (learns from history)
    ├── Load prior analyses from MongoDB
    ├── Identify repeated mistakes
    ├── Inject historical context into Gemini prompt
    └── Explain reasoning changes
    │
    ▼
Phoenix Traces → Arize UI → MCP Introspection
```

---

## Arize Phoenix Integration

Every agent action produces a Phoenix-compatible span:

| Span Kind | What it captures |
|-----------|-----------------|
| `CHAIN` | Full compliance workflow, reflection cycle, trace-aware reasoning |
| `TOOL` | Each detector call (AML, KYC, duplicates, velocity) |
| `LLM` | Every Gemini API call (auto-instrumented via OpenInference) |
| `EVAL` | Evaluation workflow with dimension scores |
| `REFLECT` | Self-reflection cycle with false positive assessments |

Span attributes include `risk_level`, `risk_score`, `issue_count`, `eval.decision_quality.score`, `eval.f1_score`, `regai.session_trend` — all queryable in the Phoenix UI.

### Phoenix MCP Server

The `.gemini/settings.json` configures the Phoenix MCP server for the Gemini CLI, enabling runtime introspection of traces, sessions, prompts, and experiments directly from your IDE:

```json
{
  "mcpServers": {
    "phoenix": {
      "command": "npx",
      "args": ["-y", "@arizeai/phoenix-mcp@latest"],
      "env": {
        "PHOENIX_HOST": "${PHOENIX_HOST}",
        "PHOENIX_API_KEY": "${PHOENIX_API_KEY}",
        "PHOENIX_PROJECT": "${PHOENIX_PROJECT_NAME}"
      }
    }
  }
}
```

---

## Google ADK Architecture

The compliance agent is built as a proper Google ADK `root_agent` with four modular tools:

```python
# backend/regai_agent/agent.py
root_agent = Agent(
    model="gemini-flash-latest",
    name="regai_compliance_agent",
    tools=[
        detect_aml_patterns,        # BSA structuring + CTR detection
        detect_duplicate_invoices,  # exact + near-duplicate detection
        detect_missing_kyc,         # FATF Rec 10 / BSA CIP validation
        detect_suspicious_activity, # velocity spike detection
    ],
)
```

Run via Gemini CLI:
```bash
adk run backend/regai_agent
# or
adk web  # opens browser UI at http://localhost:8000
```

---

## Project Structure

```
regai-agent/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── compliance_analysis_agent.py   # Core analysis agent
│   │   │   ├── evaluation_agent.py            # Quality scoring
│   │   │   ├── reflection_agent.py            # Self-reflection
│   │   │   └── trace_aware_agent.py           # History-aware analysis
│   │   ├── api/v1/endpoints/                  # REST endpoints
│   │   ├── core/
│   │   │   ├── config.py                      # Pydantic settings
│   │   │   ├── database.py                    # MongoDB (motor async)
│   │   │   └── observability.py               # Phoenix init
│   │   ├── schemas/                           # Pydantic models
│   │   ├── services/
│   │   │   ├── gemini_service.py              # google.genai wrapper
│   │   │   ├── rule_engine.py                 # Deterministic baseline
│   │   │   ├── trace_memory.py                # Historical context loader
│   │   │   └── transaction_service.py         # CSV pipeline
│   │   └── utils/csv_parser.py                # Pandas CSV validation
│   ├── regai_agent/
│   │   ├── agent.py                           # ADK root_agent
│   │   ├── instrumentation.py                 # Phoenix tracing setup
│   │   └── tools/                             # ADK tool functions
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx                       # Chat interface
│   │   │   └── observe/page.tsx               # Observability timeline
│   │   ├── components/
│   │   │   ├── ObservabilityTimeline.tsx      # Main timeline component
│   │   │   └── timeline/                      # Sub-components
│   │   └── lib/
│   │       ├── api.ts                         # Typed API client
│   │       └── types.ts                       # Shared TypeScript types
│   └── .env.example
├── demo_data/
│   ├── suspicious_transactions.csv            # 40 rows, all red flags
│   ├── normal_transactions.csv                # 40 rows, clean
│   └── mixed_transactions.csv                 # 50 rows, realistic mix
├── architecture/
│   ├── overview.md
│   └── deployment.md
├── .gemini/settings.json                      # Phoenix MCP config
├── docker-compose.yml
└── README.md
```

---

## Local Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- Arize Phoenix account (free at [app.phoenix.arize.com](https://app.phoenix.arize.com))
- Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/regai-agent.git
cd regai-agent

# Copy and fill in credentials
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Edit `backend/.env` with your credentials:

```env
GEMINI_API_KEY=your_key_from_aistudio
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/regai
PHOENIX_API_KEY=your_phoenix_jwt_key
PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com/s/your_project
PHOENIX_PROJECT_NAME=regai-compliance
```

### 2. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

### 4. Run

**Terminal 1 — Backend:**
```bash
cd backend
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Observability Timeline | http://localhost:3000/observe |
| API (FastAPI) | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

---

## Gemini CLI Setup

```bash
# Install Google ADK
pip install google-adk

# Set environment variables
export GOOGLE_API_KEY=your_key
export PHOENIX_API_KEY=your_phoenix_key
export PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com/s/your_project

# Run the ADK agent interactively
adk run backend/regai_agent

# Or open the ADK web UI
adk web  # from the backend/ directory
```

---

## Phoenix MCP Setup

The Phoenix MCP server lets you inspect traces, sessions, and experiments from your IDE or Gemini CLI.

```bash
# Install Node.js MCP server
npm install -g @arizeai/phoenix-mcp

# Load env vars and start Gemini CLI with MCP
set -a && source .env && set +a
gemini  # Phoenix MCP starts automatically via .gemini/settings.json
```

In the Gemini CLI, you can now ask:
- *"Show me the last 5 compliance analysis traces"*
- *"What was the hallucination risk score for session X?"*
- *"List all traces where risk_level was critical"*

---

## Demo Workflow

### Quick Demo (5 minutes)

1. Start both servers (see above)
2. Open **http://localhost:3000/observe**
3. Drag `demo_data/suspicious_transactions.csv` onto the upload zone
4. Watch the pipeline execute in real time:
   - **Upload** → 40 rows parsed, KYC breakdown shown
   - **Analyze** → Gemini detects CRITICAL risk (AML structuring, missing KYC, duplicates)
   - **Evaluate** → Quality scores across 4 dimensions
   - **Reflect** → Agent critiques its own output
   - **Trace-Aware** → Agent explains reasoning changes vs prior analyses
5. Click through the 5 tabs to explore each layer

### Dataset Guide

| File | Rows | Expected Risk | Key Patterns |
|------|------|---------------|--------------|
| `suspicious_transactions.csv` | 40 | CRITICAL | AML structuring, CTR breaches, duplicates, failed KYC |
| `normal_transactions.csv` | 40 | LOW | All verified, diverse SaaS vendors |
| `mixed_transactions.csv` | 50 | HIGH | 60% clean + 9 red flag clusters |

### API Testing

```bash
# Health check
curl http://localhost:8000/health

# Create session
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/sessions/ | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# Upload CSV
UPLOAD_ID=$(curl -s -X POST "http://localhost:8000/api/v1/transactions/upload?session_id=$SESSION" \
  -F "file=@demo_data/suspicious_transactions.csv" | python3 -c "import sys,json; print(json.load(sys.stdin)['upload_id'])")

# Run compliance analysis
curl -X POST http://localhost:8000/api/v1/compliance/analyze \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\",\"upload_id\":\"$UPLOAD_ID\"}"

# Run evaluation
curl -X POST http://localhost:8000/api/v1/compliance/evaluate \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\",\"upload_id\":\"$UPLOAD_ID\"}"

# Run self-reflection
curl -X POST http://localhost:8000/api/v1/compliance/reflect \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\",\"upload_id\":\"$UPLOAD_ID\"}"
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/sessions/` | Create session |
| `POST` | `/api/v1/transactions/upload` | Upload CSV |
| `POST` | `/api/v1/compliance/analyze` | Run compliance analysis |
| `POST` | `/api/v1/compliance/evaluate` | Evaluate analysis quality |
| `POST` | `/api/v1/compliance/reflect` | Run self-reflection |
| `POST` | `/api/v1/compliance/analyze/trace-aware` | History-aware analysis |
| `GET` | `/api/v1/compliance/reflect/history` | Reflection history |
| `GET` | `/api/v1/compliance/evaluate/history` | Evaluation history |

Full interactive docs: **http://localhost:8000/docs**

---

## Future Roadmap

- **Real-time streaming** — stream Gemini reasoning steps to the frontend as they happen
- **Multi-agent orchestration** — specialized sub-agents for GDPR, SOX, PCI-DSS
- **Vector search** — semantic search over prior compliance decisions
- **Sanctions screening** — OFAC/UN sanctions list integration
- **Audit trail export** — PDF compliance reports with full trace provenance
- **Webhook alerts** — real-time notifications for CRITICAL risk detections
- **Fine-tuning** — use Phoenix evaluation data to fine-tune domain-specific models

---

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

### Repo Topics

`ai-compliance` `aml-detection` `gemini` `google-adk` `arize-phoenix` `opentelemetry` `fastapi` `nextjs` `mongodb` `fintech` `llm-observability` `ai-governance` `hackathon`

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built for the Google Cloud Agent Hackathon 2025 · Arize Track*
