# mcp_servers/prometheus_server.py
from mcp.server import Server
from mcp.server.models import InitializationOptions
import httpx
import asyncio
from typing import Dict, Any, List
import os
from datetime import datetime, timedelta
import json

# Initialize server
server = Server("prometheus-analyst")

class PrometheusClient:
    def __init__(self, base_url: str = "http://localhost:9090"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def query(self, promql: str, range_minutes: int = 15) -> Dict[str, Any]:
        """Execute PromQL query"""
        try:
            end = datetime.now()
            start = end - timedelta(minutes=range_minutes)
            
            params = {
                "query": promql,
                "start": start.isoformat() + "Z",
                "end": end.isoformat() + "Z",
                "step": "30s"
            }
            
            response = await self.client.get(
                f"{self.base_url}/api/v1/query_range",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

prometheus = PrometheusClient(os.getenv("PROMETHEUS_URL", "http://localhost:9090"))

@server.list_tools()
async def handle_list_tools():
    """Expose Prometheus tools to Claude"""
    return [
        {
            "name": "query_metric",
            "description": "Query Prometheus metrics using PromQL",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "promql": {
                        "type": "string",
                        "description": "PromQL query (e.g., 'rate(http_requests_total[5m])')"
                    },
                    "time_range_minutes": {
                        "type": "integer",
                        "description": "Time range in minutes",
                        "default": 15
                    }
                },
                "required": ["promql"]
            }
        },
        {
            "name": "analyze_service_health",
            "description": "Comprehensive service health analysis",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service"
                    },
                    "check_metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Metrics to check",
                        "default": ["request_rate", "error_rate", "latency_p95", "cpu_usage", "memory_usage"]
                    }
                },
                "required": ["service_name"]
            }
        },
        {
            "name": "detect_anomalies",
            "description": "Detect anomalies in service metrics",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                    "metric": {"type": "string", "default": "request_rate"},
                    "threshold_stddev": {"type": "number", "default": 2.5}
                },
                "required": ["service_name"]
            }
        },
        {
            "name": "get_related_metrics",
            "description": "Find metrics related to a service or issue",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["keyword"]
            }
        }
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]):
    """Handle tool execution"""
    
    if name == "query_metric":
        result = await prometheus.query(
            arguments["promql"],
            arguments.get("time_range_minutes", 15)
        )
        return format_prometheus_result(result)
    
    elif name == "analyze_service_health":
        return await analyze_service_health(
            arguments["service_name"],
            arguments.get("check_metrics", [])
        )
    
    elif name == "detect_anomalies":
        return await detect_metric_anomalies(
            arguments["service_name"],
            arguments["metric"],
            arguments.get("threshold_stddev", 2.5)
        )
    
    elif name == "get_related_metrics":
        # Find metrics containing keyword
        result = await prometheus.query(
            f'{{__name__=~".*{arguments["keyword"]}.*"}}',
            5
        )
        return format_metric_list(result, arguments.get("limit", 10))

async def analyze_service_health(service: str, metrics: List[str]) -> str:
    """Comprehensive service analysis"""
    analysis = [f"Health analysis for {service}:"]
    
    # Check if service is up
    up_result = await prometheus.query(f'up{{job=~".*{service}.*"}}', 5)
    if up_result.get("data", {}).get("result"):
        analysis.append("✓ Service is UP")
    else:
        analysis.append("✗ Service is DOWN or not scraped")
    
    # Check each metric
    for metric in metrics:
        if metric == "error_rate":
            promql = f'sum(rate(http_request_errors_total{{service="{service}"}}[5m])) / sum(rate(http_requests_total{{service="{service}"}}[5m])) * 100'
        elif metric == "request_rate":
            promql = f'sum(rate(http_requests_total{{service="{service}"}}[5m]))'
        elif metric == "latency_p95":
            promql = f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) by (le))'
        else:
            promql = f'{metric}{{service="{service}"}}'
        
        result = await prometheus.query(promql, 15)
        value = extract_latest_value(result)
        analysis.append(f"{metric}: {value}")
    
    return "\n".join(analysis)

def format_prometheus_result(result: Dict) -> str:
    """Format Prometheus result for Claude"""
    if "error" in result:
        return f"Error: {result['error']}"
    
    data = result.get("data", {}).get("result", [])
    if not data:
        return "No data returned"
    
    formatted = []
    for item in data[:10]:  # Limit to 10 series
        metric = item.get("metric", {})
        values = item.get("values", [])
        latest = values[-1][1] if values else "No data"
        
        # Create readable metric string
        labels = ", ".join([f"{k}={v}" for k, v in metric.items()])
        formatted.append(f"{labels}: {latest}")
    
    return "\n".join(formatted)

async def main():
    """Run the MCP server"""
    from mcp.server import stdio
    async with stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, InitializationOptions())

if __name__ == "__main__":
    asyncio.run(main())