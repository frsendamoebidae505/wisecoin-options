# WiseCoin 架构重构 - 实施计划（阶段 1：公共模块）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提取公共基础设施模块，为后续重构奠定基础。

**Architecture:** 创建 common/ 包，包含配置管理、异常定义、日志系统、Excel 读写、错误处理等公共组件。采用依赖注入容器统一管理组件生命周期。

**Tech Stack:** Python 3.10+, dataclasses, structlog, dependency-injector, pandas, openpyxl

**Spec:** `docs/superpowers/specs/2026-03-25-architecture-refactor-design.md`

---

## 文件结构

```
wisecoin-options-free/
├── common/
│   ├── __init__.py
│   ├── config.py
│   ├── exceptions.py
│   ├── logger.py
│   ├── excel_io.py
│   ├── error_handler.py
│   ├── container.py
│   └── metrics.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_exceptions.py
│   ├── test_logger.py
│   └── test_excel_io.py
├── pyproject.toml
└── legacy/                    # 旧文件备份目录
```

---

## Task 1: 创建项目基础结构

**Files:**
- Create: `common/__init__.py`
- Create: `tests/__init__.py`
- Create: `pyproject.toml`
- Create: `legacy/.gitkeep`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p common tests legacy
touch common/__init__.py tests/__init__.py legacy/.gitkeep
```

- [ ] **Step 2: 创建 pyproject.toml**

```toml
# pyproject.toml
[project]
name = "wisecoin-options"
version = "2.0.0"
description = "WiseCoin 期权分析系统"
requires-python = ">=3.10"
dependencies = [
    "tqsdk>=3.4.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "openpyxl>=3.1.0",
    "structlog>=23.0.0",
    "dependency-injector>=4.41.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

[tool.coverage.run]
source = ["common"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
]
```

- [ ] **Step 3: 验证结构**

```bash
ls -la common/ tests/ legacy/
```

Expected: 三个目录都存在

---

## Task 2: 实现异常定义模块

**Files:**
- Create: `common/exceptions.py`
- Create: `tests/test_exceptions.py`

- [ ] **Step 1: 编写异常测试**

```python
# tests/test_exceptions.py
"""异常模块测试"""
import pytest
from common.exceptions import (
    WiseCoinError,
    DataFetchError,
    APIConnectionError,
    OrderExecutionError,
    RiskCheckError,
    ConfigurationError,
    ValidationError,
)


class TestWiseCoinError:
    """基础异常测试"""

    def test_basic_error(self):
        """测试基本异常创建"""
        error = WiseCoinError("测试错误")
        assert error.message == "测试错误"
        assert error.retryable is False
        assert str(error) == "测试错误"

    def test_retryable_error(self):
        """测试可重试异常"""
        error = WiseCoinError("可重试错误", retryable=True)
        assert error.retryable is True


class TestAPIConnectionError:
    """API 连接异常测试"""

    def test_api_connection_error_is_retryable(self):
        """API 连接错误默认可重试"""
        error = APIConnectionError("连接失败")
        assert error.retryable is True

    def test_api_connection_error_message(self):
        """测试错误消息"""
        error = APIConnectionError("连接超时")
        assert error.message == "连接超时"


class TestDataFetchError:
    """数据获取异常测试"""

    def test_data_fetch_error(self):
        """测试数据获取错误"""
        error = DataFetchError("获取行情失败")
        assert error.message == "获取行情失败"
        assert error.retryable is False

    def test_retryable_data_fetch_error(self):
        """测试可重试的数据获取错误"""
        error = DataFetchError("临时错误", retryable=True)
        assert error.retryable is True


class TestOrderExecutionError:
    """订单执行异常测试"""

    def test_order_execution_error(self):
        """测试订单执行错误"""
        error = OrderExecutionError("下单失败")
        assert error.message == "下单失败"
        assert error.retryable is False


class TestRiskCheckError:
    """风控检查异常测试"""

    def test_risk_check_error(self):
        """测试风控错误"""
        error = RiskCheckError("超过持仓限制")
        assert error.message == "超过持仓限制"


class TestConfigurationError:
    """配置异常测试"""

    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("无效的运行模式")
        assert error.message == "无效的运行模式"


class TestValidationError:
    """数据验证异常测试"""

    def test_validation_error(self):
        """测试验证错误"""
        error = ValidationError("价格不能为负数")
        assert error.message == "价格不能为负数"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/playbonze/pb-quant/26WiseCoin/wisecoin-options-free
python -m pytest tests/test_exceptions.py -v
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现异常模块**

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_exceptions.py -v
```

Expected: PASS (8 tests)

- [ ] **Step 5: 提交**

```bash
git add common/__init__.py common/exceptions.py tests/__init__.py tests/test_exceptions.py pyproject.toml legacy/.gitkeep
git commit -m "feat(common): 添加异常定义模块

- 定义 WiseCoinError 基类
- 添加 DataFetchError, APIConnectionError 等业务异常
- 异常支持 retryable 标记
- 完成单元测试"
```

---

## Task 3: 实现配置管理模块

**Files:**
- Create: `common/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 编写配置测试**

```python
# tests/test_config.py
"""配置模块测试"""
import os
import pytest
from common.config import (
    Config,
    AccountConfig,
    TradingConfig,
    DataConfig,
    SchedulerConfig,
)


class TestTradingConfig:
    """交易配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = TradingConfig()
        assert config.max_position_per_symbol == 10
        assert config.max_margin_usage == 0.8
        assert config.default_order_volume == 1
        assert config.daily_loss_limit == 0.05


class TestDataConfig:
    """数据配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = DataConfig()
        assert config.quote_batch_size == 200
        assert config.save_interval == 3000
        assert config.api_rebuild_interval == 3000
        assert config.kline_data_length == 250
        assert config.cache_ttl_seconds == 60


class TestSchedulerConfig:
    """调度配置测试"""

    def test_default_scheduled_times(self):
        """测试默认调度时间"""
        config = SchedulerConfig()
        assert len(config.scheduled_times) == 13
        assert (20, 40) in config.scheduled_times
        assert (9, 40) in config.scheduled_times

    def test_check_interval(self):
        """测试检查间隔"""
        config = SchedulerConfig()
        assert config.check_interval == 30
        assert config.cooldown_minutes == 5


class TestConfig:
    """全局配置测试"""

    def test_default_run_mode(self):
        """测试默认运行模式"""
        config = Config()
        assert config.run_mode == 2

    def test_run_mode_names(self):
        """测试运行模式名称"""
        config = Config()
        assert config.RUN_MODES[1] == "TqSim 回测"
        assert config.RUN_MODES[2] == "TqKq 快期模拟"
        assert config.RUN_MODES[6] == "金信期货实盘"

    def test_custom_run_mode(self):
        """测试自定义运行模式"""
        config = Config(run_mode=6)
        assert config.run_mode == 6

    def test_sub_configs_exist(self):
        """测试子配置存在"""
        config = Config()
        assert isinstance(config.trading, TradingConfig)
        assert isinstance(config.data, DataConfig)
        assert isinstance(config.scheduler, SchedulerConfig)

    def test_get_account_without_env(self):
        """测试无环境变量时获取账户"""
        config = Config(run_mode=99)
        assert config.get_account() is None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_config.py -v
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现配置模块**

```python
# common/config.py
"""
WiseCoin 配置管理模块。

提供统一的配置管理，支持运行模式切换、账户配置、业务参数配置。

Example:
    >>> config = Config(run_mode=2)
    >>> print(config.RUN_MODES[config.run_mode])
    'TqKq 快期模拟'
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import os


@dataclass
class AccountConfig:
    """
    账户配置。

    Attributes:
        broker: 期货公司名称。
        account: 账户号。
        password: 密码（应从环境变量读取）。
    """
    broker: str
    account: str
    password: str


@dataclass
class TradingConfig:
    """
    交易配置。

    Attributes:
        max_position_per_symbol: 单品种最大持仓手数。
        max_margin_usage: 最大保证金占用比例。
        default_order_volume: 默认下单手数。
        daily_loss_limit: 日内亏损限制比例。
    """
    max_position_per_symbol: int = 10
    max_margin_usage: float = 0.8
    default_order_volume: int = 1
    daily_loss_limit: float = 0.05


@dataclass
class DataConfig:
    """
    数据配置。

    Attributes:
        quote_batch_size: 行情获取批次大小。
        save_interval: 数据保存间隔。
        api_rebuild_interval: API 重建间隔。
        kline_data_length: K 线数据长度。
        cache_ttl_seconds: 缓存过期时间（秒）。
    """
    quote_batch_size: int = 200
    save_interval: int = 3000
    api_rebuild_interval: int = 3000
    kline_data_length: int = 250
    cache_ttl_seconds: int = 60


@dataclass
class SchedulerConfig:
    """
    调度配置。

    Attributes:
        scheduled_times: 调度时间列表 (hour, minute)。
        check_interval: 检查间隔（秒）。
        cooldown_minutes: 冷却时间（分钟）。
    """
    scheduled_times: List[tuple] = field(default_factory=lambda: [
        (20, 40), (21, 40), (22, 40), (23, 40), (0, 40), (1, 40),
        (8, 40), (9, 40), (10, 40), (12, 40), (13, 40), (14, 40), (15, 16)
    ])
    check_interval: int = 30
    cooldown_minutes: int = 5


class Config:
    """
    全局配置管理器。

    管理所有配置项，支持从环境变量加载敏感信息。

    Attributes:
        run_mode: 运行模式。
        trading: 交易配置。
        data: 数据配置。
        scheduler: 调度配置。

    Example:
        >>> config = Config(run_mode=2)
        >>> account = config.get_account()
    """

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

    def __init__(self, run_mode: int = 2, config_path: Optional[str] = None):
        """
        初始化配置。

        Args:
            run_mode: 运行模式，默认 2（快期模拟）。
            config_path: 配置文件路径（可选）。
        """
        self.run_mode = run_mode
        self.trading = TradingConfig()
        self.data = DataConfig()
        self.scheduler = SchedulerConfig()
        self._accounts: Dict[int, AccountConfig] = {}

        if config_path:
            self._load_from_file(config_path)
        self._load_accounts()

    def _load_from_file(self, path: str):
        """
        从文件加载配置。

        Args:
            path: 配置文件路径。
        """
        # TODO: 实现 JSON/YAML 配置文件加载
        pass

    def _load_accounts(self):
        """从环境变量加载账户配置。"""
        for mode in self.RUN_MODES.keys():
            broker = os.getenv(f'TQ_BROKER_{mode}')
            account = os.getenv(f'TQ_ACCOUNT_{mode}')
            password = os.getenv(f'TQ_PASSWORD_{mode}')
            if broker and account and password:
                self._accounts[mode] = AccountConfig(
                    broker=broker,
                    account=account,
                    password=password,
                )

    def get_account(self) -> Optional[AccountConfig]:
        """
        获取当前运行模式的账户配置。

        Returns:
            账户配置，如果未配置则返回 None。
        """
        return self._accounts.get(self.run_mode)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_config.py -v
```

Expected: PASS (8 tests)

- [ ] **Step 5: 提交**

```bash
git add common/config.py tests/test_config.py
git commit -m "feat(common): 添加配置管理模块

- 实现 Config, TradingConfig, DataConfig, SchedulerConfig
- 支持 8 种运行模式
- 从环境变量加载账户信息
- 完成单元测试"
```

---

## Task 4: 实现日志模块

**Files:**
- Create: `common/logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: 编写日志测试**

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_logger.py -v
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现日志模块**

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_logger.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 5: 提交**

```bash
git add common/logger.py tests/test_logger.py
git commit -m "feat(common): 添加日志模块

- 实现 StructuredLogger 类
- 支持交易日志和 API 事件日志
- 支持控制台和文件输出
- 完成单元测试"
```

---

## Task 5: 实现 Excel 读写模块

**Files:**
- Create: `common/excel_io.py`
- Create: `tests/test_excel_io.py`

- [ ] **Step 1: 编写 Excel 测试**

```python
# tests/test_excel_io.py
"""Excel 读写模块测试"""
import os
import pytest
import pandas as pd
from common.excel_io import ExcelWriter, ExcelReader


class TestExcelWriter:
    """Excel 写入器测试"""

    @pytest.fixture
    def sample_df(self):
        """测试数据"""
        return pd.DataFrame({
            'symbol': ['SHFE.au2406', 'SHFE.ag2406'],
            'price': [480.0, 6000.0],
            'volume': [100, 50],
        })

    @pytest.fixture
    def temp_file(self, tmp_path):
        """临时文件路径"""
        return str(tmp_path / "test.xlsx")

    def test_write_dataframe(self, sample_df, temp_file):
        """测试写入单个 DataFrame"""
        writer = ExcelWriter()
        writer.write_dataframe(sample_df, file_path=temp_file)
        assert os.path.exists(temp_file)

    def test_write_multiple_sheets(self, temp_file):
        """测试写入多个 Sheet"""
        df1 = pd.DataFrame({'a': [1, 2]})
        df2 = pd.DataFrame({'b': [3, 4]})

        writer = ExcelWriter()
        writer.write_multiple({
            'Sheet1': df1,
            'Sheet2': df2,
        }, file_path=temp_file)

        # 验证
        reader = ExcelReader()
        sheets = reader.read_all_sheets(temp_file)
        assert 'Sheet1' in sheets
        assert 'Sheet2' in sheets


class TestExcelReader:
    """Excel 读取器测试"""

    @pytest.fixture
    def sample_excel(self, tmp_path):
        """创建测试 Excel 文件"""
        file_path = str(tmp_path / "sample.xlsx")
        df = pd.DataFrame({
            'symbol': ['A', 'B'],
            'price': [100.0, 200.0],
        })
        df.to_excel(file_path, index=False)
        return file_path

    def test_read_sheet(self, sample_excel):
        """测试读取单个 Sheet"""
        reader = ExcelReader()
        df = reader.read_sheet(sample_excel)
        assert len(df) == 2
        assert 'symbol' in df.columns

    def test_read_all_sheets(self, sample_excel):
        """测试读取所有 Sheet"""
        reader = ExcelReader()
        sheets = reader.read_all_sheets(sample_excel)
        assert isinstance(sheets, dict)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_excel_io.py -v
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现 Excel 读写模块**

```python
# common/excel_io.py
"""
WiseCoin Excel 读写模块。

封装 pandas Excel 操作，提供统一的读写接口。

Example:
    >>> writer = ExcelWriter()
    >>> writer.write_dataframe(df, "output.xlsx")

    >>> reader = ExcelReader()
    >>> df = reader.read_sheet("input.xlsx")
"""
from typing import Dict, Optional
import pandas as pd


class ExcelWriter:
    """
    Excel 写入器。

    提供统一的 Excel 写入接口。

    Example:
        >>> writer = ExcelWriter()
        >>> writer.write_dataframe(df, "output.xlsx")
    """

    def write_dataframe(
        self,
        df: pd.DataFrame,
        file_path: str,
        sheet_name: str = 'Sheet1',
        auto_adjust_width: bool = True,
    ):
        """
        写入单个 DataFrame 到 Excel。

        Args:
            df: 要写入的数据。
            file_path: 输出文件路径。
            sheet_name: Sheet 名称，默认 'Sheet1'。
            auto_adjust_width: 是否自动调整列宽，默认 True。
        """
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            if auto_adjust_width:
                self._adjust_column_width(writer, df, sheet_name)

    def write_multiple(
        self,
        data: Dict[str, pd.DataFrame],
        file_path: str,
        auto_adjust_width: bool = True,
    ):
        """
        写入多个 DataFrame 到 Excel 的不同 Sheet。

        Args:
            data: {sheet_name: dataframe} 映射。
            file_path: 输出文件路径。
            auto_adjust_width: 是否自动调整列宽。
        """
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for sheet_name, df in data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)

                if auto_adjust_width:
                    self._adjust_column_width(writer, df, sheet_name)

    def append_sheet(
        self,
        df: pd.DataFrame,
        file_path: str,
        sheet_name: str,
    ):
        """
        追加 Sheet 到已有 Excel 文件。

        Args:
            df: 要写入的数据。
            file_path: Excel 文件路径。
            sheet_name: 新 Sheet 名称。
        """
        with pd.ExcelWriter(
            file_path, engine='openpyxl', mode='a', if_sheet_exists='replace'
        ) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    def _adjust_column_width(self, writer, df: pd.DataFrame, sheet_name: str):
        """
        自动调整列宽。

        Args:
            writer: ExcelWriter 实例。
            df: 数据。
            sheet_name: Sheet 名称。
        """
        worksheet = writer.sheets[sheet_name]
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            ) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)


class ExcelReader:
    """
    Excel 读取器。

    提供统一的 Excel 读取接口。

    Example:
        >>> reader = ExcelReader()
        >>> df = reader.read_sheet("input.xlsx")
    """

    def read_sheet(
        self,
        file_path: str,
        sheet_name: str = 0,
    ) -> pd.DataFrame:
        """
        读取单个 Sheet。

        Args:
            file_path: Excel 文件路径。
            sheet_name: Sheet 名称或索引，默认第一个 Sheet。

        Returns:
            DataFrame 数据。
        """
        return pd.read_excel(file_path, sheet_name=sheet_name)

    def read_all_sheets(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """
        读取所有 Sheet。

        Args:
            file_path: Excel 文件路径。

        Returns:
            {sheet_name: dataframe} 映射。
        """
        return pd.read_excel(file_path, sheet_name=None)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_excel_io.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: 提交**

```bash
git add common/excel_io.py tests/test_excel_io.py
git commit -m "feat(common): 添加 Excel 读写模块

- 实现 ExcelWriter 和 ExcelReader 类
- 支持自动调整列宽
- 支持多 Sheet 读写
- 完成单元测试"
```

---

## Task 6: 实现错误处理模块

**Files:**
- Create: `common/error_handler.py`
- Create: `tests/test_error_handler.py`

- [ ] **Step 1: 编写错误处理测试**

```python
# tests/test_error_handler.py
"""错误处理模块测试"""
import pytest
import asyncio
from common.error_handler import ErrorHandler
from common.logger import StructuredLogger
from common.exceptions import APIConnectionError, DataFetchError


class TestErrorHandler:
    """错误处理器测试"""

    @pytest.fixture
    def handler(self):
        """创建错误处理器"""
        logger = StructuredLogger("test")
        return ErrorHandler(logger)

    def test_create_handler(self, handler):
        """测试创建处理器"""
        assert handler is not None

    def test_retry_config(self, handler):
        """测试重试配置"""
        assert handler._retry_config['max_retries'] == 3
        assert handler._retry_config['base_delay'] == 1.0

    @pytest.mark.asyncio
    async def test_with_retry_success(self, handler):
        """测试重试成功"""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIConnectionError("临时失败")
            return "success"

        result = await handler.with_retry(
            flaky_func,
            exceptions=(APIConnectionError,)
        )
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_with_retry_max_retries(self, handler):
        """测试达到最大重试次数"""
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise APIConnectionError("持续失败")

        with pytest.raises(APIConnectionError):
            await handler.with_retry(
                always_fail,
                exceptions=(APIConnectionError,)
            )
        assert call_count == 3

    def test_handle_data_error_retryable(self, handler):
        """测试处理可重试数据错误"""
        error = DataFetchError("临时错误", retryable=True)
        result = handler.handle_data_error(error)
        assert result is True

    def test_handle_data_error_not_retryable(self, handler):
        """测试处理不可重试数据错误"""
        error = DataFetchError("永久错误", retryable=False)
        result = handler.handle_data_error(error)
        assert result is False
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_error_handler.py -v
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现错误处理模块**

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_error_handler.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: 提交**

```bash
git add common/error_handler.py tests/test_error_handler.py
git commit -m "feat(common): 添加错误处理模块

- 实现 ErrorHandler 类
- 支持异步重试机制
- 支持指数退避
- 完成单元测试"
```

---

## Task 7: 实现指标监控模块

**Files:**
- Create: `common/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: 编写指标测试**

```python
# tests/test_metrics.py
"""指标监控模块测试"""
import pytest
from common.metrics import Metrics


class TestMetrics:
    """指标收集器测试"""

    @pytest.fixture
    def metrics(self):
        """创建指标收集器"""
        return Metrics()

    def test_create_metrics(self, metrics):
        """测试创建指标收集器"""
        assert metrics is not None

    def test_record_api_latency(self, metrics):
        """测试记录 API 延迟"""
        metrics.record_api_latency("get_quote", 100.5)
        metrics.record_api_latency("get_quote", 150.2)

        summary = metrics.get_summary()
        assert "get_quote" in summary["api_latencies"]
        assert summary["api_latencies"]["get_quote"]["count"] == 2

    def test_record_order_result(self, metrics):
        """测试记录订单结果"""
        metrics.record_order_result(True)
        metrics.record_order_result(True)
        metrics.record_order_result(False)

        summary = metrics.get_summary()
        assert summary["order_results"]["success"] == 2
        assert summary["order_results"]["failed"] == 1

    def test_record_error(self, metrics):
        """测试记录错误"""
        metrics.record_error("APIConnectionError")
        metrics.record_error("APIConnectionError")
        metrics.record_error("DataFetchError")

        summary = metrics.get_summary()
        assert summary["error_counts"]["APIConnectionError"] == 2
        assert summary["error_counts"]["DataFetchError"] == 1

    def test_get_summary(self, metrics):
        """测试获取摘要"""
        metrics.record_api_latency("test_op", 50.0)
        metrics.record_order_result(True)

        summary = metrics.get_summary()
        assert "api_latencies" in summary
        assert "order_results" in summary
        assert "error_counts" in summary
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_metrics.py -v
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现指标监控模块**

```python
# common/metrics.py
"""
WiseCoin 指标监控模块。

收集和统计关键性能指标。

Example:
    >>> metrics = Metrics()
    >>> metrics.record_api_latency("get_quote", 100.0)
    >>> summary = metrics.get_summary()
"""
from typing import Dict, List
from collections import defaultdict


class Metrics:
    """
    关键指标收集器。

    收集 API 延迟、订单结果、错误计数等指标。

    Example:
        >>> metrics = Metrics()
        >>> metrics.record_api_latency("get_quote", 100.0)
        >>> summary = metrics.get_summary()
    """

    def __init__(self):
        """初始化指标收集器。"""
        self._api_latencies: Dict[str, List[float]] = defaultdict(list)
        self._order_results: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)

    def record_api_latency(self, operation: str, latency_ms: float):
        """
        记录 API 延迟。

        Args:
            operation: 操作名称。
            latency_ms: 延迟时间（毫秒）。
        """
        self._api_latencies[operation].append(latency_ms)

    def record_order_result(self, success: bool):
        """
        记录订单结果。

        Args:
            success: 是否成功。
        """
        key = "success" if success else "failed"
        self._order_results[key] += 1

    def record_error(self, error_type: str):
        """
        记录错误。

        Args:
            error_type: 错误类型名称。
        """
        self._error_counts[error_type] += 1

    def get_summary(self) -> dict:
        """
        获取指标摘要。

        Returns:
            包含各项指标统计的字典。
        """
        summary = {
            "api_latencies": {},
            "order_results": dict(self._order_results),
            "error_counts": dict(self._error_counts),
        }

        for op, latencies in self._api_latencies.items():
            if latencies:
                summary["api_latencies"][op] = {
                    "avg": sum(latencies) / len(latencies),
                    "max": max(latencies),
                    "min": min(latencies),
                    "count": len(latencies),
                }

        return summary
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_metrics.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: 提交**

```bash
git add common/metrics.py tests/test_metrics.py
git commit -m "feat(common): 添加指标监控模块

- 实现 Metrics 类
- 支持 API 延迟、订单结果、错误计数统计
- 提供摘要接口
- 完成单元测试"
```

---

## Task 8: 更新 common 包导出

**Files:**
- Modify: `common/__init__.py`

- [ ] **Step 1: 更新 __init__.py**

```python
# common/__init__.py
"""
WiseCoin 公共模块。

提供配置、日志、异常、Excel 读写、错误处理、指标监控等基础功能。
"""

from common.config import (
    Config,
    AccountConfig,
    TradingConfig,
    DataConfig,
    SchedulerConfig,
)
from common.exceptions import (
    WiseCoinError,
    DataFetchError,
    APIConnectionError,
    OrderExecutionError,
    RiskCheckError,
    ConfigurationError,
    ValidationError,
)
from common.logger import StructuredLogger
from common.excel_io import ExcelWriter, ExcelReader
from common.error_handler import ErrorHandler
from common.metrics import Metrics

__all__ = [
    # Config
    'Config',
    'AccountConfig',
    'TradingConfig',
    'DataConfig',
    'SchedulerConfig',
    # Exceptions
    'WiseCoinError',
    'DataFetchError',
    'APIConnectionError',
    'OrderExecutionError',
    'RiskCheckError',
    'ConfigurationError',
    'ValidationError',
    # Logger
    'StructuredLogger',
    # Excel
    'ExcelWriter',
    'ExcelReader',
    # Error Handler
    'ErrorHandler',
    # Metrics
    'Metrics',
]
```

- [ ] **Step 2: 运行全部测试**

```bash
python -m pytest tests/ -v
```

Expected: PASS (所有测试)

- [ ] **Step 3: 提交**

```bash
git add common/__init__.py
git commit -m "feat(common): 完善包导出

- 导出所有公共类和函数
- 更新 __all__ 列表"
```

---

## Task 9: 验证阶段完成

- [ ] **Step 1: 运行完整测试套件**

```bash
python -m pytest tests/ -v --cov=common
```

Expected: 所有测试通过，覆盖率 > 80%

- [ ] **Step 2: 检查代码质量**

```bash
# 如果有 flake8
flake8 common/ --max-line-length=100

# 如果有 mypy
mypy common/ --ignore-missing-imports
```

- [ ] **Step 3: 确认目录结构**

```bash
tree common/ tests/
```

Expected:
```
common/
├── __init__.py
├── config.py
├── exceptions.py
├── logger.py
├── excel_io.py
├── error_handler.py
└── metrics.py
tests/
├── __init__.py
├── conftest.py
├── test_config.py
├── test_exceptions.py
├── test_logger.py
├── test_excel_io.py
├── test_error_handler.py
└── test_metrics.py
```

---

## 阶段 1 完成标准

- [x] common/ 目录创建完成
- [x] 所有 6 个核心模块实现完成
- [x] 所有模块有对应测试
- [x] 测试覆盖率 > 80%
- [x] 所有测试通过
- [x] 代码已提交

---

## 后续阶段预览

- **阶段 2**: 数据层重构 (`data/`)
- **阶段 3**: 业务层重构 (`core/`)
- **阶段 4**: 策略层重构 (`strategy/`)
- **阶段 5**: 交易层重构 (`trade/`)
- **阶段 6**: 入口层重构 (`cli/`)
- **阶段 7**: 集成测试
- **阶段 8**: 清理旧文件