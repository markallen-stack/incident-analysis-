"""
RAG Retrieval Agent

Retrieves historical incidents and runbooks using vector search.
Provides context from past similar incidents for root cause analysis.

Usage:
    from agents.rag_retriever import retrieve_knowledge
    
    evidence = retrieve_knowledge(
        symptoms=["cpu_spike", "memory_leak"],
        services=["api-gateway"]
    )
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.verifier import Evidence

# Try to import vector search
try:
    from vector_db.query import search_incidents, search_runbooks
    VECTOR_SEARCH_AVAILABLE = True
except ImportError:
    VECTOR_SEARCH_AVAILABLE = False
    print("⚠️  Vector search not available for RAG.")


class RAGRetriever:
    """
    Retrieval-Augmented Generation agent for historical knowledge.
    """
    
    def __init__(self, use_vector_search: bool = True):
        """
        Initialize RAG retriever.
        
        Args:
            use_vector_search: Whether to use vector search
        """
        self.use_vector_search = use_vector_search and VECTOR_SEARCH_AVAILABLE
    
    def retrieve_knowledge(
        self,
        symptoms: List[str],
        services: List[str],
        additional_context: Optional[str] = None
    ) -> List[Evidence]:
        """
        Retrieves relevant historical incidents and runbooks.
        
        Args:
            symptoms: List of identified symptoms
            services: List of affected services
            additional_context: Optional additional search context
        
        Returns:
            List of Evidence objects with historical knowledge
        """
        evidence = []
        
        # Build search query
        query_parts = symptoms + services
        if additional_context:
            query_parts.append(additional_context)
        
        query = " ".join(query_parts)
        
        if self.use_vector_search:
            # Search historical incidents
            incident_evidence = self._search_incidents(query, services)
            evidence.extend(incident_evidence)
            
            # Search runbooks
            runbook_evidence = self._search_runbooks(query)
            evidence.extend(runbook_evidence)
        
        else:
            # Fallback: return empty or mock data
            evidence = self._fallback_search(query, symptoms, services)
        
        # Deduplicate and rank
        evidence = self._deduplicate(evidence)
        evidence = self._rank_by_relevance(evidence)
        
        return evidence
    
    def _search_incidents(
        self,
        query: str,
        services: List[str]
    ) -> List[Evidence]:
        """Search historical incidents using vector search"""
        
        results = search_incidents(
            query=query,
            top_k=5,
            min_similarity=0.6,
            service_filter=services if services else None
        )
        
        evidence = []
        for incident in results:
            content = self._format_incident(incident)
            
            evidence.append(Evidence(
                source="historical",
                content=content,
                timestamp=incident.get('date', incident.get('timestamp', '')),
                confidence=incident.get('similarity', 0.7),
                metadata={
                    'incident_id': incident.get('incident_id', incident.get('id')),
                    'root_cause': incident.get('root_cause', ''),
                    'resolution': incident.get('resolution', ''),
                    'services': incident.get('services', []),
                    'type': 'historical_incident'
                }
            ))
        
        return evidence
    
    def _search_runbooks(self, query: str) -> List[Evidence]:
        """Search runbooks and documentation"""
        
        results = search_runbooks(
            query=query,
            top_k=3,
            min_similarity=0.5
        )
        
        evidence = []
        for runbook in results:
            # Extract key sections only (not full content)
            content = runbook.get('content', '')[:300] + "..."
            
            evidence.append(Evidence(
                source="runbook",
                content=f"Runbook: {runbook.get('title', 'Unknown')} - {content}",
                timestamp='',
                confidence=runbook.get('similarity', 0.6),
                metadata={
                    'title': runbook.get('title', ''),
                    'section': runbook.get('section', ''),
                    'source': runbook.get('source', ''),
                    'type': 'runbook'
                }
            ))
        
        return evidence
    
    def _format_incident(self, incident: Dict) -> str:
        """Format historical incident for display"""
        parts = []
        
        incident_id = incident.get('incident_id', incident.get('id', 'Unknown'))
        parts.append(f"Historical Incident {incident_id}")
        
        if incident.get('root_cause'):
            parts.append(f"Root Cause: {incident['root_cause']}")
        
        if incident.get('symptoms'):
            parts.append(f"Symptoms: {incident['symptoms']}")
        
        if incident.get('services'):
            services = incident['services']
            if isinstance(services, list):
                services = ', '.join(services)
            parts.append(f"Services: {services}")
        
        if incident.get('resolution'):
            # Truncate long resolutions
            resolution = incident['resolution']
            if len(resolution) > 150:
                resolution = resolution[:150] + "..."
            parts.append(f"Resolution: {resolution}")
        
        return " | ".join(parts)
    
    def _fallback_search(
        self,
        query: str,
        symptoms: List[str],
        services: List[str]
    ) -> List[Evidence]:
        """Fallback when vector search unavailable"""
        
        # Return generic knowledge
        evidence = []
        
        # Pattern-based knowledge
        if any(s in str(symptoms).lower() for s in ['memory', 'leak', 'oom']):
            evidence.append(Evidence(
                source="runbook",
                content="Runbook: Memory Issues - Check for memory leaks, review heap dumps, monitor GC activity",
                timestamp='',
                confidence=0.5,
                metadata={'type': 'generic_runbook'}
            ))
        
        if any(s in str(symptoms).lower() for s in ['cpu', 'spike', 'high']):
            evidence.append(Evidence(
                source="runbook",
                content="Runbook: High CPU - Profile application, check for infinite loops, review thread dumps",
                timestamp='',
                confidence=0.5,
                metadata={'type': 'generic_runbook'}
            ))
        
        if any(s in str(symptoms).lower() for s in ['connection', 'timeout', 'pool']):
            evidence.append(Evidence(
                source="runbook",
                content="Runbook: Connection Issues - Verify pool configuration, check network latency, review firewall rules",
                timestamp='',
                confidence=0.5,
                metadata={'type': 'generic_runbook'}
            ))
        
        return evidence
    
    def _deduplicate(self, evidence: List[Evidence]) -> List[Evidence]:
        """Remove duplicate evidence entries"""
        seen_content = set()
        unique_evidence = []
        
        for ev in evidence:
            # Create a simplified version for comparison
            simplified = ev.content[:100].lower()
            
            if simplified not in seen_content:
                seen_content.add(simplified)
                unique_evidence.append(ev)
        
        return unique_evidence
    
    def _rank_by_relevance(self, evidence: List[Evidence]) -> List[Evidence]:
        """Rank evidence by relevance (confidence score)"""
        
        # Sort by confidence (descending)
        evidence.sort(key=lambda x: x.confidence, reverse=True)
        
        # Boost historical incidents over runbooks
        for ev in evidence:
            if ev.metadata.get('type') == 'historical_incident':
                # Already boosted in confidence during search
                pass
            elif ev.metadata.get('type') == 'runbook':
                # Slightly lower runbook confidence
                ev.confidence *= 0.9
        
        # Re-sort after boosting
        evidence.sort(key=lambda x: x.confidence, reverse=True)
        
        return evidence


# Module-level convenience function
_retriever_instance = None

def get_retriever() -> RAGRetriever:
    """Get or create singleton retriever instance"""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RAGRetriever()
    return _retriever_instance


def retrieve_knowledge(
    symptoms: List[str],
    services: List[str],
    additional_context: Optional[str] = None
) -> List[Evidence]:
    """
    Convenience function for retrieving historical knowledge.
    
    Args:
        symptoms: List of symptoms (e.g., ["cpu_spike", "memory_leak"])
        services: List of affected services
        additional_context: Optional additional context
    
    Returns:
        List of Evidence objects with historical incidents and runbooks
    """
    retriever = get_retriever()
    return retriever.retrieve_knowledge(symptoms, services, additional_context)


# CLI for testing
def main():
    """Test RAG retrieval"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Test RAG retrieval")
    parser.add_argument('--symptoms', nargs='+', default=["error"],
                       help='Symptom keywords')
    parser.add_argument('--services', nargs='+',
                       help='Service names')
    parser.add_argument('--context', help='Additional context')
    
    args = parser.parse_args()
    
    print("="*60)
    print("RAG RETRIEVAL TEST")
    print("="*60)
    print(f"Symptoms: {args.symptoms}")
    print(f"Services: {args.services or 'None'}")
    print(f"Context: {args.context or 'None'}")
    print("="*60)
    
    # Retrieve knowledge
    evidence = retrieve_knowledge(
        symptoms=args.symptoms,
        services=args.services or [],
        additional_context=args.context
    )
    
    print(f"\nFound {len(evidence)} knowledge sources:\n")
    
    # Group by type
    incidents = [e for e in evidence if e.metadata.get('type') == 'historical_incident']
    runbooks = [e for e in evidence if e.metadata.get('type') == 'runbook']
    generic = [e for e in evidence if e.metadata.get('type') == 'generic_runbook']
    
    if incidents:
        print("📚 Historical Incidents:")
        for i, ev in enumerate(incidents, 1):
            print(f"\n{i}. (confidence: {ev.confidence:.2f})")
            print(f"   {ev.content}")
    
    if runbooks:
        print("\n📖 Runbooks:")
        for i, ev in enumerate(runbooks, 1):
            print(f"\n{i}. (confidence: {ev.confidence:.2f})")
            print(f"   {ev.content}")
    
    if generic:
        print("\n📝 Generic Knowledge:")
        for i, ev in enumerate(generic, 1):
            print(f"\n{i}. (confidence: {ev.confidence:.2f})")
            print(f"   {ev.content}")
    
    if not evidence:
        print("No relevant knowledge found.")
        print("\nMake sure vector indexes are created:")
        print("  python vector_db/setup.py")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()