"""
MCP (Model Context Protocol) Integration Package

Provides MCP server clients for accessing external data sources:
- Filesystem: Read logs, runbooks, config files
- Slack: Search incident channels
- GitHub: Check deployments and commits  
- Monitoring: Query Prometheus/Grafana

Usage:
    from mcp import get_mcp_client
    
    client = get_mcp_client()
    
    # Read a file
    result = client.filesystem.read_file("logs/api.log")
    
    # Search Slack
    messages = client.slack.search_messages("incident")
    
    # Get GitHub commits
    commits = client.github.recent_commits("main")
"""

from mcp.client import (
    MCPClient,
    MCPResponse,
    FilesystemMCP,
    SlackMCP,
    GitHubMCP,
    MonitoringMCP,
    get_mcp_client
)

__all__ = [
    'MCPClient',
    'MCPResponse',
    'FilesystemMCP',
    'SlackMCP',
    'GitHubMCP',
    'MonitoringMCP',
    'get_mcp_client'
]

__version__ = '0.1.0'