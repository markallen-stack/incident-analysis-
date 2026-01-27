# Intelligent Metrics Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Incident Analysis Graph                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Image Agent  │  │  Log Agent   │  │  RAG Agent   │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│         │                 │                 │                     │
│         └─────────────────┼─────────────────┘                     │
│                           │                                       │
│                    ┌──────▼──────┐                               │
│                    │ Timeline     │                               │
│                    │ Correlator   │                               │
│                    └──────┬──────┘                               │
│                           │                                       │
│        ┌──────────────────▼──────────────────┐                   │
│        │  Hypothesis Generator               │                   │
│        │  + intelligent metrics query ◄─┐    │                   │
│        └──────────────────┬──────────────┼───┘                   │
│                           │              │                       │
│        ┌──────────────────▼─────────────┐│    │                   │
│        │  Verifier Agent                ││    │                   │
│        │  + metrics enrichment ◄────────┘│    │                   │
│        └──────────────────┬──────────────┘    │                   │
│                           │                    │                   │
│        ┌──────────────────▼─────────────┐    │                   │
│        │  Decision Gate                 │    │                   │
│        │  (answer/refuse/request_more)  │    │                   │
│        └──────────────────┬──────────────┘    │                   │
│                           │                    │                   │
│                           ▼                    │                   │
│                    Final Response              │                   │
│                                                 │                   │
└─────────────────────────────────────────────────┼───────────────────┘
                                                  │
                    ┌─────────────────────────────┘
                    │
                    ▼
        ┌──────────────────────────────┐
        │  LLM Query Handler           │
        │  (IntelligentMetricsQueryer) │
        └──────────┬───────────────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
      ▼            ▼            ▼
  ┌─────────────────────────────────────┐
  │    Claude (with MCP Tools)          │
  │  • Analyzes incident context        │
  │  • Decides what to query            │
  │  • Makes tool calls iteratively     │
  │  • Synthesizes findings             │
  └─────────────┬───────────────────────┘
                │
   ┌────────────┴────────────┐
   │                         │
   ▼                         ▼
┌─────────────────┐  ┌────────────────────┐
│  Prometheus API │  │   Grafana API      │
│  • query        │  │  • dashboards      │
│  • alerts       │  │  • annotations     │
│  • targets      │  │  • datasources     │
└─────────────────┘  └────────────────────┘
   │                         │
   └────────────┬────────────┘
                │
                ▼
        ┌──────────────────┐
        │  Evidence Output │
        │  • source        │
        │  • content       │
        │  • confidence    │
        │  • metadata      │
        └──────────────────┘
```

## Data Flow: Detailed

### 1. Initial Analysis
```
User Query: "API crashed at 14:32"
     ↓
Graph splits into parallel agents:
  • Image Agent → extract metrics from screenshots
  • Log Agent → search logs for errors
  • RAG Agent → find similar historical incidents
     ↓
Timeline Correlator → align events chronologically
```

### 2. Hypothesis Generation with Metrics
```
Timeline + Evidence → Hypothesis Generator
     ↓
Initial hypotheses generated (rule-based or LLM)
     ↓
generate_hypotheses_with_metrics() called
     ↓
Call intelligent_metrics_query():
  context = "Validate these hypotheses with metrics"
  incident_time = "2024-01-15T14:32:00Z"
  affected_services = ["api", "db"]
     ↓
Claude receives:
  • Incident context
  • Initial hypotheses
  • 7 available tools
     ↓
Claude decides: "Need to check CPU, memory, connections"
     ↓
Claude calls tools iteratively...
```

### 3. Claude's Tool Calling Loop
```
Iteration 1:
  Tool: query_prometheus_range(
    query="rate(http_requests_total[5m])",
    start="2024-01-15T14:00Z",
    end="2024-01-15T15:00Z"
  )
  Result: "Requests dropped to 0 at 14:32"

Iteration 2:
  Tool: query_prometheus_instant(
    query="process_resident_memory_bytes / 1024 / 1024"
  )
  Result: "Memory: 512MB (normal)"

Iteration 3:
  Tool: search_grafana_dashboards(
    query="api"
  )
  Result: "API Performance Dashboard found"

... up to 10 iterations ...

Final:
  Tool: get_prometheus_alerts()
  Result: "API_CrashDetected alert firing"

Claude: "Requests crashed due to API process termination.
         Memory was normal, so not OOM.
         Likely cause: application crash or deployment issue."
```

### 4. Evidence Integration
```
Claude findings → Wrap in Evidence object:
{
  source: "llm_metrics_analysis",
  content: "Claude's detailed analysis",
  confidence: 0.92,
  timestamp: "2024-01-15T14:35:00Z",
  metadata: {
    incident_time: "2024-01-15T14:32:00Z",
    services: ["api"],
    iterations: 4,
    tools_used: ["query_prometheus_range", "get_grafana_dashboard", ...]
  }
}
     ↓
Add to all_evidence for timeline, hypothesis, and verification agents
```

### 5. Verification with Metrics Enrichment
```
verify_with_metrics_enrichment() called
     ↓
First pass: Verify hypotheses with current evidence
  • Result: confidence = 0.65 (low)
     ↓
Confidence < 0.70, so trigger metrics enrichment:
     ↓
intelligent_metrics_query() called for low-confidence hypotheses:
  context = "These hypotheses need metric validation"
  affected_services = ["api"]
     ↓
Claude queries specific metrics for each hypothesis
     ↓
Evidence gathered
     ↓
Second pass: Re-verify with enriched evidence
  • Result: confidence = 0.88 (high)
     ↓
Return improved results
```

## The 7 MCP Tools

### Prometheus Tools (4)

**1. query_prometheus_instant**
```
INPUT:
  query: "process_resident_memory_bytes / 1024"
  time: (optional) "2024-01-15T14:32:00Z"

OUTPUT:
  {
    status: "success",
    data: {
      resultType: "vector",
      result: [
        {
          metric: {...},
          value: [1705330320, "512.5"]
        }
      ]
    }
  }
```

**2. query_prometheus_range**
```
INPUT:
  query: "rate(http_requests_total[5m])"
  start: "2024-01-15T14:00:00Z"
  end: "2024-01-15T15:00:00Z"
  step: "1m"

OUTPUT:
  {
    status: "success",
    data: {
      resultType: "matrix",
      result: [
        {
          metric: {...},
          values: [
            [1705327200, "1000"],
            [1705327260, "950"],
            ...
            [1705330920, "0"],  ← Crash at 14:32
            ...
          ]
        }
      ]
    }
  }
```

**3. get_prometheus_alerts**
```
OUTPUT:
  {
    status: "success",
    data: {
      alerts: [
        {
          status: "firing",
          labels: {
            alertname: "API_CrashDetected",
            severity: "critical",
            service: "api"
          },
          annotations: {
            summary: "API process crashed",
            description: "..."
          },
          activeAt: "2024-01-15T14:32:00.000Z"
        }
      ]
    }
  }
```

**4. get_prometheus_targets**
```
OUTPUT:
  {
    status: "success",
    data: {
      activeTargets: [
        {
          labels: {
            job: "api",
            instance: "api:8000",
            ...
          },
          lastScrape: "2024-01-15T14:35:00Z",
          health: "up"
        },
        ...
      ]
    }
  }
```

### Grafana Tools (3)

**5. search_grafana_dashboards**
```
INPUT:
  query: "api"
  tags: ["performance"]

OUTPUT:
  {
    status: "success",
    dashboards: [
      {
        id: 123,
        uid: "abc123",
        title: "API Performance",
        tags: ["performance", "monitoring"]
      },
      ...
    ]
  }
```

**6. get_grafana_dashboard**
```
INPUT:
  dashboard_uid: "abc123"

OUTPUT:
  {
    status: "success",
    title: "API Performance",
    description: "...",
    panels: [
      {
        id: 1,
        title: "Request Rate",
        type: "graph",
        targets: [
          {
            expr: "rate(http_requests_total[5m])"
          }
        ]
      },
      ...
    ]
  }
```

**7. get_grafana_annotations**
```
INPUT:
  start_ms: 1705327200000
  end_ms: 1705330800000
  tags: ["incident"]

OUTPUT:
  {
    status: "success",
    annotations: [
      {
        id: 1,
        time: 1705330320000,
        text: "API deployment",
        tags: ["deployment"],
        user: "admin"
      },
      ...
    ]
  }
```

## Confidence Scoring

```
Initial Confidence (without metrics):
  1 source of evidence      → 0.4
  2+ sources               → 0.6
  Corroborating timeline   → +0.1
  No contradictions        → +0.1
  Max initial             → 0.8

After Metrics Enrichment:
  Prometheus metrics      → +0.1
  Alert firing           → +0.1
  Grafana dashboard      → +0.05
  Annotation match       → +0.05
  Max final              → 1.0
```

## Error Handling

```
Claude Tool Call
     ↓
  ┌──────────────────────┐
  │ Check Response       │
  └────────┬─────────────┘
           │
    ┌──────┴──────┐
    │             │
Success         Error
    │             │
    ▼             ▼
Return       Retry or
Data         Fallback
    │             │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │ Add to      │
    │ Evidence    │
    └─────────────┘
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Instant query | 100-500ms | Current metric value |
| Range query | 500ms-2s | 30 days of 1m resolution |
| Alert fetch | 50-100ms | Fast, small response |
| Dashboard search | 100-200ms | Fast, cached |
| Dashboard get | 100-300ms | Can be large JSON |
| Annotation fetch | 100-200ms | Limited by time range |
| **Total (typical)** | **1-3 seconds** | For 4-6 tool calls |
| **With iterations** | **3-10 seconds** | Up to 10 tool calls |

## Integration Points

### Within Graph
```
graph.invoke(state) → triggers all agents
  → when confidence low, auto-calls intelligent_metrics_query()
  → enriches evidence
  → improves confidence
  → higher quality final response
```

### In Custom Code
```
from core.agents.llm_metrics_querier import intelligent_metrics_query

evidence = intelligent_metrics_query(
    context="Is database under load?",
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["database"]
)
```

### In FastAPI Endpoint
```
@app.post("/api/analyze")
async def analyze(incident: IncidentReport):
    result = graph.invoke({
        ...incident data...
    })
    return result
    # Agents auto-use metrics as needed
```

## Security Considerations

1. **Prometheus**: Direct HTTP (add auth proxy in production)
2. **Grafana**: API key in environment variable
3. **Claude**: API calls go through Anthropic (HTTPS)
4. **Sensitive Data**: No PII in incident descriptions
5. **Rate Limiting**: Claude has built-in limits
6. **Query Injection**: Claude abstracts PromQL, minimal injection risk

## Scaling Notes

- **Single incident**: 1-3 seconds with metrics enrichment
- **Parallel incidents**: Each gets own Claude + tools session
- **Prometheus query load**: Light (few queries per incident)
- **Grafana load**: Light (few API calls per incident)
- **Claude costs**: ~$0.01-0.05 per incident analysis

## Monitoring the System

Watch for:
1. **Claude response time**: Should be <10 seconds total
2. **Tool call success rate**: Monitor error responses
3. **Confidence improvement**: Should see 0.2-0.3 increase with metrics
4. **Token usage**: Claude input tokens for each incident
5. **False positives**: Verify Claude's tool selections make sense

## Future Enhancements

- [ ] Add caching of tool responses
- [ ] Support for custom PromQL templates
- [ ] Grafana dashboard auto-generation
- [ ] Multi-stage verification (confidence > 0.8 → done)
- [ ] Feedback loop (was this diagnosis correct?)
- [ ] Cost optimization (fewer Claude calls)
