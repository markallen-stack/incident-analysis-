"""
LLM utility for agents to intelligently query Prometheus/Grafana via Claude.
Agents use this when they need more detailed information about metrics or dashboards.
"""

import json
import os
import subprocess
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import anthropic
from ..graph import Evidence

# Configuration
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


class IntelligentMetricsQueryer:
    """
    Agent that uses Claude with Prometheus/Grafana tools to intelligently
    gather metrics and dashboard data based on incident context.
    """
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = "claude-3-5-sonnet-20241022"
    
    def query_with_tools(
        self,
        context: str,
        incident_time: str,
        affected_services: Optional[List[str]] = None,
        max_iterations: int = 10
    ) -> List[Evidence]:
        """
        Use Claude to intelligently query Prometheus/Grafana tools.
        
        Args:
            context: Description of what the agent needs (e.g., "Is CPU usage spiking?")
            incident_time: ISO timestamp of incident
            affected_services: List of services to focus on
            max_iterations: Max tool call iterations
        
        Returns:
            List of Evidence objects with gathered data
        """
        evidence_list = []
        
        # Parse incident time for range queries
        try:
            incident_dt = datetime.fromisoformat(incident_time.replace('Z', '+00:00'))
        except:
            incident_dt = datetime.utcnow()
        
        start_time = (incident_dt - timedelta(minutes=30)).isoformat()
        end_time = (incident_dt + timedelta(minutes=30)).isoformat()
        
        # Prepare system prompt
        system_prompt = f"""You are a Prometheus and Grafana expert helping analyze an incident.
        
Incident Context: {context}
Incident Time: {incident_time}
Analysis Window: {start_time} to {end_time}
Affected Services: {', '.join(affected_services) if affected_services else 'Unknown'}

Your goal is to:
1. Identify relevant metrics and dashboards for this incident
2. Query Prometheus for specific metrics that would help diagnose the issue
3. Fetch relevant Grafana dashboards and annotations
4. Synthesize findings into a clear summary

Use the available tools to gather data. Be specific with PromQL queries and dashboard searches."""
        
        # Initial message
        messages = [
            {
                "role": "user",
                "content": f"""Please help analyze this incident:

{context}

Incident Time: {incident_time}
Affected Services: {', '.join(affected_services) if affected_services else 'All'}

Use the available tools to query metrics and dashboards. Provide a structured summary of findings."""
            }
        ]
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            
            # Call Claude with tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                tools=self._get_tool_definitions(),
                messages=messages
            )
            
            # Check if we're done
            if response.stop_reason == "end_turn":
                # Extract final response
                for block in response.content:
                    if hasattr(block, 'text'):
                        evidence = Evidence(
                            source="llm_metrics_analysis",
                            content=block.text,
                            timestamp=datetime.utcnow().isoformat(),
                            confidence=0.85,
                            metadata={
                                "incident_time": incident_time,
                                "services": affected_services or [],
                                "iterations": iteration
                            }
                        )
                        evidence_list.append(evidence)
                break
            
            # Process tool use
            if response.stop_reason == "tool_use":
                # Add assistant response to messages
                messages.append({"role": "assistant", "content": response.content})
                
                # Process each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result)
                        })
                
                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})
            else:
                break
        
        return evidence_list
    
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for Claude."""
        return [
            {
                "name": "query_prometheus_instant",
                "description": "Execute an instant PromQL query against Prometheus",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "PromQL query (e.g., 'rate(http_requests_total[5m])')"
                        },
                        "time": {
                            "type": "string",
                            "description": "Optional Unix/ISO timestamp"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "query_prometheus_range",
                "description": "Execute a range PromQL query for time series data",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "PromQL query"},
                        "start": {"type": "string", "description": "Start time"},
                        "end": {"type": "string", "description": "End time"},
                        "step": {"type": "string", "description": "Step interval (default 1m)"}
                    },
                    "required": ["query", "start", "end"]
                }
            },
            {
                "name": "get_prometheus_alerts",
                "description": "Get active alerts from Prometheus",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "search_grafana_dashboards",
                "description": "Search Grafana dashboards by name or tags",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search term"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            {
                "name": "get_grafana_dashboard",
                "description": "Fetch dashboard definition",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dashboard_uid": {"type": "string", "description": "Dashboard UID"}
                    },
                    "required": ["dashboard_uid"]
                }
            },
            {
                "name": "get_grafana_annotations",
                "description": "Get annotations in time range",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_ms": {"type": "integer"},
                        "end_ms": {"type": "integer"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["start_ms", "end_ms"]
                }
            }
        ]
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call via the MCP server."""
        import requests
        
        try:
            if tool_name == "query_prometheus_instant":
                return self._call_prometheus_instant(tool_input)
            elif tool_name == "query_prometheus_range":
                return self._call_prometheus_range(tool_input)
            elif tool_name == "get_prometheus_alerts":
                return self._call_prometheus_alerts()
            elif tool_name == "search_grafana_dashboards":
                return self._call_grafana_search(tool_input)
            elif tool_name == "get_grafana_dashboard":
                return self._call_grafana_get_dashboard(tool_input)
            elif tool_name == "get_grafana_annotations":
                return self._call_grafana_annotations(tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    def _call_prometheus_instant(self, inputs: Dict) -> Dict:
        """Query Prometheus instant."""
        import requests
        params = {"query": inputs["query"]}
        if "time" in inputs:
            params["time"] = inputs["time"]
        
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params=params,
            timeout=10
        )
        return response.json()
    
    def _call_prometheus_range(self, inputs: Dict) -> Dict:
        """Query Prometheus range."""
        import requests
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={
                "query": inputs["query"],
                "start": inputs["start"],
                "end": inputs["end"],
                "step": inputs.get("step", "1m")
            },
            timeout=10
        )
        return response.json()
    
    def _call_prometheus_alerts(self) -> Dict:
        """Get Prometheus alerts."""
        import requests
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/alerts",
            timeout=10
        )
        return response.json()
    
    def _call_grafana_search(self, inputs: Dict) -> Dict:
        """Search Grafana dashboards."""
        import requests
        params = {}
        if "query" in inputs:
            params["query"] = inputs["query"]
        if "tags" in inputs:
            params["tags"] = inputs["tags"]
        
        headers = {}
        if GRAFANA_API_KEY:
            headers["Authorization"] = f"Bearer {GRAFANA_API_KEY}"
        
        response = requests.get(
            f"{GRAFANA_URL}/api/search",
            params=params,
            headers=headers,
            timeout=10
        )
        return {"status": "success", "dashboards": response.json()}
    
    def _call_grafana_get_dashboard(self, inputs: Dict) -> Dict:
        """Get Grafana dashboard."""
        import requests
        headers = {}
        if GRAFANA_API_KEY:
            headers["Authorization"] = f"Bearer {GRAFANA_API_KEY}"
        
        response = requests.get(
            f"{GRAFANA_URL}/api/dashboards/uid/{inputs['dashboard_uid']}",
            headers=headers,
            timeout=10
        )
        dashboard = response.json()
        
        panels = []
        for panel in dashboard.get("dashboard", {}).get("panels", []):
            panels.append({
                "id": panel.get("id"),
                "title": panel.get("title"),
                "type": panel.get("type")
            })
        
        return {
            "status": "success",
            "title": dashboard.get("dashboard", {}).get("title"),
            "panels": panels
        }
    
    def _call_grafana_annotations(self, inputs: Dict) -> Dict:
        """Get Grafana annotations."""
        import requests
        params = {
            "from": inputs["start_ms"],
            "to": inputs["end_ms"],
            "limit": 100
        }
        if "tags" in inputs:
            params["tags"] = inputs["tags"]
        
        headers = {}
        if GRAFANA_API_KEY:
            headers["Authorization"] = f"Bearer {GRAFANA_API_KEY}"
        
        response = requests.get(
            f"{GRAFANA_URL}/api/annotations",
            params=params,
            headers=headers,
            timeout=10
        )
        return {"status": "success", "annotations": response.json()}


def intelligent_metrics_query(
    context: str,
    incident_time: str,
    affected_services: Optional[List[str]] = None
) -> List[Evidence]:
    """
    Wrapper function for agents to query metrics intelligently.
    """
    querier = IntelligentMetricsQueryer()
    return querier.query_with_tools(
        context=context,
        incident_time=incident_time,
        affected_services=affected_services
    )
