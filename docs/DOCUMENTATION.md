# Incident RAG — Technical Documentation

This document describes the architecture, components, APIs, configuration, and operations for the Incident RAG system.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Backend](#3-backend)
4. [Agents](#4-agents)
5. [Vector Database](#5-vector-database)
6. [MCP Integration](#6-mcp-integration)
7. [API Reference](#7-api-reference)
8. [Configuration](#8-configuration)
9. [Data Sources](#9-data-sources)
10. [Development & Testing](#10-development--testing)
11. [Deployment](#11-deployment)

---

## 1. System Overview

### Purpose

Incident RAG performs **root cause analysis** of DevOps incidents by:

- Ingesting: incident description, timestamp, optional logs, dashboard screenshots, and affected services
- Gathering evidence from: logs, historical incidents, runbooks, Prometheus metrics, and Grafana dashboards
- Correlating events into a timeline and generating hypotheses
- **Verifying** hypotheses with strict evidence rules (≥2 independent sources, no contradictions)
- Deciding: **answer** (root cause + actions), **refuse** (insufficient evidence), or **request_more_data**

### Design Principles

- **Evidence-based:** The verifier is the main gate; unsubstantiated conclusions are refused.
- **Multi-source:** Confidence increases with image, log, RAG, and metrics evidence.
- **Observability-native:** Prometheus and Grafana are first-class evidence sources.
- **Modular:** Each agent is a node in a LangGraph; state is centralized in `IncidentAnalysisState`.

### Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Uvicorn, Pydantic |
| Orchestration | LangGraph |
| LLM | Anthropic Claude, OpenAI GPT-4o (configurable) |
| Embeddings | SentenceTransformers (BAAI/bge-large-en-v1.5) |
| Vector DB | FAISS (CPU) |
| Metrics | Prometheus, Grafana, prometheus-api-client |
| Frontend | Next.js, React, Tailwind, shadcn/ui |

---

## 2. Architecture

### High-Level Flow

```
User (query, timestamp, logs, images, services)
    → Planner
    → [Image, Log, RAG, Prometheus, Grafana]  (parallel)
    → Timeline Correlator
    → Hypothesis Generator
    → Verifier
    → Decision Gate
    → answer | refuse | request_more_data
```

### LangGraph Workflow (`core/graph.py`)

- **State:** `IncidentAnalysisState` (TypedDict) with: `user_query`, `dashboard_images`, `logs`, `timestamp`, `plan`, `image_evidence`, `log_evidence`, `rag_evidence`, `metrics_evidence`, `dashboard_evidence`, `timeline`, `correlations`, `timeline_gaps`, `hypotheses`, `verification_results`, `overall_confidence`, `decision`, `final_response`, `errors`, `agent_history`.
- **Nodes:** `planner`, `image`, `log`, `rag`, `prometheus`, `grafana`, `timeline`, `hypothesis`, `verifier`, `decision_gate`.
- **Edges:** `planner` → all evidence agents; all evidence agents → `timeline`; `timeline` → `hypothesis` → `verifier` → `decision_gate` → END.

### Data Structures

- **Evidence:** `source`, `content`, `timestamp`, `confidence`, `metadata`.
- **TimelineEvent:** `time`, `event`, `source`, `confidence`.
- **Hypothesis:** `id`, `root_cause`, `plausibility`, `supporting_evidence`, `required_evidence`, `would_refute`.
- **VerificationResult:** `hypothesis_id`, `verdict` (SUPPORTED | INSUFFICIENT_EVIDENCE | CONTRADICTED), `confidence`, `evidence_summary`, `independent_sources`, `contradictions`, `reasoning`.

### Confidence and Decisions

- **Verifier** scores each hypothesis from 0–1 using: number of independent evidence sources, contradictions, and timeline consistency.
- **Overall confidence** = max among supported hypotheses; if none, max among all.
- **Decision gate:**
  - `answer` if overall_confidence ≥ threshold and at least one SUPPORTED hypothesis
  - `request_more_data` if 0.5 ≤ overall_confidence < threshold and there are `gaps`
  - `refuse` otherwise

Threshold is `CONFIDENCE_THRESHOLD` (default 0.7).

---

## 3. Backend

### Layout

```
backend/
├── app/
│   ├── main.py          # FastAPI app, /health, /analyze, /plan, /upload-logs, /mcp/*, /stats, /cache
│   ├── schemas.py       # Pydantic: AnalysisRequest, AnalysisResponse, Evidence, Hypothesis, etc.
│   ├── client.py
│   ├── start.sh
│   └── routers/
│       ├── analysis.py
│       ├── health.py
│       ├── images.py
│       └── incidents.py
├── core/
│   ├── graph.py         # LangGraph: build_incident_analysis_graph(), state, node funcs
│   ├── config.py        # Env-based config (paths, models, thresholds, Prometheus URL)
│   ├── claude_client.py
│   ├── agents/          # See §4
│   ├── vector_db/       # See §5
│   ├── mcp/              # See §6
│   ├── mcp_servers/
│   └── prompts/
├── data/
│   ├── incidents.json
│   ├── runbooks/
│   ├── dashboards/
│   ├── historical_incidents/
│   └── images/
├── vector_db/indexes/   # FAISS + metadata .pkl
├── config.py             # Duplicate/redirect; primary in core if split
├── run.py                # uvicorn app.main:app
├── analyze.py
├── requirements.txt
├── Dockerfile
├── pytest.ini
└── tests/
```

### Entrypoints

- **API:** `python run.py` or `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Docker:** `app.main:app` via uvicorn in Dockerfile `production` stage.

### Import Conventions

- App and routers: `from core.agents.* import ...`, `from core.graph import build_incident_analysis_graph`, `from core.mcp import get_mcp_client`.
- Inside `core/agents`, modules often use `from agents.*` (depends on `sys.path` including `core`); `core.agents` is the canonical package.

---

## 4. Agents

Each agent is a function that takes `IncidentAnalysisState` and returns a partial state update. They live in `core/agents/`.

### 4.1 Planner (`planner.py`)

- **Role:** Parse the user query and timestamp into a structured plan.
- **Input:** `user_query`, `timestamp`.
- **Output:** `plan` with: `incident_time`, `affected_services`, `symptoms`, `required_agents`, `search_windows`, `prometheus_config` (window_minutes, target_services, metrics_to_collect, default_metrics), `priority`, `prometheus_url`, `debug_mode`.
- **Logic:** LLM (Anthropic/OpenAI) or fallback regex/keyword extraction; `_enhance_plan` adds time windows and `prometheus_config`. Decides when to include the Prometheus agent from symptoms and query.

### 4.2 Image Agent (`image_analyzer.py`)

- **Role:** Analyze dashboard screenshots (Grafana, etc.) via a vision model.
- **Input:** `dashboard_images` (paths or base64), `plan.search_windows.metrics`.
- **Output:** `image_evidence` (list of `Evidence`).
- **Logic:** OpenAI or Anthropic vision API; on failure, mock. Uses `prompts/image.py`.

### 4.3 Log Agent (`log_retriever.py`)

- **Role:** Retrieve and rank relevant logs from provided `logs` and/or vector search.
- **Input:** `logs`, `plan.search_windows.logs`, `plan.affected_services`.
- **Output:** `log_evidence`.
- **Logic:** Vector search (`vector_db.query.search_logs`) when available; otherwise keyword/ time filtering. Can integrate with `log_retriever_mcp.py` for MCP-based log access.

### 4.4 RAG Agent (`rag_retriever.py`)

- **Role:** Fetch similar historical incidents and runbook sections.
- **Input:** `plan.symptoms`, `plan.affected_services`.
- **Output:** `rag_evidence`.
- **Logic:** `search_incidents` and `search_runbooks` from `vector_db.query`; dedup and rank by confidence. Fallback rule-based snippets when vector DB is unavailable.

### 4.5 Prometheus Agent (`prometheus_agent.py`)

- **Role:** Query Prometheus for metrics around the incident time.
- **Input:** `timestamp`, `plan.prometheus_config` (window_minutes, target_services, metrics_to_collect), `plan.prometheus_url`, `plan.debug_mode`.
- **Output:** `metrics_evidence` (list of `Evidence` with `metadata`: metric, job, query, stats, anomalies).
- **Logic:** `PrometheusAgent` uses `prometheus_api_client`; templates for HTTP, latency, CPU, memory, GC, etc. Range queries over incident ± `window_minutes`; `parse_metric_data`, `calculate_metric_stats`, `detect_anomalies`. Entrypoint used by the graph: `collect_incident_metrics` (or `collect_prometheus_metrics` if the graph is wired to the standalone function). Auto-discovers jobs from `up` when `jobs` is empty.

### 4.6 Grafana Agent (`grafana_agent.py`)

- **Role:** Fetch dashboards and annotations from Grafana for the incident window.
- **Input:** `timestamp`, window_minutes, `plan.affected_services` as dashboard tags.
- **Output:** `dashboard_evidence`.

### 4.7 Timeline Correlator (`timeline_correlator.py`)

- **Role:** Merge all evidence into a chronological timeline and find correlations and gaps.
- **Input:** `image_evidence`, `log_evidence`, `rag_evidence`, `metrics_evidence`, `dashboard_evidence`.
- **Output:** `timeline` (list of events), `correlations`, `timeline_gaps`.
- **Logic:** `_evidence_to_events` → `_sort_events` (by parsed timestamp) → `_find_correlations` (temporal patterns, e.g. deployment→error) → `_find_gaps` (large time gaps, missing sources).

### 4.8 Hypothesis Generator (`hypothesis_generator.py`)

- **Role:** Propose 2–5 root cause hypotheses.
- **Input:** `timeline`, `correlations`, `all_evidence` (image, log, rag, etc.).
- **Output:** `hypotheses` (list of `Hypothesis`), capped by `MAX_HYPOTHESES`.
- **Logic:** LLM (Anthropic/OpenAI) with `prompts/hypothesis.py`, or rule-based from patterns (deployment, memory, CPU, connection, traffic, config). Optional `generate_hypotheses_with_metrics` uses `llm_metrics_querier.intelligent_metrics_query` to enrich with Prometheus/Grafana before re-generating.

### 4.9 Verifier (`verifier.py`)

- **Role:** For each hypothesis, check evidence, count independent sources, detect contradictions, ensure timeline consistency, and assign verdict and confidence.
- **Input:** `hypotheses`, `evidence` (dict by source), `timeline`.
- **Output:** `verification_results`, `overall_confidence`.
- **Logic:** `_find_supporting_evidence`, `_detect_contradictions`, `_check_timeline_consistency`, `_calculate_hypothesis_confidence`, `_determine_verdict`. Requires ≥2 independent sources and no contradictions for SUPPORTED.

### 4.10 Decision Gate (`decision_gate.py`)

- **Role:** Choose answer / refuse / request_more_data and format the response.
- **Input:** `verification_results`, `overall_confidence`, `hypotheses`, `timeline`, `timeline_gaps`.
- **Output:** `decision`, `final_response` (root_cause, recommended_actions, alternative_hypotheses, missing_evidence, etc. depending on decision).

---

## 5. Vector Database

### Role

- **Logs:** semantic search over log entries (from `incidents.json` and any loaded logs).
- **Incidents:** search over historical incidents (from `incidents.json`, `historical_incidents/`).
- **Runbooks:** search over runbook sections (from `data/runbooks/*.md` and runbook sections in `incidents.json`).

### Implementation (`core/vector_db/`)

- **`query.py`:** `VectorSearcher` and helpers `search_logs`, `search_incidents`, `search_runbooks`. Uses `SentenceTransformer` (from `config.EMBEDDING_MODEL`) and FAISS `IndexFlatL2`. Supports `time_window`, `service_filter`, `level_filter` for logs; `min_similarity`, `service_filter` for incidents; `min_similarity` for runbooks.
- **`setup.py`:** `VectorDBSetup` builds FAISS indexes and metadata (`.pkl`) for logs, incidents, runbooks. `--rebuild` forces recreate. Reads from `config.INCIDENTS_JSON`, `config.HISTORICAL_INCIDENTS_DIR`, `config.RUNBOOKS_DIR`, and `incidents.json` runbook sections.

### Paths (config)

- `VECTOR_DB_PATH`, `LOG_INDEX_PATH`, `INCIDENT_INDEX_PATH`, `RUNBOOK_INDEX_PATH` (from `LOG_INDEX_NAME`, `INCIDENT_INDEX_NAME`, `RUNBOOK_INDEX_NAME`).

### Usage

```bash
python core/vector_db/setup.py [--rebuild] [--model MODEL]
```

```python
from core.vector_db.query import search_logs, search_incidents, search_runbooks
search_logs("OutOfMemoryError", top_k=10, service_filter=["api"])
search_incidents("memory leak deployment", top_k=5, min_similarity=0.6)
search_runbooks("connection pool", top_k=3)
```

---

## 6. MCP Integration

### Purpose

Model Context Protocol (MCP) clients provide structured access to:

- **Filesystem:** read files, list dirs, search in files (used for logs, runbooks).
- **Slack:** search messages, incident channel history (stubs if no token).
- **GitHub:** recent commits, deployment info (stubs if no token/repo).
- **Monitoring:** Prometheus instant/range queries (stubs if no `PROMETHEUS_URL`).

### Layout

- `core/mcp/__init__.py` re-exports `MCPClient`, `get_mcp_client`, and datatypes.
- `core/mcp/client.py`: `MCPClient` composed of `FilesystemMCP`, `SlackMCP`, `GitHubMCP`, `MonitoringMCP`. `get_mcp_client()` singleton.

### Usage

```python
from core.mcp import get_mcp_client
client = get_mcp_client()
r = client.filesystem.read_file("data/incidents.json")
client.get_available_servers()
client.health_check()
```

### MCP Servers

- `core/mcp_servers/`: RAG, Prometheus, Grafana MCP servers (used by MCP tooling / LLM tools; see `ARCHITECTURE.md` for the 7 MCP tools and intelligent metrics flow).

---

## 7. API Reference

### Base URL

- Default: `http://localhost:8000`. Override in frontend via `NEXT_PUBLIC_API_URL`.

### Endpoints (from `app/main.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service name and links. |
| GET | `/health` | `HealthResponse`: status, version, agents_available, mcp_enabled, mcp_servers. |
| POST | `/analyze` | `IncidentAnalysisRequest` → `IncidentAnalysisResponse` (analysis_id, status, confidence, root_cause, evidence, timeline, recommended_actions, alternative_hypotheses, missing_evidence, processing_time_ms, agent_history, errors). |
| POST | `/plan` | Form: `query`, `timestamp` → `PlanResponse` (plan, estimated_time_seconds). |
| GET | `/analysis/{analysis_id}` | Cached `IncidentAnalysisResponse`. |
| POST | `/analyze/stream` | `IncidentAnalysisRequest` → SSE stream of stages. |
| POST | `/upload-logs` | Form: `file`, `service` → save under `logs/`. |
| GET | `/mcp/servers` | MCP enabled, servers, health. |
| POST | `/mcp/filesystem/read` | Form: `filepath` → read via MCP. |
| GET | `/stats` | total_analyses, active_analyses, cache_size_mb, mcp_enabled. |
| DELETE | `/cache` | Clear in-memory analysis cache. |

### Request / Response Schemas

- **IncidentAnalysisRequest:** `query`, `timestamp`, `dashboard_images?`, `log_files_base64?`, `logs?`, `services?`.
- **IncidentAnalysisResponse:** `analysis_id`, `status` (answer|refuse|request_more_data), `confidence`, `root_cause?`, `evidence?`, `timeline?`, `recommended_actions?`, `alternative_hypotheses?`, `missing_evidence?`, `processing_time_ms`, `agent_history`, `errors?`.

See `app/schemas.py` and `http://localhost:8000/docs` for full OpenAPI.

---

## 8. Configuration

### `config` (and `core/config` if split)

Loaded from `backend/.env` via `python-dotenv` and `config.py`.

#### API Keys and Models

- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (at least one required)
- `PRIMARY_LLM` (e.g. `claude-sonnet-4-20250514`)
- `VISION_MODEL` (e.g. `gpt-4o`)
- `EMBEDDING_MODEL` (e.g. `BAAI/bge-large-en-v1.5`)

#### Thresholds

- `CONFIDENCE_THRESHOLD` (default 0.7)
- `MIN_EVIDENCE_SOURCES` (default 2)
- `MAX_HYPOTHESES` (default 5)

#### Vector DB

- `VECTOR_DB_PATH`, `LOG_INDEX_NAME`, `INCIDENT_INDEX_NAME`, `RUNBOOK_INDEX_NAME`

#### Prometheus / Observability

- `PROMETHEUS_URL` (default `http://localhost:9090`)

#### Paths

- `DATA_DIR`, `INCIDENTS_JSON`, `RUNBOOKS_DIR`, `HISTORICAL_INCIDENTS_DIR`, `DASHBOARDS_DIR`, `LOGS_DIR`, `LOG_FILE`

#### Tuning

- `MAX_CONCURRENT_AGENTS`, `REQUEST_TIMEOUT`, `BATCH_SIZE`
- `LOG_LEVEL`, `DEBUG_MODE`, `SAVE_INTERMEDIATE_STATES`

---

## 9. Data Sources

### `data/incidents.json`

- Structure: `{ "incidents": [ { "id", "name", "user_query", "timestamp", "expected_root_cause", "logs", "historical_incidents", "runbooks" } ] }`.
- Used by: vector_db setup (logs, incidents, runbook sections), evaluation, and examples.

### `data/runbooks/`

- Markdown runbooks; `setup.py` splits by `##` and indexes sections.

### `data/historical_incidents/`

- JSON files of historical incidents; `setup.py` merges into the incident index.

### `data/dashboards/`, `data/images/`

- Sample Grafana dashboards and images for demos and image agent.

---

## 10. Development & Testing

### Running Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
# or with docker-compose dev service
```

- `tests/test_planner.py`, `test_timeline.py`, `test_vector_db.py`, `test_verifier.py`
- `conftest.py` for fixtures
- `evaluation/run_eval.py` for evaluation harness

### Code Style

- `black`, `flake8`, `mypy` in `requirements.txt` / `requirements-dev.txt`.
- `pytest.ini` for pytest settings.

### Frontend

- `npm run dev` (Next.js), `npm run build`, `npm run lint` in `frontend/`.
- `lib/api.ts`: `checkHealth`, `analyzeIncident`, `getAnalysis`, `createPlan`, `getStats`, `listMcpServers`.
- `NEXT_PUBLIC_API_URL` for API base URL.

---

## 11. Deployment

### Docker

- **Backend:** `backend/Dockerfile` — `production` stage copies `app/`, `core/`, `config.py`, `data/`, `vector_db/indexes/`; runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- **Frontend:** `frontend/Dockerfile` (if present); in `docker-compose` the `ui` service builds from `frontend/` and exposes 3000 as 8501.

### Docker Compose

- **incident-rag:** backend on 8000, volumes for `data`, `vector_db/indexes`, `logs`.
- **ui:** frontend on 8501:3000, depends on incident-rag.
- **dev:** backend with volume mount and `pytest --watch`.
- **prometheus:** `prometheus.yml`, port 9090, volume for data.
- **grafana:** port 3000, provisioning for dashboards/datasources, depends on prometheus.

### Env in Production

- Provide `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (and `OPENAI_API_KEY` for image agent if using GPT-4o).
- Set `PROMETHEUS_URL` (and Grafana URL if used) to reach your Prometheus/Grafana.
- Ensure `CONFIDENCE_THRESHOLD`, `VECTOR_DB_PATH`, and log paths fit the environment.
- For Docker, use `env_file` or `environment` in `docker-compose` or K8s.

### Vector Indexes

- Build before first run or in an init job: `python core/vector_db/setup.py`.
- In Docker, `vector_db/indexes/` is copied from the build context or mounted; ensure it exists and is populated for RAG and log search.

### Health and Observability

- `/health` and `/stats` for liveness and usage.
- `prometheus-fastapi-instrumentator` exposes Prometheus metrics on the FastAPI app.
- Grafana can be pointed at Prometheus to visualize API and app metrics.

---

## References

- **ARCHITECTURE.md** — Intelligent metrics, MCP tools, Claude tool-calling flow, confidence rules.
- **Backend docs:** `backend/docs/API.md`, `DEPLOYMENT.md`, `FAQ.md`.
- **OpenAPI:** `http://localhost:8000/docs` when the API is running.
