# common/metrics.py
"""
WiseCoin 指标监控模块。

收集和统计关键性能指标。

Example:
    >>> metrics = Metrics()
    >>> metrics.record_api_latency("get_quote", 100.0)
    >>> summary = metrics.get_summary()
"""
from typing import Dict, List
from collections import defaultdict


class Metrics:
    """
    关键指标收集器。

    收集 API 延迟、订单结果、错误计数等指标。

    Example:
        >>> metrics = Metrics()
        >>> metrics.record_api_latency("get_quote", 100.0)
        >>> summary = metrics.get_summary()
    """

    def __init__(self):
        """初始化指标收集器。"""
        self._api_latencies: Dict[str, List[float]] = defaultdict(list)
        self._order_results: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)

    def record_api_latency(self, operation: str, latency_ms: float):
        """
        记录 API 延迟。

        Args:
            operation: 操作名称。
            latency_ms: 延迟时间（毫秒）。
        """
        self._api_latencies[operation].append(latency_ms)

    def record_order_result(self, success: bool):
        """
        记录订单结果。

        Args:
            success: 是否成功。
        """
        key = "success" if success else "failed"
        self._order_results[key] += 1

    def record_error(self, error_type: str):
        """
        记录错误。

        Args:
            error_type: 错误类型名称。
        """
        self._error_counts[error_type] += 1

    def get_summary(self) -> dict:
        """
        获取指标摘要。

        Returns:
            包含各项指标统计的字典。
        """
        summary = {
            "api_latencies": {},
            "order_results": dict(self._order_results),
            "error_counts": dict(self._error_counts),
        }

        for op, latencies in self._api_latencies.items():
            if latencies:
                summary["api_latencies"][op] = {
                    "avg": sum(latencies) / len(latencies),
                    "max": max(latencies),
                    "min": min(latencies),
                    "count": len(latencies),
                }

        return summary