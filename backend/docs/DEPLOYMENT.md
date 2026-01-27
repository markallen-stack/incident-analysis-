# Incident RAG — Deployment

---

## Requirements

- Python 3.11+
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
- (Optional) Prometheus and Grafana for metrics and dashboards

---

## Docker

### Build and run backend

```bash
cd backend
docker build -t incident-rag -f Dockerfile --target production .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data -v $(pwd)/vector_db/indexes:/app/vector_db/indexes incident-rag
```

### Docker Compose (full stack)

From the project root:

```bash
docker-compose up -d
```

- **incident-rag:** API on `http://localhost:8000`
- **ui:** Frontend on `http://localhost:8501` (mapped from 3000)
- **prometheus:** `http://localhost:9090`
- **grafana:** `http://localhost:3000` (admin / admin)

Compose uses `backend/.env` for the backend. Create it from `.env.example` or equivalent.

---

## Vector indexes

Before first use (or after changing `data/incidents.json`, runbooks, or historical incidents):

```bash
cd backend
python core/vector_db/setup.py
# force rebuild:
python core/vector_db/setup.py --rebuild
```

In Docker, ensure `vector_db/indexes/` is either:

- Built into the image (copy at build time), or
- Mounted from the host so indexes are persisted and up to date.

---

## Environment variables (production)

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `OPENAI_API_KEY` | OpenAI API key (for vision if used) | `sk-...` |
| `PRIMARY_LLM` | Main LLM model | `claude-sonnet-4-20250514` |
| `VISION_MODEL` | Vision model | `gpt-4o` |
| `EMBEDDING_MODEL` | Embedding model | `BAAI/bge-large-en-v1.5` |
| `CONFIDENCE_THRESHOLD` | Answer threshold | `0.7` |
| `PROMETHEUS_URL` | Prometheus API URL | `http://prometheus:9090` |
| `VECTOR_DB_PATH` | Dir for FAISS indexes | `./vector_db/indexes` |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## Frontend

Build:

```bash
cd frontend
npm ci
npm run build
```

Set `NEXT_PUBLIC_API_URL` to the backend URL (e.g. `http://localhost:8000` or your public API URL).

For Docker, the `ui` service in `docker-compose` builds from `frontend/` and exposes the app.

---

## Health and monitoring

- **Liveness:** `GET /health`
- **Metrics:** Prometheus metrics are exposed by `prometheus-fastapi-instrumentator` on the FastAPI app (path as configured).
- **Grafana:** Use the Prometheus datasource to build dashboards for the API and, if scraped, Prometheus agent metrics.

---

## See also

- [docs/DOCUMENTATION.md](../../docs/DOCUMENTATION.md) — § Deployment, Configuration, Data
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — Performance, scaling, monitoring
