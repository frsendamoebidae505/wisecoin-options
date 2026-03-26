# WiseCoin 架构重构 - 实施计划（阶段 2：数据层）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构数据层，统一 TqSDK 客户端，实现期权/期货行情获取、K线数据、缓存等功能。

**Architecture:** 创建 data/ 包，封装所有外部数据源访问。TqSdkClient 作为核心客户端，各 Fetcher 类负责特定数据类型。

**Tech Stack:** Python 3.10+, tqsdk, pandas, asyncio

**Spec:** `docs/superpowers/specs/2026-03-25-architecture-refactor-design.md`

**Depends on:** 阶段 1 已完成（common/ 模块）

---

## 文件结构

```
wisecoin-options-free/
├── data/
│   ├── __init__.py
│   ├── tqsdk_client.py      # TqSDK 客户端（异步上下文管理）
│   ├── option_quotes.py     # 期权行情获取
│   ├── futures_quotes.py    # 期货行情获取
│   ├── klines.py            # K 线数据获取
│   ├── openctp.py           # OpenCTP 数据源
│   ├── cache.py             # 行情缓存
│   └── backup.py            # 数据备份
├── tests/
│   ├── test_tqsdk_client.py
│   ├── test_cache.py
│   └── test_backup.py
└── legacy/                   # 旧文件备份
```

---

## Task 1: 创建数据层目录结构

**Files:**
- Create: `data/__init__.py`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p data
touch data/__init__.py
```

- [ ] **Step 2: 验证**

```bash
ls -la data/
```

- [ ] **Step 3: 提交**

```bash
git add data/
git commit -m "feat(data): 创建数据层目录结构"
```

---

## Task 2: 实现行情缓存模块

**Files:**
- Create: `data/cache.py`
- Create: `tests/test_cache.py`

这是纯 Python 模块，不依赖 TqSDK，可以独立测试。

- [ ] **Step 1: 编写测试**

```python
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
```

- [ ] **Step 2: 实现缓存模块**

```python
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
```

- [ ] **Step 3: 运行测试**

```bash
python3 -m pytest tests/test_cache.py -v
```

- [ ] **Step 4: 提交**

```bash
git add data/cache.py tests/test_cache.py
git commit -m "feat(data): 实现行情缓存模块"
```

---

## Task 3: 实现数据备份模块

**Files:**
- Create: `data/backup.py`
- Create: `tests/test_backup.py`

从原 `00wisecoin_options_backup.py` 和 `00wisecoin_options_backup_clean.py` 提取逻辑。

- [ ] **Step 1: 编写测试**

```python
# tests/test_backup.py
"""备份模块测试"""
import pytest
import os
import tempfile
import shutil
from data.backup import BackupManager


class TestBackupManager:
    """备份管理器测试"""

    @pytest.fixture
    def temp_dirs(self):
        """创建临时目录"""
        source = tempfile.mkdtemp()
        backup = tempfile.mkdtemp()
        yield source, backup
        shutil.rmtree(source, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)

    def test_create_backup_manager(self, temp_dirs):
        """测试创建备份管理器"""
        source, backup = temp_dirs
        manager = BackupManager(source_dir=source, backup_dir=backup)
        assert manager is not None

    def test_create_backup(self, temp_dirs):
        """测试创建备份"""
        source, backup = temp_dirs
        # 在源目录创建文件
        with open(os.path.join(source, "test.txt"), "w") as f:
            f.write("test content")

        manager = BackupManager(source_dir=source, backup_dir=backup)
        backup_path = manager.create_backup()

        assert backup_path is not None
        assert os.path.exists(backup_path)

    def test_clean_old_backups(self, temp_dirs):
        """测试清理旧备份"""
        source, backup = temp_dirs
        manager = BackupManager(source_dir=source, backup_dir=backup)

        # 创建多个备份目录
        os.makedirs(os.path.join(backup, "20260101_0930"))
        os.makedirs(os.path.join(backup, "20260101_0940"))
        os.makedirs(os.path.join(backup, "20260101_1000"))

        # 只保留 _0940 和 _2040 结尾的
        manager.clean_old_backups(keep_suffixes=("_0940", "_2040"))

        remaining = os.listdir(backup)
        assert "20260101_0940" in remaining
        assert "20260101_0930" not in remaining
```

- [ ] **Step 2: 实现备份模块**

```python
# data/backup.py
"""
数据备份模块。

提供数据备份和清理功能。

Example:
    >>> manager = BackupManager(source_dir="./data", backup_dir="./backup")
    >>> manager.create_backup()
"""
import os
import shutil
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

from common.logger import StructuredLogger


class BackupManager:
    """
    备份管理器。

    管理数据备份的创建和清理。

    Attributes:
        source_dir: 源数据目录。
        backup_dir: 备份目录。

    Example:
        >>> manager = BackupManager("./data", "./backup")
        >>> backup_path = manager.create_backup()
    """

    def __init__(
        self,
        source_dir: str,
        backup_dir: str,
        logger: Optional[StructuredLogger] = None,
    ):
        """
        初始化备份管理器。

        Args:
            source_dir: 源数据目录路径。
            backup_dir: 备份目录路径。
            logger: 日志器实例（可选）。
        """
        self.source_dir = Path(source_dir)
        self.backup_dir = Path(backup_dir)
        self.logger = logger or StructuredLogger("backup")

    def create_backup(self, name: Optional[str] = None) -> Optional[str]:
        """
        创建备份。

        Args:
            name: 备份名称（可选），默认使用时间戳。

        Returns:
            备份目录路径，失败返回 None。
        """
        if not self.source_dir.exists():
            self.logger.warning(f"源目录不存在: {self.source_dir}")
            return None

        # 生成备份名称
        if name is None:
            name = datetime.now().strftime("%Y%m%d_%H%M")

        backup_path = self.backup_dir / name

        try:
            # 确保备份目录存在
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # 复制目录
            shutil.copytree(self.source_dir, backup_path, dirs_exist_ok=True)

            self.logger.info(f"备份创建成功: {backup_path}")
            return str(backup_path)

        except Exception as e:
            self.logger.error(f"备份创建失败: {e}")
            return None

    def clean_old_backups(
        self,
        keep_suffixes: Tuple[str, ...] = ("_0940", "_2040"),
    ) -> Tuple[int, int]:
        """
        清理旧备份，只保留特定后缀的备份。

        Args:
            keep_suffixes: 保留的备份名称后缀。

        Returns:
            (保留数量, 删除数量)
        """
        if not self.backup_dir.exists():
            return 0, 0

        kept = 0
        removed = 0

        for item in self.backup_dir.iterdir():
            if not item.is_dir():
                continue

            if item.name.endswith(keep_suffixes):
                kept += 1
            else:
                try:
                    shutil.rmtree(item)
                    self.logger.info(f"已删除旧备份: {item}")
                    removed += 1
                except Exception as e:
                    self.logger.error(f"删除失败: {item}, {e}")

        self.logger.info(f"清理完成: 保留 {kept} 个, 删除 {removed} 个")
        return kept, removed

    def list_backups(self) -> list:
        """
        列出所有备份。

        Returns:
            备份目录名称列表。
        """
        if not self.backup_dir.exists():
            return []

        return sorted([
            item.name for item in self.backup_dir.iterdir()
            if item.is_dir()
        ])
```

- [ ] **Step 3: 运行测试**

```bash
python3 -m pytest tests/test_backup.py -v
```

- [ ] **Step 4: 提交**

```bash
git add data/backup.py tests/test_backup.py
git commit -m "feat(data): 实现数据备份模块"
```

---

## Task 4: 实现 TqSDK 客户端模块

**Files:**
- Create: `data/tqsdk_client.py`

这是数据层的核心，封装 TqSDK 的初始化和生命周期管理。

**注意：** 此模块依赖 TqSDK，测试需要模拟或跳过。

- [ ] **Step 1: 实现客户端模块**

```python
# data/tqsdk_client.py
"""
TqSDK 客户端模块。

封装 TqApi 的创建和生命周期管理，支持多种运行模式。

Example:
    >>> async with TqSdkClient(run_mode=2) as client:
    ...     quote = client.api.get_quote("SHFE.au2406")
"""
from typing import Optional
from contextlib import asynccontextmanager

from common.config import Config, AccountConfig
from common.exceptions import APIConnectionError, ConfigurationError
from common.logger import StructuredLogger

# TqSDK 导入（延迟导入以支持测试）
try:
    from tqsdk import TqApi, TqAuth, TqAccount, TqKq, TqSim
    TQSDK_AVAILABLE = True
except ImportError:
    TQSDK_AVAILABLE = False
    TqApi = None


class TqSdkClient:
    """
    TqSDK 客户端。

    统一管理 TqApi 实例的创建和生命周期。
    支持多种运行模式（回测、模拟、实盘）。

    Attributes:
        run_mode: 运行模式。
        config: 配置实例。

    Example:
        >>> async with TqSdkClient(run_mode=2) as client:
        ...     api = client.api
    """

    # 运行模式定义
    RUN_MODES = {
        1: 'TqSim 回测',
        2: 'TqKq 快期模拟',
        3: 'Simnow 模拟',
        4: '渤海期货实盘',
        5: '华安期货实盘',
        6: '金信期货实盘',
        7: '东吴期货实盘',
        8: '宏源期货实盘',
    }

    def __init__(
        self,
        run_mode: int = 2,
        config: Optional[Config] = None,
        logger: Optional[StructuredLogger] = None,
    ):
        """
        初始化客户端。

        Args:
            run_mode: 运行模式，默认 2（快期模拟）。
            config: 配置实例（可选）。
            logger: 日志器实例（可选）。

        Raises:
            ConfigurationError: 如果 TqSDK 不可用。
        """
        if not TQSDK_AVAILABLE:
            raise ConfigurationError(
                "TqSDK 未安装，请运行: pip install tqsdk"
            )

        self.run_mode = run_mode
        self.config = config or Config(run_mode=run_mode)
        self.logger = logger or StructuredLogger("tqsdk_client")

        self._api: Optional[TqApi] = None
        self._auth: Optional[TqAuth] = None

    async def __aenter__(self) -> 'TqSdkClient':
        """进入异步上下文，初始化 API。"""
        self._api = self._create_api()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出时关闭连接。"""
        self.close()

    @property
    def api(self) -> TqApi:
        """
        获取 TqApi 实例。

        Returns:
            TqApi 实例。

        Raises:
            APIConnectionError: 如果 API 未初始化。
        """
        if self._api is None:
            raise APIConnectionError(
                "API 未初始化，请使用 'async with TqSdkClient()' 上下文管理器"
            )
        return self._api

    def _create_api(self) -> TqApi:
        """
        根据运行模式创建 TqApi。

        Returns:
            TqApi 实例。
        """
        self.logger.info(f"创建 TqApi, 运行模式: {self.RUN_MODES.get(self.run_mode)}")

        # TqAuth 认证（从环境变量或配置获取）
        auth = self._get_auth()

        # 根据运行模式创建不同的 TqApi
        if self.run_mode == 1:
            # TqSim 回测
            return TqApi(TqSim(), auth=auth)

        elif self.run_mode == 2:
            # TqKq 快期模拟
            return TqApi(TqKq(), auth=auth)

        elif self.run_mode in (3, 4, 5, 6, 7, 8):
            # 实盘或 Simnow
            account = self.config.get_account()
            if account is None:
                self.logger.warning(
                    f"运行模式 {self.run_mode} 需要账户配置，"
                    f"请设置环境变量 TQ_BROKER_{self.run_mode}, "
                    f"TQ_ACCOUNT_{self.run_mode}, TQ_PASSWORD_{self.run_mode}"
                )
                # 回退到模拟模式
                return TqApi(TqKq(), auth=auth)

            return TqApi(
                TqAccount(account.broker, account.account, account.password),
                auth=auth
            )

        else:
            raise ConfigurationError(f"无效的运行模式: {self.run_mode}")

    def _get_auth(self) -> TqAuth:
        """
        获取 TqAuth 认证。

        Returns:
            TqAuth 实例。
        """
        import os

        # 从环境变量获取 TqAuth 信息
        auth_user = os.getenv("TQ_AUTH_USER", "")
        auth_password = os.getenv("TQ_AUTH_PASSWORD", "")

        if auth_user and auth_password:
            return TqAuth(auth_user, auth_password)

        # 如果没有配置，使用空认证（TqSDK 会使用默认）
        return None

    def rebuild_api(self) -> TqApi:
        """
        重建 API 连接（防止超时）。

        Returns:
            新的 TqApi 实例。
        """
        self.logger.info("重建 API 连接")
        self.close()
        self._api = self._create_api()
        return self._api

    def close(self):
        """关闭连接。"""
        if self._api is not None:
            try:
                self._api.close()
            except Exception as e:
                self.logger.warning(f"关闭 API 时出错: {e}")
            finally:
                self._api = None

    @classmethod
    @asynccontextmanager
    async def create(cls, run_mode: int = 2, **kwargs):
        """
        便捷方法：创建客户端上下文。

        Args:
            run_mode: 运行模式。
            **kwargs: 其他参数。

        Yields:
            TqSdkClient 实例。
        """
        client = cls(run_mode=run_mode, **kwargs)
        async with client:
            yield client
```

- [ ] **Step 2: 创建基础测试**

```python
# tests/test_tqsdk_client.py
"""TqSDK 客户端测试"""
import pytest
from unittest.mock import patch, MagicMock


class TestTqSdkClientInit:
    """客户端初始化测试（不依赖真实 TqSDK）"""

    def test_run_mode_names(self):
        """测试运行模式名称"""
        from data.tqsdk_client import TqSdkClient

        assert TqSdkClient.RUN_MODES[1] == 'TqSim 回测'
        assert TqSdkClient.RUN_MODES[2] == 'TqKq 快期模拟'
        assert len(TqSdkClient.RUN_MODES) == 8
```

- [ ] **Step 3: 运行测试**

```bash
python3 -m pytest tests/test_tqsdk_client.py -v
```

- [ ] **Step 4: 提交**

```bash
git add data/tqsdk_client.py tests/test_tqsdk_client.py
git commit -m "feat(data): 实现 TqSDK 客户端模块"
```

---

## Task 5: 更新 data 包导出

**Files:**
- Modify: `data/__init__.py`

- [ ] **Step 1: 更新 __init__.py**

```python
# data/__init__.py
"""
WiseCoin 数据层。

提供数据获取、缓存、备份等功能。
"""

from data.cache import QuoteCache
from data.backup import BackupManager

# TqSDK 客户端（延迟导入以支持无 TqSDK 环境）
def get_tqsdk_client():
    """获取 TqSDK 客户端类。"""
    from data.tqsdk_client import TqSdkClient
    return TqSdkClient

__all__ = [
    'QuoteCache',
    'BackupManager',
    'get_tqsdk_client',
]
```

- [ ] **Step 2: 验证导入**

```bash
python3 -c "from data import QuoteCache, BackupManager; print('导入成功')"
```

- [ ] **Step 3: 提交**

```bash
git add data/__init__.py
git commit -m "feat(data): 完善数据层包导出"
```

---

## Task 6: 验证阶段完成

- [ ] **Step 1: 运行全部测试**

```bash
python3 -m pytest tests/ -v
```

- [ ] **Step 2: 检查代码结构**

```bash
ls -la data/
```

- [ ] **Step 3: 确认提交历史**

```bash
git log --oneline -20
```

---

## 阶段 2 完成标准

- [x] data/ 目录创建完成
- [x] QuoteCache 缓存模块实现并测试
- [x] BackupManager 备份模块实现并测试
- [x] TqSdkClient 客户端模块实现
- [x] 所有测试通过

---

## 注意事项

1. **TqSDK 依赖**: `tqsdk_client.py` 需要 TqSDK，测试时需要模拟或跳过
2. **期权/期货行情模块**: 由于需要 TqSDK 运行时环境，这些模块在后续阶段集成
3. **断点续传**: 将在集成测试阶段验证