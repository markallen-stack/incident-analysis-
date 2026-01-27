"""
MCP Server exposing Prometheus and Grafana as tools.
Allows Claude to intelligently query metrics and dashboards.
"""

import asyncio
import json
from typing import Any
import requests
import os
from mcp.server import Server
from mcp.types import Tool, TextContent, ToolResult

# Configuration
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY", "")

# Initialize MCP Server
server = Server("prometheus-grafana-server")

# ============================================================================
# Prometheus Tools
# ============================================================================

class PrometheusTools:
    @staticmethod
    def query_prometheus(query: str, time: str = None) -> dict:
        """Execute instant PromQL query."""
        try:
            params = {"query": query}
            if time:
                params["time"] = time
            
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    @staticmethod
    def query_prometheus_range(
        query: str, 
        start: str, 
        end: str, 
        step: str = "1m"
    ) -> dict:
        """Execute range PromQL query for time series data."""
        try:
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start,
                    "end": end,
                    "step": step
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    @staticmethod
    def get_prometheus_alerts() -> dict:
        """Get active alerts from Prometheus."""
        try:
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/alerts",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    @staticmethod
    def get_prometheus_targets() -> dict:
        """Get scrape targets from Prometheus."""
        try:
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/targets",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "status": "error"}


# ============================================================================
# Grafana Tools
# ============================================================================

class GrafanaTools:
    @staticmethod
    def search_dashboards(query: str = "", tags: list = None) -> dict:
        """Search for Grafana dashboards by name or tags."""
        try:
            params = {}
            if query:
                params["query"] = query
            if tags:
                params["tags"] = ",".join(tags)
            
            headers = {"Authorization": f"Bearer {GRAFANA_API_KEY}"} if GRAFANA_API_KEY else {}
            
            response = requests.get(
                f"{GRAFANA_URL}/api/search",
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return {"status": "success", "dashboards": response.json()}
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    @staticmethod
    def get_dashboard(dashboard_uid: str) -> dict:
        """Fetch full dashboard definition."""
        try:
            headers = {"Authorization": f"Bearer {GRAFANA_API_KEY}"} if GRAFANA_API_KEY else {}
            
            response = requests.get(
                f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_uid}",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            dashboard = response.json()
            
            # Extract key panel info
            panels = []
            for panel in dashboard.get("dashboard", {}).get("panels", []):
                panels.append({
                    "id": panel.get("id"),
                    "title": panel.get("title"),
                    "type": panel.get("type"),
                    "targets": panel.get("targets", [])
                })
            
            return {
                "status": "success",
                "title": dashboard.get("dashboard", {}).get("title"),
                "description": dashboard.get("dashboard", {}).get("description"),
                "panels": panels
            }
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    @staticmethod
    def get_annotations(start_ms: int, end_ms: int, tags: list = None) -> dict:
        """Fetch annotations within time range."""
        try:
            params = {
                "from": start_ms,
                "to": end_ms,
                "limit": 100
            }
            if tags:
                params["tags"] = tags
            
            headers = {"Authorization": f"Bearer {GRAFANA_API_KEY}"} if GRAFANA_API_KEY else {}
            
            response = requests.get(
                f"{GRAFANA_URL}/api/annotations",
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return {"status": "success", "annotations": response.json()}
        except Exception as e:
            return {"error": str(e), "status": "error"}


# ============================================================================
# MCP Tool Definitions
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="query_prometheus_instant",
            description="Execute an instant PromQL query against Prometheus. Returns metric values at a specific point in time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query string (e.g., 'rate(http_requests_total[5m])', 'process_resident_memory_bytes / 1024 / 1024')"
                    },
                    "time": {
                        "type": "string",
                        "description": "Optional Unix timestamp or ISO timestamp for query evaluation"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="query_prometheus_range",
            description="Execute a range PromQL query against Prometheus. Returns time series data over a range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query string"
                    },
                    "start": {
                        "type": "string",
                        "description": "Start time (Unix timestamp or ISO format)"
                    },
                    "end": {
                        "type": "string",
                        "description": "End time (Unix timestamp or ISO format)"
                    },
                    "step": {
                        "type": "string",
                        "description": "Query resolution step (default: '1m')"
                    }
                },
                "required": ["query", "start", "end"]
            }
        ),
        Tool(
            name="get_prometheus_alerts",
            description="Get currently active alerts from Prometheus.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_prometheus_targets",
            description="Get list of scrape targets from Prometheus.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="search_grafana_dashboards",
            description="Search for Grafana dashboards by name or tags.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Dashboard name search query"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by dashboard tags (e.g., ['system', 'performance'])"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_grafana_dashboard",
            description="Fetch full Grafana dashboard definition and panels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dashboard_uid": {
                        "type": "string",
                        "description": "Dashboard UID (unique identifier)"
                    }
                },
                "required": ["dashboard_uid"]
            }
        ),
        Tool(
            name="get_grafana_annotations",
            description="Fetch Grafana annotations (incidents, markers, events) within a time range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_ms": {
                        "type": "integer",
                        "description": "Start time in milliseconds since epoch"
                    },
                    "end_ms": {
                        "type": "integer",
                        "description": "End time in milliseconds since epoch"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by annotation tags"
                    }
                },
                "required": ["start_ms", "end_ms"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "query_prometheus_instant":
            result = PrometheusTools.query_prometheus(
                query=arguments.get("query"),
                time=arguments.get("time")
            )
        elif name == "query_prometheus_range":
            result = PrometheusTools.query_prometheus_range(
                query=arguments.get("query"),
                start=arguments.get("start"),
                end=arguments.get("end"),
                step=arguments.get("step", "1m")
            )
        elif name == "get_prometheus_alerts":
            result = PrometheusTools.get_prometheus_alerts()
        elif name == "get_prometheus_targets":
            result = PrometheusTools.get_prometheus_targets()
        elif name == "search_grafana_dashboards":
            result = GrafanaTools.search_dashboards(
                query=arguments.get("query", ""),
                tags=arguments.get("tags")
            )
        elif name == "get_grafana_dashboard":
            result = GrafanaTools.get_dashboard(
                dashboard_uid=arguments.get("dashboard_uid")
            )
        elif name == "get_grafana_annotations":
            result = GrafanaTools.get_annotations(
                start_ms=arguments.get("start_ms"),
                end_ms=arguments.get("end_ms"),
                tags=arguments.get("tags")
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e), "status": "error"}, indent=2)
        )]


async def main():
    """Start the MCP server."""
    async with server:
        print("Prometheus/Grafana MCP Server running on stdio")
        await server.wait_for_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
