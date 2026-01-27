"""
Automated evaluation of the incident analysis system.

Tests the system on synthetic incidents and measures:
1. Decision accuracy (answer/refuse/request_data)
2. Confidence calibration
3. Evidence citation quality
4. Refusal appropriateness
"""

import json
from typing import Dict, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvaluationResult:
    """Result for a single incident evaluation"""
    incident_id: str
    expected_verdict: str
    actual_verdict: str
    expected_confidence: float
    actual_confidence: float
    correct_decision: bool
    confidence_delta: float
    cited_sources: List[str]
    missing_citations: List[str]
    false_claims: List[str]


class IncidentAnalysisEvaluator:
    """
    Evaluates the incident analysis system on synthetic data.
    """
    
    def __init__(self, graph, dataset_path: str):
        """
        Args:
            graph: Compiled LangGraph instance
            dataset_path: Path to incidents.json
        """
        self.graph = graph
        self.dataset = self._load_dataset(dataset_path)
    
    def _load_dataset(self, path: str) -> Dict:
        """Load synthetic incident dataset"""
        with open(path) as f:
            return json.load(f)
    
    def run_evaluation(self) -> Dict:
        """
        Runs evaluation on all incidents in dataset.
        
        Returns:
            Dictionary with evaluation metrics
        """
        results = []
        
        for incident in self.dataset["incidents"]:
            print(f"\n{'='*60}")
            print(f"Evaluating {incident['id']}: {incident['name']}")
            print(f"{'='*60}")
            
            result = self._evaluate_single_incident(incident)
            results.append(result)
            
            self._print_incident_result(result)
        
        # Calculate aggregate metrics
        metrics = self._calculate_metrics(results)
        self._print_summary(metrics)
        
        return {
            "individual_results": results,
            "aggregate_metrics": metrics
        }
    
    def _evaluate_single_incident(self, incident: Dict) -> EvaluationResult:
        """
        Evaluates system on a single incident.
        """
        # Prepare state
        initial_state = {
            "user_query": incident["user_query"],
            "dashboard_images": [],  # Would load actual images
            "logs": incident["logs"],
            "timestamp": incident["timestamp"],
            "image_evidence": [],
            "log_evidence": [],
            "rag_evidence": [],
            "errors": [],
            "agent_history": []
        }
        
        # Mock evidence from incident data (in real system, agents would extract this)
        image_evidence = self._mock_image_evidence(incident)
        log_evidence = self._mock_log_evidence(incident)
        rag_evidence = self._mock_rag_evidence(incident)
        
        initial_state.update({
            "image_evidence": image_evidence,
            "log_evidence": log_evidence,
            "rag_evidence": rag_evidence
        })
        
        # Run graph (skipping early stages since we're mocking evidence)
        # In production, would run full graph
        result = self._run_verification_and_decision(
            initial_state,
            incident
        )
        
        # Compare with expected
        expected_verdict = incident["expected_verdict"]
        actual_verdict = result["decision"].upper()
        
        # Check if decision is correct
        correct = self._is_decision_correct(
            expected=expected_verdict,
            actual=actual_verdict,
            expected_conf=incident.get("expected_confidence", 0.7),
            actual_conf=result["overall_confidence"]
        )
        
        # Check citation quality
        cited_sources = self._extract_cited_sources(result)
        evaluation_criteria = self.dataset.get("evaluation_criteria", {}).get(
            incident["id"], {}
        )
        missing_citations = self._check_missing_citations(
            cited_sources,
            evaluation_criteria.get("must_cite", [])
        )
        false_claims = self._check_false_claims(
            result,
            evaluation_criteria.get("must_not_claim", [])
        )
        
        return EvaluationResult(
            incident_id=incident["id"],
            expected_verdict=expected_verdict,
            actual_verdict=actual_verdict,
            expected_confidence=incident.get("expected_confidence", 0.7),
            actual_confidence=result["overall_confidence"],
            correct_decision=correct,
            confidence_delta=abs(
                result["overall_confidence"] - 
                incident.get("expected_confidence", 0.7)
            ),
            cited_sources=cited_sources,
            missing_citations=missing_citations,
            false_claims=false_claims
        )
    
    def _mock_image_evidence(self, incident: Dict) -> List:
        """Convert incident dashboard data to Evidence objects"""
        from agents.verifier import Evidence
        
        evidence = []
        dashboard = incident.get("dashboard_data", {})
        
        for metric in dashboard.get("metrics", []):
            evidence.append(Evidence(
                source="image",
                content=f"{metric['name']} showed {metric.get('pattern', 'anomaly')} "
                       f"at {metric.get('spike_time', 'unknown time')}",
                timestamp=metric.get("spike_time", ""),
                confidence=0.9,
                metadata=metric
            ))
        
        return evidence
    
    def _mock_log_evidence(self, incident: Dict) -> List:
        """Convert incident logs to Evidence objects"""
        from agents.verifier import Evidence
        
        evidence = []
        for log in incident.get("logs", []):
            if log.get("level") in ["ERROR", "CRITICAL"]:
                evidence.append(Evidence(
                    source="log",
                    content=log["message"],
                    timestamp=log["timestamp"],
                    confidence=0.95,
                    metadata=log
                ))
        
        return evidence
    
    def _mock_rag_evidence(self, incident: Dict) -> List:
        """Convert historical incidents to Evidence objects"""
        from agents.verifier import Evidence
        
        evidence = []
        for hist in incident.get("historical_incidents", []):
            evidence.append(Evidence(
                source="historical",
                content=f"Historical incident {hist['incident_id']}: {hist['root_cause']}",
                timestamp=hist.get("date", ""),
                confidence=hist.get("similarity", 0.8),
                metadata=hist
            ))
        
        return evidence
    
    def _run_verification_and_decision(
        self,
        state: Dict,
        incident: Dict
    ) -> Dict:
        """
        Runs verifier and decision gate on the state.
        (Simplified for evaluation - in production would run full graph)
        """
        from agents.verifier import EvidenceVerifier, Hypothesis
        from agents.decision_gate import DecisionGate
        
        # Create mock hypothesis based on incident
        hypothesis = Hypothesis(
            id="H1",
            root_cause=incident.get(
                "expected_root_cause",
                "Unknown root cause"
            ),
            plausibility=0.8,
            supporting_evidence=[],
            required_evidence=[],
            would_refute=[]
        )
        
        # Run verifier
        verifier = EvidenceVerifier()
        verification_results, overall_confidence = verifier.verify_hypotheses(
            hypotheses=[hypothesis],
            evidence={
                "image": state["image_evidence"],
                "log": state["log_evidence"],
                "historical": state["rag_evidence"]
            },
            timeline=self._build_mock_timeline(state)
        )
        
        # Run decision gate
        decision_gate = DecisionGate()
        decision, final_response = decision_gate.make_decision(
            verification_results=verification_results,
            overall_confidence=overall_confidence,
            hypotheses=[hypothesis],
            timeline=self._build_mock_timeline(state),
            gaps=incident.get("missing_evidence", [])
        )
        
        return {
            "decision": decision,
            "overall_confidence": overall_confidence,
            "final_response": final_response,
            "verification_results": verification_results
        }
    
    def _build_mock_timeline(self, state: Dict) -> List[Dict]:
        """Build timeline from evidence"""
        timeline = []
        
        # Add events from logs
        for ev in state.get("log_evidence", []):
            timeline.append({
                "time": ev.timestamp,
                "event": ev.content,
                "source": "log"
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x["time"])
        
        return timeline
    
    def _is_decision_correct(
        self,
        expected: str,
        actual: str,
        expected_conf: float,
        actual_conf: float
    ) -> bool:
        """
        Checks if the decision matches expected outcome.
        Allows some flexibility in confidence scores.
        """
        # Exact match on decision type
        if expected != actual:
            return False
        
        # For ANSWER decisions, confidence should be high
        if expected == "ANSWER":
            return actual_conf >= 0.65  # Allow some variance
        
        # For REFUSE, confidence should be low
        if expected == "REFUSE":
            return actual_conf < 0.7
        
        return True
    
    def _extract_cited_sources(self, result: Dict) -> List[str]:
        """Extract which sources were cited in the final response"""
        response = result.get("final_response", {})
        evidence = response.get("evidence", {})
        
        cited = []
        if evidence.get("dashboard"):
            cited.append("dashboard")
        if evidence.get("logs"):
            cited.append("logs")
        if evidence.get("historical"):
            cited.append("historical")
        
        return cited
    
    def _check_missing_citations(
        self,
        cited: List[str],
        must_cite: List[str]
    ) -> List[str]:
        """Check if required evidence was cited"""
        return [item for item in must_cite if item not in str(cited).lower()]
    
    def _check_false_claims(
        self,
        result: Dict,
        must_not_claim: List[str]
    ) -> List[str]:
        """Check if any prohibited claims were made"""
        response_text = str(result.get("final_response", {})).lower()
        return [
            claim for claim in must_not_claim
            if claim.lower() in response_text
        ]
    
    def _calculate_metrics(self, results: List[EvaluationResult]) -> Dict:
        """Calculate aggregate evaluation metrics"""
        total = len(results)
        correct_decisions = sum(1 for r in results if r.correct_decision)
        
        avg_confidence_delta = sum(r.confidence_delta for r in results) / total
        
        citation_errors = sum(
            1 for r in results
            if r.missing_citations or r.false_claims
        )
        
        return {
            "accuracy": correct_decisions / total,
            "correct_decisions": correct_decisions,
            "total_incidents": total,
            "avg_confidence_delta": avg_confidence_delta,
            "citation_quality": 1 - (citation_errors / total)
        }
    
    def _print_incident_result(self, result: EvaluationResult):
        """Print results for a single incident"""
        status = "✅ PASS" if result.correct_decision else "❌ FAIL"
        
        print(f"\n{status}")
        print(f"Expected: {result.expected_verdict} (conf: {result.expected_confidence:.2f})")
        print(f"Actual:   {result.actual_verdict} (conf: {result.actual_confidence:.2f})")
        print(f"Confidence Δ: {result.confidence_delta:.3f}")
        
        if result.missing_citations:
            print(f"⚠️  Missing citations: {result.missing_citations}")
        
        if result.false_claims:
            print(f"⚠️  False claims: {result.false_claims}")
    
    def _print_summary(self, metrics: Dict):
        """Print summary statistics"""
        print(f"\n{'='*60}")
        print("EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Overall Accuracy: {metrics['accuracy']:.1%}")
        print(f"Correct Decisions: {metrics['correct_decisions']}/{metrics['total_incidents']}")
        print(f"Avg Confidence Delta: {metrics['avg_confidence_delta']:.3f}")
        print(f"Citation Quality: {metrics['citation_quality']:.1%}")
        print(f"{'='*60}\n")


# Mock DecisionGate class for evaluation
class DecisionGate:
    """Simplified decision gate for evaluation"""
    
    def make_decision(self, verification_results, overall_confidence, 
                     hypotheses, timeline, gaps):
        """Make final decision based on verification"""
        
        if overall_confidence >= 0.7:
            decision = "answer"
        elif overall_confidence >= 0.5 and gaps:
            decision = "request_more_data"
        else:
            decision = "refuse"
        
        final_response = {
            "status": decision,
            "confidence": overall_confidence,
            "evidence": {
                "dashboard": "Mock evidence",
                "logs": "Mock logs",
                "historical": "Mock historical"
            } if decision == "answer" else {},
            "missing_evidence": gaps if decision != "answer" else []
        }
        
        return decision, final_response


# Main execution
if __name__ == "__main__":
    # Would normally load the actual graph
    # graph = build_incident_analysis_graph()
    
    evaluator = IncidentAnalysisEvaluator(
        graph=None,  # Mock for now
        dataset_path="data/incidents.json"
    )
    
    results = evaluator.run_evaluation()
    
    # Save results
    with open("evaluation/results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n✅ Evaluation complete! Results saved to evaluation/results.json")