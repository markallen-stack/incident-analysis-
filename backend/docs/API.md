# Incident RAG — API Reference

Interactive API docs: **http://localhost:8000/docs** (Swagger) and **http://localhost:8000/redoc** (ReDoc) when the backend is running.

---

## Base URL

- Local: `http://localhost:8000`
- Set `NEXT_PUBLIC_API_URL` in the frontend to match your backend URL.

---

## Endpoints

### General

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info and links to `/docs`, `/health`. |
| `GET` | `/health` | Health, version, `agents_available`, `mcp_enabled`, `mcp_servers`. |
| `GET` | `/stats` | `total_analyses`, `active_analyses`, `cache_size_mb`, `mcp_enabled`. |
| `DELETE` | `/cache` | Clear in-memory analysis cache. |

### Analysis

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyze` | Run full incident analysis. Body: `IncidentAnalysisRequest`. Returns `IncidentAnalysisResponse`. |
| `POST` | `/plan` | Plan only. Form: `query`, `timestamp`. Returns `PlanResponse`. |
| `GET` | `/analysis/{analysis_id}` | Get cached analysis by ID. |
| `POST` | `/analyze/stream` | SSE stream of analysis progress. Body: `IncidentAnalysisRequest`. |

### Data

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload-logs` | Form: `file`, `service`. Saves under `logs/`. |

### MCP

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/mcp/servers` | MCP status, servers, health. |
| `POST` | `/mcp/filesystem/read` | Form: `filepath`. Read file via MCP. |

---

## Request / Response Schemas

### `IncidentAnalysisRequest` (JSON body for `/analyze`)

```json
{
  "query": "string, required",
  "timestamp": "string, required (ISO)",
  "dashboard_images": ["base64 or paths"],
  "log_files_base64": [{"filename": "...", "content_base64": "..."}],
  "logs": [{"content": "...", "source": "..."}],
  "services": ["api-gateway", "db"]
}
```

### `IncidentAnalysisResponse`

```json
{
  "analysis_id": "string",
  "status": "answer | refuse | request_more_data",
  "confidence": 0.0–1.0,
  "root_cause": "string or null",
  "evidence": {"logs": [...], "rag": [...], "metrics": [...], "images": [...], "dashboards": [...]},
  "timeline": [{"time", "event", "confidence"}],
  "recommended_actions": ["string"],
  "alternative_hypotheses": [{"hypothesis", "why_less_likely"}],
  "missing_evidence": ["string"],
  "processing_time_ms": 0,
  "agent_history": [{"agent", "status", "evidence_count", ...}],
  "errors": ["string"]
}
```

### `HealthResponse`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "agents_available": ["planner", "log_retriever", "rag_retriever", ...],
  "mcp_enabled": true,
  "mcp_servers": ["filesystem", ...]
}
```

### `PlanResponse` (from `/plan`)

```json
{
  "plan": {
    "incident_time", "affected_services", "symptoms",
    "required_agents", "search_windows", "prometheus_config", "priority"
  },
  "estimated_time_seconds": 0
}
```

---

## Errors

- `404` — Analysis or resource not found.
- `500` — Analysis or server error; `detail` contains the message.
- `503` — MCP or dependency not available.

---

## See also

- **Project docs:** [docs/DOCUMENTATION.md](../../docs/DOCUMENTATION.md) (§ API Reference, Configuration)
- **Architecture:** [ARCHITECTURE.md](../../ARCHITECTURE.md) (intelligent metrics, MCP tools)
