# test_planner_prometheus.py
from planner import plan_incident_analysis

# Test queries
test_cases = [
    {
        "query": "High latency and CPU spikes on API gateway at 14:30 UTC",
        "timestamp": "2024-01-15T14:30:00Z"
    },
    {
        "query": "Database connection errors and memory leaks at 09:15",
        "timestamp": "2024-01-15T09:15:00Z"
    },
    {
        "query": "5xx errors on user-service around 16:45",
        "timestamp": "2024-01-15T16:45:00Z"
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*60}")
    print(f"TEST CASE {i}: {test['query']}")
    print(f"{'='*60}")
    
    plan = plan_incident_analysis(test["query"], test["timestamp"])
    
    print(f"Incident Time: {plan.get('incident_time')}")
    print(f"Affected Services: {', '.join(plan.get('affected_services', []))}")
    print(f"Symptoms: {', '.join(plan.get('symptoms', []))}")
    print(f"Required Agents: {', '.join(plan.get('required_agents', []))}")
    
    if 'prometheus' in plan.get('required_agents', []):
        print(f"\nPrometheus Config:")
        prom_config = plan.get('prometheus_config', {})
        print(f"  Window: {prom_config.get('window_minutes')} minutes")
        print(f"  Target Services: {prom_config.get('target_services', [])}")
        print(f"  Metrics to Collect: {prom_config.get('metrics_to_collect', [])}")
    
    print(f"\nSearch Windows:")
    for source, window in plan.get('search_windows', {}).items():
        print(f"  {source}: {window}")
    
    print(f"Priority: {plan.get('priority')}")