"""
Verifier Agent - The Critical Quality Gate

This agent is the MOST IMPORTANT component. It enforces evidence-based
reasoning and prevents the system from making unsubstantiated claims.

Key responsibilities:
1. Verify each hypothesis against ALL available evidence
2. Enforce multi-source verification (≥2 independent sources)
3. Detect contradictions in evidence
4. Calculate confidence scores based on evidence quality
5. Recommend ANSWER/REFUSE/REQUEST_MORE_DATA
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum
import json


class Verdict(Enum):
    SUPPORTED = "SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"


class EvidenceSource(Enum):
    IMAGE = "image"
    LOG = "log"
    HISTORICAL = "historical"
    RUNBOOK = "runbook"


@dataclass
class Evidence:
    source: str
    content: str
    timestamp: str
    confidence: float
    metadata: Dict


@dataclass
class Hypothesis:
    id: str
    root_cause: str
    plausibility: float
    supporting_evidence: List[str]
    required_evidence: List[str]
    would_refute: List[str]


@dataclass
class VerificationResult:
    hypothesis_id: str
    verdict: Verdict
    confidence: float
    evidence_summary: Dict[str, List[str]]
    independent_sources: int
    contradictions: List[str]
    reasoning: str


class EvidenceVerifier:
    """
    Verifies hypotheses using strict evidence requirements.
    
    Confidence Scoring:
    - 0.9-1.0: ≥3 independent sources, no contradictions, perfect timeline
    - 0.7-0.9: 2 independent sources, minor gaps acceptable
    - 0.5-0.7: 2 sources with ambiguity OR strong single source + historical
    - <0.5:   Single source, conflicts, or major gaps → REFUSE
    """
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM for semantic matching (optional)
        """
        self.llm = llm_client
        self.min_confidence_threshold = 0.7
        self.min_sources_for_high_confidence = 2
    
    def verify_hypotheses(
        self,
        hypotheses: List[Hypothesis],
        evidence: Dict[str, List[Evidence]],
        timeline: List[Dict]
    ) -> Tuple[Dict[str, VerificationResult], float]:
        """
        Main verification method.
        
        Args:
            hypotheses: List of root cause hypotheses
            evidence: Dict mapping source type to evidence list
            timeline: Chronological event list
        
        Returns:
            (verification_results, overall_confidence)
        """
        results = {}
        
        for hypothesis in hypotheses:
            result = self._verify_single_hypothesis(
                hypothesis,
                evidence,
                timeline
            )
            results[hypothesis.id] = result
        
        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(results)
        # print(results, overall_confidence)
        return results, overall_confidence
    
    def _verify_single_hypothesis(
        self,
        hypothesis: Hypothesis,
        evidence: Dict[str, List[Evidence]],
        timeline: List[Dict]
    ) -> VerificationResult:
        """
        Verifies a single hypothesis against all available evidence.
        """
        # Step 1: Collect supporting evidence from each source
        evidence_summary = {
            "image": [],
            "log": [],
            "historical": [],
            "runbook": [],
            "rag": [],          # ← ADD THESE
            "metrics": [],      # ← ADD THESE
            "dashboard": [],    # ← ADD THESE
            "prometheus": [] 
        }
        
        for source_type, evidence_list in evidence.items():
            matching = self._find_supporting_evidence(
                hypothesis,
                evidence_list,
                source_type
            )
            evidence_summary[source_type].extend(matching)
        
        # Step 2: Count independent sources
        independent_sources = sum(
            1 for items in evidence_summary.values() if len(items) > 0
        )
        
        # Step 3: Check for contradictions
        contradictions = self._detect_contradictions(
            hypothesis,
            evidence,
            timeline
        )
        
        # Step 4: Verify timeline consistency
        timeline_consistent = self._check_timeline_consistency(
            hypothesis,
            timeline,
            evidence_summary
        )
        
        # Step 5: Calculate confidence
        confidence = self._calculate_hypothesis_confidence(
            independent_sources=independent_sources,
            has_contradictions=len(contradictions) > 0,
            timeline_consistent=timeline_consistent,
            evidence_summary=evidence_summary
        )
        
        # Step 6: Determine verdict
        verdict = self._determine_verdict(
            confidence=confidence,
            independent_sources=independent_sources,
            has_contradictions=len(contradictions) > 0
        )
        
        # Step 7: Generate reasoning
        reasoning = self._generate_reasoning(
            hypothesis=hypothesis,
            verdict=verdict,
            confidence=confidence,
            independent_sources=independent_sources,
            contradictions=contradictions,
            timeline_consistent=timeline_consistent
        )
        
        return VerificationResult(
            hypothesis_id=hypothesis.id,
            verdict=verdict,
            confidence=confidence,
            evidence_summary=evidence_summary,
            independent_sources=independent_sources,
            contradictions=contradictions,
            reasoning=reasoning
        )
    
    def _find_supporting_evidence(
        self,
        hypothesis: Hypothesis,
        evidence_list: List[Evidence],
        source_type: str
    ) -> List[str]:
        """
        Finds evidence that supports the hypothesis.
        Uses both keyword matching and semantic similarity.
        """
        supporting = []
        
        # Extract key terms from hypothesis
        key_terms = self._extract_key_terms(hypothesis.root_cause)
        
        for ev in evidence_list:
            # Simple keyword matching (can be enhanced with embeddings)
            content_lower = ev.content.lower()
            matches = sum(1 for term in key_terms if term in content_lower)
            
            if matches >= 2:  # At least 2 key terms match
                supporting.append(
                    f"{ev.content} (confidence: {ev.confidence:.2f})"
                )
        
        return supporting
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract important terms from hypothesis text."""
        # Remove common words and extract key terms
        common_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'from', 'by'}
        words = text.lower().split()
        key_terms = [w for w in words if w not in common_words and len(w) > 3]
        return key_terms
    
    def _detect_contradictions(
        self,
        hypothesis: Hypothesis,
        evidence: Dict[str, List[Evidence]],
        timeline: List[Dict]
    ) -> List[str]:
        """
        Detects evidence that contradicts the hypothesis.
        """
        contradictions = []
        
        # Check if any evidence explicitly refutes the hypothesis
        refutation_terms = hypothesis.would_refute
        
        for source_type, evidence_list in evidence.items():
            for ev in evidence_list:
                for refutation in refutation_terms:
                    if refutation.lower() in ev.content.lower():
                        contradictions.append(
                            f"[{source_type}] {ev.content}"
                        )
        
        # Check timeline contradictions
        # (e.g., if hypothesis claims X caused Y, but Y happened before X)
        timeline_contradictions = self._check_temporal_contradictions(
            hypothesis,
            timeline
        )
        contradictions.extend(timeline_contradictions)
        
        return contradictions
    
    def _check_temporal_contradictions(
        self,
        hypothesis: Hypothesis,
        timeline: List[Dict]
    ) -> List[str]:
        """
        Checks if timeline contradicts causal claims in hypothesis.
        """
        contradictions = []
        
        # This is simplified - in production, would use more sophisticated
        # causal inference from the hypothesis text
        
        # Example: If hypothesis mentions "deployment caused spike"
        # but spike happened before deployment, that's a contradiction
        
        return contradictions
    
    def _check_timeline_consistency(
        self,
        hypothesis: Hypothesis,
        timeline: List[Dict],
        evidence_summary: Dict[str, List[str]]
    ) -> bool:
        """
        Verifies that evidence aligns temporally with hypothesis.
        """
        # If we have no timeline, we can't verify consistency
        if not timeline:
            return False
        
        # Check if all pieces of evidence appear in timeline
        # and are in logical causal order
        
        # This is simplified - production version would do proper
        # temporal reasoning
        
        # For now, just check we have timeline events
        return len(timeline) >= 2
    
    def _calculate_hypothesis_confidence(
        self,
        independent_sources: int,
        has_contradictions: bool,
        timeline_consistent: bool,
        evidence_summary: Dict[str, List[str]]
    ) -> float:
        """
        Calculates confidence score for a hypothesis.
        
        Scoring rubric:
        - Base score from number of independent sources
        - Penalties for contradictions or timeline issues
        - Bonuses for high-quality evidence
        """
        # Base score from number of sources
        if independent_sources >= 3:
            base_score = 0.85
        elif independent_sources == 2:
            base_score = 0.70
        elif independent_sources == 1:
            base_score = 0.40
        else:
            base_score = 0.20
        
        # Penalties
        if has_contradictions:
            base_score -= 0.30
        
        if not timeline_consistent:
            base_score -= 0.15
        
        # Bonuses
        # If we have historical incident match, boost confidence
        if len(evidence_summary.get("historical", [])) > 0:
            base_score += 0.10
        
        # If we have high-confidence image evidence
        if len(evidence_summary.get("image", [])) > 0:
            base_score += 0.05
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, base_score))
    
    def _determine_verdict(
        self,
        confidence: float,
        independent_sources: int,
        has_contradictions: bool
    ) -> Verdict:
        """
        Determines final verdict based on evidence analysis.
        """
        if has_contradictions:
            return Verdict.CONTRADICTED
        
        if confidence >= 0.7 and independent_sources >= 2:
            return Verdict.SUPPORTED
        
        return Verdict.INSUFFICIENT_EVIDENCE
    
    def _generate_reasoning(
        self,
        hypothesis: Hypothesis,
        verdict: Verdict,
        confidence: float,
        independent_sources: int,
        contradictions: List[str],
        timeline_consistent: bool
    ) -> str:
        """
        Generates human-readable reasoning for the verification result.
        """
        if verdict == Verdict.SUPPORTED:
            reasoning = (
                f"Hypothesis supported with {independent_sources} independent sources "
                f"(confidence: {confidence:.2f}). "
            )
            if timeline_consistent:
                reasoning += "Timeline is consistent. "
            else:
                reasoning += "Minor timeline gaps but overall plausible. "
        
        elif verdict == Verdict.CONTRADICTED:
            reasoning = (
                f"Hypothesis contradicted by evidence. "
                f"Found {len(contradictions)} contradictions: "
                f"{', '.join(contradictions[:2])}"
            )
        
        else:  # INSUFFICIENT_EVIDENCE
            reasoning = (
                f"Insufficient evidence (only {independent_sources} source(s), "
                f"confidence: {confidence:.2f}). "
            )
            if independent_sources < 2:
                reasoning += "Need at least 2 independent sources for verification. "
        
        return reasoning
    
    def _calculate_overall_confidence(
        self,
        results: Dict[str, VerificationResult]
    ) -> float:
        """
        Calculates overall system confidence across all hypotheses.
        """
        if not results:
            return 0.0
        
        # Find the highest confidence SUPPORTED hypothesis
        supported = [
            r.confidence for r in results.values()
            if r.verdict == Verdict.SUPPORTED
        ]
        
        if supported:
            return max(supported)
        
        # If no hypotheses are supported, return max confidence among all
        # (but this will be low and should trigger refusal)
        return max(r.confidence for r in results.values())


# Usage example
if __name__ == "__main__":
    # Example usage
    verifier = EvidenceVerifier()
    
    # Mock data
    hypothesis = Hypothesis(
        id="H1",
        root_cause="Memory leak from deployment",
        plausibility=0.85,
        supporting_evidence=["deployment", "memory", "leak"],
        required_evidence=["heap dump", "memory metrics"],
        would_refute=["memory stable", "occurred before deployment"]
    )
    
    evidence = {
        "image": [
            Evidence(
                source="dashboard",
                content="CPU spiked to 95% at 14:31",
                timestamp="14:31:00Z",
                confidence=0.9,
                metadata={}
            )
        ],
        "log": [
            Evidence(
                source="application-logs",
                content="OutOfMemoryError in ConnectionPool",
                timestamp="14:31:45Z",
                confidence=0.95,
                metadata={}
            )
        ],
        "historical": [
            Evidence(
                source="incident-db",
                content="INC-2023-089: Memory leak in connection pool",
                timestamp="2023-11-12",
                confidence=0.92,
                metadata={"similarity": 0.92}
            )
        ]
    }
    
    timeline = [
        {"time": "14:29:00Z", "event": "Deployment started"},
        {"time": "14:31:00Z", "event": "CPU spike"},
        {"time": "14:31:45Z", "event": "OOM errors"}
    ]
    
    results, overall_conf = verifier.verify_hypotheses(
        hypotheses=[hypothesis],
        evidence=evidence,
        timeline=timeline
    )
    
    print(f"Verdict: {results['H1'].verdict}")
    print(f"Confidence: {results['H1'].confidence:.2f}")
    print(f"Independent sources: {results['H1'].independent_sources}")
    print(f"Reasoning: {results['H1'].reasoning}")
    print(f"\nOverall confidence: {overall_conf:.2f}")
    print(f"Recommendation: {'ANSWER' if overall_conf >= 0.7 else 'REFUSE'}")