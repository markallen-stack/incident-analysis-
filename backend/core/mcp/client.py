"""
MCP (Model Context Protocol) Server Integration

Integrates MCP servers for enhanced data access:
- Filesystem: Read logs, runbooks, config files
- Slack: Search incident channels and communications
- GitHub: Check deployments and code changes
- Custom: Query monitoring systems

Usage:
    from mcp.client import MCPClient
    
    client = MCPClient()
    
    # Read a file
    content = client.filesystem.read("logs/api-gateway.log")
    
    # Search Slack
    messages = client.slack.search("incident api-gateway")
    
    # Get GitHub commits
    commits = client.github.recent_commits("main", since="2024-01-15")
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import subprocess

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


@dataclass
class MCPResponse:
    """Response from an MCP server"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict] = None


class FilesystemMCP:
    """
    MCP client for filesystem operations.
    Useful for reading logs, runbooks, config files.
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize filesystem MCP.
        
        Args:
            base_path: Base directory for file operations (default: project root)
        """
        self.base_path = base_path or Path.cwd()
    
    def read_file(self, filepath: str) -> MCPResponse:
        """
        Read a file's contents.
        
        Args:
            filepath: Path to file (relative to base_path)
        
        Returns:
            MCPResponse with file contents
        """
        try:
            full_path = self.base_path / filepath
            
            if not full_path.exists():
                return MCPResponse(
                    success=False,
                    data=None,
                    error=f"File not found: {filepath}"
                )
            
            with open(full_path, 'r') as f:
                content = f.read()
            
            return MCPResponse(
                success=True,
                data=content,
                metadata={
                    "filepath": str(full_path),
                    "size_bytes": len(content),
                    "lines": len(content.splitlines())
                }
            )
        
        except Exception as e:
            return MCPResponse(
                success=False,
                data=None,
                error=str(e)
            )
    
    def list_files(self, directory: str, pattern: str = "*") -> MCPResponse:
        """
        List files in a directory.
        
        Args:
            directory: Directory path
            pattern: Glob pattern (e.g., "*.log")
        
        Returns:
            MCPResponse with list of files
        """
        try:
            dir_path = self.base_path / directory
            
            if not dir_path.exists():
                return MCPResponse(
                    success=False,
                    data=None,
                    error=f"Directory not found: {directory}"
                )
            
            files = [str(f.relative_to(self.base_path)) for f in dir_path.glob(pattern)]
            
            return MCPResponse(
                success=True,
                data=files,
                metadata={"count": len(files), "directory": str(dir_path)}
            )
        
        except Exception as e:
            return MCPResponse(
                success=False,
                data=None,
                error=str(e)
            )
    
    def search_in_files(
        self,
        directory: str,
        query: str,
        file_pattern: str = "*.log"
    ) -> MCPResponse:
        """
        Search for text in files.
        
        Args:
            directory: Directory to search
            query: Search query
            file_pattern: File pattern to search in
        
        Returns:
            MCPResponse with matching lines
        """
        try:
            dir_path = self.base_path / directory
            results = []
            
            for filepath in dir_path.glob(f"**/{file_pattern}"):
                try:
                    with open(filepath, 'r') as f:
                        for line_num, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append({
                                    "file": str(filepath.relative_to(self.base_path)),
                                    "line_number": line_num,
                                    "content": line.strip()
                                })
                except:
                    continue  # Skip files we can't read
            
            return MCPResponse(
                success=True,
                data=results,
                metadata={"matches": len(results)}
            )
        
        except Exception as e:
            return MCPResponse(
                success=False,
                data=None,
                error=str(e)
            )


class SlackMCP:
    """
    MCP client for Slack integration.
    Useful for searching incident channels and team communications.
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize Slack MCP.
        
        Args:
            token: Slack API token (optional, reads from env if not provided)
        """
        self.token = token or config.__dict__.get('SLACK_TOKEN')
        self.enabled = bool(self.token)
    
    def search_messages(
        self,
        query: str,
        channel: Optional[str] = None,
        limit: int = 10
    ) -> MCPResponse:
        """
        Search Slack messages.
        
        Args:
            query: Search query
            channel: Optional channel to search in
            limit: Max results
        
        Returns:
            MCPResponse with messages
        """
        if not self.enabled:
            return MCPResponse(
                success=False,
                data=None,
                error="Slack MCP not configured. Set SLACK_TOKEN in config."
            )
        
        # TODO: Implement actual Slack API call
        # For now, return mock data
        return MCPResponse(
            success=True,
            data=[
                {
                    "timestamp": "2024-01-15T14:30:00Z",
                    "user": "alice",
                    "channel": "incidents",
                    "text": f"Seeing API errors related to {query}",
                    "thread_ts": "1234567890.123456"
                }
            ],
            metadata={"mock": True, "message": "Slack API not yet implemented"}
        )
    
    def get_incident_channel_history(
        self,
        channel: str,
        since: str
    ) -> MCPResponse:
        """
        Get incident channel history.
        
        Args:
            channel: Channel name
            since: ISO timestamp
        
        Returns:
            MCPResponse with channel messages
        """
        if not self.enabled:
            return MCPResponse(
                success=False,
                data=None,
                error="Slack MCP not configured"
            )
        
        # Mock implementation
        return MCPResponse(
            success=True,
            data=[],
            metadata={"mock": True}
        )


class GitHubMCP:
    """
    MCP client for GitHub integration.
    Useful for checking deployments, code changes, and commits.
    """
    
    def __init__(self, token: Optional[str] = None, repo: Optional[str] = None):
        """
        Initialize GitHub MCP.
        
        Args:
            token: GitHub API token
            repo: Repository (format: "owner/repo")
        """
        self.token = token or config.__dict__.get('GITHUB_TOKEN')
        self.repo = repo or config.__dict__.get('GITHUB_REPO')
        self.enabled = bool(self.token and self.repo)
    
    def recent_commits(
        self,
        branch: str = "main",
        since: Optional[str] = None,
        limit: int = 10
    ) -> MCPResponse:
        """
        Get recent commits.
        
        Args:
            branch: Branch name
            since: ISO timestamp (e.g., "2024-01-15T14:00:00Z")
            limit: Max commits
        
        Returns:
            MCPResponse with commits
        """
        if not self.enabled:
            return MCPResponse(
                success=False,
                data=None,
                error="GitHub MCP not configured. Set GITHUB_TOKEN and GITHUB_REPO."
            )
        
        # Mock implementation
        return MCPResponse(
            success=True,
            data=[
                {
                    "sha": "abc123def456",
                    "timestamp": "2024-01-15T14:29:00Z",
                    "author": "developer",
                    "message": "Update connection pool configuration",
                    "files_changed": ["src/db/pool.py"]
                }
            ],
            metadata={"mock": True, "message": "GitHub API not yet implemented"}
        )
    
    def get_deployment(self, deployment_id: str) -> MCPResponse:
        """
        Get deployment details.
        
        Args:
            deployment_id: Deployment ID
        
        Returns:
            MCPResponse with deployment info
        """
        if not self.enabled:
            return MCPResponse(
                success=False,
                data=None,
                error="GitHub MCP not configured"
            )
        
        # Mock implementation
        return MCPResponse(
            success=True,
            data={
                "id": deployment_id,
                "timestamp": "2024-01-15T14:29:00Z",
                "environment": "production",
                "status": "success",
                "commit": "abc123def456"
            },
            metadata={"mock": True}
        )


class MonitoringMCP:
    """
    MCP client for monitoring systems (Prometheus, Grafana, etc.)
    Useful for querying real-time metrics.
    """
    
    def __init__(self, prometheus_url: Optional[str] = None):
        """
        Initialize monitoring MCP.
        
        Args:
            prometheus_url: Prometheus API URL
        """
        self.prometheus_url = prometheus_url or config.__dict__.get('PROMETHEUS_URL')
        self.enabled = bool(self.prometheus_url)
    
    def query_metric(
        self,
        query: str,
        time: Optional[str] = None
    ) -> MCPResponse:
        """
        Query Prometheus metric.
        
        Args:
            query: PromQL query (e.g., "rate(http_requests_total[5m])")
            time: ISO timestamp for point query
        
        Returns:
            MCPResponse with metric data
        """
        if not self.enabled:
            return MCPResponse(
                success=False,
                data=None,
                error="Monitoring MCP not configured. Set PROMETHEUS_URL."
            )
        
        # Mock implementation
        return MCPResponse(
            success=True,
            data={
                "metric": query,
                "value": 95.0,
                "timestamp": time or "2024-01-15T14:32:00Z"
            },
            metadata={"mock": True, "message": "Prometheus API not yet implemented"}
        )
    
    def query_range(
        self,
        query: str,
        start: str,
        end: str,
        step: str = "1m"
    ) -> MCPResponse:
        """
        Query metric range.
        
        Args:
            query: PromQL query
            start: Start time (ISO)
            end: End time (ISO)
            step: Step size (e.g., "1m")
        
        Returns:
            MCPResponse with time series data
        """
        if not self.enabled:
            return MCPResponse(
                success=False,
                data=None,
                error="Monitoring MCP not configured"
            )
        
        # Mock implementation
        return MCPResponse(
            success=True,
            data={
                "metric": query,
                "values": [
                    {"timestamp": start, "value": 15.0},
                    {"timestamp": end, "value": 95.0}
                ]
            },
            metadata={"mock": True}
        )


class MCPClient:
    """
    Unified MCP client for all integrations.
    """
    
    def __init__(self):
        """Initialize all MCP clients"""
        self.filesystem = FilesystemMCP()
        self.slack = SlackMCP()
        self.github = GitHubMCP()
        self.monitoring = MonitoringMCP()
    
    def get_available_servers(self) -> List[str]:
        """Get list of enabled MCP servers"""
        servers = []
        
        if self.filesystem:
            servers.append("filesystem")
        if self.slack.enabled:
            servers.append("slack")
        if self.github.enabled:
            servers.append("github")
        if self.monitoring.enabled:
            servers.append("monitoring")
        
        return servers
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all MCP servers"""
        return {
            "filesystem": True,  # Always available
            "slack": self.slack.enabled,
            "github": self.github.enabled,
            "monitoring": self.monitoring.enabled
        }


# Global client instance
_mcp_client = None

def get_mcp_client() -> MCPClient:
    """Get or create global MCP client instance"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


# CLI for testing
def main():
    """Test MCP client"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCP client")
    parser.add_argument('--test', choices=['filesystem', 'slack', 'github', 'monitoring'],
                       help='Which MCP server to test')
    
    args = parser.parse_args()
    
    client = get_mcp_client()
    
    print("="*60)
    print("MCP CLIENT TEST")
    print("="*60)
    
    # Show available servers
    available = client.get_available_servers()
    print(f"\nAvailable MCP servers: {', '.join(available)}")
    
    # Health check
    health = client.health_check()
    print("\nHealth Check:")
    for server, status in health.items():
        symbol = "✅" if status else "❌"
        print(f"  {symbol} {server}")
    
    # Test specific server
    if args.test == 'filesystem':
        print("\n--- Testing Filesystem MCP ---")
        
        # List files
        result = client.filesystem.list_files("data", "*.json")
        print(f"\nList files in data/: {result.success}")
        if result.success:
            print(f"  Found {len(result.data)} files:")
            for f in result.data[:5]:
                print(f"    • {f}")
        
        # Read file
        result = client.filesystem.read_file("data/incidents.json")
        print(f"\nRead data/incidents.json: {result.success}")
        if result.success:
            print(f"  Size: {result.metadata['size_bytes']} bytes")
            print(f"  Lines: {result.metadata['lines']}")
        
        # Search
        result = client.filesystem.search_in_files("data/logs", "error", "*.json")
        print(f"\nSearch for 'error' in logs: {result.success}")
        if result.success:
            print(f"  Matches: {result.metadata['matches']}")
    
    elif args.test == 'slack':
        print("\n--- Testing Slack MCP ---")
        result = client.slack.search_messages("incident api")
        print(f"Search result: {result.success}")
        if result.metadata and result.metadata.get('mock'):
            print(f"  Note: {result.metadata['message']}")
    
    elif args.test == 'github':
        print("\n--- Testing GitHub MCP ---")
        result = client.github.recent_commits()
        print(f"Recent commits: {result.success}")
        if result.metadata and result.metadata.get('mock'):
            print(f"  Note: {result.metadata['message']}")
    
    elif args.test == 'monitoring':
        print("\n--- Testing Monitoring MCP ---")
        result = client.monitoring.query_metric("cpu_usage")
        print(f"Query metric: {result.success}")
        if result.metadata and result.metadata.get('mock'):
            print(f"  Note: {result.metadata['message']}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()