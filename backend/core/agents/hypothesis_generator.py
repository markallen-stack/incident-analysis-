"""
Hypothesis Generator Agent

Generates 2-5 possible root cause hypotheses based on timeline and evidence.
Each hypothesis includes supporting evidence and what would refute it.

Usage:
    from agents.hypothesis_generator import generate_hypotheses
    
    hypotheses = generate_hypotheses(
        timeline=timeline_events,
        correlations=correlations,
        all_evidence=evidence_dict
    )
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

import config
from prompts.hypothesis import HYPOTHESIS_AGENT_PROMPT
from agents.verifier import Hypothesis, Evidence


class HypothesisGenerator:
    """
    Generates root cause hypotheses from timeline and evidence.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize hypothesis generator.
        
        Args:
            llm_client: Optional LLM client
        """
        self.llm_client = llm_client
        
        if self.llm_client is None:
            if config.ANTHROPIC_API_KEY and ANTHROPIC_AVAILABLE:
                self.llm_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
                self.llm_type = "anthropic"
            elif config.OPENAI_API_KEY and OPENAI_AVAILABLE:
                self.llm_client = OpenAI(api_key=config.OPENAI_API_KEY)
                self.llm_type = "openai"
            else:
                print("⚠️  No LLM available. Using rule-based generation.")
                self.llm_type = "rule_based"
    
    def generate_hypotheses(
        self,
        timeline: List[Dict],
        correlations: List[Dict],
        all_evidence: Dict[str, List[Evidence]]
    ) -> List[Hypothesis]:
        """
        Generates 2-5 root cause hypotheses.
        
        Args:
            timeline: Chronological list of events
            correlations: Identified correlations
            all_evidence: Dict of evidence by source type
        
        Returns:
            List of Hypothesis objects ranked by plausibility
        """
        if self.llm_type in ["anthropic", "openai"]:
            hypotheses = self._llm_generate(timeline, correlations, all_evidence)
        else:
            hypotheses = self._rule_based_generate(timeline, correlations, all_evidence)
        
        # Ensure we have 2-5 hypotheses
        if len(hypotheses) > config.MAX_HYPOTHESES:
            hypotheses = hypotheses[:config.MAX_HYPOTHESES]
        
        # Rank by plausibility
        hypotheses.sort(key=lambda h: h.plausibility, reverse=True)
        
        return hypotheses
    
    def generate_hypotheses_with_metrics(
        self,
        timeline: List[Dict],
        correlations: List[Dict],
        all_evidence: Dict[str, List[Evidence]],
        incident_time: str,
        affected_services: List[str] = None
    ) -> List[Hypothesis]:
        """
        Generate hypotheses with intelligent metrics querying via Claude.
        Claude will query Prometheus/Grafana as needed to validate hypotheses.
        
        Args:
            timeline: Chronological list of events
            correlations: Identified correlations
            all_evidence: Dict of evidence by source type
            incident_time: ISO timestamp of incident
            affected_services: Services affected by incident
        
        Returns:
            List of Hypothesis objects with metrics validation
        """
        from agents.llm_metrics_querier import intelligent_metrics_query
        
        # First generate initial hypotheses
        initial_hypotheses = self.generate_hypotheses(
            timeline, correlations, all_evidence
        )
        
        if not initial_hypotheses:
            return []
        
        # Query metrics to enrich hypotheses
        context = f"""
Based on the incident analysis so far, we have generated these initial hypotheses:
{json.dumps([{
    'root_cause': h.root_cause,
    'plausibility': h.plausibility,
    'supporting_evidence': h.supporting_evidence
} for h in initial_hypotheses], indent=2)}

Please validate these hypotheses by querying relevant metrics and dashboards.
Check for:
1. Performance anomalies (CPU, memory, latency)
2. Error rates and types
3. Resource exhaustion or constraints
4. Correlation with known failure patterns
5. Any alerts or annotations around the incident time
"""
        
        metrics_evidence = intelligent_metrics_query(
            context=context,
            incident_time=incident_time,
            affected_services=affected_services
        )
        
        # Add metrics evidence to all_evidence
        all_evidence["metrics_analysis"] = metrics_evidence
        
        # Re-generate hypotheses with enriched evidence
        enriched_hypotheses = self.generate_hypotheses(
            timeline, correlations, all_evidence
        )
        
        return enriched_hypotheses
    
    def _llm_generate(
        self,
        timeline: List[Dict],
        correlations: List[Dict],
        all_evidence: Dict[str, List[Evidence]]
    ) -> List[Hypothesis]:
        """Use LLM to generate hypotheses"""
        
        # Format context for LLM
        context = self._format_context(timeline, correlations, all_evidence)
        
        prompt = f"""{HYPOTHESIS_AGENT_PROMPT}

{context}

Generate 2-5 hypotheses in JSON format:"""
        
        try:
            if self.llm_type == "anthropic":
                response = self.llm_client.messages.create(
                    model=config.PRIMARY_LLM,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text
            
            else:  # OpenAI
                response = self.llm_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000
                )
                response_text = response.choices[0].message.content
            
            # Parse response
            hypotheses = self._parse_llm_response(response_text)
            return hypotheses
        
        except Exception as e:
            print(f"⚠️  LLM generation failed: {e}. Using rule-based fallback.")
            return self._rule_based_generate(timeline, correlations, all_evidence)
    
    def _format_context(
        self,
        timeline: List[Dict],
        correlations: List[Dict],
        all_evidence: Dict[str, List[Evidence]]
    ) -> str:
        """Format context for LLM"""
        parts = []
        
        # Timeline
        parts.append("Timeline:")
        for event in timeline[:10]:  # Limit to first 10 events
            parts.append(f"  {event['time']}: {event['event']}")
        
        # Correlations
        if correlations:
            parts.append("\nCorrelations:")
            for corr in correlations[:5]:
                parts.append(f"  {corr['pattern']} ({corr['strength']} correlation)")
        
        # Evidence summary
        parts.append(f"\nEvidence Summary:")
        parts.append(f"  Image evidence: {len(all_evidence.get('image', []))} observations")
        parts.append(f"  Log evidence: {len(all_evidence.get('log', []))} entries")
        parts.append(f"  Historical evidence: {len(all_evidence.get('historical', []))} incidents")
        
        return "\n".join(parts)
    
    def _parse_llm_response(self, response_text: str) -> List[Hypothesis]:
        """Parse LLM response into Hypothesis objects"""
        try:
            # Remove markdown code blocks
            cleaned = response_text.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]
            
            data = json.loads(cleaned.strip())
            
            # Handle different response formats
            if isinstance(data, dict) and "hypotheses" in data:
                hypotheses_data = data["hypotheses"]
            elif isinstance(data, list):
                hypotheses_data = data
            else:
                raise ValueError("Unexpected response format")
            
            # Convert to Hypothesis objects
            hypotheses = []
            for i, h in enumerate(hypotheses_data):
                hypotheses.append(Hypothesis(
                    id=h.get("id", f"H{i+1}"),
                    root_cause=h.get("root_cause", "Unknown"),
                    plausibility=h.get("plausibility", 0.5),
                    supporting_evidence=h.get("supporting_evidence_types", []),
                    required_evidence=h.get("required_evidence_for_confirmation", []),
                    would_refute=h.get("would_refute", [])
                ))
            
            return hypotheses
        
        except Exception as e:
            print(f"⚠️  Failed to parse LLM response: {e}")
            return self._rule_based_generate([], [], {})
    
    def _rule_based_generate(
        self,
        timeline: List[Dict],
        correlations: List[Dict],
        all_evidence: Dict[str, List[Evidence]]
    ) -> List[Hypothesis]:
        """Rule-based hypothesis generation (fallback)"""
        hypotheses = []
        
        # Extract patterns from timeline and correlations
        has_deployment = any(
            "deploy" in str(event.get("event", "")).lower()
            for event in timeline
        )
        
        has_memory_issue = any(
            any(keyword in str(ev.content).lower() for keyword in ["memory", "oom", "heap"])
            for ev_list in all_evidence.values()
            for ev in ev_list
        )
        
        has_cpu_spike = any(
            "cpu" in str(ev.content).lower() and any(w in str(ev.content).lower() for w in ["spike", "high", "95", "100"])
            for ev_list in all_evidence.values()
            for ev in ev_list
        )
        
        has_connection_errors = any(
            "connection" in str(ev.content).lower()
            for ev_list in all_evidence.values()
            for ev in ev_list
        )
        
        has_traffic_spike = any(
            any(keyword in str(ev.content).lower() for keyword in ["traffic", "requests", "load"])
            for ev_list in all_evidence.values()
            for ev in ev_list
        )
        
        # Generate hypotheses based on patterns
        
        # Hypothesis 1: Deployment-related issue
        if has_deployment and (has_memory_issue or has_cpu_spike or has_connection_errors):
            hypotheses.append(Hypothesis(
                id="H1",
                root_cause="Issue introduced in recent deployment",
                plausibility=0.85 if has_deployment else 0.3,
                supporting_evidence=[
                    "Deployment timing correlates with symptom onset",
                    "Resource usage spike after deployment"
                ],
                required_evidence=[
                    "Deployment logs with change details",
                    "Code diff of deployment",
                    "Resource metrics before/after deploy"
                ],
                would_refute=[
                    "Issue started before deployment",
                    "No code changes in deployment"
                ]
            ))
        
        # Hypothesis 2: Memory leak
        if has_memory_issue:
            hypotheses.append(Hypothesis(
                id="H2",
                root_cause="Memory leak causing resource exhaustion",
                plausibility=0.80 if has_memory_issue else 0.4,
                supporting_evidence=[
                    "OutOfMemoryError in logs",
                    "Gradual memory increase visible"
                ],
                required_evidence=[
                    "Heap dump",
                    "Memory usage metrics over time",
                    "GC logs"
                ],
                would_refute=[
                    "Memory usage remains stable",
                    "Issue occurs immediately, not gradually"
                ]
            ))
        
        # Hypothesis 3: Traffic spike
        if has_traffic_spike or has_connection_errors:
            hypotheses.append(Hypothesis(
                id="H3",
                root_cause="Unexpected traffic spike overwhelming system",
                plausibility=0.60 if has_traffic_spike else 0.5,
                supporting_evidence=[
                    "Connection pool exhaustion",
                    "Increased load visible"
                ],
                required_evidence=[
                    "Request rate metrics",
                    "Load balancer logs",
                    "Connection pool metrics"
                ],
                would_refute=[
                    "Request rate at normal levels",
                    "Connection pool size adequate for load"
                ]
            ))
        
        # Hypothesis 4: External dependency failure
        hypotheses.append(Hypothesis(
            id="H4",
            root_cause="External dependency failure or degradation",
            plausibility=0.50,
            supporting_evidence=[
                "Timeout errors in logs"
            ],
            required_evidence=[
                "External service status",
                "Network latency metrics",
                "Downstream service logs"
            ],
            would_refute=[
                "All external services healthy",
                "No network issues detected"
            ]
        ))
        
        # Hypothesis 5: Configuration change
        hypotheses.append(Hypothesis(
            id="H5",
            root_cause="Recent configuration change causing issues",
            plausibility=0.45,
            supporting_evidence=[
                "Symptom onset timing"
            ],
            required_evidence=[
                "Configuration change history",
                "Config diff",
                "Rollback test results"
            ],
            would_refute=[
                "No config changes in timeframe",
                "Config rollback doesn't resolve issue"
            ]
        ))
        
        # Filter to only hypotheses with some evidence
        hypotheses = [h for h in hypotheses if h.plausibility > 0.4]
        
        # Ensure we have at least 2
        if len(hypotheses) < 2:
            hypotheses.append(Hypothesis(
                id=f"H{len(hypotheses)+1}",
                root_cause="Unknown root cause - insufficient data",
                plausibility=0.3,
                supporting_evidence=[],
                required_evidence=["Additional logs", "Metrics", "Timeline data"],
                would_refute=[]
            ))
        
        return hypotheses


# Module-level convenience function
_generator_instance = None

def get_generator() -> HypothesisGenerator:
    """Get or create singleton generator instance"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = HypothesisGenerator()
    return _generator_instance


def generate_hypotheses(
    timeline: List[Dict],
    correlations: List[Dict],
    all_evidence: Dict[str, List[Evidence]]
) -> List[Hypothesis]:
    """
    Convenience function for generating hypotheses.
    
    Args:
        timeline: Timeline events
        correlations: Temporal correlations
        all_evidence: Evidence dictionary by source
    
    Returns:
        List of Hypothesis objects
    """
    generator = get_generator()
    # print(generator.generate_hypotheses(timeline, correlations, all_evidence))
    return generator.generate_hypotheses(timeline, correlations, all_evidence)


# CLI for testing
def main():
    """Test hypothesis generation"""
    import json
    
    # Sample data
    timeline = [
        {"time": "14:29:00", "event": "Deployment started", "source": "log"},
        {"time": "14:31:00", "event": "CPU spike to 95%", "source": "image"},
        {"time": "14:31:45", "event": "OutOfMemoryError", "source": "log"}
    ]
    
    correlations = [
        {"pattern": "Deployment → CPU spike", "strength": "strong"}
    ]
    
    all_evidence = {
        "image": [Evidence("image", "CPU 95%", "14:31", 0.9, {})],
        "log": [Evidence("log", "OOM error", "14:31:45", 0.95, {})],
        "historical": []
    }
    
    print("="*60)
    print("HYPOTHESIS GENERATION TEST")
    print("="*60)
    
    hypotheses = generate_hypotheses(timeline, correlations, all_evidence)
    
    print(f"\nGenerated {len(hypotheses)} hypotheses:\n")
    
    for h in hypotheses:
        print(f"{h.id}: {h.root_cause}")
        print(f"   Plausibility: {h.plausibility:.2f}")
        print(f"   Supporting: {', '.join(h.supporting_evidence[:2])}")
        print(f"   Required: {', '.join(h.required_evidence[:2])}")
        print()
    
    print("="*60)


if __name__ == "__main__":
    main()