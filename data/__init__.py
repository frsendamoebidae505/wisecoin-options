"""
WiseCoin 数据层。

提供数据获取、缓存、备份等功能。
"""

# 使用延迟导入避免循环导入警告
# 当运行 `python3 -m data.backup` 时，不会触发这些导入

def __getattr__(name):
    """延迟导入模块成员"""
    if name == 'QuoteCache':
        from data.cache import QuoteCache
        return QuoteCache
    elif name == 'BackupManager':
        from data.backup import BackupManager
        return BackupManager
    elif name == 'OpenCTPClient':
        from data.openctp import OpenCTPClient
        return OpenCTPClient
    elif name == 'fetch_openctp_data':
        from data.openctp import fetch_openctp_data
        return fetch_openctp_data
    elif name == 'check_margin_ratios':
        from data.openctp import check_margin_ratios
        return check_margin_ratios
    elif name == 'LiveSymbolGenerator':
        from data.live_symbol import LiveSymbolGenerator
        return LiveSymbolGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
    'LiveSymbolGenerator',
]
