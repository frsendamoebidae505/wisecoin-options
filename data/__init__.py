"""
WiseCoin 数据层。

提供数据获取、缓存、备份等功能。
"""

from data.cache import QuoteCache
from data.backup import BackupManager

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


__all__ = [
    'QuoteCache',
    'BackupManager',
    'get_tqsdk_client',
]
