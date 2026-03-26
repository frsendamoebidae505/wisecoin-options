"""
WiseCoin 数据层。

提供数据获取、缓存、备份等功能。
"""

from data.cache import QuoteCache
from data.backup import BackupManager
from data.openctp import OpenCTPClient, fetch_openctp_data, check_margin_ratios

# TqSDK 客户端（延迟导入以支持无 TqSDK 环境）
def get_tqsdk_client():
    """
    获取 TqSDK 客户端类。

    Returns:
        TqSdkClient 类

    Raises:
        ConfigurationError: 如果 TqSDK 未安装
    """
    from data.tqsdk_client import TqSdkClient
    return TqSdkClient


# K线获取（延迟导入以支持无 TqSDK 环境）
def get_futures_kline_fetcher():
    """
    获取期货K线获取器类。

    Returns:
        FuturesKlineFetcher 类

    Raises:
        ImportError: 如果 TqSDK 未安装
    """
    from data.klines import FuturesKlineFetcher
    return FuturesKlineFetcher


def get_fetch_futures_klines():
    """
    获取期货K线获取便捷函数。

    Returns:
        fetch_futures_klines 函数

    Raises:
        ImportError: 如果 TqSDK 未安装
    """
    from data.klines import fetch_futures_klines
    return fetch_futures_klines


# 期权行情管理器（延迟导入）
def get_option_quotes_manager():
    """
    获取期权行情管理器类。

    Returns:
        OptionQuotesManager 类
    """
    from data.option_quotes import OptionQuotesManager
    return OptionQuotesManager


__all__ = [
    'QuoteCache',
    'BackupManager',
    'get_tqsdk_client',
    'get_futures_kline_fetcher',
    'get_fetch_futures_klines',
    'get_option_quotes_manager',
    'OpenCTPClient',
    'fetch_openctp_data',
    'check_margin_ratios',
]
