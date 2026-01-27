from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
from core.agents.verifier import Evidence
import json
from typing import List, Optional, Dict, Any

class PrometheusAgent:
    def __init__(self, url: str = "http://localhost:9090", debug=False):
        self.client = PrometheusConnect(url=url, disable_ssl=True)
        self.debug = debug
        
        # Updated metrics based on actual incident-rag metrics
        self.metrics = {
            # HTTP Metrics - try rate first, fall back to raw counter
            "http_requests_rate": 'rate(http_requests_total{job="%s"}[5m])',
            "http_requests_2xx": 'rate(http_requests_total{job="%s",status="2xx"}[5m])',
            "http_requests_4xx": 'rate(http_requests_total{job="%s",status="4xx"}[5m])',
            "http_requests_5xx": 'rate(http_requests_total{job="%s",status="5xx"}[5m])',
            "http_requests_total_raw": 'http_requests_total{job="%s"}',
            
            # Latency Metrics (using the highr histogram)
            "latency_p99": 'histogram_quantile(0.99, rate(http_request_duration_highr_seconds_bucket{job="%s"}[5m]))',
            "latency_p95": 'histogram_quantile(0.95, rate(http_request_duration_highr_seconds_bucket{job="%s"}[5m]))',
            "latency_p50": 'histogram_quantile(0.50, rate(http_request_duration_highr_seconds_bucket{job="%s"}[5m]))',
            "latency_avg": 'rate(http_request_duration_highr_seconds_sum{job="%s"}[5m]) / rate(http_request_duration_highr_seconds_count{job="%s"}[5m])',
            
            # Resource Metrics - these are gauges, no rate() needed
            "cpu_usage_rate": 'rate(process_cpu_seconds_total{job="%s"}[5m]) * 100',
            "cpu_seconds_total": 'process_cpu_seconds_total{job="%s"}',
            "memory_usage_mb": 'process_resident_memory_bytes{job="%s"} / 1024 / 1024',
            "memory_virtual_mb": 'process_virtual_memory_bytes{job="%s"} / 1024 / 1024',
            "open_file_descriptors": 'process_open_fds{job="%s"}',
            
            # Response Size
            "response_size_rate": 'rate(http_response_size_bytes_sum{job="%s"}[5m])',
            "response_size_avg": 'rate(http_response_size_bytes_sum{job="%s"}[5m]) / rate(http_response_size_bytes_count{job="%s"}[5m])',
            "response_size_bytes_total": 'http_response_size_bytes_sum{job="%s"}',
            
            # Python GC Metrics
            "gc_collections_rate": 'rate(python_gc_collections_total{job="%s"}[5m])',
            "gc_collections_total": 'python_gc_collections_total{job="%s"}',
            "gc_objects_collected_rate": 'rate(python_gc_objects_collected_total{job="%s"}[5m])',
        }

    def range_query(self, query: str, start: datetime, end: datetime, step: str = "1m") -> List[Dict]:
        """Execute a Prometheus range query with error handling."""
        if self.debug:
            print(f"[PROMETHEUS] QUERY: {query}")
            print(f"[PROMETHEUS] TIME RANGE: {start} to {end}")
        
        try:
            result = self.client.custom_query_range(
                query=query, 
                start_time=start, 
                end_time=end, 
                step=step
            )
            
            if self.debug and result:
                print(f"[PROMETHEUS] SUCCESS: Retrieved {len(result)} metric series")
            elif self.debug:
                print(f"[PROMETHEUS] WARNING: No data returned")
                
            return result
        except Exception as e:
            print(f"[PROMETHEUS] ERROR: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return []

    def instant_query(self, query: str) -> List[Dict]:
        """Execute a Prometheus instant query."""
        if self.debug:
            print(f"[PROMETHEUS] INSTANT QUERY: {query}")
        
        try:
            result = self.client.custom_query(query=query)
            return result
        except Exception as e:
            print(f"[PROMETHEUS] ERROR: {e}")
            return []

    def get_available_jobs(self) -> List[str]:
        """Discover available jobs from Prometheus."""
        try:
            result = self.instant_query('up')
            jobs = set()
            
            if isinstance(result, list):
                for metric in result:
                    if 'metric' in metric and 'job' in metric['metric']:
                        jobs.add(metric['metric']['job'])
            
            return sorted(list(jobs))
        except Exception as e:
            print(f"[PROMETHEUS] ERROR discovering jobs: {e}")
            return []
    
    def get_data_time_range(self, job: str, metric: str = "up") -> Dict[str, Any]:
        """Get the time range where data is available for a job."""
        try:
            # Query for the metric over the last 24 hours
            now = datetime.utcnow()
            start = now - timedelta(hours=24)
            
            result = self.range_query(
                f'{metric}{{job="{job}"}}',
                start,
                now,
                step="5m"
            )
            
            if not result or not result[0].get('values'):
                return {
                    'has_data': False,
                    'message': f'No data found for {metric} in the last 24 hours'
                }
            
            values = result[0]['values']
            first_timestamp = datetime.fromtimestamp(values[0][0])
            last_timestamp = datetime.fromtimestamp(values[-1][0])
            
            return {
                'has_data': True,
                'first_data_point': first_timestamp.isoformat(),
                'last_data_point': last_timestamp.isoformat(),
                'data_points': len(values),
                'message': f'Data available from {first_timestamp} to {last_timestamp}'
            }
        except Exception as e:
            return {
                'has_data': False,
                'error': str(e)
            }

    def parse_metric_data(self, data: Any) -> List[Dict[str, Any]]:
        """Parse and normalize metric data from Prometheus response."""
        parsed_data = []
        
        if not data:
            return parsed_data
        
        # Handle single float value
        if isinstance(data, (int, float)):
            parsed_data.append({
                "time": datetime.utcnow().isoformat(),
                "value": float(data)
            })
        # Handle list of metric results
        elif isinstance(data, list):
            for series in data:
                if not isinstance(series, dict):
                    continue
                
                metric_labels = series.get('metric', {})
                values = series.get('values', [])
                
                for timestamp, value in values:
                    try:
                        parsed_data.append({
                            "time": datetime.fromtimestamp(timestamp).isoformat(),
                            "value": float(value),
                            "labels": metric_labels
                        })
                    except (ValueError, TypeError) as e:
                        if self.debug:
                            print(f"[PROMETHEUS] WARNING: Could not parse value: {value}, error: {e}")
                        continue
        
        return parsed_data
    # In your PrometheusAgent class from the first code block
    def collect_filtered_metrics(
        self,
        incident_time: str,
        window_minutes: int = 30,
        jobs: Optional[List[str]] = None,
        metrics_filter: Optional[List[str]] = None
    ) -> List[Evidence]:
        """
        Collect metrics with optional filtering.
        
        Args:
            incident_time: ISO timestamp
            window_minutes: Time window
            jobs: Jobs to query
            metrics_filter: List of metric names to collect (None for all)
        
        Returns:
            Filtered list of Evidence
        """
        # Collect all metrics first
        evidence = self.collect_incident_metrics(
            incident_time=incident_time,
            window_minutes=window_minutes,
            jobs=jobs,
            include_stats=True,
            detect_anomalies=True
        )
        
        # Filter if requested
        if metrics_filter and evidence:
            filtered_evidence = []
            for ev in evidence:
                metric_name = ev.metadata.get("metric", "")
                # Check if any filter keyword matches the metric name
                if any(filter_keyword in metric_name for filter_keyword in metrics_filter):
                    filtered_evidence.append(ev)
                # Also check metric categories
                elif self._metric_matches_category(metric_name, metrics_filter):
                    filtered_evidence.append(ev)
            
            if self.debug:
                print(f"[PROMETHEUS] Filtered from {len(evidence)} to {len(filtered_evidence)} metrics")
            
            return filtered_evidence
        
        return evidence


    def collect_filtered_metrics(
        self,
        incident_time: str,
        window_minutes: int = 30,
        jobs: Optional[List[str]] = None,
        metrics_filter: Optional[List[str]] = None
    ) -> List[Evidence]:
        """
        Collect metrics with optional filtering.
        
        Args:
            incident_time: ISO timestamp
            window_minutes: Time window
            jobs: Jobs to query
            metrics_filter: List of metric names to collect (None for all)
        
        Returns:
            Filtered list of Evidence
        """
        # Collect all metrics first
        evidence = self.collect_incident_metrics(
            incident_time=incident_time,
            window_minutes=window_minutes,
            jobs=jobs,
            include_stats=True,
            detect_anomalies=True
        )
        
        # Filter if requested
        if metrics_filter and evidence:
            filtered_evidence = []
            for ev in evidence:
                metric_name = ev.metadata.get("metric", "")
                # Check if any filter keyword matches the metric name
                if any(filter_keyword in metric_name for filter_keyword in metrics_filter):
                    filtered_evidence.append(ev)
                # Also check metric categories
                elif self._metric_matches_category(metric_name, metrics_filter):
                    filtered_evidence.append(ev)
            
            if self.debug:
                print(f"[PROMETHEUS] Filtered from {len(evidence)} to {len(filtered_evidence)} metrics")
            
            return filtered_evidence
        
        return evidence


    def _metric_matches_category(self, metric_name: str, filters: List[str]) -> bool:
        """Check if a metric belongs to a requested category."""
        category_mapping = {
            "cpu": ["cpu_usage", "process_cpu"],
            "memory": ["memory_usage", "process_resident_memory", "process_virtual_memory"],
            "latency": ["latency_", "request_duration"],
            "http": ["http_requests", "http_response"],
            "error": ["5xx", "4xx", "error"]
        }
        
        for filter_keyword in filters:
            filter_lower = filter_keyword.lower()
            for category, keywords in category_mapping.items():
                if category in filter_lower:
                    # Check if this metric matches any keyword in the category
                    if any(keyword in metric_name.lower() for keyword in keywords):
                        return True
        
        return False


    def collect_evidence_for_state_machine(
        self,
        incident_time: str,
        window_minutes: int = 30,
        affected_services: Optional[List[str]] = None
    ) -> List[Evidence]:
        """
        Wrapper method specifically for the LangGraph state machine.
        
        Args:
            incident_time: ISO format timestamp
            window_minutes: Time window around incident
            affected_services: Services to query
            
        Returns:
            List of Evidence objects in the format expected by the state machine
        """
        return self.collect_incident_metrics(
            incident_time=incident_time,
            window_minutes=window_minutes,
            jobs=affected_services,
            include_stats=True,
            detect_anomalies=True
        )

    def _metric_matches_category(self, metric_name: str, filters: List[str]) -> bool:
        """Check if a metric belongs to a requested category."""
        category_mapping = {
            "cpu": ["cpu_usage", "process_cpu"],
            "memory": ["memory_usage", "process_resident_memory", "process_virtual_memory"],
            "latency": ["latency_", "request_duration"],
            "http": ["http_requests", "http_response"],
            "error": ["5xx", "4xx", "error"]
        }
        
        for filter_keyword in filters:
            filter_lower = filter_keyword.lower()
            for category, keywords in category_mapping.items():
                if category in filter_lower:
                    # Check if this metric matches any keyword in the category
                    if any(keyword in metric_name.lower() for keyword in keywords):
                        return True
        
        return False

    def calculate_metric_stats(self, parsed_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate basic statistics for a metric."""
        if not parsed_data:
            return {}
        
        values = [p['value'] for p in parsed_data if 'value' in p]
        
        if not values:
            return {}
        
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values)
        }

    def detect_anomalies(self, parsed_data: List[Dict[str, Any]], metric_name: str) -> List[Dict[str, Any]]:
        """Detect potential anomalies in metric data."""
        anomalies = []
        
        if not parsed_data or len(parsed_data) < 3:
            return anomalies
        
        values = [p['value'] for p in parsed_data if 'value' in p]
        
        if not values:
            return anomalies
        
        # Calculate simple thresholds
        avg = sum(values) / len(values)
        
        # Define thresholds based on metric type
        thresholds = {
            'latency': {'warning': 1.0, 'critical': 5.0},  # seconds
            'cpu': {'warning': 80, 'critical': 95},  # percentage
            'memory': {'warning': 1500, 'critical': 2000},  # MB
            'error_rate': {'warning': 0.01, 'critical': 0.05},  # 1% and 5%
        }
        
        # Determine metric category
        category = None
        if 'latency' in metric_name:
            category = 'latency'
        elif 'cpu' in metric_name:
            category = 'cpu'
        elif 'memory' in metric_name:
            category = 'memory'
        elif '5xx' in metric_name or 'error' in metric_name:
            category = 'error_rate'
        
        if category and category in thresholds:
            for point in parsed_data:
                value = point.get('value', 0)
                
                if value > thresholds[category]['critical']:
                    anomalies.append({
                        'time': point['time'],
                        'value': value,
                        'severity': 'critical',
                        'threshold': thresholds[category]['critical']
                    })
                elif value > thresholds[category]['warning']:
                    anomalies.append({
                        'time': point['time'],
                        'value': value,
                        'severity': 'warning',
                        'threshold': thresholds[category]['warning']
                    })
        
        return anomalies
    # Inside the PrometheusAgent class in your first code block
    def collect_evidence_for_state_machine(
        self,
        incident_time: str,
        window_minutes: int = 30,
        affected_services: Optional[List[str]] = None
    ) -> List[Evidence]:
        """
        Wrapper method specifically for the LangGraph state machine.
        
        Args:
            incident_time: ISO format timestamp
            window_minutes: Time window around incident
            affected_services: Services to query
            
        Returns:
            List of Evidence objects in the format expected by the state machine
        """
        return self.collect_incident_metrics(
            incident_time=incident_time,
            window_minutes=window_minutes,
            jobs=affected_services,
            include_stats=True,
            detect_anomalies=True
        )

# Fix 1: Add 'self' parameter to collect_incident_metrics method
# Replace this method in your PrometheusAgent class:

    def collect_incident_metrics(
        self,  # <-- ADD THIS
        incident_time: str, 
        window_minutes: int = 30, 
        jobs: Optional[List[str]] = None,
        include_stats: bool = True,
        detect_anomalies: bool = True
    ) -> List[Evidence]:
        """
        Collect metrics around an incident time.
        
        Args:
            incident_time: ISO format timestamp of the incident
            window_minutes: Minutes before and after incident to collect
            jobs: List of job names to query (None to auto-discover)
            include_stats: Whether to include statistical summary in metadata
            detect_anomalies: Whether to detect anomalies in the data
            
        Returns:
            List of Evidence objects containing metric data
        """
        evidence_list = []
        
        # Auto-discover jobs if not provided
        if jobs is None or len(jobs) == 0:
            if self.debug:
                print("[PROMETHEUS] Auto-discovering jobs...")
            jobs = self.get_available_jobs()
            if self.debug:
                print(f"[PROMETHEUS] Found jobs: {jobs}")
        
        if not jobs:
            print("[PROMETHEUS] WARNING: No jobs available to query")
            return evidence_list

        # Parse incident time and create time window
        incident_dt = datetime.fromisoformat(incident_time.replace('Z', '+00:00'))
        start = incident_dt - timedelta(minutes=window_minutes)
        end = incident_dt + timedelta(minutes=window_minutes)
        
        if self.debug:
            print(f"\n[PROMETHEUS] Incident time: {incident_dt}")
            print(f"[PROMETHEUS] Query window: {start} to {end} ({window_minutes*2} minutes)")

        # Collect metrics for each job
        for job in jobs:
            if self.debug:
                print(f"\n[PROMETHEUS] Processing job: {job}")
            
            for metric_name, query_template in self.metrics.items():
                # Some metrics need the job name twice (like avg calculations)
                job_count = query_template.count("%s")
                query = query_template % tuple([job] * job_count)
                
                # Execute query
                raw_data = self.range_query(query, start, end)
                
                if not raw_data:
                    if self.debug:
                        print(f"[PROMETHEUS] No data for {metric_name} on job {job}")
                    continue

                # Parse and structure the data
                parsed_data = self.parse_metric_data(raw_data)
                
                if not parsed_data:
                    continue

                # Build metadata
                metadata = {
                    "metric": metric_name,
                    "job": job,
                    "query": query,
                    "window_minutes": window_minutes,
                    "incident_time": incident_time,
                    "data_points": len(parsed_data)
                }
                
                # Add statistics if requested
                if include_stats:
                    stats = self.calculate_metric_stats(parsed_data)
                    metadata["stats"] = stats
                
                # Detect anomalies if requested
                anomalies = []
                if detect_anomalies:
                    anomalies = self.detect_anomalies(parsed_data, metric_name)
                    if anomalies:
                        metadata["anomalies"] = anomalies
                        metadata["anomaly_count"] = len(anomalies)

                # Create evidence object
                evidence = Evidence(
                    source="prometheus",
                    content=json.dumps(parsed_data, indent=2),
                    timestamp=datetime.utcnow().isoformat(),
                    confidence=0.95,
                    metadata=metadata
                )
                evidence_list.append(evidence)
                
                if self.debug:
                    anomaly_info = f" ({len(anomalies)} anomalies)" if detect_anomalies and anomalies else ""
                    print(f"[PROMETHEUS] ✓ Collected {metric_name}: {len(parsed_data)} data points{anomaly_info}")

        if self.debug:
            print(f"\n[PROMETHEUS] Total evidence collected: {len(evidence_list)}")
        
        return evidence_list
def collect_prometheus_metrics(
    incident_time: str,
    window_minutes: int = 30,
    affected_services: Optional[List[str]] = None,
    prometheus_url: str = "http://localhost:9090",
    debug: bool = False
) -> List[Evidence]:
    """
    Main function to be called by the LangGraph state machine.
    
    Args:
        incident_time: ISO format timestamp of the incident
        window_minutes: Minutes before and after incident to collect
        affected_services: List of services/jobs to query
        prometheus_url: URL of Prometheus instance
        debug: Enable debug logging
        
    Returns:
        List of Evidence objects
    """
    # Initialize the agent
    agent = PrometheusAgent(url=prometheus_url, debug=debug)
    
    # If affected_services is provided, use it; otherwise auto-discover
    jobs = affected_services if affected_services else None
    
    # Collect metrics
    evidence = agent.collect_incident_metrics(
        incident_time=incident_time,
        window_minutes=window_minutes,
        jobs=jobs,
        include_stats=True,
        detect_anomalies=True
    )
    
    return evidence

# -----------------------------
# TEST CONFIGURATION
# -----------------------------
PROM_URL = "http://localhost:9090"
JOBS = ["incident-rag"]  # Set to None to auto-discover
WINDOW_MINUTES = 5

def test_prometheus_agent():
    """Test the Prometheus agent functionality."""
    agent = PrometheusAgent(url=PROM_URL, debug=True)

    print("=" * 70)
    print("PROMETHEUS AGENT TEST")
    print("=" * 70)

    # Test 1: Discover available jobs
    print("\n[TEST] Discovering available jobs...")
    available_jobs = agent.get_available_jobs()
    print(f"Available jobs: {available_jobs}")

    # Test 2: Check if data exists NOW
    test_jobs = JOBS if JOBS else available_jobs
    print(f"\n[TEST] Checking current data availability for: {test_jobs}")
    
    suggested_time = None
    for job in test_jobs:
        result = agent.instant_query(f'up{{job="{job}"}}')
        if result and result[0].get('value', [None, '0'])[1] == '1':
            print(f"  ✓ {job} is UP and being scraped")
        
        # Check data time range
        time_range = agent.get_data_time_range(job, "process_resident_memory_bytes")
        if time_range.get('has_data'):
            print(f"  ✓ Data range: {time_range['message']}")
            suggested_time = time_range['last_data_point']
        else:
            print(f"  ⚠️  {time_range.get('message', 'No data available')}")

    # Test 3: Collect incident metrics using a time with actual data
    if suggested_time:
        # Use the last data point time
        incident_dt = datetime.fromisoformat(suggested_time)
        incident_time = incident_dt.isoformat()
        print(f"\n[TEST] Using most recent data time: {incident_time}")
    else:
        # Fallback to 2 minutes ago
        incident_time = (datetime.utcnow() - timedelta(minutes=2)).isoformat()
        print(f"\n[TEST] Using fallback time: {incident_time} (2 minutes ago)")

    print(f"[TEST] Collecting metrics for jobs: {test_jobs}")
    print(f"[TEST] Time window: ±{WINDOW_MINUTES} minutes\n")

    evidence_list = agent.collect_incident_metrics(
        incident_time=incident_time,
        window_minutes=WINDOW_MINUTES,
        jobs=test_jobs,
        detect_anomalies=True
    )

    # Display results
    print("\n" + "=" * 70)
    print(f"RESULTS: Collected {len(evidence_list)} evidence items")
    print("=" * 70 + "\n")

    for idx, ev in enumerate(evidence_list, 1):
        print(f"[{idx}] {ev.metadata.get('metric')} - {ev.metadata.get('job')}")
        print(f"    Confidence: {ev.confidence}")
        print(f"    Data points: {ev.metadata.get('data_points', 0)}")
        
        if 'stats' in ev.metadata:
            stats = ev.metadata['stats']
            print(f"    Stats: min={stats.get('min', 0):.2f}, "
                  f"max={stats.get('max', 0):.2f}, "
                  f"avg={stats.get('avg', 0):.2f}")
        
        if 'anomalies' in ev.metadata:
            anomaly_count = ev.metadata.get('anomaly_count', 0)
            print(f"    ⚠️  Anomalies detected: {anomaly_count}")
            for anomaly in ev.metadata['anomalies'][:3]:  # Show first 3
                print(f"        - {anomaly['severity'].upper()}: {anomaly['value']:.2f} "
                      f"(threshold: {anomaly['threshold']:.2f}) at {anomaly['time']}")
        
        # Show content preview
        try:
            content = json.loads(ev.content)
            if content:
                sample = content[0] if len(content) > 0 else {}
                print(f"    Sample: time={sample.get('time', 'N/A')}, value={sample.get('value', 0):.4f}")
        except:
            snippet = str(ev.content)[:100].replace("\n", " ")
            print(f"    Content: {snippet}...")
        
        print()

if __name__ == "__main__":
    test_prometheus_agent()