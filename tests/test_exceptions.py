# tests/test_exceptions.py
"""异常模块测试"""
import pytest
from common.exceptions import (
    WiseCoinError,
    DataFetchError,
    APIConnectionError,
    OrderExecutionError,
    RiskCheckError,
    ConfigurationError,
    ValidationError,
)


class TestWiseCoinError:
    """基础异常测试"""

    def test_basic_error(self):
        """测试基本异常创建"""
        error = WiseCoinError("测试错误")
        assert error.message == "测试错误"
        assert error.retryable is False
        assert str(error) == "测试错误"

    def test_retryable_error(self):
        """测试可重试异常"""
        error = WiseCoinError("可重试错误", retryable=True)
        assert error.retryable is True


class TestAPIConnectionError:
    """API 连接异常测试"""

    def test_api_connection_error_is_retryable(self):
        """API 连接错误默认可重试"""
        error = APIConnectionError("连接失败")
        assert error.retryable is True

    def test_api_connection_error_message(self):
        """测试错误消息"""
        error = APIConnectionError("连接超时")
        assert error.message == "连接超时"


class TestDataFetchError:
    """数据获取异常测试"""

    def test_data_fetch_error(self):
        """测试数据获取错误"""
        error = DataFetchError("获取行情失败")
        assert error.message == "获取行情失败"
        assert error.retryable is False

    def test_retryable_data_fetch_error(self):
        """测试可重试的数据获取错误"""
        error = DataFetchError("临时错误", retryable=True)
        assert error.retryable is True


class TestOrderExecutionError:
    """订单执行异常测试"""

    def test_order_execution_error(self):
        """测试订单执行错误"""
        error = OrderExecutionError("下单失败")
        assert error.message == "下单失败"
        assert error.retryable is False


class TestRiskCheckError:
    """风控检查异常测试"""

    def test_risk_check_error(self):
        """测试风控错误"""
        error = RiskCheckError("超过持仓限制")
        assert error.message == "超过持仓限制"


class TestConfigurationError:
    """配置异常测试"""

    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("无效的运行模式")
        assert error.message == "无效的运行模式"


class TestValidationError:
    """数据验证异常测试"""

    def test_validation_error(self):
        """测试验证错误"""
        error = ValidationError("价格不能为负数")
        assert error.message == "价格不能为负数"