"""
Python client for Incident Analysis API

Usage:
    from api.client import IncidentAnalysisClient
    
    client = IncidentAnalysisClient("http://localhost:8000")
    
    result = client.analyze_incident(
        query="API outage at 14:32",
        timestamp="2024-01-15T14:32:00Z",
        log_files=["logs/api-gateway.log"]
    )
    
    print(f"Confidence: {result['confidence']}")
    print(f"Root cause: {result['root_cause']}")
"""

import requests
from typing import List, Optional, Dict, Any
from pathlib import Path
import json


class IncidentAnalysisClient:
    """
    Python client for the Incident Analysis API.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize client.
        
        Args:
            base_url: API base URL
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    def health_check(self) -> Dict:
        """
        Check API health.
        
        Returns:
            Health status dict
        """
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def analyze_incident(
        self,
        query: str,
        timestamp: str,
        dashboard_images: Optional[List[str]] = None,
        log_files: Optional[List[str]] = None,
        logs: Optional[List[Dict]] = None,
        services: Optional[List[str]] = None
    ) -> Dict:
        """
        Analyze an incident.
        
        Args:
            query: Incident description
            timestamp: Incident timestamp (ISO format)
            dashboard_images: Dashboard image paths
            log_files: Log file paths (for MCP)
            logs: Structured log entries
            services: Affected services
        
        Returns:
            Analysis result dict
        """
        payload = {
            "query": query,
            "timestamp": timestamp
        }
        
        if dashboard_images:
            payload["dashboard_images"] = dashboard_images
        if log_files:
            payload["log_files"] = log_files
        if logs:
            payload["logs"] = logs
        if services:
            payload["services"] = services
        
        response = self.session.post(
            f"{self.base_url}/analyze",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def create_plan(self, query: str, timestamp: str) -> Dict:
        """
        Create an execution plan without running full analysis.
        
        Args:
            query: Incident description
            timestamp: Incident timestamp
        
        Returns:
            Plan dict
        """
        response = self.session.post(
            f"{self.base_url}/plan",
            data={"query": query, "timestamp": timestamp}
        )
        response.raise_for_status()
        return response.json()
    
    def get_analysis(self, analysis_id: str) -> Dict:
        """
        Retrieve a previous analysis by ID.
        
        Args:
            analysis_id: Analysis ID
        
        Returns:
            Analysis result dict
        """
        response = self.session.get(f"{self.base_url}/analysis/{analysis_id}")
        response.raise_for_status()
        return response.json()
    
    def upload_logs(self, file_path: str, service: str) -> Dict:
        """
        Upload a log file.
        
        Args:
            file_path: Path to log file
            service: Service name
        
        Returns:
            Upload result dict
        """
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"service": service}
            
            response = self.session.post(
                f"{self.base_url}/upload-logs",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()
    
    def list_mcp_servers(self) -> Dict:
        """
        List available MCP servers.
        
        Returns:
            MCP servers status dict
        """
        response = self.session.get(f"{self.base_url}/mcp/servers")
        response.raise_for_status()
        return response.json()
    
    def read_file_via_mcp(self, filepath: str) -> Dict:
        """
        Read a file using MCP filesystem.
        
        Args:
            filepath: File path
        
        Returns:
            File content and metadata
        """
        response = self.session.post(
            f"{self.base_url}/mcp/filesystem/read",
            data={"filepath": filepath}
        )
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> Dict:
        """
        Get API usage statistics.
        
        Returns:
            Stats dict
        """
        response = self.session.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()
    
    def clear_cache(self) -> Dict:
        """
        Clear analysis cache.
        
        Returns:
            Clear result dict
        """
        response = self.session.delete(f"{self.base_url}/cache")
        response.raise_for_status()
        return response.json()


# CLI for testing
def main():
    """Test the API client"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Incident Analysis API client")
    parser.add_argument('--url', default='http://localhost:8000', help='API URL')
    parser.add_argument('--query', default='API outage at 14:32', help='Incident query')
    parser.add_argument('--timestamp', default='2024-01-15T14:32:00Z', help='Timestamp')
    parser.add_argument('--log-files', nargs='+', help='Log files')
    
    args = parser.parse_args()
    
    # Create client
    client = IncidentAnalysisClient(args.url)
    
    print("="*60)
    print("API CLIENT TEST")
    print("="*60)
    
    # Health check
    print("\n1. Health Check:")
    try:
        health = client.health_check()
        print(f"   Status: {health['status']}")
        print(f"   Version: {health['version']}")
        print(f"   Agents: {', '.join(health['agents_available'])}")
        print(f"   MCP: {health['mcp_enabled']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print(f"   Make sure API is running: uvicorn api.main:app --reload")
        return
    
    # Create plan
    print("\n2. Create Plan:")
    try:
        plan_result = client.create_plan(args.query, args.timestamp)
        print(f"   Services: {plan_result['plan'].get('affected_services', [])}")
        print(f"   Symptoms: {plan_result['plan'].get('symptoms', [])}")
        print(f"   Estimated time: {plan_result['estimated_time_seconds']}s")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Analyze incident
    print("\n3. Analyze Incident:")
    try:
        result = client.analyze_incident(
            query=args.query,
            timestamp=args.timestamp,
            log_files=args.log_files
        )
        
        print(f"   Analysis ID: {result['analysis_id']}")
        print(f"   Status: {result['status']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        
        if result.get('root_cause'):
            print(f"   Root Cause: {result['root_cause']}")
        
        if result.get('missing_evidence'):
            print(f"   Missing: {', '.join(result['missing_evidence'][:3])}")
        
        print(f"   Processing time: {result['processing_time_ms']:.0f}ms")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Stats
    print("\n4. API Stats:")
    try:
        stats = client.get_stats()
        print(f"   Total analyses: {stats['total_analyses']}")
        print(f"   Cache size: {stats['cache_size_mb']:.2f}MB")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()