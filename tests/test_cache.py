# tests/test_cache.py
"""缓存模块测试"""
import pytest
import time
from data.cache import QuoteCache


class TestQuoteCache:
    """行情缓存测试"""

    def test_create_cache(self):
        """测试创建缓存"""
        cache = QuoteCache(ttl_seconds=60)
        assert cache is not None

    def test_set_and_get(self):
        """测试设置和获取"""
        cache = QuoteCache(ttl_seconds=60)
        cache.set("SHFE.au2406", {"price": 480.0})
        result = cache.get("SHFE.au2406")
        assert result == {"price": 480.0}

    def test_get_nonexistent(self):
        """测试获取不存在的数据"""
        cache = QuoteCache(ttl_seconds=60)
        result = cache.get("NONEXISTENT")
        assert result is None

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = QuoteCache(ttl_seconds=0.1)  # 100ms TTL
        cache.set("SHFE.au2406", {"price": 480.0})

        # 立即获取应该成功
        assert cache.get("SHFE.au2406") is not None

        # 等待过期
        time.sleep(0.15)
        assert cache.get("SHFE.au2406") is None

    def test_clear(self):
        """测试清空缓存"""
        cache = QuoteCache(ttl_seconds=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None