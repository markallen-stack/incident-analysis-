"""
Decision Gate Agent

Makes final decision: ANSWER, REFUSE, or REQUEST_MORE_DATA
Formats the output for the user.

Usage:
    from agents.decision_gate import make_decision
    
    decision, response = make_decision(
        verification_results=results,
        overall_confidence=0.85,
        hypotheses=hypotheses,
        timeline=timeline,
        gaps=gaps
    )
"""

import sys
from pathlib import Path
from typing import Dict, Tuple, List
from unittest import result

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from agents.verifier import VerificationResult, Hypothesis, Verdict


class DecisionGate:
    """
    Final decision gate that determines whether to answer or refuse.
    """
    
    def __init__(self, confidence_threshold: float = None):
        """
        Initialize decision gate.
        
        Args:
            confidence_threshold: Minimum confidence to provide answer (default from config)
        """
        self.confidence_threshold = confidence_threshold or config.CONFIDENCE_THRESHOLD
    
    def make_decision(
        self,
        verification_results: Dict[str, VerificationResult],
        overall_confidence: float,
        hypotheses: List[Hypothesis],
        timeline: List[Dict],
        gaps: List[str]
    ) -> Tuple[str, Dict]:
        """
        Makes final decision based on verification results.
        
        Args:
            verification_results: Results from verifier agent
            overall_confidence: Overall confidence score
            hypotheses: List of hypotheses
            timeline: Timeline events
            gaps: Identified gaps in evidence
        
        Returns:
            Tuple of (decision_type, formatted_response)
            decision_type: "answer", "refuse", or "request_more_data"
        """
        # Find supported hypotheses
        supported = [
            (h_id, result)
            for h_id, result in verification_results.items()
            if result.verdict.value == "SUPPORTED"
        ]

        # Use current config threshold (allows Settings UI to take effect)
        threshold = config.CONFIDENCE_THRESHOLD
        if overall_confidence >= threshold and supported:
            decision = "answer"
            response = self._format_answer(
                supported, hypotheses, verification_results, timeline, overall_confidence
            )
        
        elif overall_confidence >= 0.5 and gaps:
            decision = "request_more_data"
            response = self._format_request_more_data(
                verification_results, hypotheses, gaps, overall_confidence
            )
        
        else:
            decision = "refuse"
            response = self._format_refusal(
                verification_results, hypotheses, gaps, overall_confidence
            )
        
        return decision, response
    
    def _format_answer(
        self,
        supported: List[Tuple[str, VerificationResult]],
        hypotheses: List[Hypothesis],
        verification_results: Dict[str, VerificationResult],
        timeline: List[Dict],
        confidence: float
    ) -> Dict:
        """Format answer response with full details"""
        
        # Get the best hypothesis (highest confidence)
        best_hypothesis_id, best_result = max(
            supported,
            key=lambda x: x[1].confidence
        )
        
        # Find the hypothesis object
        best_hypothesis = next(
            (h for h in hypotheses if h.id == best_hypothesis_id),
            None
        )
        
        if not best_hypothesis:
            # Fallback if hypothesis not found
            best_hypothesis = Hypothesis(
                id=best_hypothesis_id,
                root_cause="Unknown",
                plausibility=0.5,
                supporting_evidence=[],
                required_evidence=[],
                would_refute=[]
            )
        
        # Build evidence section
        evidence_dict = {}
        for source, items in best_result.evidence_summary.items():
            if items:
                # Take first item from each source
                evidence_dict[source] = items[0] if len(items) == 1 else f"{len(items)} pieces of evidence"
        
        # Build timeline string
        timeline_str = self._format_timeline(timeline[:5])  # Top 5 events
        
        # Find alternative hypotheses
        alternatives = []
        for h_id, result in verification_results.items():
            if h_id != best_hypothesis_id and result.verdict != Verdict.SUPPORTED:
                hypothesis = next((h for h in hypotheses if h.id == h_id), None)
                if hypothesis:
                    alternatives.append({
                        "hypothesis": hypothesis.root_cause,
                        "why_less_likely": result.reasoning
                    })
        
        # Generate recommended actions
        actions = self._generate_actions(best_hypothesis, best_result)
        
        return {
            "status": "answer",
            "root_cause": best_hypothesis.root_cause,
            "confidence": confidence,
            "evidence": evidence_dict,
            "timeline": timeline_str,
            "recommended_actions": actions,
            "alternative_hypotheses": alternatives[:2]  # Limit to 2
        }
    
    def _format_refusal(
        self,
        verification_results: Dict[str, VerificationResult],
        hypotheses: List[Hypothesis],
        gaps: List[str],
        confidence: float
    ) -> Dict:
        """Format refusal response"""
        
        # What do we know?
        what_we_know = []
        for h_id, result in verification_results.items():
            if result.evidence_summary:
                for source, items in result.evidence_summary.items():
                    what_we_know.extend(items[:2])  # Max 2 per source
        
        # Deduplicate
        what_we_know = list(set(what_we_know))[:5]  # Max 5 total
        
        # What's missing?
        missing_evidence = []
        for result in verification_results.values():
            if result.verdict == Verdict.INSUFFICIENT_EVIDENCE:
                # Extract what's missing from reasoning
                if "missing" in result.reasoning.lower():
                    missing_evidence.append(result.reasoning)
        
        # Add gaps
        missing_evidence.extend(gaps[:3])
        missing_evidence = list(set(missing_evidence))[:5]  # Deduplicate and limit
        
        # Suggestion
        if missing_evidence:
            suggestion = f"Please provide {', '.join(missing_evidence[:2])} for accurate analysis"
        else:
            suggestion = "Additional data needed for confident root cause determination"
        
        return {
            "status": "refused",
            "reason": "Insufficient corroborating evidence for confident diagnosis",
            "confidence": confidence,
            "what_we_know": what_we_know,
            "missing_evidence": missing_evidence,
            "suggestion": suggestion
        }
    
    def _format_request_more_data(
        self,
        verification_results: Dict[str, VerificationResult],
        hypotheses: List[Hypothesis],
        gaps: List[str],
        confidence: float
    ) -> Dict:
        """Format request for more data"""
        
        # Find the most plausible hypothesis
        leading_hypothesis = max(hypotheses, key=lambda h: h.plausibility) if hypotheses else None
        
        # Determine what data is needed
        needed_data = []
        
        if leading_hypothesis:
            needed_data.extend(leading_hypothesis.required_evidence[:3])
        
        # Add from gaps
        needed_data.extend(gaps[:3])
        
        # Deduplicate
        needed_data = list(set(needed_data))[:5]
        
        # Why is this data needed?
        if leading_hypothesis:
            why_needed = f"Current evidence suggests {leading_hypothesis.root_cause.lower()}, but lacks direct confirmation"
        else:
            why_needed = "Unable to determine root cause with current data"
        
        return {
            "status": "request_more_data",
            "current_confidence": confidence,
            "leading_hypothesis": leading_hypothesis.root_cause if leading_hypothesis else "Unknown",
            "needed_data": needed_data,
            "why_needed": why_needed
        }
    
    def _format_timeline(self, events: List[Dict]) -> str:
        """Format timeline events into a string"""
        if not events:
            return "No timeline data available"
        
        lines = []
        for event in events:
            time = event.get('time', 'unknown')
            if 'T' in time:
                time = time.split('T')[1][:5]  # Extract HH:MM
            
            evt = event.get('event', 'Unknown event')
            # Truncate long events
            if len(evt) > 60:
                evt = evt[:60] + "..."
            
            lines.append(f"{time} → {evt}")
        
        return "\n".join(lines)
    
    def _generate_actions(
        self,
        hypothesis: Hypothesis,
        verification: VerificationResult
    ) -> List[str]:
        """Generate recommended actions based on hypothesis"""
        actions = []
        
        root_cause_lower = hypothesis.root_cause.lower()
        
        # Deployment-related actions
        if "deploy" in root_cause_lower:
            actions.append("Consider rolling back the recent deployment")
            actions.append("Review deployment changes and git diff")
            actions.append("Check deployment logs for errors")
        
        # Memory-related actions
        if "memory" in root_cause_lower or "leak" in root_cause_lower:
            actions.append("Capture heap dump for analysis")
            actions.append("Review memory allocation patterns in recent changes")
            actions.append("Monitor garbage collection metrics")
        
        # Connection-related actions
        if "connection" in root_cause_lower or "pool" in root_cause_lower:
            actions.append("Verify connection pool configuration")
            actions.append("Check for connection leaks in code")
            actions.append("Review database/service connection limits")
        
        # CPU-related actions
        if "cpu" in root_cause_lower:
            actions.append("Capture thread dump to identify hot spots")
            actions.append("Profile application for CPU-intensive operations")
            actions.append("Check for infinite loops or recursive calls")
        
        # Traffic-related actions
        if "traffic" in root_cause_lower or "load" in root_cause_lower:
            actions.append("Review request rate metrics")
            actions.append("Check load balancer configuration")
            actions.append("Consider scaling horizontally")
        
        # Generic actions if none specific
        if not actions:
            actions.append("Review recent changes to the system")
            actions.append("Check service dependencies and health")
            actions.append("Examine error logs for additional context")
        
        # Limit to 3-5 actions
        return actions[:5]


# Module-level convenience function
_gate_instance = None

def get_gate() -> DecisionGate:
    """Get or create singleton gate instance"""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = DecisionGate()
    return _gate_instance


def make_decision(
    verification_results: Dict[str, VerificationResult],
    overall_confidence: float,
    hypotheses: List[Hypothesis],
    timeline: List[Dict],
    gaps: List[str]
) -> Tuple[str, Dict]:
    """
    Convenience function for making final decision.
    
    Args:
        verification_results: Verification results
        overall_confidence: Overall confidence score
        hypotheses: List of hypotheses
        timeline: Timeline events
        gaps: Evidence gaps
    
    Returns:
        (decision_type, formatted_response)
    """
    gate = get_gate()
    return gate.make_decision(
        verification_results,
        overall_confidence,
        hypotheses,
        timeline,
        gaps
    )


# CLI for testing
def main():
    """Test decision gate"""
    import json
    from agents.verifier import Evidence
    
    # Sample verification results
    verification_results = {
        "H1": VerificationResult(
            hypothesis_id="H1",
            verdict=Verdict.SUPPORTED,
            confidence=0.85,
            evidence_summary={
                "image": ["CPU spike at 14:31"],
                "log": ["OutOfMemoryError in logs"],
                "historical": ["Similar to INC-2023-089"]
            },
            independent_sources=3,
            contradictions=[],
            reasoning="Strong evidence from 3 independent sources"
        )
    }
    
    hypotheses = [
        Hypothesis(
            id="H1",
            root_cause="Memory leak from recent deployment",
            plausibility=0.85,
            supporting_evidence=[],
            required_evidence=[],
            would_refute=[]
        )
    ]
    
    timeline = [
        {"time": "14:29:00Z", "event": "Deployment started"},
        {"time": "14:31:00Z", "event": "CPU spike to 95%"},
        {"time": "14:31:45Z", "event": "OutOfMemoryError"}
    ]
    
    gaps = []
    
    print("="*60)
    print("DECISION GATE TEST")
    print("="*60)
    
    decision, response = make_decision(
        verification_results,
        0.85,
        hypotheses,
        timeline,
        gaps
    )
    
    print(f"\nDecision: {decision.upper()}")
    print("\nResponse:")
    print(json.dumps(response, indent=2))
    print("\n" + "="*60)


if __name__ == "__main__":
    main()