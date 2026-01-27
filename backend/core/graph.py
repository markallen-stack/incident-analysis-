"""
LangGraph state machine for agentic incident analysis.
Orchestrates multiple agents with proper state management and decision gates.
"""

from typing import TypedDict, List, Dict, Literal, Annotated
from dataclasses import dataclass
from datetime import datetime
import operator

# State type definitions
@dataclass
class Evidence:
    """Single piece of evidence from any source"""
    source: str  # "image", "log", "rag"
    content: str
    timestamp: str
    confidence: float
    metadata: Dict

@dataclass
class TimelineEvent:
    """Single event in the incident timeline"""
    time: str
    event: str
    source: str
    confidence: float

@dataclass
class Hypothesis:
    """A root cause hypothesis"""
    id: str
    root_cause: str
    plausibility: float
    supporting_evidence: List[str]
    required_evidence: List[str]
    would_refute: List[str]

@dataclass
class VerificationResult:
    """Result of hypothesis verification"""
    hypothesis_id: str
    verdict: Literal["SUPPORTED", "INSUFFICIENT_EVIDENCE", "CONTRADICTED"]
    confidence: float
    evidence_summary: Dict
    contradictions: List[str]

# Main state
class IncidentAnalysisState(TypedDict):
    """
    Central state object passed between all agents.
    Each agent reads from and writes to this state.
    """
    # Input
    user_query: str
    dashboard_images: List[str]  # Base64 or file paths
    logs: List[Dict]
    timestamp: str
    
    # Planner output
    plan: Dict
    
    # Evidence collection (parallel)
    image_evidence: Annotated[List[Evidence], operator.add]
    log_evidence: Annotated[List[Evidence], operator.add]
    rag_evidence: Annotated[List[Evidence], operator.add]
    metrics_evidence: Annotated[List[Evidence], operator.add]
    dashboard_evidence: Annotated[List[Evidence], operator.add]
    
    # Timeline
    timeline: List[TimelineEvent]
    correlations: List[Dict]
    timeline_gaps: List[str]
    
    # Hypotheses
    hypotheses: List[Hypothesis]
    
    # Verification
    verification_results: Dict[str, VerificationResult]
    overall_confidence: float
    
    # Decision
    decision: Literal["answer", "refuse", "request_more_data"]
    final_response: Dict
    
    # Metadata
    errors: Annotated[List[str], operator.add]
    agent_history: Annotated[List[Dict], operator.add]


# Agent node functions
def planner_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Analyzes user query and creates execution plan.
    """
    print(f"🟢 [PLANNER AGENT] Starting")
    from agents.planner import plan_incident_analysis
    
    plan = plan_incident_analysis(
        query=state["user_query"],
        timestamp=state["timestamp"]
    )
    
    return {
        "plan": plan,
        "agent_history": [{"agent": "planner", "timestamp": datetime.now().isoformat()}]
    }


def image_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Analyzes dashboard screenshots.
    """
    print(f"🟢 [IMAGE AGENT] Starting")
    from agents.image_analyzer import analyze_dashboards
    
    if not state.get("dashboard_images"):
        return {
            "errors": ["No dashboard images provided"],
            "agent_history": [{"agent": "image", "status": "skipped"}]
        }
    
    evidence = analyze_dashboards(
        images=state["dashboard_images"],
        time_window=state["plan"].get("search_windows", {}).get("metrics")
    )
    
    return {
        "image_evidence": evidence,
        "agent_history": [{"agent": "image", "evidence_count": len(evidence)}]
    }


def log_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Retrieves and analyzes relevant logs.
    """
    print(f"🟢 [LOG AGENT] Starting")

    from agents.log_retriever import retrieve_logs
    
    evidence = retrieve_logs(
        logs=state["logs"],
        time_window=state["plan"].get("search_windows", {}).get("logs"),
        services=state["plan"].get("affected_services", [])
    )
    
    return {
        "log_evidence": evidence,
        "agent_history": [{"agent": "log", "evidence_count": len(evidence)}]
    }


def rag_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Retrieves historical incidents and runbooks.
    """

    print(f"🟢 [RAG AGENT] Starting")

    from agents.rag_retriever import retrieve_knowledge
    
    evidence = retrieve_knowledge(
        symptoms=state["plan"].get("symptoms", []),
        services=state["plan"].get("affected_services", [])
    )
    
    return {
        "rag_evidence": evidence,
        "agent_history": [{"agent": "rag", "evidence_count": len(evidence)}]
    }


# Update your prometheus_agent function in graph.py
def prometheus_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Collects system and application metrics from Prometheus.
    """
    print(f"🟢 [PROMETHEUS AGENT] Starting")
    
    from agents.prometheus_agent import PrometheusAgent

    
    try:
        plan = state.get("plan", {})
        prometheus_config = plan.get("prometheus_config", {})
        print(f"🔵 [PROMETHEUS AGENT] Config: {prometheus_config}")
        
        # Get configuration from plan
        window_minutes = prometheus_config.get("window_minutes", 35)
        target_services = prometheus_config.get("target_services", [])
        metrics_to_collect = prometheus_config.get("metrics_to_collect", [])
        prometheus_url = plan.get("prometheus_url", "http://localhost:9090")
        debug_mode = plan.get("debug_mode", True)
        agent = PrometheusAgent(url=prometheus_url, debug=debug_mode)
        
        # If no specific services from plan, use affected_services
        if not target_services:
            target_services = plan.get("affected_services", [])
        
        print(f"🔵 [PROMETHEUS AGENT] Starting collection:")
        print(f"   - Window: {window_minutes} minutes")
        print(f"   - Services: {target_services}")
        print(f"   - Metrics to collect: {metrics_to_collect}")
        
        # DEBUG: Check what parameters collect_incident_metrics accepts
        import inspect
        sig = inspect.signature(agent.collect_incident_metrics)
        print(f"🔵 [PROMETHEUS AGENT] Function signature: {sig}")
        
        # Call the function with correct parameters
        # Based on your earlier code, it might need 'jobs' instead of 'affected_services'
        evidence = agent.collect_incident_metrics(
            incident_time=state["timestamp"],
            window_minutes=window_minutes,
            jobs=target_services,
            detect_anomalies=True  # CHANGED: from affected_services to jobs
            # metrics_filter=metrics_to_collect,
            # prometheus_url=prometheus_url,
            # debug=debug_mode
        )
        
        print(f"🔵 [PROMETHEUS AGENT] Collection complete. Got {len(evidence)} evidence items")
        
        return {
            "metrics_evidence": evidence,
            "agent_history": [{
                "agent": "prometheus", 
                "timestamp": datetime.now().isoformat(),
                "evidence_count": len(evidence),
                "window_minutes": window_minutes,
                "target_services": target_services,
                "requested_metrics": metrics_to_collect,
                "collected_metrics": [e.metadata.get("metric") for e in evidence],
                "status": "success"
            }]
        }
    except Exception as e:
        error_msg = f"Prometheus agent error: {str(e)}"
        print(f"🔴 [PROMETHEUS AGENT ERROR] {error_msg}")
        import traceback
        traceback.print_exc()
        
        return {
            "metrics_evidence": [],
            "errors": [error_msg],
            "agent_history": [{
                "agent": "prometheus", 
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }]
        }
def grafana_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Retrieves dashboards and annotations from Grafana.
    """
    print(f"🟢 [GRAFANA AGENT] Starting")

    from agents.grafana_agent import analyze_grafana_incident
    
    evidence = analyze_grafana_incident(
        incident_time=state["timestamp"],
        window_minutes=30,
        dashboard_tags=state["plan"].get("affected_services", [])
    )
    
    return {
        "dashboard_evidence": evidence,
        "agent_history": [{"agent": "grafana", "evidence_count": len(evidence)}]
    }


def timeline_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Correlates all evidence into a timeline.
    """
    from agents.timeline_correlator import build_timeline
    
    all_evidence = (
        state.get("image_evidence", []) +
        state.get("log_evidence", []) +
        state.get("rag_evidence", []) +
        state.get("metrics_evidence", []) +
        state.get("dashboard_evidence", [])+
        state.get("rag_evidence", [])
    )
    
    timeline, correlations, gaps = build_timeline(all_evidence)
    
    return {
        "timeline": timeline,
        "correlations": correlations,
        "timeline_gaps": gaps,
        "agent_history": [{"agent": "timeline", "events": len(timeline)}]
    }


def hypothesis_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Generates root cause hypotheses.
    """
    from agents.hypothesis_generator import generate_hypotheses
    
    hypotheses = generate_hypotheses(
        timeline=state["timeline"],
        correlations=state["correlations"],
        all_evidence={
            "image": state.get("image_evidence", []),
            "log": state.get("log_evidence", []),
            "rag": state.get("rag_evidence", [])
        }
    )
    
    return {
        "hypotheses": hypotheses,
        "agent_history": [{"agent": "hypothesis", "count": len(hypotheses)}]
    }


def verifier_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Verifies each hypothesis against evidence.
    CRITICAL: This is the quality gate.
    """
    from agents.verifier import EvidenceVerifier

    verifier=EvidenceVerifier()
    verification_results, overall_confidence = verifier.verify_hypotheses(
        hypotheses=state["hypotheses"],
        evidence={
            "image": state.get("image_evidence", []),
            "log": state.get("log_evidence", []),
            "rag": state.get("rag_evidence", []),
            "metrics": state.get("metrics_evidence", []),
            "dashboard": state.get("dashboard_evidence", [])
        },
        timeline=state["timeline"]
    )
    
    return {
        "verification_results": verification_results,
        "overall_confidence": overall_confidence,
        "agent_history": [{"agent": "verifier", "confidence": overall_confidence}]
    }


def decision_gate_agent(state: IncidentAnalysisState) -> IncidentAnalysisState:
    """
    Makes final decision: answer, refuse, or request more data.
    """
    from agents.decision_gate import make_decision
    
    decision, final_response = make_decision(
        verification_results=state["verification_results"],
        overall_confidence=state["overall_confidence"],
        hypotheses=state["hypotheses"],
        timeline=state["timeline"],
        gaps=state.get("timeline_gaps", [])
    )
    
    return {
        "decision": decision,
        "final_response": final_response,
        "agent_history": [{"agent": "decision_gate", "decision": decision}]
    }


# Conditional routing
def should_collect_evidence(state: IncidentAnalysisState) -> bool:
    """Check if we have a valid plan to proceed."""
    return bool(state.get("plan"))


def should_verify(state: IncidentAnalysisState) -> bool:
    """Check if we have hypotheses to verify."""
    return len(state.get("hypotheses", [])) > 0


def route_after_verification(state: IncidentAnalysisState) -> str:
    """
    Decide next step based on confidence.
    High confidence → decision_gate
    Medium/low → might need more data or should refuse
    """
    confidence = state.get("overall_confidence", 0.0)
    
    if confidence >= 0.7:
        return "decision_gate"
    elif confidence >= 0.5:
        return "decision_gate"  # Will likely request more data
    else:
        return "decision_gate"  # Will likely refuse


# Build the graph
from langgraph.graph import StateGraph, END

def build_incident_analysis_graph():
    """
    Constructs the full LangGraph workflow.
    
    Flow:
    1. Planner analyzes query
    2. Parallel evidence collection (image, log, rag, metrics, dashboard)
    3. Timeline correlation
    4. Hypothesis generation
    5. Verification (CRITICAL GATE)
    6. Decision gate (answer/refuse/request)
    """
    
    workflow = StateGraph(IncidentAnalysisState)
    
    # Add nodes
    workflow.add_node("planner", planner_agent)
    workflow.add_node("image", image_agent)
    workflow.add_node("log", log_agent)
    workflow.add_node("rag", rag_agent)
    workflow.add_node("prometheus", prometheus_agent)
    workflow.add_node("grafana", grafana_agent)
    workflow.add_node("timeline", timeline_agent)
    workflow.add_node("hypothesis", hypothesis_agent)
    workflow.add_node("verifier", verifier_agent)
    workflow.add_node("decision_gate", decision_gate_agent)
    
    # Define edges
    workflow.set_entry_point("planner")
    
    # After planner → parallel evidence collection
    workflow.add_edge("planner", "image")
    workflow.add_edge("planner", "log")
    workflow.add_edge("planner", "rag")
    workflow.add_edge("planner", "prometheus")
    # workflow.add_edge("planner", "grafana")
    
    # All evidence collectors → timeline
    workflow.add_edge("image", "timeline")
    workflow.add_edge("log", "timeline")
    workflow.add_edge("rag", "timeline")
    workflow.add_edge("prometheus", "timeline")
    workflow.add_edge("grafana", "timeline")
    
    # Timeline → hypothesis → verifier → decision_gate
    workflow.add_edge("timeline", "hypothesis")
    workflow.add_edge("hypothesis", "verifier")
    workflow.add_edge("verifier", "decision_gate")
    workflow.add_edge("decision_gate", END)
    
    return workflow.compile()


# Usage example
if __name__ == "__main__":
    graph = build_incident_analysis_graph()
    
    # Example invocation
    initial_state = {
        "user_query": "API outage at 14:32 UTC with 500 errors",
        "dashboard_images": ["path/to/grafana_screenshot.png"],
        "logs": [],  # Would be loaded from DB
        "timestamp": "2024-01-15T14:32:00Z",
        "image_evidence": [],
        "log_evidence": [],
        "rag_evidence": [],
        "metrics_evidence": [],
        "dashboard_evidence": [],
        "errors": [],
        "agent_history": []
    }
    
    # Run the graph
    result = graph.invoke(initial_state)
    
    print(f"Decision: {result['decision']}")
    print(f"Confidence: {result['overall_confidence']}")
    print(f"Response: {result['final_response']}")