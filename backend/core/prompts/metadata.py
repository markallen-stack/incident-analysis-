AGENT_METADATA = {
    "planner": {
        "role": "Query decomposition and task planning",
        "inputs": ["user_query"],
        "outputs": ["plan"]
    },
    "image": {
        "role": "Dashboard analysis",
        "inputs": ["dashboard_images", "time_window"],
        "outputs": ["metric_observations"]
    },
    "log": {
        "role": "Log retrieval and pattern detection",
        "inputs": ["log_database", "time_window"],
        "outputs": ["relevant_logs"]
    },
    "rag": {
        "role": "Historical incident and runbook retrieval",
        "inputs": ["symptoms", "services"],
        "outputs": ["similar_incidents", "runbooks"]
    },
    "timeline": {
        "role": "Event correlation and timeline construction",
        "inputs": ["image_output", "log_output", "rag_output"],
        "outputs": ["timeline", "correlations"]
    },
    "hypothesis": {
        "role": "Root cause hypothesis generation",
        "inputs": ["timeline", "correlations"],
        "outputs": ["hypotheses"]
    },
    "verifier": {
        "role": "Evidence-based hypothesis verification",
        "inputs": ["hypotheses", "all_evidence"],
        "outputs": ["verification_results", "confidence"]
    },
    "decision_gate": {
        "role": "Final decision and output formatting",
        "inputs": ["verification_results"],
        "outputs": ["final_response"]
    }
}