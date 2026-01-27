"""
Log Retrieval Agent

Retrieves relevant logs using vector search and time filtering.
Integrates with the vector database for semantic search.

Usage:
    from agents.log_retriever import retrieve_logs
    
    evidence = retrieve_logs(
        logs=all_logs,
        time_window="14:25-14:40",
        services=["api-gateway"],
        symptoms=["error", "timeout"]
    )
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.verifier import Evidence

# Try to import vector search
try:
    from vector_db.query import search_logs as vector_search_logs
    VECTOR_SEARCH_AVAILABLE = True
except ImportError:
    VECTOR_SEARCH_AVAILABLE = False
    print("⚠️  Vector search not available. Using keyword matching.")


class LogRetriever:
    """
    Log retrieval agent that combines vector search with filtering.
    """
    
    def __init__(self, use_vector_search: bool = True):
        """
        Initialize log retriever.
        
        Args:
            use_vector_search: Whether to use vector search (if available)
        """
        self.use_vector_search = use_vector_search and VECTOR_SEARCH_AVAILABLE
    
    def retrieve_logs(
        self,
        logs: List[Dict],
        time_window: Optional[str] = None,
        services: Optional[List[str]] = None,
        symptoms: Optional[List[str]] = None,
        top_k: int = 20
    ) -> List[Evidence]:
        """
        Retrieves relevant logs based on query and filters.
        
        Args:
            logs: List of log entries
            time_window: Time range string (e.g., "14:25-14:40")
            services: List of service names to filter
            symptoms: List of symptom keywords for search
            top_k: Maximum number of logs to return
        
        Returns:
            List of Evidence objects with relevant logs
        """
        if not logs:
            return []
        
        # Build search query from symptoms
        query = " ".join(symptoms) if symptoms else "error exception failure"
        
        if self.use_vector_search:
            # Use vector search
            evidence = self._vector_search(
                query=query,
                time_window=time_window,
                services=services,
                top_k=top_k
            )
        else:
            # Fallback to keyword search
            evidence = self._keyword_search(
                logs=logs,
                query=query,
                time_window=time_window,
                services=services,
                top_k=top_k
            )
        
        # Detect patterns in retrieved logs
        evidence = self._detect_patterns(evidence)
        
        return evidence
    
    def _vector_search(
        self,
        query: str,
        time_window: Optional[str],
        services: Optional[List[str]],
        top_k: int
    ) -> List[Evidence]:
        """Use vector search to find relevant logs"""
        
        # Parse time window
        time_filter = None
        if time_window and time_window != "unknown":
            try:
                parts = time_window.split('-')
                if len(parts) == 2:
                    # Convert HH:MM to full ISO timestamp (simplified)
                    start = f"2024-01-15T{parts[0]}:00Z"
                    end = f"2024-01-15T{parts[1]}:59Z"
                    time_filter = (start, end)
            except:
                pass
        
        # Call vector search
        results = vector_search_logs(
            query=query,
            top_k=top_k,
            time_window=time_filter,
            service_filter=services,
            level_filter=["ERROR", "CRITICAL", "WARN"]
        )
        
        # Convert to Evidence objects
        evidence = []
        for log in results:
            evidence.append(Evidence(
                source="log",
                content=self._format_log_message(log),
                timestamp=log.get('timestamp', ''),
                confidence=log.get('similarity', 0.8),
                metadata=log
            ))
        
        return evidence
    
    def _keyword_search(
        self,
        logs: List[Dict],
        query: str,
        time_window: Optional[str],
        services: Optional[List[str]],
        top_k: int
    ) -> List[Evidence]:
        """Fallback keyword-based search"""
        
        # Extract keywords from query
        keywords = query.lower().split()
        
        scored_logs = []
        
        for log in logs:
            # Apply filters
            if not self._passes_filters(log, time_window, services):
                continue
            
            # Score log based on keyword matches
            score = self._score_log(log, keywords)
            
            if score > 0:
                scored_logs.append((score, log))
        
        # Sort by score (descending)
        scored_logs.sort(key=lambda x: x[0], reverse=True)
        
        # Convert top results to Evidence
        evidence = []
        for score, log in scored_logs[:top_k]:
            # Normalize score to confidence (0-1)
            confidence = min(0.95, score / 10.0)
            
            evidence.append(Evidence(
                source="log",
                content=self._format_log_message(log),
                timestamp=log.get('timestamp', ''),
                confidence=confidence,
                metadata=log
            ))
        
        return evidence
    
    def _passes_filters(
        self,
        log: Dict,
        time_window: Optional[str],
        services: Optional[List[str]]
    ) -> bool:
        """Check if log passes time and service filters"""
        
        # Service filter
        if services:
            log_service = log.get('service', '')
            if log_service not in services:
                return False
        
        # Time window filter
        if time_window and time_window != "unknown":
            log_time = log.get('timestamp', '')
            if not self._in_time_window(log_time, time_window):
                return False
        
        return True
    
    def _in_time_window(self, timestamp: str, window: str) -> bool:
        """Check if timestamp is within time window"""
        try:
            # Extract time part (HH:MM)
            if 'T' in timestamp:
                time_part = timestamp.split('T')[1][:5]  # HH:MM
            else:
                return True  # Can't verify, allow it
            
            # Parse window
            start, end = window.split('-')
            
            # Simple string comparison (works for HH:MM format)
            return start <= time_part <= end
        
        except:
            return True  # On error, allow it
    
    def _score_log(self, log: Dict, keywords: List[str]) -> float:
        """Score log based on keyword matches"""
        score = 0.0
        
        # Get searchable text
        text = ' '.join([
            str(log.get('message', '')),
            str(log.get('service', '')),
            str(log.get('level', '')),
            str(log.get('stack_trace', ''))
        ]).lower()
        
        # Count keyword matches
        for keyword in keywords:
            if keyword in text:
                score += 2.0
        
        # Bonus for error levels
        level = log.get('level', '').upper()
        if level == 'ERROR':
            score += 3.0
        elif level == 'CRITICAL':
            score += 5.0
        elif level == 'WARN':
            score += 1.0
        
        # Bonus for stack traces
        if log.get('stack_trace'):
            score += 2.0
        
        # Bonus for error count
        if log.get('count', 0) > 10:
            score += 1.0
        
        return score
    
    def _format_log_message(self, log: Dict) -> str:
        """Format log entry for display"""
        parts = []
        
        if log.get('service'):
            parts.append(f"[{log['service']}]")
        
        if log.get('level'):
            parts.append(f"{log['level']}:")
        
        if log.get('message'):
            parts.append(log['message'])
        
        if log.get('count') and log['count'] > 1:
            parts.append(f"(occurred {log['count']} times)")
        
        return ' '.join(parts)
    
    def _detect_patterns(self, evidence: List[Evidence]) -> List[Evidence]:
        """
        Detect patterns in logs (error clusters, repeating issues).
        Adds pattern information to metadata.
        """
        if not evidence:
            return evidence
        
        # Group logs by message similarity
        message_groups = defaultdict(list)
        
        for ev in evidence:
            # Extract core message (remove timestamps, IDs)
            core_message = self._extract_core_message(ev.content)
            message_groups[core_message].append(ev)
        
        # Identify clusters (same error repeated)
        for core_msg, group in message_groups.items():
            if len(group) >= 3:
                # This is a cluster
                for ev in group:
                    if 'patterns' not in ev.metadata:
                        ev.metadata['patterns'] = []
                    ev.metadata['patterns'].append({
                        'type': 'error_cluster',
                        'count': len(group),
                        'message': core_msg
                    })
        
        # Sort by timestamp
        try:
            evidence.sort(key=lambda x: x.timestamp)
        except:
            pass  # If timestamps aren't comparable, skip sorting
        
        # Detect temporal patterns (cascading failures)
        for i in range(len(evidence) - 1):
            ev1, ev2 = evidence[i], evidence[i + 1]
            
            # If two different errors occur close together
            if ev1.content != ev2.content:
                time_diff = self._calculate_time_diff(ev1.timestamp, ev2.timestamp)
                
                if time_diff and time_diff < 60:  # Within 60 seconds
                    for ev in [ev1, ev2]:
                        if 'patterns' not in ev.metadata:
                            ev.metadata['patterns'] = []
                        ev.metadata['patterns'].append({
                            'type': 'temporal_correlation',
                            'time_diff_seconds': time_diff
                        })
        
        return evidence
    
    def _extract_core_message(self, message: str) -> str:
        """Extract core message, removing variable parts"""
        import re
        
        # Remove timestamps
        core = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '', message)
        
        # Remove IDs (UUIDs, numbers)
        core = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '', core, flags=re.IGNORECASE)
        core = re.sub(r'\b\d+\b', '', core)
        
        # Remove parenthetical counts
        core = re.sub(r'\(occurred \d+ times\)', '', core)
        
        return core.strip()
    
    def _calculate_time_diff(self, time1: str, time2: str) -> Optional[float]:
        """Calculate time difference in seconds between two timestamps"""
        try:
            dt1 = datetime.fromisoformat(time1.replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(time2.replace('Z', '+00:00'))
            return abs((dt2 - dt1).total_seconds())
        except:
            return None


# Module-level convenience function
_retriever_instance = None

def get_retriever() -> LogRetriever:
    """Get or create singleton retriever instance"""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = LogRetriever()
    return _retriever_instance


def retrieve_logs(
    logs: List[Dict],
    time_window: Optional[str] = None,
    services: Optional[List[str]] = None,
    symptoms: Optional[List[str]] = None,
    top_k: int = 20
) -> List[Evidence]:
    """
    Convenience function for retrieving logs.
    
    Args:
        logs: List of log entries
        time_window: Time range string (e.g., "14:25-14:40")
        services: List of service names
        symptoms: List of symptom keywords
        top_k: Maximum results
    
    Returns:
        List of Evidence objects
    """
    retriever = get_retriever()
    return retriever.retrieve_logs(logs, time_window, services, symptoms, top_k)


# CLI for testing
def main():
    """Test log retrieval"""
    import json
    import argparse
    
    parser = argparse.ArgumentParser(description="Test log retrieval")
    parser.add_argument('--logs', help='Path to logs JSON file')
    parser.add_argument('--query', default="error", help='Search query')
    parser.add_argument('--service', help='Service filter')
    parser.add_argument('--time', help='Time window (HH:MM-HH:MM)')
    parser.add_argument('--top-k', type=int, default=10, help='Number of results')
    
    args = parser.parse_args()
    
    # Load logs
    if args.logs:
        with open(args.logs) as f:
            data = json.load(f)
            logs = data.get('logs', data) if isinstance(data, dict) else data
    else:
        # Use sample logs
        logs = [
            {
                "timestamp": "2024-01-15T14:31:45Z",
                "level": "ERROR",
                "service": "api-gateway",
                "message": "Connection pool exhausted",
                "count": 47
            },
            {
                "timestamp": "2024-01-15T14:32:00Z",
                "level": "ERROR",
                "service": "api-gateway",
                "message": "HTTP 500: Internal Server Error",
                "count": 312
            }
        ]
    
    print("="*60)
    print("LOG RETRIEVAL TEST")
    print("="*60)
    print(f"Query: {args.query}")
    print(f"Total logs: {len(logs)}")
    print("="*60)
    
    # Retrieve logs
    evidence = retrieve_logs(
        logs=logs,
        time_window=args.time,
        services=[args.service] if args.service else None,
        symptoms=[args.query],
        top_k=args.top_k
    )
    
    print(f"\nFound {len(evidence)} relevant logs:\n")
    
    for i, ev in enumerate(evidence, 1):
        print(f"{i}. [{ev.timestamp}] (confidence: {ev.confidence:.2f})")
        print(f"   {ev.content}")
        
        if ev.metadata.get('patterns'):
            print(f"   Patterns: {ev.metadata['patterns']}")
        
        print()
    
    print("="*60)


if __name__ == "__main__":
    main()