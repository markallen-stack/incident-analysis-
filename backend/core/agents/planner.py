"""
Planner Agent - Query Decomposition and Task Planning

Analyzes user's incident query and creates a structured execution plan
for other agents to follow.

Usage:
    from agents.planner import plan_incident_analysis
    
    plan = plan_incident_analysis(
        query="API outage at 14:32 with 500 errors",
        timestamp="2024-01-15T14:32:00Z"
    )
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, Optional
import sys
from pathlib import Path
from typing import List
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

import config
from prompts.planner import PLANNER_PROMPT


class PlannerAgent:
    """
    Planner Agent that decomposes incident queries into structured plans.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize the planner agent.
        
        Args:
            llm_client: Optional LLM client (Anthropic or OpenAI)
        """
        self.llm_client = llm_client
        
        if self.llm_client is None:
            # Auto-detect which client to use
            if config.ANTHROPIC_API_KEY and ANTHROPIC_AVAILABLE:
                self.llm_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
                self.llm_type = "anthropic"
            elif config.OPENAI_API_KEY and OPENAI_AVAILABLE:
                self.llm_client = OpenAI(api_key=config.OPENAI_API_KEY)
                self.llm_type = "openai"
            else:
                raise ValueError("No API key available. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
    
    def plan_incident_analysis(
        self,
        query: str,
        timestamp: Optional[str] = None
    ) -> Dict:
        """
        Creates an execution plan for analyzing an incident.
        
        Args:
            query: User's incident description
            timestamp: Incident timestamp (ISO format)
        
        Returns:
            Structured plan dictionary with:
            - incident_time: Parsed timestamp or time range
            - affected_services: List of mentioned services
            - symptoms: Identified symptoms
            - required_agents: Which agents to invoke
            - search_windows: Time ranges for searching
        """
        # Use LLM to parse the query
        llm_plan = self._call_llm(query, timestamp)
        
        # Extract and validate the plan
        plan = self._extract_plan(llm_plan)
        
        # Enhance with heuristics
        plan = self._enhance_plan(plan, query, timestamp)
        
        return plan
    
    def _call_llm(self, query: str, timestamp: Optional[str]) -> str:
        """Call LLM to generate initial plan"""
        
        prompt = f"""{PLANNER_PROMPT}

Query: {query}
Timestamp: {timestamp or 'Not provided'}

Generate the execution plan in JSON format:"""
        
        try:
            if self.llm_type == "anthropic":
                response = self.llm_client.messages.create(
                    model=config.PRIMARY_LLM,
                    max_tokens=1000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                return response.content[0].text
            
            else:  # OpenAI
                response = self.llm_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=1000
                )
                return response.choices[0].message.content
        
        except Exception as e:
            print(f"⚠️  LLM call failed: {e}. Using fallback parsing.")
            return self._fallback_parse(query, timestamp)
    
    def _extract_plan(self, llm_response: str) -> Dict:
        """Extract JSON plan from LLM response"""
        try:
            # Remove markdown code blocks if present
            cleaned = llm_response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]
            
            plan = json.loads(cleaned.strip())
            return plan
        
        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse LLM response as JSON: {e}")
            print(f"Response: {llm_response[:200]}...")
            
            # Try to extract structured data manually
            return self._manual_extract(llm_response)
    
    def _manual_extract(self, text: str) -> Dict:
        """Manually extract plan elements from text"""
        plan = {
            "incident_time": None,
            "affected_services": [],
            "symptoms": [],
            "required_agents": ["image", "log", "rag"],
            "search_windows": {},
            "prometheus_config": {
                "window_minutes": 35,
                "target_services": [],
                "metrics_to_collect": [],
                "default_metrics": True
            }
        }
        
        # Extract timestamps
        time_patterns = [
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
            r'\d{2}:\d{2}',
            r'\d{1,2}:\d{2}\s*(?:AM|PM|UTC|EST|PST)'
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                plan["incident_time"] = matches[0]
                break
        
        # Extract services
        services = [
            "incident-rag"
        ]
        
        text_lower = text.lower()
        plan["affected_services"] = [
            s for s in services if s in text_lower
        ]
        
        # Extract symptoms
        symptoms_keywords = {
            "high cpu": "high_cpu",
            "cpu spike": "cpu_spike",
            "memory leak": "memory_leak",
            "slow response": "slow_response",
            "timeout": "timeout",
            "500 error": "http_500",
            "503 error": "http_503",
            "connection": "connection_error",
            "outage": "outage",
            "latency": "high_latency",
            "error rate": "error_rate_spike"
        }
        
        for keyword, symptom in symptoms_keywords.items():
            if keyword in text_lower:
                plan["symptoms"].append(symptom)
        
        # Determine if prometheus is needed
        if any(s in plan["symptoms"] for s in [
            "high_cpu", "cpu_spike", "memory_leak", "slow_response",
            "high_latency", "error_rate_spike", "http_500", "http_503"
        ]):
            if "prometheus" not in plan["required_agents"]:
                plan["required_agents"].append("prometheus")
            
            # Set target services for prometheus
            plan["prometheus_config"]["target_services"] = plan["affected_services"]
            
            # Determine metrics to collect
            metrics = []
            if any(s in plan["symptoms"] for s in ["high_cpu", "cpu_spike"]):
                metrics.extend(["cpu_usage_rate", "cpu_seconds_total"])
            if "memory_leak" in plan["symptoms"]:
                metrics.extend(["memory_usage_mb", "memory_virtual_mb"])
            if any(s in plan["symptoms"] for s in ["slow_response", "high_latency", "timeout"]):
                metrics.extend(["latency_p99", "latency_p95"])
            if any(s in plan["symptoms"] for s in ["http_500", "http_503", "error_rate_spike"]):
                metrics.extend(["http_requests_5xx", "http_requests_rate"])
            
            plan["prometheus_config"]["metrics_to_collect"] = list(set(metrics))
        
        return plan
        
    def _fallback_parse(self, query: str, timestamp: Optional[str]) -> str:
        """Fallback parsing when LLM is unavailable"""
        plan = {
            "incident_time": timestamp or "unknown",
            "affected_services": [],
            "symptoms": [],
            "required_agents": ["image", "log", "rag"],
            "search_windows": {
                "logs": "unknown",
                "metrics": "unknown"
            }
        }
        
        # Basic keyword extraction
        query_lower = query.lower()
        
        # Extract services
        common_services = [
            "api", "database", "db", "redis", "cache",
            "gateway", "service", "server", "web"
        ]
        
        for service in common_services:
            if service in query_lower:
                plan["affected_services"].append(service)
        
        # Extract symptoms
        symptom_keywords = [
            "error", "timeout", "slow", "spike", "high",
            "outage", "down", "failure", "crash"
        ]
        
        for symptom in symptom_keywords:
            if symptom in query_lower:
                plan["symptoms"].append(symptom)
        
        return json.dumps(plan, indent=2)
    
    # In your planner.py file, update the _enhance_plan method:
# In your planner.py file, update the _enhance_plan method
    def _enhance_plan(
        self,
        plan: Dict,
        query: str,
        timestamp: Optional[str]
    ) -> Dict:
        """Enhance plan with additional logic and time windows"""
        
        # Ensure incident_time is set
        if not plan.get("incident_time"):
            plan["incident_time"] = timestamp or "unknown"
        
        # Calculate search windows based on incident time
        if timestamp:
            try:
                incident_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                # Logs: 15 minutes before and after
                log_start = (incident_dt - timedelta(minutes=15)).strftime("%H:%M")
                log_end = (incident_dt + timedelta(minutes=15)).strftime("%H:%M")
                
                # Metrics: 30 minutes before and after
                metric_start = (incident_dt - timedelta(minutes=30)).strftime("%H:%M")
                metric_end = (incident_dt + timedelta(minutes=30)).strftime("%H:%M")
                
                # Prometheus: 35 minutes before and after (slightly larger window)
                prom_start = (incident_dt - timedelta(minutes=35)).strftime("%H:%M")
                prom_end = (incident_dt + timedelta(minutes=35)).strftime("%H:%M")
                
                plan["search_windows"] = {
                    "logs": f"{log_start}-{log_end}",
                    "metrics": f"{metric_start}-{metric_end}",
                    "prometheus": f"{prom_start}-{prom_end}"
                }
                
                # Add prometheus_config if not present from LLM
                if "prometheus_config" not in plan:
                    plan["prometheus_config"] = {
                        "window_minutes": 35,
                        "target_services": plan.get("affected_services", []),
                        "metrics_to_collect": self._determine_prometheus_metrics(plan.get("symptoms", [])),
                        "default_metrics": True
                    }
                
                # Add easy access fields
                plan["metrics_window_minutes"] = 35
                
            except Exception as e:
                print(f"⚠️  Failed to parse timestamp: {e}")
                plan["search_windows"] = {
                    "logs": "unknown",
                    "metrics": "unknown",
                    "prometheus": "unknown"
                }
                plan["prometheus_config"] = {
                    "window_minutes": 35,
                    "target_services": plan.get("affected_services", []),
                    "metrics_to_collect": self._determine_prometheus_metrics(plan.get("symptoms", [])),
                    "default_metrics": True
                }
        
        # Ensure prometheus is in required_agents if symptoms warrant it
        required_agents = plan.get("required_agents", ["image", "log", "rag"])
        symptoms = plan.get("symptoms", [])
        
        # Check if we need prometheus
        needs_prometheus = self._should_include_prometheus(symptoms, query)
        
        if needs_prometheus and "prometheus" not in required_agents:
            required_agents.append("prometheus")
        
        plan["required_agents"] = required_agents
        
        # Add Prometheus URL and debug mode
        plan["prometheus_url"] = "http://localhost:9090"
        plan["debug_mode"] = False
        
        # Add priority
        plan["priority"] = self._determine_priority(symptoms)
        
        return plan

    def _should_include_prometheus(self, symptoms: List[str], query: str) -> bool:
        """Determine if Prometheus metrics collection is needed."""
        symptoms_lower = [str(s).lower() for s in symptoms]
        query_lower = query.lower()
        
        # Keywords that indicate metrics are needed
        metrics_keywords = [
            # Performance
            "latency", "response time", "slow", "timeout",
            # Resources
            "cpu", "memory", "disk", "load",
            # Errors
            "error", "5xx", "4xx", "failure",
            # Traffic
            "throughput", "requests", "traffic",
            # System metrics
            "spike", "surge", "high usage", "utilization"
        ]
        
        # Check symptoms
        for symptom in symptoms_lower:
            if any(keyword in symptom for keyword in metrics_keywords):
                return True
        
        # Check query directly
        if any(keyword in query_lower for keyword in metrics_keywords):
            return True
        
        return False

    def _determine_prometheus_metrics(self, symptoms: List[str]) -> List[str]:
        """Determine which Prometheus metrics to collect based on symptoms."""
        symptoms_lower = [str(s).lower() for s in symptoms]
        
        metrics_mapping = {
            # Error-related symptoms
            ["error", "5xx", "4xx", "failure"]: [
                "http_requests_rate",
                "http_requests_2xx",
                "http_requests_4xx",
                "http_requests_5xx"
            ],
            # Latency/performance symptoms
            ["latency", "slow", "response time", "timeout"]: [
                "latency_p99",
                "latency_p95",
                "latency_p50",
                "latency_avg"
            ],
            # CPU-related symptoms
            ["cpu", "load", "utilization"]: [
                "cpu_usage_rate",
                "cpu_seconds_total"
            ],
            # Memory-related symptoms
            ["memory", "leak"]: [
                "memory_usage_mb",
                "memory_virtual_mb"
            ],
            # Resource saturation
            ["saturation", "capacity"]: [
                "cpu_usage_rate",
                "memory_usage_mb",
                "open_file_descriptors"
            ]
        }
        
        metrics_to_collect = []
        
        for symptom_keywords, metrics in metrics_mapping.items():
            for keyword in symptom_keywords:
                if any(keyword in symptom for symptom in symptoms_lower):
                    metrics_to_collect.extend(metrics)
        
        # Add basic metrics if none specified
        if not metrics_to_collect:
            metrics_to_collect = [
                "http_requests_rate",
                "http_requests_5xx",
                "latency_p99",
                "cpu_usage_rate"
            ]
        
        # Remove duplicates and return
        return list(set(metrics_to_collect))

    def _determine_priority(self, symptoms: List[str]) -> str:
        """Determine incident priority based on symptoms."""
        symptoms_lower = [str(s).lower() for s in symptoms]
        
        high_priority_keywords = [
            "outage", "down", "crash", "failure",
            "5xx", "error", "unavailable", "severe"
        ]
        
        medium_priority_keywords = [
            "slow", "latency", "degraded", "high cpu",
            "memory", "warning", "partial"
        ]
        
        for symptom in symptoms_lower:
            if any(keyword in symptom for keyword in high_priority_keywords):
                return "high"
        
        for symptom in symptoms_lower:
            if any(keyword in symptom for keyword in medium_priority_keywords):
                return "medium"
        
        return "low"
# Module-level convenience function
_planner_instance = None

def get_planner() -> PlannerAgent:
    """Get or create singleton planner instance"""
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = PlannerAgent()
    return _planner_instance


def plan_incident_analysis(query: str, timestamp: Optional[str] = None) -> Dict:
    """
    Convenience function for planning incident analysis.
    
    Args:
        query: User's incident description
        timestamp: Optional incident timestamp
    
    Returns:
        Structured execution plan
    """
    planner = get_planner()
    return planner.plan_incident_analysis(query, timestamp)


# CLI for testing
def main():
    """Test the planner agent"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test planner agent")
    parser.add_argument('query', help='Incident query')
    parser.add_argument('--timestamp', '-t', help='Incident timestamp')
    
    args = parser.parse_args()
    
    print("="*60)
    print("PLANNER AGENT TEST")
    print("="*60)
    print(f"Query: {args.query}")
    print(f"Timestamp: {args.timestamp or 'None'}")
    print("="*60)
    
    try:
        plan = plan_incident_analysis(args.query, args.timestamp)
        
        print("\nGenerated Plan:")
        print(json.dumps(plan, indent=2))
        
        print("\n" + "="*60)
        print("Plan Summary:")
        print(f"  Incident Time: {plan.get('incident_time')}")
        print(f"  Services: {', '.join(plan.get('affected_services', []))}")
        print(f"  Symptoms: {', '.join(plan.get('symptoms', []))}")
        print(f"  Required Agents: {', '.join(plan.get('required_agents', []))}")
        print(f"  Priority: {plan.get('priority', 'unknown')}")
        print("="*60)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    
    # Test with default query if no args
    if len(sys.argv) == 1:
        print("Running default test...\n")
        plan = plan_incident_analysis(
            "API outage at 14:32 UTC. Users reporting 500 errors and slow response times.",
            "2024-01-15T14:32:00Z"
        )
        print(json.dumps(plan, indent=2))
    else:
        sys.exit(main())