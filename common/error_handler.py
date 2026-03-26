# common/error_handler.py
"""
WiseCoin 错误处理模块。

提供统一的错误处理和重试机制。

Example:
    >>> handler = ErrorHandler(logger)
    >>> result = await handler.with_retry(fetch_data)
"""
import asyncio
from typing import Callable, TypeVar, Tuple

from common.exceptions import WiseCoinError, OrderExecutionError, DataFetchError


T = TypeVar('T')


class ErrorHandler:
    """
    统一错误处理器。

    提供错误处理、重试、通知等功能。

    Attributes:
        logger: 日志器实例。
        _retry_config: 重试配置。

    Example:
        >>> handler = ErrorHandler(logger)
        >>> result = await handler.with_retry(fetch_func)
    """

    def __init__(self, logger):
        """
        初始化错误处理器。

        Args:
            logger: 日志器实例。
        """
        self.logger = logger
        self._retry_config = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 30.0,
        }

    async def with_retry(
        self,
        func: Callable[..., T],
        *args,
        exceptions: Tuple = None,
        **kwargs
    ) -> T:
        """
        带重试的异步执行。

        Args:
            func: 异步函数。
            *args: 位置参数。
            exceptions: 需要重试的异常类型元组。
            **kwargs: 关键字参数。

        Returns:
            函数返回值。

        Raises:
            最后一次异常。
        """
        if exceptions is None:
            exceptions = (WiseCoinError,)

        last_error = None
        for attempt in range(self._retry_config['max_retries']):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                last_error = e
                if not e.retryable:
                    raise

                delay = min(
                    self._retry_config['base_delay'] * (2 ** attempt),
                    self._retry_config['max_delay']
                )
                self.logger.warning(
                    f"操作失败，{delay}秒后重试",
                    attempt=attempt + 1,
                    max_retries=self._retry_config['max_retries'],
                    error=str(e),
                )
                await asyncio.sleep(delay)

        raise last_error

    def handle_trade_error(self, error: OrderExecutionError):
        """
        处理交易错误。

        交易错误是关键操作，需要记录日志并通知用户。

        Args:
            error: 订单执行异常。
        """
        self.logger.error(
            "订单执行失败",
            error=error.message,
        )
        self._notify_user(error)

    def handle_data_error(self, error: DataFetchError) -> bool:
        """
        处理数据错误。

        Args:
            error: 数据获取异常。

        Returns:
            是否可以继续（可重试返回 True）。
        """
        if error.retryable:
            self.logger.warning(f"数据获取失败，可重试: {error.message}")
            return True
        self.logger.error(f"数据获取失败: {error.message}")
        return False

    def _notify_user(self, error: WiseCoinError):
        """
        通知用户（预留接口）。

        Args:
            error: 异常实例。

        TODO:
            接入通知渠道（钉钉/微信/邮件）。
        """
        # 预留通知接口
        pass