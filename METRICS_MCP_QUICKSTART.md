# Quick Reference: Intelligent Metrics with MCP & Claude

## One-Liner Summary
Agents now call Claude with MCP tools to intelligently query Prometheus/Grafana when they need more evidence during incident analysis.

## Files Created/Modified

### New Files
```
backend/core/mcp_servers/prometheus_grafana_server.py     (MCP server with 7 tools)
backend/core/agents/llm_metrics_querier.py               (Claude integration)
backend/core/mcp_servers/__init__.py                      
INTELLIGENT_METRICS_GUIDE.md                              (Detailed guide)
```

### Modified Files
```
backend/core/agents/hypothesis_generator.py              (+generate_hypotheses_with_metrics)
backend/core/agents/verifier.py                          (+verify_with_metrics_enrichment)
backend/requirements.txt                                 (+mcp, prometheus-client, requests)
```

## How It Works

1. **Agent needs more info** → Calls `intelligent_metrics_query(context, incident_time)`
2. **LLM sees 7 tools** → Decides which Prometheus/Grafana queries to run
3. **Tools execute** → APIs called directly, data returned as Evidence
4. **Claude synthesizes** → Creates structured findings
5. **Agent uses evidence** → For hypothesis verification

## Use in Your Code

### Hypothesis Generation with Metrics
```python
from core.agents.hypothesis_generator import HypothesisGenerator

gen = HypothesisGenerator()
hypotheses = gen.generate_hypotheses_with_metrics(
    timeline=timeline,
    correlations=correlations,
    all_evidence=evidence,
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["api", "db"]
)
```

### Verification with Metrics Enrichment
```python
from core.agents.verifier import Verifier

verifier = Verifier()
results, confidence = verifier.verify_with_metrics_enrichment(
    hypotheses=hypotheses,
    evidence=evidence,
    timeline=timeline,
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["api", "db"]
)
```

### Direct Metrics Query
```python
from core.agents.llm_metrics_querier import intelligent_metrics_query

evidence = intelligent_metrics_query(
    context="Check if CPU was spiking during outage",
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["api-server"]
)
```

## MCP Tools Available

| Tool | Purpose |
|------|---------|
| `query_prometheus_instant` | Get current metric value |
| `query_prometheus_range` | Get metric time series |
| `get_prometheus_alerts` | Fetch active alerts |
| `get_prometheus_targets` | List monitored services |
| `search_grafana_dashboards` | Find relevant dashboards |
| `get_grafana_dashboard` | Get dashboard panels/config |
| `get_grafana_annotations` | Get incident markers/events |

## Environment Setup

```bash
# Required
export ANTHROPIC_API_KEY=sk-...

# For Prometheus/Grafana (use defaults if running locally)
export PROMETHEUS_URL=http://prometheus:9090
export GRAFANA_URL=http://grafana:3000
export GRAFANA_API_KEY=your-api-key  # Optional but recommended
```

## Get Grafana API Key

1. Open http://localhost:3000
2. Login as admin/admin
3. Settings (gear icon) → API Keys
4. Create new key with "Editor" role
5. Copy and set as `GRAFANA_API_KEY`

## Testing

```python
# Test the MCP server
from core.agents.llm_metrics_querier import IntelligentMetricsQueryer

querier = IntelligentMetricsQueryer()
evidence = querier.query_with_tools(
    context="Is the database under load?",
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["database"]
)

for ev in evidence:
    print(f"Found: {ev.source} (confidence: {ev.confidence})")
```

## Architecture Diagram

```
┌─────────────────────────────────┐
│   Incident Analysis Graph       │
├─────────────────────────────────┤
│  ├─ Image Agent                 │
│  ├─ Log Agent                   │
│  ├─ RAG Agent                   │
│  ├─ Hypothesis Generator  ───┐  │
│  ├─ Verifier             ───┼─→ LLM Query
│  └─ Timeline Correlator  ───┘  │
└─────────────────────────────────┘
              ↓
        ┌─────────────────────┐
        │ LLM (Claude)        │
        │ with MCP Tools      │
        └────────┬────────────┘
                 ↓
        ┌─────────────────────┐
        │  7 MCP Tools        │
        ├─────────────────────┤
        │ Prometheus APIs     │
        │ Grafana APIs        │
        └─────────────────────┘
```

## Key Concepts

- **MCP** = Model Context Protocol. Claude-native protocol for tools.
- **Tool Calling** = Claude decides which tools to use and calls them.
- **Evidence** = Structured output with confidence scores.
- **Iterative** = Claude can make multiple tool calls per query (up to 10).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Claude can't reach Prometheus | Check `PROMETHEUS_URL`, ensure containers running |
| Grafana queries fail | Verify `GRAFANA_API_KEY` is set and valid |
| "No tool use in response" | Claude may not recognize query needs metrics. Be explicit. |
| Slow queries | Adjust incident time window or limit affected_services |

## Next Steps

1. ✅ Install dependencies: `pip install mcp prometheus-client requests`
2. ✅ Set `ANTHROPIC_API_KEY`
3. ✅ Start Prometheus/Grafana: `docker-compose up -d`
4. ✅ (Optional) Set Grafana API key
5. Test with sample incident report
6. Monitor Claude's tool calls in logs
