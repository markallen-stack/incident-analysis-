"""
MCP-Enhanced Log Retriever

Uses MCP filesystem server to read actual log files in addition to
vector search. This makes the system work with real logs.

Usage:
    from agents.log_retriever_mcp import retrieve_logs_with_mcp
    
    evidence = retrieve_logs_with_mcp(
        log_files=["logs/api-gateway.log", "logs/database.log"],
        time_window="14:25-14:40",
        services=["api-gateway"],
        symptoms=["error", "timeout"]
    )
"""

import base64
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.verifier import Evidence
from agents.log_retriever import LogRetriever

# Import MCP client
try:
    from mcp.client import get_mcp_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️  MCP client not available")


class MCPLogRetriever(LogRetriever):
    """
    Enhanced log retriever that uses MCP to read actual log files.
    """
    
    def __init__(self, use_vector_search: bool = True, use_mcp: bool = True):
        """
        Initialize MCP-enhanced log retriever.
        
        Args:
            use_vector_search: Whether to use vector search
            use_mcp: Whether to use MCP filesystem
        """
        super().__init__(use_vector_search)
        self.use_mcp = use_mcp and MCP_AVAILABLE
        
        if self.use_mcp:
            self.mcp_client = get_mcp_client()
    
    import base64

    def _parse_base64_log_file(self, file) -> List[Dict]:
        decoded = base64.b64decode(file.content_base64).decode("utf-8", errors="ignore")
        logs = []

        for line_num, line in enumerate(decoded.splitlines(), 1):
            if not line.strip():
                continue
        try:
            import json
            log_entry = json.loads(line)
        except:
            log_entry = {
                "message": line,
                "timestamp": self._extract_timestamp(line),
                "level": self._extract_log_level(line),
                "service": self._extract_service_from_filename(file.filename)
            }

        log_entry["_source_file"] = file.filename
        log_entry["_line_number"] = line_num
        log_entry["_source"] = "base64"

        logs.append(log_entry)

        return logs


    def retrieve_logs_from_files(
        self,
        log_files: List[str],
        time_window: Optional[str] = None,
        services: Optional[List[str]] = None,
        symptoms: Optional[List[str]] = None,
        top_k: int = 20
    ) -> List[Evidence]:
        """
        Retrieve logs from actual files using MCP.
        
        Args:
            log_files: List of log file paths
            time_window: Time range
            services: Service filter
            symptoms: Search keywords
            top_k: Max results
        
        Returns:
            List of Evidence objects
        """
        if not self.use_mcp:
            return []
        
        all_logs = []
        
        # Read each log file
        for log_file in log_files:
            logs = self._read_and_parse_log_file(log_file)
            all_logs.extend(logs)
        
        # Now use the parent class logic to filter and retrieve
        evidence = self.retrieve_logs(
            logs=all_logs,
            time_window=time_window,
            services=services,
            symptoms=symptoms,
            top_k=top_k
        )
        
        return evidence
    
    def search_log_directory(
        self,
        directory: str,
        query: str,
        file_pattern: str = "*.log",
        top_k: int = 20
    ) -> List[Evidence]:
        """
        Search for logs in a directory using MCP filesystem search.
        
        Args:
            directory: Directory to search
            query: Search query
            file_pattern: File pattern
            top_k: Max results
        
        Returns:
            List of Evidence objects
        """
        if not self.use_mcp:
            return []
        
        # Use MCP to search
        result = self.mcp_client.filesystem.search_in_files(
            directory=directory,
            query=query,
            file_pattern=file_pattern
        )
        
        if not result.success:
            print(f"⚠️  MCP search failed: {result.error}")
            return []
        
        # Convert search results to Evidence
        evidence = []
        for match in result.data[:top_k]:
            evidence.append(Evidence(
                source="log",
                content=match["content"],
                timestamp=self._extract_timestamp(match["content"]),
                confidence=0.8,
                metadata={
                    "file": match["file"],
                    "line_number": match["line_number"],
                    "source": "mcp_filesystem"
                }
            ))
        
        return evidence
    
    def _read_and_parse_log_file(self, log_file: str) -> List[Dict]:
        """Read and parse a log file into structured log entries"""
        result = self.mcp_client.filesystem.read_file(log_file)
        
        if not result.success:
            print(f"⚠️  Failed to read {log_file}: {result.error}")
            return []
        
        content = result.data
        logs = []
        
        # Parse each line
        for line_num, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue
            
            # Try to parse as JSON (common log format)
            try:
                import json
                log_entry = json.loads(line)
            except:
                # Fallback: treat as plain text
                log_entry = {
                    "message": line,
                    "timestamp": self._extract_timestamp(line),
                    "level": self._extract_log_level(line),
                    "service": self._extract_service_from_filename(log_file)
                }
            
            # Add metadata
            log_entry["_source_file"] = log_file
            log_entry["_line_number"] = line_num
            
            logs.append(log_entry)
        
        return logs
    
    def _extract_timestamp(self, line: str) -> str:
        """Extract timestamp from log line"""
        import re
        
        # Common timestamp patterns
        patterns = [
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?',
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
            r'\d{2}:\d{2}:\d{2}'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(0)
        
        return ""
    
    def _extract_log_level(self, line: str) -> str:
        """Extract log level from line"""
        line_upper = line.upper()
        
        for level in ["ERROR", "CRITICAL", "WARN", "WARNING", "INFO", "DEBUG"]:
            if level in line_upper:
                return level
        
        return "UNKNOWN"
    
    def _extract_service_from_filename(self, filename: str) -> str:
        """Extract service name from log filename"""
        # e.g., "logs/api-gateway.log" -> "api-gateway"
        path = Path(filename)
        return path.stem


# Convenience function
def retrieve_logs_with_mcp(
    log_files: Optional[List[str]] = None,
    log_files_base64: Optional[List[dict]] = None,
    log_directory: Optional[str] = None,
    query: Optional[str] = None,
    time_window: Optional[str] = None,
    services: Optional[List[str]] = None,
    symptoms: Optional[List[str]] = None,
    top_k: int = 20
) -> List[Evidence]:

    retriever = MCPLogRetriever(use_mcp=True)
    all_logs = []

    if log_files:
        for f in log_files:
            all_logs.extend(retriever._read_and_parse_log_file(f))

    if log_files_base64:
        for f in log_files_base64:
            all_logs.extend(retriever._parse_base64_log_file(f))

    if all_logs:
        return retriever.retrieve_logs(
            logs=all_logs,
            time_window=time_window,
            services=services,
            symptoms=symptoms,
            top_k=top_k
        )

    if log_directory and query:
        return retriever.search_log_directory(
            directory=log_directory,
            query=query,
            top_k=top_k
        )

    return []

# CLI for testing
def main():
    """Test MCP log retrieval"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCP log retrieval")
    parser.add_argument('--files', nargs='+', help='Log files to read')
    parser.add_argument('--dir', help='Directory to search')
    parser.add_argument('--query', default="error", help='Search query')
    parser.add_argument('--top-k', type=int, default=10, help='Max results')
    
    args = parser.parse_args()
    
    print("="*60)
    print("MCP LOG RETRIEVAL TEST")
    print("="*60)
    
    if args.files:
        print(f"Reading files: {args.files}")
        evidence = retrieve_logs_with_mcp(
            log_files=args.files,
            top_k=args.top_k
        )
    
    elif args.dir:
        print(f"Searching directory: {args.dir}")
        print(f"Query: {args.query}")
        evidence = retrieve_logs_with_mcp(
            log_directory=args.dir,
            query=args.query,
            top_k=args.top_k
        )
    
    else:
        print("❌ Specify --files or --dir")
        return
    
    print(f"\nFound {len(evidence)} log entries:\n")
    
    for i, ev in enumerate(evidence, 1):
        print(f"{i}. [{ev.timestamp}] (confidence: {ev.confidence:.2f})")
        print(f"   {ev.content}")
        if ev.metadata.get('file'):
            print(f"   From: {ev.metadata['file']}:{ev.metadata.get('line_number', '?')}")
        print()
    
    print("="*60)


if __name__ == "__main__":
    main()