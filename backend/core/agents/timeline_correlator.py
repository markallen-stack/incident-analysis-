"""
Timeline Correlation Agent

Aligns events from different sources (dashboards, logs, deployments) 
chronologically and identifies temporal correlations.

Usage:
    from agents.timeline_correlator import build_timeline
    
    timeline, correlations, gaps = build_timeline(all_evidence)
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.verifier import Evidence


class TimelineCorrelator:
    """
    Correlates events across time from multiple evidence sources.
    """
    
    def __init__(self, correlation_window: int = 300):
        """
        Initialize timeline correlator.
        
        Args:
            correlation_window: Time window in seconds for correlating events (default 5min)
        """
        self.correlation_window = correlation_window
    
    def build_timeline(
        self,
        all_evidence: List[Evidence]
    ) -> Tuple[List[Dict], List[Dict], List[str]]:
        """
        Builds a chronological timeline from all evidence sources.
        
        Args:
            all_evidence: Combined evidence from all agents
        
        Returns:
            Tuple of (timeline_events, correlations, gaps)
            - timeline_events: Chronologically sorted list of events
            - correlations: Identified temporal correlations
            - gaps: Missing data periods
        """
        # Convert evidence to timeline events
        events = self._evidence_to_events(all_evidence)
        
        # Sort chronologically
        events = self._sort_events(events)
        
        # Identify correlations
        correlations = self._find_correlations(events)
        
        # Identify gaps
        gaps = self._find_gaps(events)
        
        return events, correlations, gaps
    
    def _evidence_to_events(self, evidence_list: List[Evidence]) -> List[Dict]:
        """Convert Evidence objects to timeline events"""
        events = []
        
        for evidence in evidence_list:
            event = {
                "time": evidence.timestamp,
                "event": self._extract_event_description(evidence),
                "source": evidence.source,
                "confidence": evidence.confidence,
                "raw_evidence": evidence
            }
            
            # Add event type classification
            event["event_type"] = self._classify_event(evidence)
            
            events.append(event)
        
        return events
    
    def _extract_event_description(self, evidence: Evidence) -> str:
        """Extract concise event description from evidence"""
        content = evidence.content
        
        # Truncate long content
        if len(content) > 150:
            content = content[:150] + "..."
        
        # For logs, extract key message
        if evidence.source == "log":
            if "ERROR" in content:
                # Extract error message
                parts = content.split("ERROR:")
                if len(parts) > 1:
                    return f"Error: {parts[1].strip()}"
            
            if "CRITICAL" in content:
                parts = content.split("CRITICAL:")
                if len(parts) > 1:
                    return f"Critical: {parts[1].strip()}"
        
        return content
    
    def _classify_event(self, evidence: Evidence) -> str:
        """Classify event type for correlation analysis"""
        content_lower = evidence.content.lower()
        
        # Deployment events
        if any(word in content_lower for word in ['deploy', 'deployment', 'release']):
            return "deployment"
        
        # Metric anomalies
        if any(word in content_lower for word in ['spike', 'increase', 'high', 'drop', 'low']):
            return "metric_anomaly"
        
        # Errors
        if any(word in content_lower for word in ['error', 'exception', 'failure', 'crash']):
            return "error"
        
        # Performance
        if any(word in content_lower for word in ['slow', 'timeout', 'latency']):
            return "performance"
        
        # Capacity
        if any(word in content_lower for word in ['memory', 'cpu', 'disk', 'connection']):
            return "capacity"
        
        # Configuration changes
        if any(word in content_lower for word in ['config', 'setting', 'update']):
            return "configuration"
        
        return "other"
    
    def _sort_events(self, events: List[Dict]) -> List[Dict]:
        """Sort events chronologically"""
        
        # Filter out events without timestamps
        events_with_time = []
        events_without_time = []
        
        for event in events:
            if event["time"] and event["time"] != "unknown":
                events_with_time.append(event)
            else:
                events_without_time.append(event)
        
        # Sort events with timestamps
        try:
            events_with_time.sort(key=lambda x: self._parse_timestamp(x["time"]))
        except Exception as e:
            print(f"⚠️  Failed to sort timeline: {e}")
            # Fall back to string sort
            events_with_time.sort(key=lambda x: x["time"])
        
        # Combine: timestamped events first, then others
        return events_with_time + events_without_time
    
    def _parse_timestamp(self, timestamp: str) -> datetime:
        """Parse timestamp string to datetime"""
        # Handle different timestamp formats
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp, fmt)
            except:
                continue
        
        # Fallback: try to extract date/time parts
        try:
            # Remove timezone info and try again
            cleaned = timestamp.replace('+00:00', '').replace('Z', '')
            return datetime.fromisoformat(cleaned)
        except:
            # Default to epoch if all parsing fails
            return datetime(1970, 1, 1)
    
    def _find_correlations(self, events: List[Dict]) -> List[Dict]:
        """Find temporal correlations between events"""
        correlations = []
        
        # Look for patterns in adjacent events
        for i in range(len(events) - 1):
            for j in range(i + 1, min(i + 5, len(events))):  # Check next 4 events
                corr = self._check_correlation(events[i], events[j])
                if corr:
                    correlations.append(corr)
        
        # Deduplicate correlations
        correlations = self._deduplicate_correlations(correlations)
        
        return correlations
    
    def _check_correlation(self, event1: Dict, event2: Dict) -> Optional[Dict]:
        """Check if two events are temporally correlated"""
        
        # Calculate time difference
        time_diff = self._calculate_time_diff(event1["time"], event2["time"])
        
        if time_diff is None:
            return None
        
        # Events must be within correlation window
        if time_diff > self.correlation_window:
            return None
        
        # Check for meaningful correlation patterns
        type1 = event1["event_type"]
        type2 = event2["event_type"]
        
        # Known correlation patterns
        correlation_patterns = {
            ("deployment", "error"): "Deployment likely caused errors",
            ("deployment", "metric_anomaly"): "Deployment triggered metric change",
            ("metric_anomaly", "error"): "Metric anomaly preceded errors",
            ("capacity", "performance"): "Capacity issue caused performance degradation",
            ("error", "error"): "Cascading errors",
            ("configuration", "error"): "Config change may have caused errors"
        }
        
        pattern_key = (type1, type2)
        if pattern_key in correlation_patterns:
            return {
                "event1": event1["event"],
                "event2": event2["event"],
                "time1": event1["time"],
                "time2": event2["time"],
                "time_delta_seconds": time_diff,
                "pattern": correlation_patterns[pattern_key],
                "strength": self._calculate_correlation_strength(time_diff, type1, type2),
                "causal_direction": "event1 → event2"
            }
        
        # Generic correlation for nearby events
        if time_diff < 120:  # Within 2 minutes
            return {
                "event1": event1["event"],
                "event2": event2["event"],
                "time1": event1["time"],
                "time2": event2["time"],
                "time_delta_seconds": time_diff,
                "pattern": f"{type1} followed by {type2}",
                "strength": "weak",
                "causal_direction": "possible"
            }
        
        return None
    
    def _calculate_time_diff(self, time1: str, time2: str) -> Optional[float]:
        """Calculate time difference in seconds"""
        try:
            dt1 = self._parse_timestamp(time1)
            dt2 = self._parse_timestamp(time2)
            return abs((dt2 - dt1).total_seconds())
        except:
            return None
    
    def _calculate_correlation_strength(
        self,
        time_diff: float,
        type1: str,
        type2: str
    ) -> str:
        """Calculate correlation strength"""
        
        # Closer in time = stronger correlation
        if time_diff < 60:  # Within 1 minute
            base_strength = "strong"
        elif time_diff < 180:  # Within 3 minutes
            base_strength = "medium"
        else:
            base_strength = "weak"
        
        # Boost for known causal patterns
        strong_patterns = [
            ("deployment", "error"),
            ("deployment", "metric_anomaly"),
            ("configuration", "error")
        ]
        
        if (type1, type2) in strong_patterns and time_diff < 300:
            return "strong"
        
        return base_strength
    
    def _deduplicate_correlations(self, correlations: List[Dict]) -> List[Dict]:
        """Remove duplicate or redundant correlations"""
        seen = set()
        unique_correlations = []
        
        for corr in correlations:
            # Create a signature for this correlation
            sig = (corr["time1"], corr["time2"], corr["pattern"])
            
            if sig not in seen:
                seen.add(sig)
                unique_correlations.append(corr)
        
        return unique_correlations
    
    def _find_gaps(self, events: List[Dict]) -> List[str]:
        """Identify gaps in the timeline (missing data)"""
        gaps = []
        
        if len(events) < 2:
            return ["Insufficient timeline data"]
        
        # Check for large time gaps between events
        for i in range(len(events) - 1):
            time_diff = self._calculate_time_diff(
                events[i]["time"],
                events[i + 1]["time"]
            )
            
            if time_diff and time_diff > 600:  # > 10 minutes gap
                gaps.append(
                    f"Large time gap ({int(time_diff/60)} minutes) between "
                    f"{events[i]['time']} and {events[i+1]['time']}"
                )
        
        # Check for missing data sources
        sources = set(event["source"] for event in events)
        
        if "image" not in sources:
            gaps.append("No dashboard metrics provided")
        
        if "log" not in sources:
            gaps.append("No application logs provided")
        
        if "historical" not in sources:
            gaps.append("No historical incident data available")
        
        return gaps


# Module-level convenience function
_correlator_instance = None

def get_correlator() -> TimelineCorrelator:
    """Get or create singleton correlator instance"""
    global _correlator_instance
    if _correlator_instance is None:
        _correlator_instance = TimelineCorrelator()
    return _correlator_instance


def build_timeline(
    all_evidence: List[Evidence]
) -> Tuple[List[Dict], List[Dict], List[str]]:
    """
    Convenience function for building timeline.
    
    Args:
        all_evidence: Combined evidence from all sources
    
    Returns:
        (timeline_events, correlations, gaps)
    """
    correlator = get_correlator()
    return correlator.build_timeline(all_evidence)


# CLI for testing
def main():
    """Test timeline correlation"""
    import json
    
    # Create sample evidence
    sample_evidence = [
        Evidence(
            source="log",
            content="Deployment v2.1.5 started",
            timestamp="2024-01-15T14:29:00Z",
            confidence=0.95,
            metadata={}
        ),
        Evidence(
            source="image",
            content="CPU usage spiked to 95%",
            timestamp="2024-01-15T14:31:00Z",
            confidence=0.9,
            metadata={}
        ),
        Evidence(
            source="log",
            content="ERROR: OutOfMemoryError in ConnectionPool",
            timestamp="2024-01-15T14:31:45Z",
            confidence=0.95,
            metadata={}
        ),
        Evidence(
            source="log",
            content="HTTP 500 errors starting",
            timestamp="2024-01-15T14:32:00Z",
            confidence=0.9,
            metadata={}
        ),
        Evidence(
            source="historical",
            content="INC-2023-089: Memory leak in connection pool",
            timestamp="2023-11-12",
            confidence=0.92,
            metadata={}
        )
    ]
    
    print("="*60)
    print("TIMELINE CORRELATION TEST")
    print("="*60)
    
    timeline, correlations, gaps = build_timeline(sample_evidence)
    
    print("\n📅 Timeline:")
    for i, event in enumerate(timeline, 1):
        print(f"{i}. [{event['time']}] ({event['source']}) {event['event_type']}")
        print(f"   {event['event']}")
    
    print("\n🔗 Correlations:")
    for i, corr in enumerate(correlations, 1):
        print(f"{i}. {corr['pattern']} (strength: {corr['strength']})")
        print(f"   {corr['event1']}")
        print(f"   → ({corr['time_delta_seconds']:.0f}s later) →")
        print(f"   {corr['event2']}")
        print()
    
    print("⚠️  Gaps:")
    for gap in gaps:
        print(f"   • {gap}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()