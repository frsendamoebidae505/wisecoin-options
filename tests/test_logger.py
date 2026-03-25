# tests/test_logger.py
"""日志模块测试"""
import pytest
from common.logger import StructuredLogger


class TestStructuredLogger:
    """结构化日志测试"""

    def test_create_logger(self):
        """测试创建日志器"""
        logger = StructuredLogger("test")
        assert logger is not None

    def test_info_logging(self, caplog):
        """测试 info 级别日志"""
        import logging
        logging.basicConfig(level=logging.DEBUG)

        logger = StructuredLogger("test")
        logger.info("测试消息", key="value")

    def test_warning_logging(self, caplog):
        """测试 warning 级别日志"""
        import logging
        logging.basicConfig(level=logging.DEBUG)

        logger = StructuredLogger("test")
        logger.warning("警告消息")

    def test_error_logging(self, caplog):
        """测试 error 级别日志"""
        import logging
        logging.basicConfig(level=logging.DEBUG)

        logger = StructuredLogger("test")
        logger.error("错误消息")

    def test_log_trade(self, caplog):
        """测试交易日志"""
        import logging
        logging.basicConfig(level=logging.DEBUG)

        logger = StructuredLogger("test")
        logger.log_trade(
            symbol="SHFE.au2406C480",
            action="BUY",
            price=15.0,
            volume=1,
            result="FILLED"
        )

    def test_log_api_event(self, caplog):
        """测试 API 事件日志"""
        import logging
        logging.basicConfig(level=logging.DEBUG)

        logger = StructuredLogger("test")
        logger.log_api_event("get_quote", duration_ms=123.5)