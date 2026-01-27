"""
Grafana agent for incident analysis.
Queries Grafana API to retrieve dashboards and annotations for incident investigation.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import requests
import json
import config
from ..graph import Evidence


class GrafanaAgent:
    """Agent for querying Grafana dashboards and data."""
    
    def __init__(self, grafana_url: str = None, api_key: str = None):
        self.base_url = grafana_url or config.GRAFANA_URL
        self.api_key = api_key or config.GRAFANA_API_KEY
        self.headers = {
            "Authorization": f"Bearer {api_key}" if api_key else "",
            "Content-Type": "application/json"
        }
    
    def search_dashboards(self, query: str = "", tags: List[str] = []) -> List[Dict]:
        """
        Search for dashboards by name or tags.
        
        Args:
            query: Dashboard name search query
            tags: List of tags to filter by
        
        Returns:
            List of dashboard metadata
        """
        try:
            params = {}
            if query:
                params["query"] = query
            if tags:
                params["tags"] = ",".join(tags)
            
            response = requests.get(
                f"{self.base_url}/api/search",
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_dashboard(self, dashboard_id: int) -> Dict:
        """
        Fetch full dashboard definition and data.
        
        Args:
            dashboard_id: Grafana dashboard ID or UID
        
        Returns:
            Dashboard JSON with panels and metadata
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/dashboards/uid/{dashboard_id}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "status": "error"}
    
    def get_annotations(
        self, 
        start_time: str, 
        end_time: str, 
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Fetch annotations (incidents, markers, etc.) within time range.
        
        Args:
            start_time: Start time (Unix timestamp ms)
            end_time: End time (Unix timestamp ms)
            tags: Filter by annotation tags
        
        Returns:
            List of annotations
        """
        try:
            params = {
                "from": start_time,
                "to": end_time,
                "limit": 100
            }
            if tags:
                params["tags"] = tags
            
            response = requests.get(
                f"{self.base_url}/api/annotations",
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_dashboard_panels(self, dashboard_uid: str) -> Dict:
        """
        Extract panels from a dashboard for metric analysis.
        
        Args:
            dashboard_uid: Dashboard UID
        
        Returns:
            Dictionary of panel configurations
        """
        dashboard = self.get_dashboard(dashboard_uid)
        
        if "error" in dashboard:
            return dashboard
        
        panels = {}
        dashboard_panels = dashboard.get("dashboard", {}).get("panels", [])
        
        for panel in dashboard_panels:
            panel_id = panel.get("id")
            panels[panel_id] = {
                "title": panel.get("title"),
                "type": panel.get("type"),
                "targets": panel.get("targets", []),
                "gridPos": panel.get("gridPos")
            }
        
        return panels
    
    def analyze_incident_dashboards(
        self, 
        incident_time: str,
        window_minutes: int = 30,
        dashboard_tags: Optional[List[str]] = None
    ) -> List[Evidence]:
        """
        Collect dashboard snapshots and annotations around incident time.
        
        Args:
            incident_time: ISO timestamp of incident
            window_minutes: Time window before/after incident
            dashboard_tags: Tags to search for relevant dashboards
        
        Returns:
            List of Evidence objects with dashboard data
        """
        evidence_list = []
        
        # Parse incident time
        try:
            incident_dt = datetime.fromisoformat(incident_time.replace('Z', '+00:00'))
        except:
            incident_dt = datetime.utcnow()
        
        start_time_ms = int((incident_dt - timedelta(minutes=window_minutes)).timestamp() * 1000)
        end_time_ms = int((incident_dt + timedelta(minutes=window_minutes)).timestamp() * 1000)
        
        # Fetch annotations around incident
        annotations = self.get_annotations(
            str(start_time_ms), 
            str(end_time_ms),
            tags=dashboard_tags
        )
        
        if annotations and not ("error" in annotations[0] if annotations else False):
            evidence = Evidence(
                source="grafana_annotations",
                content=json.dumps(annotations),
                timestamp=datetime.utcnow().isoformat(),
                confidence=0.9,
                metadata={
                    "annotation_count": len(annotations),
                    "incident_time": incident_time,
                    "time_window": f"{start_time_ms}/{end_time_ms}"
                }
            )
            evidence_list.append(evidence)
        
        # Search for relevant dashboards
        dashboard_search_terms = ["system", "performance", "api", "database", "infrastructure"]
        if dashboard_tags:
            dashboard_search_terms.extend(dashboard_tags)
        
        for search_term in dashboard_search_terms:
            dashboards = self.search_dashboards(query=search_term)
            
            for dashboard in dashboards[:3]:  # Limit to top 3 per search
                if "uid" in dashboard:
                    dashboard_data = self.get_dashboard(dashboard["uid"])
                    
                    if "dashboard" in dashboard_data:
                        evidence = Evidence(
                            source="grafana_dashboard",
                            content=json.dumps({
                                "title": dashboard_data["dashboard"].get("title"),
                                "description": dashboard_data["dashboard"].get("description"),
                                "panels": [
                                    {
                                        "title": p.get("title"),
                                        "type": p.get("type")
                                    }
                                    for p in dashboard_data["dashboard"].get("panels", [])[:5]
                                ]
                            }),
                            timestamp=datetime.utcnow().isoformat(),
                            confidence=0.85,
                            metadata={
                                "dashboard_uid": dashboard["uid"],
                                "dashboard_name": dashboard.get("title", "Unknown"),
                                "search_term": search_term,
                                "incident_time": incident_time
                            }
                        )
                        evidence_list.append(evidence)
        
        return evidence_list


def analyze_grafana_incident(
    incident_time: str,
    window_minutes: int = 30,
    dashboard_tags: Optional[List[str]] = None
) -> List[Evidence]:
    """
    Wrapper function for analyzing incident dashboards.
    """
    agent = GrafanaAgent()
    return agent.analyze_incident_dashboards(
        incident_time=incident_time,
        window_minutes=window_minutes,
        dashboard_tags=dashboard_tags
    )
