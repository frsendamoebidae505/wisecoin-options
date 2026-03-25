# common/exceptions.py
"""
WiseCoin 统一异常定义。

所有业务异常都继承自 WiseCoinError，便于统一处理。
"""
from typing import Optional


class WiseCoinError(Exception):
    """
    WiseCoin 基础异常。

    所有业务异常的基类，提供统一的错误处理接口。

    Attributes:
        message: 错误消息。
        retryable: 是否可重试。

    Example:
        >>> raise WiseCoinError("系统错误")
        WiseCoinError: 系统错误
    """

    def __init__(self, message: str, retryable: bool = False):
        """
        初始化异常。

        Args:
            message: 错误消息。
            retryable: 是否可重试，默认 False。
        """
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class DataFetchError(WiseCoinError):
    """
    数据获取失败异常。

    当从外部数据源获取数据失败时抛出。

    Example:
        >>> raise DataFetchError("获取期权行情失败")
    """
    pass


class APIConnectionError(WiseCoinError):
    """
    API 连接失败异常。

    当 TqSDK 或其他 API 连接失败时抛出，默认可重试。

    Example:
        >>> raise APIConnectionError("TqSDK 连接超时")
    """

    def __init__(self, message: str):
        super().__init__(message, retryable=True)


class OrderExecutionError(WiseCoinError):
    """
    订单执行失败异常。

    当下单、撤单等交易操作失败时抛出。

    Example:
        >>> raise OrderExecutionError("下单被拒绝")
    """
    pass


class RiskCheckError(WiseCoinError):
    """
    风控检查失败异常。

    当交易请求未通过风控检查时抛出。

    Example:
        >>> raise RiskCheckError("超过单品种持仓限制")
    """
    pass


class ConfigurationError(WiseCoinError):
    """
    配置错误异常。

    当配置无效或缺失时抛出。

    Example:
        >>> raise ConfigurationError("无效的运行模式: 99")
    """
    pass


class ValidationError(WiseCoinError):
    """
    数据验证失败异常。

    当输入数据不符合要求时抛出。

    Example:
        >>> raise ValidationError("期权价格不能为负数")
    """
    pass