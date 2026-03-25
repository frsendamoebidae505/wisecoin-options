# data/cache.py
"""
行情缓存模块。

提供 TTL 缓存功能，减少重复数据请求。

Example:
    >>> cache = QuoteCache(ttl_seconds=60)
    >>> cache.set("SHFE.au2406", quote_data)
    >>> data = cache.get("SHFE.au2406")
"""
from typing import Optional, Any, Dict, Tuple
import time


class QuoteCache:
    """
    行情缓存器。

    基于 TTL (Time To Live) 的简单内存缓存。

    Attributes:
        ttl: 缓存过期时间（秒）。

    Example:
        >>> cache = QuoteCache(ttl_seconds=60)
        >>> cache.set("symbol", {"price": 100})
        >>> cache.get("symbol")
        {'price': 100}
    """

    def __init__(self, ttl_seconds: float = 60.0):
        """
        初始化缓存器。

        Args:
            ttl_seconds: 缓存过期时间（秒），默认 60 秒。
        """
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存数据。

        Args:
            key: 缓存键。

        Returns:
            缓存数据，如果不存在或已过期则返回 None。
        """
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return data
            else:
                # 过期，删除
                del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        """
        设置缓存数据。

        Args:
            key: 缓存键。
            value: 缓存值。
        """
        self._cache[key] = (value, time.time())

    def delete(self, key: str):
        """
        删除缓存数据。

        Args:
            key: 缓存键。
        """
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """清空所有缓存。"""
        self._cache.clear()

    def keys(self) -> list:
        """
        获取所有有效的缓存键。

        Returns:
            缓存键列表。
        """
        valid_keys = []
        current_time = time.time()
        for key, (_, timestamp) in self._cache.items():
            if current_time - timestamp < self._ttl:
                valid_keys.append(key)
        return valid_keys

    def __len__(self) -> int:
        """获取缓存条目数量。"""
        return len(self.keys())