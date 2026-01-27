#!/usr/bin/env python3
"""
CLI interface for analyzing incidents.

Usage:
    python analyze.py --query "API outage at 14:32" \
                      --dashboard grafana.png \
                      --logs logs.json \
                      --timestamp "2024-01-15T14:32:00Z"
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional
import logging

from core.graph import build_incident_analysis_graph
import config

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_logs(log_path: str) -> list:
    """Load logs from JSON file."""
    try:
        with open(log_path) as f:
            logs = json.load(f)
            if isinstance(logs, dict):
                logs = logs.get("logs", [])
            return logs
    except Exception as e:
        logger.error(f"Failed to load logs from {log_path}: {e}")
        return []


def format_output(result: dict) -> str:
    """Format the analysis result for display."""
    decision = result.get("decision", "unknown")
    final_response = result.get("final_response", {})
    confidence = result.get("overall_confidence", 0.0)
    
    output = []
    output.append("=" * 63)
    output.append("🎯 INCIDENT ANALYSIS RESULT")
    output.append("=" * 63)
    output.append("")
    
    if decision == "answer":
        output.append(f"Status: ANSWER")
        output.append(f"Confidence: {confidence:.2f} ({'HIGH' if confidence >= 0.8 else 'MEDIUM'})")
        output.append("")
        
        output.append("Root Cause:")
        output.append(final_response.get("root_cause", "N/A"))
        output.append("")
        
        evidence = final_response.get("evidence", {})
        if evidence:
            output.append("Evidence:")
            for source, content in evidence.items():
                output.append(f"✓ {source.title()}: {content}")
            output.append("")
        
        timeline = final_response.get("timeline")
        if timeline:
            output.append("Timeline:")
            output.append(timeline)
            output.append("")
        
        actions = final_response.get("recommended_actions", [])
        if actions:
            output.append("Recommended Actions:")
            for i, action in enumerate(actions, 1):
                output.append(f"{i}. {action}")
            output.append("")
        
        alternatives = final_response.get("alternative_hypotheses", [])
        if alternatives:
            output.append("Alternative Hypotheses Considered:")
            for alt in alternatives:
                output.append(f"• {alt.get('hypothesis', '')} → {alt.get('why_less_likely', '')}")
    
    elif decision == "refuse":
        output.append(f"Status: REFUSED")
        output.append(f"Confidence: {confidence:.2f} (LOW)")
        output.append("")
        output.append(f"Reason: {final_response.get('reason', 'Insufficient evidence')}")
        output.append("")
        
        what_we_know = final_response.get("what_we_know", [])
        if what_we_know:
            output.append("What We Know:")
            for item in what_we_know:
                output.append(f"• {item}")
            output.append("")
        
        missing = final_response.get("missing_evidence", [])
        if missing:
            output.append("Missing Evidence:")
            for item in missing:
                output.append(f"• {item}")
            output.append("")
        
        suggestion = final_response.get("suggestion")
        if suggestion:
            output.append(f"Suggestion: {suggestion}")
    
    elif decision == "request_more_data":
        output.append(f"Status: REQUEST MORE DATA")
        output.append(f"Confidence: {confidence:.2f} (MEDIUM)")
        output.append("")
        
        leading = final_response.get("leading_hypothesis")
        if leading:
            output.append(f"Leading Hypothesis: {leading}")
            output.append("")
        
        needed = final_response.get("needed_data", [])
        if needed:
            output.append("Needed Data:")
            for item in needed:
                output.append(f"• {item}")
            output.append("")
        
        why = final_response.get("why_needed")
        if why:
            output.append(f"Why Needed: {why}")
    
    output.append("=" * 63)
    
    return "\n".join(output)


def analyze_incident(
    query: str,
    timestamp: str,
    dashboard_images: Optional[list] = None,
    logs: Optional[list] = None,
    output_format: str = "text"
) -> dict:
    """
    Analyzes an incident using the agentic system.
    
    Args:
        query: User's incident description
        timestamp: Incident timestamp
        dashboard_images: List of dashboard screenshot paths
        logs: List of log entries
        output_format: Output format ("text" or "json")
    
    Returns:
        Analysis result dictionary
    """
    logger.info(f"Starting incident analysis: {query}")
    
    # Build graph
    graph = build_incident_analysis_graph()
    
    # Prepare initial state
    initial_state = {
        "user_query": query,
        "dashboard_images": dashboard_images or [],
        "logs": logs or [],
        "timestamp": timestamp,
        "image_evidence": [],
        "log_evidence": [],
        "rag_evidence": [],
        "errors": [],
        "agent_history": []
    }
    
    try:
        # Run analysis
        result = graph.invoke(initial_state)
        logger.info(f"Analysis complete. Decision: {result.get('decision')}")
        return result
    
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return {
            "decision": "error",
            "final_response": {
                "error": str(e)
            },
            "overall_confidence": 0.0
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze DevOps incidents using AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze with all data sources
  python analyze.py --query "API outage at 14:32" \\
                    --dashboard grafana.png \\
                    --logs logs.json \\
                    --timestamp "2024-01-15T14:32:00Z"
  
  # Analyze with just logs
  python analyze.py --query "Database errors" \\
                    --logs db_logs.json \\
                    --timestamp "2024-01-15T10:00:00Z"
  
  # Output as JSON
  python analyze.py --query "Memory spike" \\
                    --logs logs.json \\
                    --timestamp "2024-01-15T14:32:00Z" \\
                    --format json
        """
    )
    
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="Incident description or query"
    )
    
    parser.add_argument(
        "--timestamp", "-t",
        required=True,
        help="Incident timestamp (ISO format)"
    )
    
    parser.add_argument(
        "--dashboard", "-d",
        action="append",
        help="Dashboard screenshot path(s) (can be used multiple times)"
    )
    
    parser.add_argument(
        "--logs", "-l",
        help="Path to logs JSON file"
    )
    
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load logs if provided
    logs = load_logs(args.logs) if args.logs else []
    
    # Run analysis
    result = analyze_incident(
        query=args.query,
        timestamp=args.timestamp,
        dashboard_images=args.dashboard,
        logs=logs,
        output_format=args.format
    )
    
    # Format output
    if args.format == "json":
        output = json.dumps(result, indent=2, default=str)
    else:
        output = format_output(result)
    
    # Write output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"✅ Results written to {args.output}")
    else:
        print(output)
    
    # Exit code based on confidence
    confidence = result.get("overall_confidence", 0.0)
    if confidence >= config.CONFIDENCE_THRESHOLD:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()