# Incident RAG

**AI-powered DevOps incident root cause analysis** using a multi-agent system with RAG (Retrieval-Augmented Generation), vector search, and observability integration (Prometheus, Grafana).

---

## Overview

Incident RAG analyzes incidents by:

1. **Planning** — Decomposing the user’s incident query into affected services, symptoms, and required data sources  
2. **Collecting evidence** — In parallel: logs, RAG (historical incidents + runbooks), dashboard screenshots, **Prometheus** metrics, and **Grafana** dashboards  
3. **Timeline correlation** — Ordering events from all sources  
4. **Hypothesis generation** — Proposing 2–5 root cause hypotheses (LLM or rule-based)  
5. **Verification** — Checking each hypothesis against evidence and requiring ≥2 independent sources  
6. **Decision** — Answer, refuse, or request more data based on confidence (default threshold 0.7)

The pipeline is implemented as a **LangGraph** state machine. Evidence is stored and searched via **FAISS** vector indexes (logs, incidents, runbooks) and **SentenceTransformers** embeddings.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- PostgreSQL database (free tier on Supabase recommended) - see [docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md)
- Docker & Docker Compose (optional, for Prometheus/Grafana)

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Create `backend/.env`:

```env
# Database (required for persistent storage)
DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname
# Or for Supabase:
# SUPABASE_DB_URL=postgresql+asyncpg://postgres.xxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY
PRIMARY_LLM=claude-sonnet-4-20250514
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
PROMETHEUS_URL=http://localhost:9090
CONFIDENCE_THRESHOLD=0.7
```

**Set up database:**
1. Create a free Supabase project: [supabase.com](https://supabase.com)
2. Get connection string (see [docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md))
3. Add `DATABASE_URL` to `.env`
4. Initialize tables: `python scripts/init_db.py`

Initialize database tables:

```bash
cd backend
python scripts/init_db.py
```

Build vector indexes (logs, incidents, runbooks):

```bash
cd backend
python core/vector_db/setup.py
```

(Optional) Migrate existing settings from `data/settings.json`:

```bash
python scripts/migrate_settings.py
```

Run the API:

```bash
cd backend
python run.py
# or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000  
- Swagger: http://localhost:8000/docs  

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

- UI: http://localhost:3000  

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` if the API is not on 8000.

### 3. Observability (optional)

With Docker Compose:

```bash
docker-compose up -d prometheus grafana
```

- Prometheus: http://localhost:9090  
- Grafana: http://localhost:3000 (admin / admin)

---

## Project Structure

```
incident_rag/
├── backend/                 # Python API & agents
│   ├── app/                 # FastAPI app, routers, schemas
│   ├── core/
│   │   ├── agents/          # Planner, RAG, Log, Image, Prometheus, Grafana, Timeline, Hypothesis, Verifier, DecisionGate
│   │   ├── database/        # PostgreSQL models, CRUD, session management
│   │   ├── vector_db/      # FAISS indexes, query, setup
│   │   ├── mcp/             # MCP client (filesystem, Slack, GitHub, monitoring)
│   │   ├── mcp_servers/     # RAG, Prometheus, Grafana MCP servers
│   │   ├── prompts/         # LLM prompts
│   │   ├── graph.py         # LangGraph workflow
│   │   └── config.py        # Configuration
│   ├── scripts/             # init_db.py, migrate_settings.py
│   ├── data/                # incidents.json, runbooks, dashboards, historical_incidents
│   ├── vector_db/indexes/   # FAISS indexes and metadata
│   ├── config.py
│   ├── run.py               # Uvicorn entrypoint
│   └── requirements.txt
├── frontend/                # Next.js UI
│   ├── app/                 # Layout, pages
│   ├── components/          # AnalysisForm, AnalysisResults, AnalysisHistory, AnalyticsDashboard, ApiStatus
│   ├── lib/                 # api.ts, useAnalysis hook
│   └── domain/              # Types
├── docker-compose.yml       # incident-rag, ui, dev, prometheus, grafana
├── ARCHITECTURE.md          # Intelligent metrics & MCP tools
└── docs/
    └── DOCUMENTATION.md     # Full technical documentation
```

---

## Main APIs

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health, agents, MCP status |
| `POST` | `/analyze` | Run full incident analysis |
| `POST` | `/plan` | Generate execution plan only |
| `GET` | `/analysis/{id}` | Get analysis (from database) |
| `GET` | `/analyses` | List analyses (with user_id filter) |
| `POST` | `/analyze/stream` | SSE streaming analysis |
| `POST` | `/upload-logs` | Upload log file |
| `GET` | `/mcp/servers` | List MCP servers |
| `GET` | `/stats` | Usage stats |

See `backend/docs/API.md` and `http://localhost:8000/docs` for request/response schemas.

---

## Configuration (backend)

Key `config.py` / env vars:

- **Database:** `DATABASE_URL` or `SUPABASE_DB_URL` (PostgreSQL connection string)  
- **LLM:** `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, `PRIMARY_LLM`, `VISION_MODEL`, `EMBEDDING_MODEL`  
- **Confidence:** `CONFIDENCE_THRESHOLD` (default 0.7), `MIN_EVIDENCE_SOURCES`, `MAX_HYPOTHESES`  
- **Vector DB:** `VECTOR_DB_PATH`, `LOG_INDEX_NAME`, `INCIDENT_INDEX_NAME`, `RUNBOOK_INDEX_NAME`  
- **Prometheus:** `PROMETHEUS_URL`  
- **Paths:** `DATA_DIR`, `RUNBOOKS_DIR`, `HISTORICAL_INCIDENTS_DIR`, etc.

**Settings Storage:**
- System-wide defaults: `.env` file and `data/settings.json` (backward compatibility)
- Per-user settings: PostgreSQL `user_settings` table (when `user_id` provided)

---

## Documentation

- **[docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)** — Full technical documentation (architecture, agents, vector DB, API, config, runbook, deployment)  
- **[docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md)** — Step-by-step Supabase setup guide  
- **[docs/DATABASE_MIGRATION.md](docs/DATABASE_MIGRATION.md)** — Database migration details and schema  
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Intelligent metrics, MCP tools, data flow, confidence  
- **backend/docs/** — API, deployment, FAQ (extend as needed)

---

## License

See repository license file.
