# observability/promql.py
from typing import Dict, Optional


class PromQLBuilder:
    """
    Safe PromQL query builder.
    Ensures labels are applied ONLY to metric names.
    """

    def __init__(self, labels: Optional[Dict[str, str]] = None):
        self.labels = labels or {}

    def _label_str(self, extra: Optional[Dict[str, str]] = None) -> str:
        labels = dict(self.labels)
        if extra:
            labels.update(extra)

        if not labels:
            return ""

        inner = ",".join(f'{k}="{v}"' for k, v in labels.items())
        return f"{{{inner}}}"

    # ---- Core metrics ----

    def cpu_usage(self, window: str = "5m") -> str:
        return (
            f'rate(process_cpu_seconds_total'
            f'{self._label_str()}[{window}]) * 100'
        )

    def memory_mb(self) -> str:
        return (
            f'process_resident_memory_bytes'
            f'{self._label_str()} / 1024 / 1024'
        )

    def http_requests(self, window: str = "5m") -> str:
        return (
            f'rate(http_requests_total'
            f'{self._label_str()}[{window}])'
        )

    def http_errors(self, window: str = "5m") -> str:
        return (
            f'rate(http_requests_total'
            f'{self._label_str({"status": "~5.."})}[{window}])'
        )

    def latency_p99(self, window: str = "5m") -> str:
        return (
            'histogram_quantile(0.99, '
            f'rate(http_request_duration_seconds_bucket'
            f'{self._label_str()}[{window}]))'
        )
