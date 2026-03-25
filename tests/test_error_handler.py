# tests/test_error_handler.py
"""错误处理模块测试"""
import pytest
import asyncio
from common.error_handler import ErrorHandler
from common.logger import StructuredLogger
from common.exceptions import APIConnectionError, DataFetchError


class TestErrorHandler:
    """错误处理器测试"""

    @pytest.fixture
    def handler(self):
        """创建错误处理器"""
        logger = StructuredLogger("test")
        return ErrorHandler(logger)

    def test_create_handler(self, handler):
        """测试创建处理器"""
        assert handler is not None

    def test_retry_config(self, handler):
        """测试重试配置"""
        assert handler._retry_config['max_retries'] == 3
        assert handler._retry_config['base_delay'] == 1.0

    def test_with_retry_success(self, handler):
        """测试重试成功"""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIConnectionError("临时失败")
            return "success"

        async def run_test():
            result = await handler.with_retry(
                flaky_func,
                exceptions=(APIConnectionError,)
            )
            return result, call_count

        result, final_count = asyncio.run(run_test())
        assert result == "success"
        assert final_count == 2

    def test_with_retry_max_retries(self, handler):
        """测试达到最大重试次数"""
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise APIConnectionError("持续失败")

        async def run_test():
            with pytest.raises(APIConnectionError):
                await handler.with_retry(
                    always_fail,
                    exceptions=(APIConnectionError,)
                )
            return call_count

        final_count = asyncio.run(run_test())
        assert final_count == 3

    def test_handle_data_error_retryable(self, handler):
        """测试处理可重试数据错误"""
        error = DataFetchError("临时错误", retryable=True)
        result = handler.handle_data_error(error)
        assert result is True

    def test_handle_data_error_not_retryable(self, handler):
        """测试处理不可重试数据错误"""
        error = DataFetchError("永久错误", retryable=False)
        result = handler.handle_data_error(error)
        assert result is False