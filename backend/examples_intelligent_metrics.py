"""
Example: Using Intelligent Metrics Querying in the Incident Analysis Graph

This shows how to enable Claude-powered metrics querying for your agents.
The agents will automatically query Prometheus/Grafana when they need evidence.
"""

from core.graph import build_incident_analysis_graph
from core.agents.hypothesis_generator import HypothesisGenerator
from core.agents.verifier import Verifier
from core.agents.llm_metrics_querier import intelligent_metrics_query

# ============================================================================
# Example 1: Automatic Metrics Enrichment (Recommended)
# ============================================================================

def analyze_incident_with_intelligent_metrics(
    query: str,
    incident_time: str,
    dashboard_images: list,
    logs: list,
    affected_services: list = None
):
    """
    Full incident analysis with intelligent metrics querying.
    Agents will automatically use Claude to query Prometheus/Grafana as needed.
    """
    graph = build_incident_analysis_graph()
    
    initial_state = {
        "user_query": query,
        "timestamp": incident_time,
        "dashboard_images": dashboard_images,
        "logs": logs,
        "image_evidence": [],
        "log_evidence": [],
        "rag_evidence": [],
        "metrics_evidence": [],
        "dashboard_evidence": [],
        "errors": [],
        "agent_history": []
    }
    
    result = graph.invoke(initial_state)
    
    return {
        "decision": result["decision"],
        "confidence": result["overall_confidence"],
        "response": result["final_response"],
        "hypotheses": result["hypotheses"],
        "verification": result["verification_results"],
        "timeline": result["timeline"],
        "agent_history": result["agent_history"]
    }


# ============================================================================
# Example 2: Hypothesis Generation with Metrics
# ============================================================================

def generate_hypotheses_with_metrics(
    timeline,
    correlations,
    all_evidence,
    incident_time: str,
    affected_services: list
):
    """
    Generate hypotheses and validate with intelligent metrics queries.
    Claude will query Prometheus/Grafana to support/refute hypotheses.
    """
    generator = HypothesisGenerator()
    
    # This internally calls Claude with Prometheus/Grafana tools
    hypotheses = generator.generate_hypotheses_with_metrics(
        timeline=timeline,
        correlations=correlations,
        all_evidence=all_evidence,
        incident_time=incident_time,
        affected_services=affected_services
    )
    
    return hypotheses


# ============================================================================
# Example 3: Verification with Metrics Enrichment
# ============================================================================

def verify_with_enriched_metrics(
    hypotheses,
    evidence,
    timeline,
    incident_time: str,
    affected_services: list
):
    """
    Verify hypotheses and auto-query metrics for low-confidence cases.
    If initial verification < 70% confidence, Claude queries metrics
    to gather more evidence.
    """
    verifier = Verifier()
    
    results, confidence = verifier.verify_with_metrics_enrichment(
        hypotheses=hypotheses,
        evidence=evidence,
        timeline=timeline,
        incident_time=incident_time,
        affected_services=affected_services
    )
    
    return results, confidence


# ============================================================================
# Example 4: Direct Metrics Query
# ============================================================================

def query_metrics_for_diagnosis(
    diagnostic_question: str,
    incident_time: str,
    affected_services: list
):
    """
    Directly ask Claude to diagnose using metrics.
    Example questions:
    - "Is the database under high load?"
    - "Did CPU spike during the outage?"
    - "Are memory leaks apparent from metrics?"
    """
    evidence = intelligent_metrics_query(
        context=diagnostic_question,
        incident_time=incident_time,
        affected_services=affected_services
    )
    
    # Evidence objects include Claude's synthesis
    for ev in evidence:
        print(f"\n📊 Metrics Analysis")
        print(f"Source: {ev.source}")
        print(f"Confidence: {ev.confidence * 100:.0f}%")
        print(f"Findings:\n{ev.content}")
        print(f"Metadata: {ev.metadata}")
    
    return evidence


# ============================================================================
# Example 5: Custom Agent Using Metrics Tools
# ============================================================================

def custom_agent_with_metrics(context_description: str):
    """
    Create a custom agent that uses metrics querying.
    The agent can decide what metrics are needed based on the context.
    """
    from core.agents.llm_metrics_querier import IntelligentMetricsQueryer
    
    querier = IntelligentMetricsQueryer()
    
    # Query with maximum iterations for thorough analysis
    evidence = querier.query_with_tools(
        context=context_description,
        incident_time="2024-01-15T14:32:00Z",
        affected_services=["api", "database", "cache"],
        max_iterations=10  # Allow Claude to make multiple tool calls
    )
    
    return evidence


# ============================================================================
# Full Example: API Outage Analysis
# ============================================================================

def analyze_api_outage_example():
    """
    Complete example analyzing an API outage incident.
    """
    
    # Step 1: Collect initial information
    incident_info = {
        "query": "API server crashed at 14:32 UTC returning 500 errors to all users",
        "timestamp": "2024-01-15T14:32:00Z",
        "affected_services": ["api-server", "database", "load-balancer"],
        "dashboard_images": ["path/to/grafana_screenshot.png"],
        "logs": [
            {"timestamp": "2024-01-15T14:32:15Z", "level": "ERROR", "message": "Connection pool exhausted"},
            {"timestamp": "2024-01-15T14:32:17Z", "level": "ERROR", "message": "Query timeout after 30s"},
            {"timestamp": "2024-01-15T14:32:25Z", "level": "FATAL", "message": "Service shutdown"},
        ]
    }
    
    # Step 2: Run analysis with intelligent metrics querying
    print("🔍 Analyzing incident with intelligent metrics querying...\n")
    
    result = analyze_incident_with_intelligent_metrics(
        query=incident_info["query"],
        incident_time=incident_info["timestamp"],
        dashboard_images=incident_info["dashboard_images"],
        logs=incident_info["logs"],
        affected_services=incident_info["affected_services"]
    )
    
    # Step 3: Display results
    print(f"\n✅ Analysis Complete")
    print(f"Decision: {result['decision']}")
    print(f"Confidence: {result['confidence'] * 100:.0f}%")
    print(f"\nTop Hypotheses:")
    for h in result["hypotheses"][:3]:
        print(f"  • {h.root_cause} ({h.plausibility * 100:.0f}% plausible)")
    
    print(f"\nVerification Results:")
    for hyp_id, verification in result["verification"].items():
        print(f"  • {hyp_id}: {verification.verdict}")
    
    print(f"\nTimeline:")
    for event in result["timeline"][:5]:
        print(f"  {event['time']}: {event['event']}")
    
    return result


# ============================================================================
# Environment Check
# ============================================================================

def check_setup():
    """Verify all required services and env vars are set up."""
    import os
    from urllib.request import urlopen
    
    checks = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY") is not None,
        "Prometheus (http://prometheus:9090)": False,
        "Grafana (http://grafana:3000)": False,
        "GRAFANA_API_KEY": os.getenv("GRAFANA_API_KEY") is not None,
    }
    
    # Check services
    try:
        urlopen("http://prometheus:9090/-/healthy", timeout=2)
        checks["Prometheus (http://prometheus:9090)"] = True
    except:
        pass
    
    try:
        urlopen("http://grafana:3000/api/health", timeout=2)
        checks["Grafana (http://grafana:3000)"] = True
    except:
        pass
    
    print("\n🔧 Setup Status:")
    for check, status in checks.items():
        symbol = "✅" if status else "❌"
        print(f"  {symbol} {check}")
    
    return all(checks.values())


if __name__ == "__main__":
    # Run example
    print("🚀 Intelligent Metrics Querying Example\n")
    
    # Check setup first
    if not check_setup():
        print("\n⚠️  Some services are not configured. Setup:")
        print("  1. export ANTHROPIC_API_KEY=sk-...")
        print("  2. docker-compose up -d")
        exit(1)
    
    # Run analysis
    result = analyze_api_outage_example()
    
    # Pretty print final response
    print(f"\n📋 Final Response:")
    print(result["response"])
