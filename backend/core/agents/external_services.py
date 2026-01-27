from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests
from github import Github  # pip install PyGithub

@dataclass
class ServiceResponse:
    """Standardized response from any external service"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict] = None

# ------------------------------
# GitHub Service
# ------------------------------
class GitHubService:
    def __init__(self, token: str, repo: str):
        self.client = Github(token)
        self.repo = self.client.get_repo(repo)

    def recent_commits(self, branch: str = "main", limit: int = 5) -> ServiceResponse:
        try:
            commits = [
                {
                    "sha": c.sha,
                    "author": c.commit.author.name,
                    "message": c.commit.message,
                    "date": c.commit.author.date.isoformat()
                }
                for c in self.repo.get_commits(sha=branch)[:limit]
            ]
            return ServiceResponse(success=True, data=commits, metadata={"count": len(commits)})
        except Exception as e:
            return ServiceResponse(success=False, data=None, error=str(e))

# ------------------------------
# Prometheus Service
# ------------------------------
class PrometheusService:
    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def query_metric(self, promql: str, time: Optional[str] = None) -> ServiceResponse:
        try:
            r = requests.get(f"{self.url}/api/v1/query", params={"query": promql, "time": time})
            r.raise_for_status()
            return ServiceResponse(success=True, data=r.json())
        except Exception as e:
            return ServiceResponse(success=False, data=None, error=str(e))

    def query_range(self, promql: str, start: str, end: str, step: str = "1m") -> ServiceResponse:
        try:
            r = requests.get(f"{self.url}/api/v1/query_range", params={"query": promql, "start": start, "end": end, "step": step})
            r.raise_for_status()
            return ServiceResponse(success=True, data=r.json())
        except Exception as e:
            return ServiceResponse(success=False, data=None, error=str(e))

# ------------------------------
# Slack Service
# ------------------------------
class SlackService:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://slack.com/api"

    def search_messages(self, query: str, channel: Optional[str] = None, limit: int = 10) -> ServiceResponse:
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {"query": query, "count": limit}
            if channel:
                params["channel"] = channel
            r = requests.get(f"{self.base_url}/search.messages", headers=headers, params=params)
            r.raise_for_status()
            return ServiceResponse(success=True, data=r.json())
        except Exception as e:
            return ServiceResponse(success=False, data=None, error=str(e))

# ------------------------------
# Unified External Service Agent
# ------------------------------
class ExternalServiceAgent:
    """Agent to query multiple external services"""
    def __init__(self, github_service: GitHubService, prometheus_service: PrometheusService, slack_service: Optional[SlackService] = None):
        self.github = github_service
        self.prometheus = prometheus_service
        self.slack = slack_service

    def fetch_context(self, query: str) -> Dict[str, Any]:
        """Fetch data from all available services"""
        context = {}

        # GitHub commits
        github_res = self.github.recent_commits()
        context['github_commits'] = github_res

        # Prometheus CPU usage example
        prom_res = self.prometheus.query_metric("cpu_usage")
        context['prometheus_cpu'] = prom_res

        # Slack messages
        if self.slack:
            slack_res = self.slack.search_messages(query)
            context['slack_messages'] = slack_res

        return context
