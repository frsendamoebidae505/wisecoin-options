# common/logger.py
"""
WiseCoin 日志模块。

提供结构化日志功能，支持交易日志、API 事件日志等。

Example:
    >>> logger = StructuredLogger("wisecoin")
    >>> logger.log_trade("SHFE.au2406C480", "BUY", 15.0, 1, "FILLED")
"""
import logging
from typing import Optional


class StructuredLogger:
    """
    结构化日志器。

    提供统一的日志记录接口，支持结构化字段。

    Attributes:
        name: 日志器名称。
        logger: 标准 logging.Logger 实例。

    Example:
        >>> logger = StructuredLogger("wisecoin")
        >>> logger.info("系统启动")
    """

    def __init__(self, name: str, log_file: Optional[str] = None):
        """
        初始化日志器。

        Args:
            name: 日志器名称。
            log_file: 日志文件路径（可选）。
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_handlers(log_file)

    def _setup_handlers(self, log_file: Optional[str]):
        """
        配置日志处理器。

        Args:
            log_file: 日志文件路径。
        """
        if not self.logger.handlers:
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            # 文件处理器
            if log_file:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)

            self.logger.setLevel(logging.DEBUG)

    def info(self, message: str, **kwargs):
        """
        记录 info 级别日志。

        Args:
            message: 日志消息。
            **kwargs: 附加字段。
        """
        extra = ' '.join(f'{k}={v}' for k, v in kwargs.items())
        self.logger.info(f"{message} {extra}".strip())

    def warning(self, message: str, **kwargs):
        """
        记录 warning 级别日志。

        Args:
            message: 日志消息。
            **kwargs: 附加字段。
        """
        extra = ' '.join(f'{k}={v}' for k, v in kwargs.items())
        self.logger.warning(f"{message} {extra}".strip())

    def error(self, message: str, **kwargs):
        """
        记录 error 级别日志。

        Args:
            message: 日志消息。
            **kwargs: 附加字段。
        """
        extra = ' '.join(f'{k}={v}' for k, v in kwargs.items())
        self.logger.error(f"{message} {extra}".strip())

    def debug(self, message: str, **kwargs):
        """
        记录 debug 级别日志。

        Args:
            message: 日志消息。
            **kwargs: 附加字段。
        """
        extra = ' '.join(f'{k}={v}' for k, v in kwargs.items())
        self.logger.debug(f"{message} {extra}".strip())

    def log_trade(self, symbol: str, action: str, price: float,
                  volume: int, result: str):
        """
        记录交易日志。

        Args:
            symbol: 合约代码。
            action: 交易动作 (BUY/SELL)。
            price: 成交价格。
            volume: 成交数量。
            result: 交易结果。
        """
        self.logger.info(
            f"TRADE symbol={symbol} action={action} "
            f"price={price} volume={volume} result={result}"
        )

    def log_api_event(self, event: str, duration_ms: Optional[float] = None):
        """
        记录 API 事件日志。

        Args:
            event: 事件名称。
            duration_ms: 耗时（毫秒）。
        """
        if duration_ms:
            self.logger.info(f"API event={event} duration_ms={duration_ms:.2f}")
        else:
            self.logger.info(f"API event={event}")