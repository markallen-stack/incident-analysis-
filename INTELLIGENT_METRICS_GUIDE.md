# Intelligent Metrics Querying via MCP and Claude

## Architecture

The system now enables intelligent, on-demand metrics querying through a three-tier architecture:

```
Agent needs more info
    ↓
Agent calls intelligent_metrics_query()
    ↓
LLM (Claude) analyzes what data is needed
    ↓
Claude calls MCP tools (Prometheus/Grafana API wrappers)
    ↓
Tools return data, Claude synthesizes into Evidence
    ↓
Agent continues with enriched evidence
```

## Components

### 1. MCP Server (`core/mcp_servers/prometheus_grafana_server.py`)

Exposes these tools to Claude:

- **query_prometheus_instant** - Execute instant PromQL queries
- **query_prometheus_range** - Get time series data
- **get_prometheus_alerts** - Fetch active alerts
- **get_prometheus_targets** - List monitored targets
- **search_grafana_dashboards** - Find dashboards by name/tags
- **get_grafana_dashboard** - Fetch dashboard definition
- **get_grafana_annotations** - Get annotations in time range

### 2. LLM Query Utility (`core/agents/llm_metrics_querier.py`)

**IntelligentMetricsQueryer** class:
- Maintains conversation with Claude
- Claude decides which tools to call based on incident context
- Iteratively refines queries until confident (max 10 iterations)
- Returns Evidence objects

**Key function:**
```python
def intelligent_metrics_query(
    context: str,              # What we're trying to understand
    incident_time: str,        # ISO timestamp
    affected_services: List[str]  # Services to focus on
) -> List[Evidence]:
```

### 3. Enhanced Agents

**Hypothesis Generator** (`hypothesis_generator.py`):
```python
# New method
hypotheses = generator.generate_hypotheses_with_metrics(
    timeline=timeline,
    correlations=correlations,
    all_evidence=evidence,
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["api", "database"]
)
```

**Verifier** (`verifier.py`):
```python
# New method - auto-enriches low-confidence hypotheses
results, confidence = verifier.verify_with_metrics_enrichment(
    hypotheses=hypotheses,
    evidence=evidence,
    timeline=timeline,
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["api", "database"]
)
```

## Usage Example

### Basic Usage (Automatic)

The agents will automatically use intelligent querying when needed:

```python
from core.graph import build_incident_analysis_graph

graph = build_incident_analysis_graph()

state = {
    "user_query": "API crashed with 500 errors at 14:32",
    "timestamp": "2024-01-15T14:32:00Z",
    "dashboard_images": [...],
    "logs": [...],
    ...
}

result = graph.invoke(state)
# Agents will auto-query metrics as needed
```

### Advanced Usage (Explicit)

Query metrics directly in your agent:

```python
from core.agents.llm_metrics_querier import intelligent_metrics_query

evidence = intelligent_metrics_query(
    context="Is CPU usage spiking? Check for memory leaks.",
    incident_time="2024-01-15T14:32:00Z",
    affected_services=["api-server", "cache"]
)

for ev in evidence:
    print(f"Source: {ev.source}")
    print(f"Confidence: {ev.confidence}")
    print(f"Content: {ev.content}")
```

## Configuration

Set these environment variables:

```bash
# Prometheus/Grafana
PROMETHEUS_URL=http://prometheus:9090
GRAFANA_URL=http://grafana:3000
GRAFANA_API_KEY=your-grafana-api-key

# Claude
ANTHROPIC_API_KEY=sk-...
```

## What Claude Sees

When Claude is called, it has access to:

1. **Incident context** - What problem we're solving
2. **Incident time window** - 30min before/after incident
3. **Affected services** - Which systems to focus on
4. **Available tools** - 7 Prometheus/Grafana query tools

Claude decides intelligently:
- Which metrics to query based on symptoms
- What time ranges to examine
- Which dashboards might be relevant
- How to interpret and correlate findings

## Example Interaction

```
Agent: "We have a hypothesis that the database connection pool was exhausted. 
        But we don't have metrics evidence yet. Let me query Prometheus/Grafana."

Claude (with tools):
1. Calls: query_prometheus_range(
     query="pg_stat_activity_count",
     start="2024-01-15T14:00Z",
     end="2024-01-15T15:00Z"
   )
   → Returns: Connection count reached 100/100 at 14:32

2. Calls: search_grafana_dashboards(
     query="database",
     tags=["postgres"]
   )
   → Returns: "PostgreSQL Dashboard" UID: abc123

3. Calls: get_grafana_dashboard(dashboard_uid="abc123")
   → Returns: Panel showing connection count, queries/sec, query duration

4. Calls: get_prometheus_alerts()
   → Returns: "PG_ConnectionPoolExhausted" alert firing at 14:32

Claude: "Connection pool was definitely exhausted. Found 3 independent sources 
         confirming this. Evidence confidence: 0.95"

Agent: Uses this enriched evidence in hypothesis verification
```

## Benefits

✅ **Intelligent querying** - Claude knows what metrics matter for this incident
✅ **Evidence-based** - Automatically validates/refutes hypotheses with data
✅ **Efficient** - Only queries what's needed, not pre-defined metrics
✅ **Explainable** - Claude explains why it queried each metric
✅ **Iterative** - Can ask follow-up questions and drill down
✅ **Integrated** - Seamlessly feeds into existing graph structure

## Next Steps

1. Start Prometheus and Grafana:
   ```bash
   docker-compose up -d prometheus grafana
   ```

2. Generate Grafana API key:
   - Go to http://localhost:3000 → Settings → API keys
   - Create new key, set GRAFANA_API_KEY env var

3. Configure Prometheus scrape targets for your services

4. Test with a sample incident - agents will auto-query metrics as needed

5. Check Claude's reasoning in agent logs to see what queries were made
