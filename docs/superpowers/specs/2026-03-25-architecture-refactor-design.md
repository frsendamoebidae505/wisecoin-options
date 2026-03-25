# WiseCoin 期权分析系统 - 架构重构设计文档

## 概述

将 WiseCoin 期权分析系统从扁平文件结构重构为分层架构，提高代码可维护性和可扩展性。

## 当前问题

- 28 个 Python 文件全部堆在根目录（扁平结构）
- 总代码量约 34,000 行
- 3 个超大文件（>5000行）承担过多职责
- 用数字前缀区分功能，缺乏模块化设计
- 代码重复（TqApi 初始化、Excel 读写等）
- 大量使用 asyncio 但缺乏统一的异步架构
- 缺乏统一的错误处理机制

## 目标架构

```
wisecoin-options-free/
├── data/                    # 数据层
│   ├── __init__.py
│   ├── tqsdk_client.py      # TqSDK 统一客户端封装
│   ├── option_quotes.py     # 期权行情获取
│   ├── futures_quotes.py    # 期货行情获取
│   ├── klines.py            # K线数据获取
│   ├── openctp.py           # OpenCTP 数据源
│   ├── cache.py             # 行情缓存
│   └── backup.py            # 数据备份与清理
├── core/                    # 业务层
│   ├── __init__.py
│   ├── models.py            # 数据模型定义
│   ├── analyzer.py          # 期权分析器
│   ├── iv_calculator.py     # IV 计算器
│   └── futures_analyzer.py  # 期货分析器
├── strategy/                # 策略层
│   ├── __init__.py
│   ├── evaluator.py         # 策略评估器
│   ├── arbitrage.py         # 套利扫描器
│   └── signals.py           # 信号生成器
├── trade/                   # 交易层
│   ├── __init__.py
│   ├── position.py          # 持仓管理器
│   ├── position_mock.py      # 模拟持仓管理器
│   ├── executor.py          # 订单执行器
│   └── risk.py              # 风控检查器
├── cli/                     # 入口层
│   ├── __init__.py
│   ├── oneclick.py          # 一键执行
│   ├── scheduler.py         # 定时调度
│   ├── live.py              # 实时监控
│   └── commands.py          # CLI 命令
├── common/                  # 公共模块
│   ├── __init__.py
│   ├── config.py            # 配置管理
│   ├── logger.py            # 日志系统
│   ├── excel_io.py          # Excel 读写
│   ├── utils.py             # 工具函数
│   ├── exceptions.py        # 统一异常定义
│   ├── error_handler.py     # 错误处理器
│   ├── container.py         # 依赖注入容器
│   └── metrics.py           # 指标监控
├── tests/                   # 测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_iv_calculator.py
│   ├── test_analyzer.py
│   ├── test_arbitrage.py
│   ├── test_executor.py
│   └── fixtures/
│       ├── option_quotes.json
│       └── futures_quotes.json
├── docs/                    # 文档
├── main.py                  # 统一入口
└── pyproject.toml           # 项目配置
```

---

## 层间职责边界

### 业务层 vs 策略层

**问题：** `AnalyzedOption.score` 的归属不清晰，容易导致评分逻辑分散。

**解决方案：**

```python
# core/analyzer.py - 只负责数据清洗和基础指标
class OptionAnalyzer:
    """
    期权分析器 - 业务层

    职责：
    - 数据清洗和验证
    - 计算基础指标（ITM/OTM、杠杆率、时间价值等）
    - 不涉及评分和交易决策
    """

    def analyze(self, quotes: List[OptionQuote],
                futures_quotes: Dict[str, float]) -> List[AnalyzedOption]:
        """
        分析期权数据，计算基础指标。

        Args:
            quotes: 期权行情列表
            futures_quotes: 标的期货价格映射

        Returns:
            AnalyzedOption 列表，包含基础指标，score 默认为 0
        """
        results = []
        for quote in quotes:
            # 计算基础指标
            is_itm = quote.is_itm(futures_quotes.get(quote.underlying, 0))
            leverage = self._calculate_leverage(quote, futures_quotes)
            time_value = self._calculate_time_value(quote)

            results.append(AnalyzedOption(
                option=quote,
                iv=None,  # 后续由 IVCalculator 填充
                score=0.0,  # 由 StrategyEvaluator 填充
                signal=Signal.HOLD,
                reasons=[
                    f"{'实值' if is_itm else '虚值'}",
                    f"杠杆率: {leverage:.2f}",
                    f"时间价值: {time_value:.2f}",
                ]
            ))
        return results


# strategy/evaluator.py - 负责评分和排序
class StrategyEvaluator:
    """
    策略评估器 - 策略层

    职责：
    - 多因子评分
    - 市场环境加权
    - 机会排序
    - 生成交易信号
    """

    def evaluate(self, analyzed: List[AnalyzedOption],
                 market_context: MarketContext) -> List[ScoredOption]:
        """
        对分析结果进行评分和排序。

        Args:
            analyzed: 分析后的期权列表（来自 OptionAnalyzer）
            market_context: 市场环境上下文

        Returns:
            ScoredOption 列表，按评分降序排列
        """
        results = []
        for opt in analyzed:
            score = self._calculate_score(opt, market_context)
            signal = self._determine_signal(score, opt, market_context)
            results.append(ScoredOption(
                analyzed_option=opt,
                score=score,
                signal=signal,
            ))
        return sorted(results, key=lambda x: x.score, reverse=True)
```

**数据流向：**

```
OptionQuote → OptionAnalyzer → AnalyzedOption (基础指标)
                                          ↓
                              StrategyEvaluator → ScoredOption (评分+信号)
                                          ↓
                                 SignalGenerator → StrategySignal
```

---

## 大文件拆分映射表

| 原文件 | 行数 | 拆分到新模块 | 保留/废弃 |
|--------|------|--------------|-----------|
| `03wisecoin-options-analyze.py` | ~1177 | `core/analyzer.py` + `strategy/evaluator.py` | 废弃 |
| `04wisecoin-options-iv.py` | ~1545 | `core/iv_calculator.py` | 废弃 |
| `05wisecoin-futures-analyze.py` | ~1622 | `core/futures_analyzer.py` | 废弃 |
| `19wisecoin_options_client_strategy.py` | ~4796 | `strategy/evaluator.py` + `strategy/signals.py` | 废弃 |
| `19wisecoin_options_client_arbitrage.py` | ~1463 | `strategy/arbitrage.py` | 废弃 |
| `01wisecoin-options-ranking.py` | ~885 | `data/option_quotes.py` + `data/futures_quotes.py` | 废弃 |
| `02wisecoin-openctp-api.py` | ~530 | `data/openctp.py` | 废弃 |
| `09wisecoin-futures-klines.py` | ~328 | `data/klines.py` | 废弃 |
| `10wisecoin_options_client.py` | ~1888 | `data/option_quotes.py` + `trade/executor.py` | 废弃 |
| `14wisecoin_options_client_data.py` | ~747 | `data/option_quotes.py` + `data/futures_quotes.py` | 废弃 |
| `14wisecoin_options_client_data_klines.py` | ~332 | `data/klines.py` | 废弃 |
| `15wisecoin_options_client_analyze_options.py` | ~1183 | `core/analyzer.py` | 废弃 |
| `16wisecoin_options_client_iv.py` | ~1550 | `core/iv_calculator.py` | 废弃 |
| `17wisecoin_options_client_analyze_futures.py` | ~1627 | `core/futures_analyzer.py` | 废弃 |
| `18wisecoin_options_client_live.py` | ~2017 | `cli/live.py` | 废弃 |
| `06wisecoin_oneclick.py` | ~300 | `cli/oneclick.py` | 废弃 |
| `07wisecoin_run.py` | ~302 | `cli/scheduler.py` | 废弃 |
| `08wisecoin_symbol_lsn.py` | ~100 | `strategy/signals.py` | 废弃 |
| `00wisecoin_options_backup.py` | ~100 | `data/backup.py` | 废弃 |
| `00wisecoin_options_backup_clean.py` | ~80 | `data/backup.py` | 废弃 |
| `31wisecoin_options_position_deal_taget.py` | ~100 | `trade/position.py` | 废弃 |
| `32wisecoin_options_position_deal_1sell.py` | ~200 | `trade/executor.py` | 废弃 |
| `33wisecoin_options_position_deal_2buy.py` | ~200 | `trade/executor.py` | 废弃 |
| `41wisecoin_options_position.py` | ~150 | `trade/position.py` | 废弃 |
| `42wisecoin_options_position_client.py` | ~5230 | `trade/position.py` + `trade/executor.py` | 废弃 |
| `51wisecoin_options_position_mock.py` | ~382 | `trade/position_mock.py` | 废弃 |
| `52wisecoin_options_position_client_mock.py` | ~5294 | `trade/position_mock.py` | 废弃 |

**说明：**
- 所有原文件重构后移入 `legacy/` 目录保留备份
- 新模块按职责单一原则组织，每个文件不超过 500 行

---

## 文档字符串规范

所有公共函数和类必须遵循 Google 风格文档字符串：

```python
def calculate_iv(self, option: OptionQuote,
                 future_price: float,
                 risk_free_rate: float = 0.03) -> float:
    """
    计算期权隐含波动率。

    使用 Black-Scholes 模型反推隐含波动率。

    Args:
        option: 期权行情对象，包含价格和行权价信息。
        future_price: 标的期货当前价格。
        risk_free_rate: 无风险利率（年化），默认 3%。

    Returns:
        隐含波动率（年化百分比）。如果无法计算则返回 None。

    Raises:
        ValueError: 当 future_price <= 0 或 option.last_price <= 0 时。

    Example:
        >>> calculator = IVCalculator()
        >>> option = OptionQuote(
        ...     symbol="SHFE.au2406C480",
        ...     strike_price=480.0,
        ...     last_price=15.0,
        ...     ...
        ... )
        >>> iv = calculator.calculate_iv(option, 490.0)
        >>> print(f"IV: {iv:.2%}")
        IV: 18.50%

    Note:
        - 深度虚值期权的 IV 计算可能不稳定
        - 建议先检查 option.is_itm() 判断期权状态
    """
    pass


class OptionAnalyzer:
    """
    期权分析器。

    对期权数据进行基础分析，计算各种指标，不涉及交易决策。

    Attributes:
        config: 分析配置参数。

    Example:
        >>> analyzer = OptionAnalyzer(config)
        >>> results = analyzer.analyze(quotes, futures_prices)
        >>> for r in results[:5]:
        ...     print(f"{r.option.symbol}: {r.reasons}")
    """

    def __init__(self, config: dict = None):
        """
        初始化期权分析器。

        Args:
            config: 可选配置字典，包含分析参数。
        """
        pass
```

**文档字符串检查清单：**
- [ ] 函数目的描述（首句）
- [ ] Args 参数说明
- [ ] Returns 返回值说明
- [ ] Raises 异常说明（如有）
- [ ] Example 使用示例（复杂函数）
- [ ] Note 注意事项（如有）

---

## 异步处理策略

### 设计原则

1. **数据层：全异步** - TqSDK 本身是异步的，数据层必须使用 async/await
2. **业务层：同步为主** - 纯计算逻辑不需要异步，保持简单
3. **交易层：全异步** - 订单执行需要等待回报，必须异步
4. **入口层：异步入口** - 调度异步任务

### 数据层异步设计

```python
# data/tqsdk_client.py
class TqSdkClient:
    """TqSDK 客户端 - 异步上下文管理"""

    def __init__(self, run_mode: int = 2):
        self.run_mode = run_mode
        self._api: Optional[TqApi] = None

    async def __aenter__(self) -> 'TqSdkClient':
        """进入异步上下文，初始化 API"""
        self._api = await self._create_api()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出时关闭连接"""
        if self._api:
            self._api.close()
            self._api = None

    @property
    def api(self) -> TqApi:
        """获取当前 API 实例"""
        if not self._api:
            raise APIConnectionError("API 未初始化，请使用 async with")
        return self._api

    async def rebuild_api(self) -> TqApi:
        """重建 API 连接（防止超时）"""
        if self._api:
            self._api.close()
        self._api = await self._create_api()
        return self._api


# data/option_quotes.py
class OptionQuoteFetcher:
    """期权行情获取器 - 异步"""

    def __init__(self, client: TqSdkClient):
        self.client = client

    async def get_option_symbols(self, exchanges: List[str] = None) -> pd.DataFrame:
        """获取期权合约列表"""
        api = self.client.api
        # ... 异步获取逻辑

    async def get_option_quotes(self, symbols: List[str],
                                 batch_size: int = 200,
                                 max_concurrent: int = 5) -> Dict:
        """批量获取期权行情，并发控制"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_batch(batch):
            async with semaphore:
                return await self._fetch_batch(batch)

        tasks = [fetch_batch(symbols[i:i+batch_size])
                 for i in range(0, len(symbols), batch_size)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._merge_results(results)
```

### 业务层同步设计

```python
# core/analyzer.py
class OptionAnalyzer:
    """期权分析器 - 同步，纯计算"""

    def analyze(self, quotes: List[OptionQuote],
                futures_quotes: Dict[str, float]) -> List[AnalyzedOption]:
        """执行多因子分析 - 纯计算，无需异步"""
        results = []
        for quote in quotes:
            score = self._calculate_score(quote, futures_quotes)
            signal = self._determine_signal(score)
            results.append(AnalyzedOption(
                option=quote,
                iv=None,  # 后续由 IVCalculator 填充
                score=score,
                signal=signal
            ))
        return results
```

### 异步调用示例

```python
# cli/oneclick.py
async def run_analysis():
    """一键分析流程"""
    async with TqSdkClient(run_mode=2) as client:
        # 数据层：异步获取
        fetcher = OptionQuoteFetcher(client)
        symbols = await fetcher.get_option_symbols()
        quotes = await fetcher.get_option_quotes(symbols)

        # 业务层：同步计算
        analyzer = OptionAnalyzer()
        results = analyzer.analyze(quotes, futures_prices)

        # 输出
        return results
```

---

## 错误处理策略

### 异常层次结构

```python
# common/exceptions.py
class WiseCoinError(Exception):
    """基础异常"""
    def __init__(self, message: str, retryable: bool = False):
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class DataFetchError(WiseCoinError):
    """数据获取失败"""
    pass


class APIConnectionError(WiseCoinError):
    """API 连接失败"""
    def __init__(self, message: str):
        super().__init__(message, retryable=True)


class OrderExecutionError(WiseCoinError):
    """订单执行失败"""
    pass


class RiskCheckError(WiseCoinError):
    """风控检查失败"""
    pass


class ConfigurationError(WiseCoinError):
    """配置错误"""
    pass


class ValidationError(WiseCoinError):
    """数据验证失败"""
    pass
```

### 错误处理器

```python
# common/error_handler.py
import asyncio
from typing import Callable, TypeVar

T = TypeVar('T')


class ErrorHandler:
    """统一错误处理器"""

    def __init__(self, logger: 'StructuredLogger'):
        self.logger = logger
        self._retry_config = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 30.0,
        }

    async def with_retry(self, func: Callable[..., T],
                         *args,
                         exceptions: tuple = (APIConnectionError,),
                         **kwargs) -> T:
        """带重试的执行"""
        last_error = None
        for attempt in range(self._retry_config['max_retries']):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                last_error = e
                delay = min(
                    self._retry_config['base_delay'] * (2 ** attempt),
                    self._retry_config['max_delay']
                )
                self.logger.warning(
                    f"操作失败，{delay}秒后重试 ({attempt + 1}/{self._retry_config['max_retries']})",
                    error=str(e)
                )
                await asyncio.sleep(delay)
        raise last_error

    def handle_trade_error(self, error: OrderExecutionError):
        """处理交易错误 - 关键操作"""
        self.logger.error(
            "订单执行失败",
            symbol=error.symbol if hasattr(error, 'symbol') else None,
            error=error.message
        )
        # 交易错误需要通知用户
        self._notify_user(error)

    def handle_data_error(self, error: DataFetchError) -> bool:
        """处理数据错误，返回是否可继续"""
        if error.retryable:
            self.logger.warning(f"数据获取失败，可重试: {error.message}")
            return True
        self.logger.error(f"数据获取失败: {error.message}")
        return False

    def _notify_user(self, error: WiseCoinError):
        """通知用户（预留接口）"""
        # TODO: 接入通知渠道（钉钉/微信/邮件）
        pass
```

### 各层错误处理规范

| 层级 | 错误类型 | 处理方式 |
|------|----------|----------|
| 数据层 | `APIConnectionError` | 自动重试 + 日志 |
| 数据层 | `DataFetchError` | 记录日志 + 通知用户 |
| 业务层 | `ValidationError` | 记录日志 + 跳过无效数据 |
| 交易层 | `OrderExecutionError` | 记录日志 + 通知用户 + 暂停交易 |
| 入口层 | 所有异常 | 捕获 + 汇总 + 优雅退出 |

---

## 各层详细设计

### 1. 数据层 (data/)

**职责：** 封装所有外部数据源的访问，提供统一的数据获取接口。

| 模块 | 职责 | 来源文件 |
|------|------|----------|
| `tqsdk_client.py` | TqSDK 客户端生命周期管理、运行模式切换 | 多文件重复代码提取 |
| `option_quotes.py` | 期权合约列表、期权行情获取 | 01, 10, 14 系列文件 |
| `futures_quotes.py` | 标的期货、非标的期货行情获取 | 01, 05, 14 系列文件 |
| `klines.py` | 期货 K 线数据获取 | 09, 14_klines |
| `openctp.py` | OpenCTP 数据源适配 | 02 文件 |
| `cache.py` | 行情缓存，减少重复请求 | 新增 |
| `backup.py` | 数据备份与清理 | 00 系列 |

**缓存设计：**

```python
# data/cache.py
from typing import Optional, Any, Dict, Tuple
import time

class QuoteCache:
    """行情缓存"""

    def __init__(self, ttl_seconds: int = 60):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def get(self, symbol: str) -> Optional[Any]:
        if symbol in self._cache:
            data, timestamp = self._cache[symbol]
            if time.time() - timestamp < self._ttl:
                return data
            else:
                del self._cache[symbol]
        return None

    def set(self, symbol: str, data: Any):
        self._cache[symbol] = (data, time.time())

    def clear(self):
        self._cache.clear()
```

### 2. 业务层 (core/)

**职责：** 核心计算逻辑，不依赖具体数据源，接收数据返回分析结果。

| 模块 | 职责 | 来源文件 |
|------|------|----------|
| `models.py` | 数据模型定义（Option, Future, Position 等） | 各文件散落的 dataclass |
| `analyzer.py` | 期权多因子分析、评分筛选 | 03, 15 系列 |
| `iv_calculator.py` | 隐含波动率计算、波动率微笑 | 04, 16 系列 |
| `futures_analyzer.py` | 期货技术分析、趋势判断 | 05, 17 系列 |

**完整数据模型：**

```python
# core/models.py
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class CallOrPut(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class OptionQuote:
    """期权行情模型"""
    symbol: str
    underlying: str
    exchange_id: str
    strike_price: float
    call_or_put: CallOrPut
    last_price: float
    bid_price: float
    ask_price: float
    volume: int
    open_interest: int
    expire_date: date
    instrument_name: str = ""
    margin: float = 0.0
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    iv: Optional[float] = None

    def is_itm(self, underlying_price: float) -> bool:
        """判断是否实值"""
        if self.call_or_put == CallOrPut.CALL:
            return underlying_price > self.strike_price
        else:
            return underlying_price < self.strike_price

    def time_to_expiry(self, as_of: date = None) -> float:
        """计算剩余时间（年）"""
        as_of = as_of or date.today()
        days = (self.expire_date - as_of).days
        return max(days / 365.0, 0)


@dataclass
class FutureQuote:
    """期货行情模型"""
    symbol: str
    exchange_id: str
    last_price: float
    bid_price: float
    ask_price: float
    volume: int
    open_interest: int
    high: float
    low: float
    pre_close: float


@dataclass
class Position:
    """持仓模型"""
    symbol: str
    exchange_id: str
    direction: str  # LONG / SHORT
    volume: int
    avg_price: float
    current_price: float
    unrealized_pnl: float
    margin: float
    volume_today: int = 0  # 今仓

    def market_value(self) -> float:
        """市值"""
        return self.current_price * self.volume


@dataclass
class AnalyzedOption:
    """分析后的期权"""
    option: OptionQuote
    iv: Optional[float]
    score: float
    signal: Signal
    reasons: List[str] = field(default_factory=list)


@dataclass
class StrategySignal:
    """策略信号"""
    symbol: str
    direction: str  # BUY / SELL
    volume: int
    price: Optional[float]
    score: float
    strategy_type: str
    reasons: List[str] = field(default_factory=list)


@dataclass
class ArbitrageOpportunity:
    """套利机会"""
    opportunity_type: str  # CONVERSION, STRADDLE, CALENDAR
    legs: List[dict]  # 各腿合约信息
    expected_profit: float
    risk_level: str
    confidence: float
```

### 3. 策略层 (strategy/)

**职责：** 基于分析结果生成交易策略和套利机会。

| 模块 | 职责 | 来源文件 |
|------|------|----------|
| `evaluator.py` | 策略评分、机会排序 | 19_strategy 核心逻辑 |
| `arbitrage.py` | 套利机会识别（时间价值、跨式等） | 19_arbitrage |
| `signals.py` | 交易信号生成、开仓方向判断 | 08, 19 |

### 4. 交易层 (trade/)

**职责：** 持仓管理、订单执行、风控。

| 模块 | 职责 | 来源文件 |
|------|------|----------|
| `position.py` | 真实持仓查询、目标管理、止盈止损 | 31-42 系列 |
| `position_mock.py` | 模拟持仓管理、回测支持 | 51-52 系列 |
| `executor.py` | 订单执行、盘口吃单 | 10_eat, 32, 33 |
| `risk.py` | 风控检查 | 新增 |

**持仓管理器设计：**

```python
# trade/position.py
from abc import ABC, abstractmethod
from typing import List, Optional

class BasePositionManager(ABC):
    """持仓管理器基类"""

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """获取当前持仓"""
        pass

    @abstractmethod
    def set_target(self, symbol: str, target_price: float,
                   stop_loss: float = None, take_profit: float = None):
        """设置持仓目标"""
        pass

    @abstractmethod
    def check_targets(self) -> List[TargetHit]:
        """检查是否有持仓触及目标"""
        pass


class PositionManager(BasePositionManager):
    """
    真实持仓管理器。

    通过 TqSDK 获取实盘或模拟账户持仓。

    Attributes:
        client: TqSDK 客户端实例。
    """

    def __init__(self, client: TqSdkClient):
        self.client = client

    def get_positions(self) -> List[Position]:
        """获取当前账户所有持仓。"""
        api = self.client.api
        position_data = api.get_position()
        return self._parse_positions(position_data)

    def set_target(self, symbol: str, target_price: float,
                   stop_loss: float = None, take_profit: float = None):
        """设置持仓目标价格。"""
        # 保存到配置文件或数据库
        pass

    def check_targets(self) -> List[TargetHit]:
        """检查持仓是否触及目标。"""
        positions = self.get_positions()
        hits = []
        for pos in positions:
            target = self._get_target(pos.symbol)
            if target and self._is_hit(pos, target):
                hits.append(TargetHit(
                    symbol=pos.symbol,
                    position=pos,
                    target=target,
                    hit_type='STOP_LOSS' if target.stop_loss else 'TAKE_PROFIT'
                ))
        return hits
```

**模拟持仓管理器设计：**

```python
# trade/position_mock.py
import json
from datetime import datetime
from typing import Dict, List, Optional

class MockPositionManager(BasePositionManager):
    """
    模拟持仓管理器。

    用于策略回测和模拟交易，不依赖真实账户。

    Attributes:
        positions: 模拟持仓字典。
        initial_capital: 初始资金。
        current_capital: 当前资金。
    """

    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, MockPosition] = {}
        self.trade_history: List[dict] = []

    def get_positions(self) -> List[Position]:
        """获取所有模拟持仓。"""
        return list(self.positions.values())

    def open_position(self, symbol: str, direction: str,
                      volume: int, price: float,
                      timestamp: datetime = None) -> bool:
        """
        开仓。

        Args:
            symbol: 合约代码
            direction: 方向 (LONG/SHORT)
            volume: 数量
            price: 开仓价格
            timestamp: 时间戳

        Returns:
            是否成功开仓
        """
        margin = self._calculate_margin(symbol, volume, price)
        if margin > self.current_capital:
            return False

        self.current_capital -= margin
        self.positions[symbol] = MockPosition(
            symbol=symbol,
            direction=direction,
            volume=volume,
            avg_price=price,
            margin=margin,
            open_time=timestamp or datetime.now(),
        )

        self.trade_history.append({
            'action': 'OPEN',
            'symbol': symbol,
            'direction': direction,
            'volume': volume,
            'price': price,
            'timestamp': timestamp or datetime.now(),
        })
        return True

    def close_position(self, symbol: str, volume: int,
                       price: float, timestamp: datetime = None) -> Optional[float]:
        """
        平仓。

        Args:
            symbol: 合约代码
            volume: 平仓数量
            price: 平仓价格
            timestamp: 时间戳

        Returns:
            平仓盈亏，如果失败返回 None
        """
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        if volume > pos.volume:
            volume = pos.volume

        pnl = self._calculate_pnl(pos, volume, price)
        self.current_capital += pos.margin * (volume / pos.volume) + pnl

        if volume == pos.volume:
            del self.positions[symbol]
        else:
            pos.volume -= volume
            pos.margin *= (pos.volume / (pos.volume + volume))

        self.trade_history.append({
            'action': 'CLOSE',
            'symbol': symbol,
            'volume': volume,
            'price': price,
            'pnl': pnl,
            'timestamp': timestamp or datetime.now(),
        })
        return pnl

    def update_prices(self, prices: Dict[str, float]):
        """
        更新持仓市值。

        Args:
            prices: 合约价格映射 {symbol: price}
        """
        for symbol, pos in self.positions.items():
            if symbol in prices:
                pos.current_price = prices[symbol]
                pos.unrealized_pnl = self._calculate_unrealized_pnl(pos)

    def get_statistics(self) -> dict:
        """
        获取模拟交易统计。

        Returns:
            包含总盈亏、胜率、最大回撤等统计信息
        """
        closed_trades = [t for t in self.trade_history if t['action'] == 'CLOSE']
        total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
        win_trades = [t for t in closed_trades if t.get('pnl', 0) > 0]

        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'total_pnl': total_pnl,
            'total_return': (self.current_capital - self.initial_capital) / self.initial_capital,
            'total_trades': len(closed_trades),
            'win_trades': len(win_trades),
            'win_rate': len(win_trades) / len(closed_trades) if closed_trades else 0,
            'position_count': len(self.positions),
        }

    def save_state(self, filepath: str):
        """保存模拟持仓状态到文件。"""
        state = {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'positions': {k: v.__dict__ for k, v in self.positions.items()},
            'trade_history': self.trade_history,
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)

    def load_state(self, filepath: str):
        """从文件加载模拟持仓状态。"""
        with open(filepath, 'r', encoding='utf-8') as f:
            state = json.load(f)
        self.initial_capital = state['initial_capital']
        self.current_capital = state['current_capital']
        self.positions = {k: MockPosition(**v) for k, v in state['positions'].items()}
        self.trade_history = state['trade_history']


@dataclass
class MockPosition:
    """模拟持仓"""
    symbol: str
    direction: str
    volume: int
    avg_price: float
    margin: float
    open_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
```

**风控设计：**

```python
# trade/risk.py
from typing import Tuple

class RiskChecker:
    """风控检查器"""

    def __init__(self, config: 'TradingConfig'):
        self.config = config
        self._daily_pnl = 0.0
        self._positions = {}

    def check_position_limit(self, symbol: str, volume: int,
                              current_position: int) -> bool:
        """检查持仓限制"""
        new_position = current_position + volume
        return new_position <= self.config.max_position_per_symbol

    def check_margin_usage(self, required_margin: float,
                            available_margin: float) -> bool:
        """检查保证金占用"""
        usage = required_margin / available_margin
        return usage <= self.config.max_margin_usage

    def check_daily_loss_limit(self, initial_capital: float) -> Tuple[bool, float]:
        """检查日内亏损限制"""
        loss_ratio = abs(self._daily_pnl) / initial_capital
        return loss_ratio < 0.05, loss_ratio  # 默认 5% 止损线

    def check_order_validity(self, order: 'Order') -> Tuple[bool, str]:
        """检查订单有效性"""
        if order.volume <= 0:
            return False, "下单数量必须大于0"
        if order.price and order.price <= 0:
            return False, "下单价格必须大于0"
        return True, ""

    def update_daily_pnl(self, pnl: float):
        """更新日内盈亏"""
        self._daily_pnl += pnl
```

### 5. 入口层 (cli/)

**职责：** 命令行入口、任务编排、调度执行。

| 模块 | 职责 | 来源文件 |
|------|------|----------|
| `oneclick.py` | 一键执行完整流程 | 06 |
| `scheduler.py` | 定时调度系统 | 07 |
| `live.py` | 实时监控循环 | 18 |
| `commands.py` | CLI 命令定义 | 新增 |

### 6. 公共模块 (common/)

**职责：** 配置管理、日志、Excel 读写、工具函数、错误处理、依赖注入。

| 模块 | 职责 | 来源文件 |
|------|------|----------|
| `config.py` | 运行模式、账户配置、参数管理 | 各文件散落的 RUN_MODE 等 |
| `logger.py` | 统一日志系统 | UnifiedLogger |
| `excel_io.py` | Excel 读写封装 | 各文件重复的 pandas Excel 操作 |
| `utils.py` | 通用工具函数 | 散落的各种辅助函数 |
| `exceptions.py` | 统一异常定义 | 新增 |
| `error_handler.py` | 错误处理 | 新增 |
| `container.py` | 依赖注入容器 | 新增 |
| `metrics.py` | 指标监控 | 新增 |

**配置管理：**

```python
# common/config.py
from dataclasses import dataclass, field
from typing import Optional, List
import os
import json

@dataclass
class AccountConfig:
    """账户配置"""
    broker: str
    account: str
    password: str  # 实际使用时应从环境变量读取


@dataclass
class TradingConfig:
    """交易配置"""
    max_position_per_symbol: int = 10
    max_margin_usage: float = 0.8
    default_order_volume: int = 1
    daily_loss_limit: float = 0.05


@dataclass
class DataConfig:
    """数据配置"""
    quote_batch_size: int = 200
    save_interval: int = 3000
    api_rebuild_interval: int = 3000
    kline_data_length: int = 250
    cache_ttl_seconds: int = 60


@dataclass
class SchedulerConfig:
    """调度配置"""
    scheduled_times: List[tuple] = field(default_factory=lambda: [
        (20, 40), (21, 40), (22, 40), (23, 40), (0, 40), (1, 40),
        (8, 40), (9, 40), (10, 40), (12, 40), (13, 40), (14, 40), (15, 16)
    ])
    check_interval: int = 30
    cooldown_minutes: int = 5


class Config:
    """全局配置"""

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

    def __init__(self, run_mode: int = 2, config_path: str = None):
        self.run_mode = run_mode
        self.trading = TradingConfig()
        self.data = DataConfig()
        self.scheduler = SchedulerConfig()
        self._accounts: dict = {}

        if config_path:
            self._load_from_file(config_path)
        self._load_accounts()

    def _load_from_file(self, path: str):
        """从 JSON 文件加载配置"""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 更新配置
                if 'trading' in data:
                    self.trading = TradingConfig(**data['trading'])
                if 'data' in data:
                    self.data = DataConfig(**data['data'])

    def _load_accounts(self):
        """从环境变量或配置文件加载账户信息"""
        # 优先从环境变量读取敏感信息
        for mode, name in self.RUN_MODES.items():
            broker = os.getenv(f'TQ_BROKER_{mode}')
            account = os.getenv(f'TQ_ACCOUNT_{mode}')
            password = os.getenv(f'TQ_PASSWORD_{mode}')
            if broker and account and password:
                self._accounts[mode] = AccountConfig(broker, account, password)

    def get_account(self) -> Optional[AccountConfig]:
        """获取当前模式的账户配置"""
        return self._accounts.get(self.run_mode)
```

**日志系统：**

```python
# common/logger.py
import logging
import structlog
from typing import Optional


class StructuredLogger:
    """结构化日志"""

    def __init__(self, name: str, log_file: Optional[str] = None):
        self.logger = structlog.get_logger(name)
        self._setup_handlers(log_file)

    def _setup_handlers(self, log_file: Optional[str]):
        """配置日志处理器"""
        # 配置 structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )

    def info(self, message: str, **kwargs):
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        self.logger.error(message, **kwargs)

    def debug(self, message: str, **kwargs):
        self.logger.debug(message, **kwargs)

    def log_trade(self, symbol: str, action: str, price: float,
                  volume: int, result: str):
        """交易日志 - 关键操作"""
        self.logger.info("trade_executed",
                        symbol=symbol, action=action,
                        price=price, volume=volume, result=result)

    def log_api_event(self, event: str, duration_ms: float = None):
        """API 事件日志"""
        self.logger.info("api_event", event=event, duration_ms=duration_ms)
```

**依赖注入：**

```python
# common/container.py
from dependency_injector import containers, providers
from data.tqsdk_client import TqSdkClient
from data.option_quotes import OptionQuoteFetcher
from core.analyzer import OptionAnalyzer
from trade.executor import OrderExecutor
from trade.risk import RiskChecker
from common.config import Config
from common.logger import StructuredLogger
from common.error_handler import ErrorHandler


class Container(containers.DeclarativeContainer):
    """依赖注入容器"""

    config = providers.Configuration()

    # 配置
    app_config = providers.Singleton(Config, run_mode=config.run_mode)

    # 日志
    logger = providers.Singleton(StructuredLogger, name="wisecoin")

    # 错误处理
    error_handler = providers.Singleton(ErrorHandler, logger=logger)

    # 数据层
    tq_client = providers.Singleton(
        TqSdkClient,
        run_mode=config.run_mode
    )

    option_fetcher = providers.Factory(
        OptionQuoteFetcher,
        client=tq_client
    )

    # 业务层
    analyzer = providers.Factory(OptionAnalyzer)

    # 交易层
    risk_checker = providers.Factory(
        RiskChecker,
        config=providers.Factory(lambda c: c.trading, c=app_config)
    )

    executor = providers.Factory(
        OrderExecutor,
        client=tq_client,
        risk_checker=risk_checker
    )
```

**指标监控：**

```python
# common/metrics.py
from typing import Dict, List
from collections import defaultdict
import time


class Metrics:
    """关键指标收集"""

    def __init__(self):
        self._api_latencies: Dict[str, List[float]] = defaultdict(list)
        self._order_results: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)

    def record_api_latency(self, operation: str, latency_ms: float):
        """记录 API 延迟"""
        self._api_latencies[operation].append(latency_ms)

    def record_order_result(self, success: bool):
        """记录订单结果"""
        key = "success" if success else "failed"
        self._order_results[key] += 1

    def record_error(self, error_type: str):
        """记录错误"""
        self._error_counts[error_type] += 1

    def get_summary(self) -> dict:
        """获取指标摘要"""
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
                    "count": len(latencies),
                }

        return summary
```

---

## 测试策略

### 测试矩阵

| 模块 | 测试类型 | 测试场景 | 优先级 |
|------|----------|----------|--------|
| `iv_calculator.py` | 单元测试 | 平值期权 IV 计算 | 高 |
| `iv_calculator.py` | 单元测试 | 深度虚值边界处理 | 高 |
| `iv_calculator.py` | 单元测试 | 无效价格输入处理 | 高 |
| `analyzer.py` | 单元测试 | 多因子评分逻辑 | 高 |
| `analyzer.py` | 集成测试 | 完整分析流程 | 中 |
| `executor.py` | 单元测试 | 上期所平今逻辑 | 高 |
| `executor.py` | 集成测试 | 模拟下单流程 | 中 |
| `arbitrage.py` | 单元测试 | 转换套利识别 | 中 |
| `tqsdk_client.py` | 集成测试 | API 重建逻辑 | 高 |

### Mock 策略

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json

@pytest.fixture
def mock_tqapi():
    """模拟 TqApi，不依赖真实连接"""
    with patch('tqsdk.TqApi') as mock:
        mock_instance = Mock()
        mock_instance.get_quote = Mock(return_value={
            'last_price': 100.0,
            'bid_price1': 99.0,
            'ask_price1': 101.0,
        })
        mock_instance.query_quotes = Mock(return_value=[])
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_option_quotes():
    """测试用期权行情数据"""
    with open('tests/fixtures/option_quotes.json') as f:
        return json.load(f)


@pytest.fixture
def sample_futures_quotes():
    """测试用期货行情数据"""
    with open('tests/fixtures/futures_quotes.json') as f:
        return json.load(f)


@pytest.fixture
def config():
    """测试配置"""
    from common.config import Config
    return Config(run_mode=2)
```

### 示例测试

```python
# tests/test_iv_calculator.py
import pytest
from core.iv_calculator import IVCalculator
from core.models import OptionQuote, CallOrPut
from datetime import date


class TestIVCalculator:

    @pytest.fixture
    def calculator(self):
        return IVCalculator()

    @pytest.fixture
    def atm_call(self):
        """平值看涨期权"""
        return OptionQuote(
            symbol="SHFE.au2406C480",
            underlying="SHFE.au2406",
            exchange_id="SHFE",
            strike_price=480.0,
            call_or_put=CallOrPut.CALL,
            last_price=10.0,
            bid_price=9.8,
            ask_price=10.2,
            volume=100,
            open_interest=500,
            expire_date=date(2024, 6, 15),
        )

    def test_atm_call_iv(self, calculator, atm_call):
        """测试平值看涨期权 IV 计算"""
        future_price = 480.0  # 标的价格等于行权价
        iv = calculator.calculate_iv(atm_call, future_price)
        assert iv is not None
        assert 0 < iv < 1  # IV 应在合理范围内

    def test_deep_otm_iv(self, calculator, atm_call):
        """测试深度虚值期权 IV 计算"""
        future_price = 600.0  # 标的价格远高于行权价
        iv = calculator.calculate_iv(atm_call, future_price)
        # 深度虚值期权 IV 可能不稳定
        assert iv is None or iv >= 0

    def test_invalid_price(self, calculator, atm_call):
        """测试无效价格输入"""
        with pytest.raises(ValueError):
            calculator.calculate_iv(atm_call, -100.0)
```

---

## 迁移策略

### 阶段 1：创建新目录结构，提取公共模块

```
任务清单：
□ 1.1 创建目录结构
    □ 1.1.1 创建 common/, data/, core/, strategy/, trade/, cli/ 目录
    □ 1.1.2 创建各目录 __init__.py 文件
    □ 1.1.3 添加 pyproject.toml

□ 1.2 提取 common/config.py
    □ 1.2.1 整理各文件中的 RUN_MODE 定义
    □ 1.2.2 整理账户配置（脱敏处理，使用环境变量）
    □ 1.2.3 创建 Config, TradingConfig, DataConfig, SchedulerConfig 类
    □ 1.2.4 编写单元测试

□ 1.3 提取 common/exceptions.py
    □ 1.3.1 定义异常层次结构
    □ 1.3.2 编写单元测试

□ 1.4 提取 common/logger.py
    □ 1.4.1 整理 UnifiedLogger 用法
    □ 1.4.2 创建 StructuredLogger 类
    □ 1.4.3 添加交易日志和 API 事件日志方法

□ 1.5 提取 common/excel_io.py
    □ 1.5.1 整理 Excel 读写函数
    □ 1.5.2 创建 ExcelWriter/ExcelReader 类
    □ 1.5.3 统一列宽调整逻辑
    □ 1.5.4 编写单元测试

□ 1.6 创建 common/error_handler.py
    □ 1.6.1 实现 ErrorHandler 类
    □ 1.6.2 实现重试逻辑

□ 1.7 验证
    □ 1.7.1 公共模块单元测试通过
    □ 1.7.2 现有脚本仍可正常运行
```

### 阶段 2：重构数据层

```
任务清单：
□ 2.1 创建 data/tqsdk_client.py
    □ 2.1.1 实现 TqSdkClient 类（异步上下文管理）
    □ 2.1.2 支持所有 RUN_MODE
    □ 2.1.3 实现 API 重建逻辑
    □ 2.1.4 编写集成测试

□ 2.2 创建 data/cache.py
    □ 2.2.1 实现 QuoteCache 类
    □ 2.2.2 编写单元测试

□ 2.3 创建 data/option_quotes.py
    □ 2.3.1 从 01, 10, 14 文件提取期权获取逻辑
    □ 2.3.2 实现 OptionQuoteFetcher 类
    □ 2.3.3 支持断点续传
    □ 2.3.4 实现并发控制

□ 2.4 创建 data/futures_quotes.py
    □ 2.4.1 从 01, 05, 14 文件提取期货获取逻辑
    □ 2.4.2 实现 FuturesQuoteFetcher 类

□ 2.5 创建 data/klines.py
    □ 2.5.1 从 09, 14_klines 提取 K 线获取逻辑

□ 2.6 创建 data/backup.py
    □ 2.6.1 从 00 系列提取备份逻辑

□ 2.7 验证
    □ 2.7.1 数据层单元测试通过
    □ 2.7.2 能成功获取期权和期货行情
```

### 阶段 3-8：后续阶段

（详细任务清单类似，此处省略）

---

## 性能优化设计

### 大数据量场景

针对数万合约行情获取场景：

```python
# data/option_quotes.py
class OptionQuoteFetcher:

    async def get_option_quotes_batch(
        self,
        symbols: List[str],
        batch_size: int = 200,
        max_concurrent: int = 5,
        progress_callback: Callable[[int, int], None] = None
    ) -> Dict:
        """并发获取行情，控制并发数，支持进度回调"""
        semaphore = asyncio.Semaphore(max_concurrent)
        total = len(symbols)
        completed = 0

        async def fetch_batch(batch, batch_index):
            nonlocal completed
            async with semaphore:
                result = await self._fetch_batch(batch)
                completed += len(batch)
                if progress_callback:
                    progress_callback(completed, total)
                return batch_index, result

        batches = [
            (symbols[i:i+batch_size], i // batch_size)
            for i in range(0, len(symbols), batch_size)
        ]

        tasks = [fetch_batch(batch, idx) for batch, idx in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return self._merge_results(results)
```

### 断点续传优化

```python
# data/option_quotes.py
class OptionQuoteFetcher:

    async def get_option_quotes_with_resume(
        self,
        symbols: List[str],
        output_file: str,
        batch_size: int = 200
    ) -> Dict:
        """支持断点续传的行情获取"""
        # 检查已有数据
        already_fetched = set()
        if os.path.exists(output_file):
            existing_df = pd.read_excel(output_file)
            already_fetched = set(existing_df['symbol'].tolist())

        # 只获取缺失的数据
        symbols_to_fetch = [s for s in symbols if s not in already_fetched]

        if not symbols_to_fetch:
            self.logger.info("所有数据已存在，跳过获取")
            return self._load_from_excel(output_file)

        # 分批获取，定期保存
        all_data = {}
        for i in range(0, len(symbols_to_fetch), batch_size):
            batch = symbols_to_fetch[i:i+batch_size]
            batch_data = await self._fetch_batch(batch)
            all_data.update(batch_data)

            # 每 save_interval 保存一次
            if len(all_data) % self.config.data.save_interval == 0:
                self._save_to_excel(all_data, output_file)

        # 最终保存
        self._save_to_excel(all_data, output_file)
        return all_data
```

---

## 风险缓解措施

| 风险 | 可能性 | 影响 | 缓解措施 | 责任人 |
|------|--------|------|----------|--------|
| 重构过程中破坏现有功能 | 高 | 高 | 1. 每阶段运行完整测试<br>2. 保留旧文件备份<br>3. 灰度发布 | 开发者 |
| 大文件拆分逻辑遗漏 | 中 | 高 | 1. 先写测试覆盖核心逻辑<br>2. 代码审查<br>3. 对比新旧输出 | 开发者 |
| API 超时/连接失败 | 高 | 高 | 1. 断点续传机制<br>2. 自动重连<br>3. 告警通知 | 开发者 |
| 配置泄露（账户密码） | 低 | 极高 | 1. 环境变量存储敏感信息<br>2. 配置文件不入库<br>3. 定期轮换密码 | 安全 |
| 异步处理不当导致死锁 | 中 | 高 | 1. 统一异步模式<br>2. 超时保护<br>3. 充分测试 | 开发者 |

---

## 兼容性保证

- 保留原有输出文件名和格式（`wisecoin-期权行情.xlsx` 等）
- 保留原有 JSON 配置文件兼容
- 提供统一的 `main.py` 入口，支持旧版命令行参数
- 旧脚本保留在 `legacy/` 目录，标记为废弃

---

## 成功标准

1. 所有模块职责单一，文件不超过 500 行
2. 核心计算逻辑有测试覆盖（覆盖率 > 80%）
3. 现有工作流可正常运行
4. 关键错误有统一处理和日志记录
5. 新功能开发效率提升（新模块开发时间减少 50%）