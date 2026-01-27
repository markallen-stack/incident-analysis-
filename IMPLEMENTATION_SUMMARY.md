# Implementation Summary: Intelligent Metrics Querying with MCP & Claude

## What Was Built

You now have a complete system where **Claude intelligently queries Prometheus and Grafana** during incident analysis. Instead of agents blindly collecting pre-defined metrics, Claude *decides what to query* based on the incident context.

## Architecture

### Three-Layer System

```
Layer 1: Agents
├─ hypothesis_generator.generate_hypotheses_with_metrics()
├─ verifier.verify_with_metrics_enrichment()
└─ Any custom agent using intelligent_metrics_query()

        ↓ (when they need evidence)

Layer 2: LLM Query Utility
├─ IntelligentMetricsQueryer class
├─ Maintains Claude conversation
├─ Handles tool calling loop (up to 10 iterations)
└─ Synthesizes results into Evidence objects

        ↓ (Claude calls tools)

Layer 3: MCP Server + Direct API Calls
├─ MCP tool definitions (7 tools)
├─ Direct HTTP calls to Prometheus API
├─ Direct HTTP calls to Grafana API
└─ Returns raw data back to Claude
```

## Files Created

| File | Purpose |
|------|---------|
| `backend/core/mcp_servers/prometheus_grafana_server.py` | MCP server with 7 tools |
| `backend/core/agents/llm_metrics_querier.py` | Claude integration + tool executor |
| `backend/examples_intelligent_metrics.py` | Example usage |
| `INTELLIGENT_METRICS_GUIDE.md` | Detailed technical guide |
| `METRICS_MCP_QUICKSTART.md` | Quick reference |

## Files Modified

| File | Changes |
|------|---------|
| `backend/core/agents/hypothesis_generator.py` | +`generate_hypotheses_with_metrics()` |
| `backend/core/agents/verifier.py` | +`verify_with_metrics_enrichment()` |
| `backend/requirements.txt` | +mcp, prometheus-client, requests |

## How It Works (Step by Step)

### Example: API Outage

```
1. Agent gets hypothesis: "Database connection pool exhausted"
   (But no metrics evidence yet)

2. Agent calls: intelligent_metrics_query(
     context="Check if DB connection pool was exhausted",
     incident_time="2024-01-15T14:32:00Z",
     affected_services=["database"]
   )

3. Claude receives the context + 7 available tools:
   - query_prometheus_instant()
   - query_prometheus_range()
   - get_prometheus_alerts()
   - search_grafana_dashboards()
   - get_grafana_dashboard()
   - get_grafana_annotations()
   - get_prometheus_targets()

4. Claude decides: "I need to check DB connection metrics"
   Tool call #1: query_prometheus_range(
     query="pg_stat_activity_count",
     start="2024-01-15T14:00Z",
     end="2024-01-15T15:00Z"
   )
   Result: [Shows connection count hit 100/100 at 14:32]

5. Claude: "Good! Found spike. Let me verify with dashboard"
   Tool call #2: search_grafana_dashboards(
     query="postgres"
   )
   Result: [Returns PostgreSQL monitoring dashboard]

6. Claude: "Let me get the actual dashboard panels"
   Tool call #3: get_grafana_dashboard(
     dashboard_uid="abc123"
   )
   Result: [Shows 5 panels with connection pool data]

7. Claude: "Strong evidence found. Let me check for alerts"
   Tool call #4: get_prometheus_alerts()
   Result: [PG_ConnectionPoolExhausted alert firing]

8. Claude synthesizes:
   "Connection pool exhausted at 14:32.
    Found in 4 independent sources: metrics spike, 
    dashboard panels, Grafana annotations, Prometheus alert.
    Confidence: 0.95"

9. Returns: Evidence object with findings
   - source: "llm_metrics_analysis"
   - content: Full analysis text
   - confidence: 0.95
   - metadata: {incident_time, services, iterations: 4}

10. Agent uses this evidence in hypothesis verification
    Initial plausibility 0.6 → Now 0.95 with metric evidence
```

## The 7 MCP Tools

Claude has access to:

1. **query_prometheus_instant** - Instant queries (e.g., "current CPU?")
2. **query_prometheus_range** - Time series (e.g., "CPU over 30 min?")
3. **get_prometheus_alerts** - What's alerting right now?
4. **get_prometheus_targets** - What services are monitored?
5. **search_grafana_dashboards** - Find dashboards by name/tags
6. **get_grafana_dashboard** - Get dashboard panel definitions
7. **get_grafana_annotations** - Get incident markers in time range

## Usage Patterns

### Pattern 1: Auto-Enrichment (Simplest)

```python
# Just use the new methods - they auto-query metrics when needed
generator = HypothesisGenerator()
hypotheses = generator.generate_hypotheses_with_metrics(
    timeline=timeline,
    correlations=correlations,
    all_evidence=evidence,
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["api", "db"]
)
# Claude automatically queries metrics, returns enriched hypotheses
```

### Pattern 2: Manual Query

```python
# Explicitly ask Claude to diagnose
evidence = intelligent_metrics_query(
    context="Is the database under high load?",
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["database"]
)
```

### Pattern 3: Low-Confidence Enrichment

```python
# Automatically query metrics if confidence is <70%
results, confidence = verifier.verify_with_metrics_enrichment(
    hypotheses=hypotheses,
    evidence=evidence,
    timeline=timeline,
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["api", "db"]
)
# Returns higher confidence due to metric validation
```

## Key Advantages

✅ **Intelligent** - Claude knows what matters for *this* incident
✅ **Efficient** - Only queries needed metrics, not pre-defined ones
✅ **Iterative** - Can make multiple queries per analysis (up to 10)
✅ **Explainable** - You see Claude's reasoning in logs
✅ **Evidence-Based** - Automatically validates/refutes hypotheses
✅ **Confident** - Confidence scores increase with metric validation
✅ **Integrated** - Works seamlessly with existing graph

## Configuration

Required:
```bash
export ANTHROPIC_API_KEY=sk-...
```

Optional but recommended:
```bash
export PROMETHEUS_URL=http://prometheus:9090
export GRAFANA_URL=http://grafana:3000
export GRAFANA_API_KEY=your-api-key
```

## Testing

```bash
# Run the example
cd backend
python examples_intelligent_metrics.py

# Or test a single query
python -c "
from core.agents.llm_metrics_querier import intelligent_metrics_query
from datetime import datetime, timedelta

evidence = intelligent_metrics_query(
    context='Is CPU usage abnormally high?',
    incident_time=datetime.utcnow().isoformat(),
    affected_services=['api-server']
)

for ev in evidence:
    print(f'Confidence: {ev.confidence}')
    print(f'Finding: {ev.content}')
"
```

## What Happens Behind the Scenes

When `intelligent_metrics_query()` is called:

1. **IntelligentMetricsQueryer** creates Anthropic client
2. Formats system prompt with incident context + time window
3. Calls Claude with tool definitions
4. Claude responds with tool calls (if needed)
5. Each tool call is executed against Prometheus/Grafana APIs
6. Results are added back to Claude's conversation
7. Claude iterates (up to 10 times) refining queries
8. When Claude says "I'm done", we extract the findings
9. Wrap findings in Evidence objects with confidence
10. Return to agent

## Integration with Graph

The agents automatically use this when they detect insufficient evidence:

- **Hypothesis Generator**: Auto-queries if hypotheses need validation
- **Verifier**: Auto-queries if confidence < 70%
- **Custom Agents**: Explicit call to `intelligent_metrics_query()`

## Next Steps

1. **Set Anthropic API key**
   ```bash
   export ANTHROPIC_API_KEY=sk-...
   ```

2. **Start services** (if not already running)
   ```bash
   cd /Users/eliteit/Documents/incident_rag
   docker-compose up -d prometheus grafana
   ```

3. **Generate Grafana API key** (optional but recommended)
   - Visit http://localhost:3000
   - Login as admin/admin
   - Settings → API Keys → Create
   - Export GRAFANA_API_KEY

4. **Test it**
   ```bash
   python backend/examples_intelligent_metrics.py
   ```

5. **Try a real incident**
   - Submit an incident report to your API
   - Watch agents auto-query metrics
   - Check logs for Claude's tool calls

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Claude returned empty response" | Check ANTHROPIC_API_KEY is set |
| Prometheus queries fail | Ensure containers running: `docker ps` |
| Grafana returns 403 | Verify GRAFANA_API_KEY is valid |
| Slow queries | Increase Claude max_iterations or reduce services |
| "Tool not found" | Ensure MCP tools are registered in IntelligentMetricsQueryer |

## Performance Tips

- **Time Window**: Default 30min before/after incident - adjust if needed
- **Affected Services**: Limit to 2-3 services for faster queries
- **Max Iterations**: 10 is default - reduce to 5 for speed
- **Caching**: Consider caching Prometheus queries if repeated

## Architecture Benefits

This design is superior to static metrics collection because:

1. **Context-Aware** - Claude understands the incident before querying
2. **Adaptive** - Different incidents get different metrics
3. **Efficient** - Only queries what's needed
4. **Transparent** - You see Claude's reasoning
5. **Iterative** - Can drill down with follow-up queries
6. **Conversational** - Claude can explain findings naturally

## See Also

- `INTELLIGENT_METRICS_GUIDE.md` - Detailed guide
- `METRICS_MCP_QUICKSTART.md` - Quick reference
- `backend/examples_intelligent_metrics.py` - Code examples
