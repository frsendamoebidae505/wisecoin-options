# tests/test_metrics.py
"""指标监控模块测试"""
import pytest
from common.metrics import Metrics


class TestMetrics:
    """指标收集器测试"""

    @pytest.fixture
    def metrics(self):
        """创建指标收集器"""
        return Metrics()

    def test_create_metrics(self, metrics):
        """测试创建指标收集器"""
        assert metrics is not None

    def test_record_api_latency(self, metrics):
        """测试记录 API 延迟"""
        metrics.record_api_latency("get_quote", 100.5)
        metrics.record_api_latency("get_quote", 150.2)

        summary = metrics.get_summary()
        assert "get_quote" in summary["api_latencies"]
        assert summary["api_latencies"]["get_quote"]["count"] == 2

    def test_record_order_result(self, metrics):
        """测试记录订单结果"""
        metrics.record_order_result(True)
        metrics.record_order_result(True)
        metrics.record_order_result(False)

        summary = metrics.get_summary()
        assert summary["order_results"]["success"] == 2
        assert summary["order_results"]["failed"] == 1

    def test_record_error(self, metrics):
        """测试记录错误"""
        metrics.record_error("APIConnectionError")
        metrics.record_error("APIConnectionError")
        metrics.record_error("DataFetchError")

        summary = metrics.get_summary()
        assert summary["error_counts"]["APIConnectionError"] == 2
        assert summary["error_counts"]["DataFetchError"] == 1

    def test_get_summary(self, metrics):
        """测试获取摘要"""
        metrics.record_api_latency("test_op", 50.0)
        metrics.record_order_result(True)

        summary = metrics.get_summary()
        assert "api_latencies" in summary
        assert "order_results" in summary
        assert "error_counts" in summary