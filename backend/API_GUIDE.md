"""
Complete FastAPI Application for Incident Analysis RAG System

This module provides a production-ready REST API for analyzing incidents using:
- Agentic multi-source evidence collection
- Dashboard image analysis with vision models
- Log correlation and timeline building  
- Hypothesis generation and verification
- Evidence-based decision making

## Running the API

### Development Mode
```bash
python run.py
# or
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode  
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`

## API Endpoints

### Health & Status
- `GET /` - API information
- `GET /health/` - Health check
- `GET /health/config` - Current configuration
- `GET /health/ready` - Readiness probe

### Incident Analysis
- `POST /api/v1/analysis/` - Analyze incident with images, logs, query
- `GET /api/v1/analysis/` - List all analyses
- `GET /api/v1/analysis/{request_id}` - Get specific analysis result

### Image Analysis
- `POST /api/v1/images/analyze` - Analyze single dashboard image
- `POST /api/v1/images/batch` - Analyze multiple images
- `GET /api/v1/images/supported-formats` - Get supported formats

### Incident Queries
- `POST /api/v1/incidents/search` - Search historical incidents
- `GET /api/v1/incidents/historical` - List historical incidents
- `GET /api/v1/incidents/{incident_id}` - Get incident details
- `GET /api/v1/incidents/stats/summary` - Get statistics

## Request/Response Examples

### POST /api/v1/analysis/
```json
{
  "query": "API server crashed at 14:32 UTC",
  "dashboard_images": ["data/images/cpu-mem-cluster-panels.png"],
  "logs": [
    {
      "timestamp": "2024-01-15T14:30:00Z",
      "level": "ERROR",
      "message": "Database connection failed",
      "service": "api-server"
    },
    {
      "timestamp": "2024-01-15T14:32:00Z",
      "level": "CRITICAL",
      "message": "Service crashed",
      "service": "api-server"
    }
  ],
  "time_window": "14:20-14:45"
}
```

Response:
```json
{
  "request_id": "abc-123-def-456",
  "status": "completed",
  "decision": "answer",
  "overall_confidence": 0.85,
  "root_cause": "Database connection pool exhaustion",
  "evidence": [
    {
      "source": "log",
      "content": "Database connection failed",
      "timestamp": "2024-01-15T14:30:00Z",
      "confidence": 0.9,
      "metadata": {"service": "api-server"}
    }
  ],
  "timeline": [...],
  "hypotheses": [...],
  "recommendations": [
    "Increase database connection pool size",
    "Monitor connection pool metrics"
  ],
  "created_at": "2026-01-19T12:30:00",
  "completed_at": "2026-01-19T12:30:30"
}
```

### POST /api/v1/images/analyze
```json
{
  "image_data": "base64_encoded_image_or_file_path",
  "time_window": "14:20-14:45"
}
```

Response:
```json
[
  {
    "source": "image",
    "content": "CPU usage spike detected from 30-40% to 95%",
    "timestamp": "14:30",
    "confidence": 0.90,
    "metadata": {
      "metric_name": "cpu_usage_percent",
      "pattern": "spike",
      "baseline": "30-40%",
      "anomaly_value": "95%"
    }
  }
]
```

### POST /api/v1/incidents/search
```json
{
  "query": "database connection timeout",
  "limit": 10,
  "min_confidence": 0.7
}
```

Response:
```json
{
  "total_results": 3,
  "search_query": "database connection timeout",
  "incidents": [...]
}
```

## Decision Logic

The system makes three types of decisions:

1. **ANSWER** (confidence ≥ 0.8)
   - Multiple independent evidence sources
   - No contradictions
   - Clear temporal correlation
   - Provides specific root cause

2. **REQUEST_MORE_DATA** (confidence 0.5-0.8)
   - Some evidence available
   - Ambiguity or gaps present
   - Recommends additional logs/metrics

3. **REFUSE** (confidence < 0.5)
   - Insufficient evidence
   - Contradictory information
   - Cannot determine root cause

## Architecture

```
FastAPI Application
├── main.py              # FastAPI app initialization
├── schemas.py           # Pydantic models
└── routers/
    ├── health.py        # Health checks
    ├── analysis.py      # Incident analysis
    ├── images.py        # Image analysis
    └── incidents.py     # Incident queries
```

The routers integrate with the core agents:
- `ImageAnalyzer` - Vision model analysis
- `LogRetriever` - Log correlation  
- `HypothesisGenerator` - Root cause generation
- `EvidenceVerifier` - Evidence validation
"""

print(__doc__)
