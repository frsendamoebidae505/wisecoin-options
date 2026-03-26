# WiseCoin 架构重构 - 实施计划（阶段 3：业务层）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构业务层，实现数据模型、期权分析器、IV 计算器、期货分析器。

**Architecture:** 创建 core/ 包，包含纯计算逻辑，不依赖外部数据源。

**Tech Stack:** Python 3.10+, dataclasses, numpy, scipy

**Spec:** `docs/superpowers/specs/2026-03-25-architecture-refactor-design.md`

**Depends on:** 阶段 1 完成（common/），阶段 2 完成（data/）

---

## 文件结构

```
wisecoin-options-free/
├── core/
│   ├── __init__.py
│   ├── models.py            # 数据模型（OptionQuote, FutureQuote, Position 等）
│   ├── analyzer.py          # 期权分析器（基础指标计算）
│   ├── iv_calculator.py     # IV 计算器
│   └── futures_analyzer.py  # 期货分析器
├── tests/
│   ├── test_models.py
│   ├── test_analyzer.py
│   ├── test_iv_calculator.py
│   └── test_futures_analyzer.py
```

---

## Task 1: 创建业务层目录结构

**Files:**
- Create: `core/__init__.py`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p core
touch core/__init__.py
```

- [ ] **Step 2: 提交**

```bash
git add core/
git commit -m "feat(core): 创建业务层目录结构"
```

---

## Task 2: 实现数据模型模块

**Files:**
- Create: `core/models.py`
- Create: `tests/test_models.py`

这是核心数据结构定义，后续所有模块都依赖此模块。

- [ ] **Step 1: 编写测试**

```python
# tests/test_models.py
"""数据模型测试"""
import pytest
from datetime import date
from core.models import (
    CallOrPut,
    Signal,
    OptionQuote,
    FutureQuote,
    Position,
    AnalyzedOption,
)


class TestCallOrPut:
    """看涨看跌枚举测试"""

    def test_call_value(self):
        assert CallOrPut.CALL == "CALL"

    def test_put_value(self):
        assert CallOrPut.PUT == "PUT"


class TestSignal:
    """信号枚举测试"""

    def test_signals(self):
        assert Signal.BUY == "BUY"
        assert Signal.SELL == "SELL"
        assert Signal.HOLD == "HOLD"


class TestOptionQuote:
    """期权行情模型测试"""

    @pytest.fixture
    def call_option(self):
        return OptionQuote(
            symbol="SHFE.au2406C480",
            underlying="SHFE.au2406",
            exchange_id="SHFE",
            strike_price=480.0,
            call_or_put=CallOrPut.CALL,
            last_price=15.0,
            bid_price=14.8,
            ask_price=15.2,
            volume=100,
            open_interest=500,
            expire_date=date(2024, 6, 15),
        )

    def test_create_option(self, call_option):
        assert call_option.symbol == "SHFE.au2406C480"
        assert call_option.strike_price == 480.0
        assert call_option.call_or_put == CallOrPut.CALL

    def test_is_itm_call(self, call_option):
        """看涨期权实值判断"""
        # 标的 500 > 行权价 480，看涨期权实值
        assert call_option.is_itm(500.0) == True
        # 标的 460 < 行权价 480，看涨期权虚值
        assert call_option.is_itm(460.0) == False

    def test_is_itm_put(self):
        """看跌期权实值判断"""
        put_option = OptionQuote(
            symbol="SHFE.au2406P480",
            underlying="SHFE.au2406",
            exchange_id="SHFE",
            strike_price=480.0,
            call_or_put=CallOrPut.PUT,
            last_price=10.0,
            bid_price=9.8,
            ask_price=10.2,
            volume=100,
            open_interest=500,
            expire_date=date(2024, 6, 15),
        )
        # 标的 460 < 行权价 480，看跌期权实值
        assert put_option.is_itm(460.0) == True
        # 标的 500 > 行权价 480，看跌期权虚值
        assert put_option.is_itm(500.0) == False

    def test_time_to_expiry(self, call_option):
        """剩余时间计算"""
        # 假设今天是 2024-06-01
        today = date(2024, 6, 1)
        days = call_option.time_to_expiry(today)
        assert days == 14 / 365.0  # 14 天


class TestFutureQuote:
    """期货行情模型测试"""

    def test_create_future(self):
        future = FutureQuote(
            symbol="SHFE.au2406",
            exchange_id="SHFE",
            last_price=480.0,
            bid_price=479.8,
            ask_price=480.2,
            volume=1000,
            open_interest=5000,
            high=485.0,
            low=475.0,
            pre_close=478.0,
        )
        assert future.symbol == "SHFE.au2406"
        assert future.last_price == 480.0


class TestPosition:
    """持仓模型测试"""

    def test_create_position(self):
        position = Position(
            symbol="SHFE.au2406C480",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=15.0,
            current_price=16.0,
            unrealized_pnl=10.0,
            margin=1000.0,
        )
        assert position.symbol == "SHFE.au2406C480"
        assert position.volume == 10

    def test_market_value(self):
        position = Position(
            symbol="SHFE.au2406C480",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=15.0,
            current_price=16.0,
            unrealized_pnl=10.0,
            margin=1000.0,
        )
        assert position.market_value() == 160.0  # 16.0 * 10
```

- [ ] **Step 2: 实现数据模型**

```python
# core/models.py
"""
WiseCoin 数据模型模块。

定义期权、期货、持仓等核心数据结构。

Example:
    >>> option = OptionQuote(
    ...     symbol="SHFE.au2406C480",
    ...     strike_price=480.0,
    ...     call_or_put=CallOrPut.CALL,
    ...     ...
    ... )
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import date
from enum import Enum


class CallOrPut(str, Enum):
    """看涨看跌枚举。"""
    CALL = "CALL"
    PUT = "PUT"


class Signal(str, Enum):
    """交易信号枚举。"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class OptionQuote:
    """
    期权行情模型。

    Attributes:
        symbol: 合约代码。
        underlying: 标的合约代码。
        exchange_id: 交易所代码。
        strike_price: 行权价。
        call_or_put: 看涨看跌。
        last_price: 最新价。
        bid_price: 买一价。
        ask_price: 卖一价。
        volume: 成交量。
        open_interest: 持仓量。
        expire_date: 到期日。
        instrument_name: 合约名称。
        margin: 保证金。
        delta: Delta 值。
        gamma: Gamma 值。
        theta: Theta 值。
        vega: Vega 值。
        iv: 隐含波动率。
    """
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
        """
        判断是否实值（In The Money）。

        Args:
            underlying_price: 标的价格。

        Returns:
            是否实值。
        """
        if self.call_or_put == CallOrPut.CALL:
            return underlying_price > self.strike_price
        else:
            return underlying_price < self.strike_price

    def time_to_expiry(self, as_of: date = None) -> float:
        """
        计算剩余时间（年）。

        Args:
            as_of: 计算基准日，默认今天。

        Returns:
            剩余时间（年）。
        """
        as_of = as_of or date.today()
        days = (self.expire_date - as_of).days
        return max(days / 365.0, 0.0)


@dataclass
class FutureQuote:
    """
    期货行情模型。

    Attributes:
        symbol: 合约代码。
        exchange_id: 交易所代码。
        last_price: 最新价。
        bid_price: 买一价。
        ask_price: 卖一价。
        volume: 成交量。
        open_interest: 持仓量。
        high: 最高价。
        low: 最低价。
        pre_close: 昨收价。
    """
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
    """
    持仓模型。

    Attributes:
        symbol: 合约代码。
        exchange_id: 交易所代码。
        direction: 方向 (LONG/SHORT)。
        volume: 持仓量。
        avg_price: 开仓均价。
        current_price: 当前价格。
        unrealized_pnl: 未实现盈亏。
        margin: 占用保证金。
        volume_today: 今仓数量。
    """
    symbol: str
    exchange_id: str
    direction: str  # LONG / SHORT
    volume: int
    avg_price: float
    current_price: float
    unrealized_pnl: float
    margin: float
    volume_today: int = 0

    def market_value(self) -> float:
        """计算市值。"""
        return self.current_price * self.volume


@dataclass
class AnalyzedOption:
    """
    分析后的期权。

    Attributes:
        option: 期权行情。
        iv: 隐含波动率。
        score: 评分。
        signal: 交易信号。
        reasons: 分析原因列表。
    """
    option: OptionQuote
    iv: Optional[float]
    score: float = 0.0
    signal: Signal = Signal.HOLD
    reasons: List[str] = field(default_factory=list)


@dataclass
class StrategySignal:
    """
    策略信号。

    Attributes:
        symbol: 合约代码。
        direction: 方向 (BUY/SELL)。
        volume: 数量。
        price: 价格。
        score: 评分。
        strategy_type: 策略类型。
        reasons: 原因列表。
    """
    symbol: str
    direction: str
    volume: int
    price: Optional[float]
    score: float
    strategy_type: str
    reasons: List[str] = field(default_factory=list)


@dataclass
class ArbitrageOpportunity:
    """
    套利机会。

    Attributes:
        opportunity_type: 套利类型。
        legs: 各腿合约信息。
        expected_profit: 预期收益。
        risk_level: 风险等级。
        confidence: 置信度。
    """
    opportunity_type: str  # CONVERSION, STRADDLE, CALENDAR
    legs: List[dict]
    expected_profit: float
    risk_level: str
    confidence: float
```

- [ ] **Step 3: 运行测试**

```bash
python3 -m pytest tests/test_models.py -v
```

- [ ] **Step 4: 提交**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat(core): 实现数据模型模块"
```

---

## Task 3: 实现 IV 计算器模块

**Files:**
- Create: `core/iv_calculator.py`
- Create: `tests/test_iv_calculator.py`

IV 计算是核心算法，需要精确测试。

- [ ] **Step 1: 编写测试**

```python
# tests/test_iv_calculator.py
"""IV 计算器测试"""
import pytest
from datetime import date
from core.models import OptionQuote, CallOrPut
from core.iv_calculator import IVCalculator


class TestIVCalculator:
    """IV 计算器测试"""

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
            last_price=15.0,
            bid_price=14.8,
            ask_price=15.2,
            volume=100,
            open_interest=500,
            expire_date=date(2024, 6, 15),
        )

    def test_create_calculator(self, calculator):
        """测试创建计算器"""
        assert calculator is not None

    def test_calculate_iv_atm(self, calculator, atm_call):
        """测试平值期权 IV 计算"""
        future_price = 480.0  # 标的价格等于行权价
        iv = calculator.calculate_iv(atm_call, future_price)
        # IV 应该是正数
        assert iv is not None
        assert iv > 0

    def test_calculate_iv_itm(self, calculator, atm_call):
        """测试实值期权 IV 计算"""
        future_price = 500.0  # 标的价格高于行权价
        iv = calculator.calculate_iv(atm_call, future_price)
        assert iv is not None
        assert iv > 0

    def test_calculate_iv_otm(self, calculator, atm_call):
        """测试虚值期权 IV 计算"""
        future_price = 460.0  # 标的价格低于行权价
        iv = calculator.calculate_iv(atm_call, future_price)
        # 深度虚值可能无法计算
        if iv is not None:
            assert iv > 0

    def test_calculate_iv_invalid_price(self, calculator, atm_call):
        """测试无效价格"""
        with pytest.raises(ValueError):
            calculator.calculate_iv(atm_call, -100.0)
```

- [ ] **Step 2: 实现 IV 计算器**

```python
# core/iv_calculator.py
"""
隐含波动率计算模块。

使用 Black-Scholes 模型计算期权隐含波动率。

Example:
    >>> calculator = IVCalculator()
    >>> iv = calculator.calculate_iv(option, future_price)
"""
from typing import Optional, List
import math

from core.models import OptionQuote, CallOrPut


class IVCalculator:
    """
    隐含波动率计算器。

    使用牛顿迭代法求解 Black-Scholes 模型中的 IV。

    Example:
        >>> calculator = IVCalculator()
        >>> iv = calculator.calculate_iv(option, 480.0)
    """

    def __init__(
        self,
        risk_free_rate: float = 0.03,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ):
        """
        初始化计算器。

        Args:
            risk_free_rate: 无风险利率（年化），默认 3%。
            max_iterations: 最大迭代次数。
            tolerance: 收敛容差。
        """
        self.risk_free_rate = risk_free_rate
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def calculate_iv(
        self,
        option: OptionQuote,
        future_price: float,
        time_to_expiry: float = None,
    ) -> Optional[float]:
        """
        计算隐含波动率。

        Args:
            option: 期权行情。
            future_price: 标的期货价格。
            time_to_expiry: 剩余时间（年），可选。

        Returns:
            隐含波动率（年化），如果无法计算返回 None。

        Raises:
            ValueError: 如果价格无效。
        """
        # 参数验证
        if future_price <= 0:
            raise ValueError("标的期货价格必须大于 0")
        if option.last_price <= 0:
            raise ValueError("期权价格必须大于 0")

        # 计算剩余时间
        if time_to_expiry is None:
            time_to_expiry = option.time_to_expiry()

        if time_to_expiry <= 0:
            return None  # 已到期

        # 提取参数
        S = future_price  # 标的价格
        K = option.strike_price  # 行权价
        T = time_to_expiry  # 剩余时间
        r = self.risk_free_rate  # 无风险利率
        market_price = option.last_price  # 期权市场价格
        is_call = option.call_or_put == CallOrPut.CALL

        # 牛顿迭代法求解 IV
        iv = 0.2  # 初始猜测值

        for _ in range(self.max_iterations):
            # 计算 Black-Scholes 价格和 Vega
            price = self._bs_price(S, K, T, r, iv, is_call)
            vega = self._bs_vega(S, K, T, r, iv)

            if abs(vega) < 1e-10:
                break

            # 牛顿迭代
            diff = market_price - price
            new_iv = iv + diff / vega

            # 边界检查
            if new_iv < 0.001:
                new_iv = 0.001
            elif new_iv > 5.0:
                new_iv = 5.0

            # 收敛检查
            if abs(new_iv - iv) < self.tolerance:
                return new_iv

            iv = new_iv

        # 未收敛，返回当前值
        if 0 < iv < 5:
            return iv
        return None

    def _bs_price(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        is_call: bool,
    ) -> float:
        """计算 Black-Scholes 期权价格。"""
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if is_call:
            price = S * self._norm_cdf(d1) - K * math.exp(-r * T) * self._norm_cdf(d2)
        else:
            price = K * math.exp(-r * T) * self._norm_cdf(-d2) - S * self._norm_cdf(-d1)

        return price

    def _bs_vega(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """计算 Black-Scholes Vega。"""
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        return S * math.sqrt(T) * self._norm_pdf(d1)

    @staticmethod
    def _norm_cdf(x: float) -> float:
        """标准正态分布累积分布函数。"""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _norm_pdf(x: float) -> float:
        """标准正态分布概率密度函数。"""
        return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)

    def calculate_smile(
        self,
        options: List[OptionQuote],
        future_price: float,
    ) -> dict:
        """
        计算波动率微笑。

        Args:
            options: 期权列表。
            future_price: 标的期货价格。

        Returns:
            {strike_price: iv} 映射。
        """
        smile = {}
        for option in options:
            iv = self.calculate_iv(option, future_price)
            if iv is not None:
                smile[option.strike_price] = iv
        return smile
```

- [ ] **Step 3: 运行测试**

```bash
python3 -m pytest tests/test_iv_calculator.py -v
```

- [ ] **Step 4: 提交**

```bash
git add core/iv_calculator.py tests/test_iv_calculator.py
git commit -m "feat(core): 实现 IV 计算器模块"
```

---

## Task 4: 实现期权分析器模块

**Files:**
- Create: `core/analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_analyzer.py
"""期权分析器测试"""
import pytest
from datetime import date
from core.models import OptionQuote, CallOrPut
from core.analyzer import OptionAnalyzer


class TestOptionAnalyzer:
    """期权分析器测试"""

    @pytest.fixture
    def analyzer(self):
        return OptionAnalyzer()

    @pytest.fixture
    def sample_options(self):
        """测试用期权列表"""
        return [
            OptionQuote(
                symbol="SHFE.au2406C480",
                underlying="SHFE.au2406",
                exchange_id="SHFE",
                strike_price=480.0,
                call_or_put=CallOrPut.CALL,
                last_price=15.0,
                bid_price=14.8,
                ask_price=15.2,
                volume=100,
                open_interest=500,
                expire_date=date(2024, 6, 15),
            ),
            OptionQuote(
                symbol="SHFE.au2406P480",
                underlying="SHFE.au2406",
                exchange_id="SHFE",
                strike_price=480.0,
                call_or_put=CallOrPut.PUT,
                last_price=10.0,
                bid_price=9.8,
                ask_price=10.2,
                volume=200,
                open_interest=800,
                expire_date=date(2024, 6, 15),
            ),
        ]

    def test_create_analyzer(self, analyzer):
        """测试创建分析器"""
        assert analyzer is not None

    def test_analyze_basic(self, analyzer, sample_options):
        """测试基础分析"""
        futures_prices = {"SHFE.au2406": 480.0}
        results = analyzer.analyze(sample_options, futures_prices)

        assert len(results) == 2
        for result in results:
            assert result.option is not None
            assert len(result.reasons) > 0

    def test_analyze_with_itm_check(self, analyzer, sample_options):
        """测试实值虚值判断"""
        futures_prices = {"SHFE.au2406": 500.0}  # 标的 500，行权价 480
        results = analyzer.analyze(sample_options, futures_prices)

        # 看涨期权应该实值
        call_result = next(r for r in results if r.option.call_or_put == CallOrPut.CALL)
        assert "实值" in call_result.reasons[0]

        # 看跌期权应该虚值
        put_result = next(r for r in results if r.option.call_or_put == CallOrPut.PUT)
        assert "虚值" in put_result.reasons[0]

    def test_calculate_leverage(self, analyzer, sample_options):
        """测试杠杆计算"""
        option = sample_options[0]
        future_price = 480.0
        leverage = analyzer._calculate_leverage(option, future_price)
        assert leverage > 0
```

- [ ] **Step 2: 实现分析器**

```python
# core/analyzer.py
"""
期权分析器模块。

计算期权基础指标，不涉及评分和交易决策。

Example:
    >>> analyzer = OptionAnalyzer()
    >>> results = analyzer.analyze(options, futures_prices)
"""
from typing import List, Dict, Optional
from dataclasses import dataclass

from core.models import OptionQuote, AnalyzedOption, Signal


class OptionAnalyzer:
    """
    期权分析器。

    计算基础指标，如 ITM/OTM 状态、杠杆率、时间价值等。
    不涉及评分和交易决策。

    Example:
        >>> analyzer = OptionAnalyzer()
        >>> results = analyzer.analyze(options, futures_prices)
    """

    def __init__(self, config: Optional[dict] = None):
        """
        初始化分析器。

        Args:
            config: 分析配置（可选）。
        """
        self.config = config or {}

    def analyze(
        self,
        quotes: List[OptionQuote],
        futures_quotes: Dict[str, float],
    ) -> List[AnalyzedOption]:
        """
        分析期权数据，计算基础指标。

        Args:
            quotes: 期权行情列表。
            futures_quotes: 标的期货价格映射 {symbol: price}。

        Returns:
            AnalyzedOption 列表，包含基础指标。
        """
        results = []

        for quote in quotes:
            # 获取标的价格
            future_price = futures_quotes.get(quote.underlying, 0)

            if future_price <= 0:
                continue

            # 计算基础指标
            is_itm = quote.is_itm(future_price)
            leverage = self._calculate_leverage(quote, future_price)
            time_value = self._calculate_time_value(quote, future_price)
            moneyness = self._calculate_moneyness(quote, future_price)

            # 构建原因列表
            reasons = [
                f"{'实值' if is_itm else '虚值'}",
                f"杠杆率: {leverage:.2f}x",
                f"时间价值: {time_value:.2f}",
                f"价值度: {moneyness:.2%}",
            ]

            results.append(AnalyzedOption(
                option=quote,
                iv=None,  # 后续由 IVCalculator 填充
                score=0.0,  # 由 StrategyEvaluator 填充
                signal=Signal.HOLD,
                reasons=reasons,
            ))

        return results

    def _calculate_leverage(
        self,
        option: OptionQuote,
        future_price: float,
    ) -> float:
        """
        计算杠杆率。

        杠杆率 = 标的价格 / 期权价格 * Delta

        Args:
            option: 期权行情。
            future_price: 标的价格。

        Returns:
            杠杆率。
        """
        if option.last_price <= 0:
            return 0.0

        # 简化计算：使用标的价格与期权价格之比
        # 精确计算需要 Delta
        if option.delta:
            return future_price / option.last_price * abs(option.delta)
        else:
            return future_price / option.last_price

    def _calculate_time_value(
        self,
        option: OptionQuote,
        future_price: float,
    ) -> float:
        """
        计算时间价值。

        时间价值 = 期权价格 - 内在价值

        Args:
            option: 期权行情。
            future_price: 标的价格。

        Returns:
            时间价值。
        """
        # 计算内在价值
        if option.call_or_put == CallOrPut.CALL:
            intrinsic = max(future_price - option.strike_price, 0)
        else:
            intrinsic = max(option.strike_price - future_price, 0)

        return option.last_price - intrinsic

    def _calculate_moneyness(
        self,
        option: OptionQuote,
        future_price: float,
    ) -> float:
        """
        计算价值度（Moneyness）。

        Moneyness = 标的价格 / 行权价

        Args:
            option: 期权行情。
            future_price: 标的价格。

        Returns:
            价值度。
        """
        if option.strike_price <= 0:
            return 0.0

        return future_price / option.strike_price
```

- [ ] **Step 3: 运行测试**

```bash
python3 -m pytest tests/test_analyzer.py -v
```

- [ ] **Step 4: 提交**

```bash
git add core/analyzer.py tests/test_analyzer.py
git commit -m "feat(core): 实现期权分析器模块"
```

---

## Task 5: 更新 core 包导出

**Files:**
- Modify: `core/__init__.py`

- [ ] **Step 1: 更新导出**

```python
# core/__init__.py
"""
WiseCoin 业务层。

提供数据模型、分析器、计算器等核心功能。
"""

from core.models import (
    CallOrPut,
    Signal,
    OptionQuote,
    FutureQuote,
    Position,
    AnalyzedOption,
    StrategySignal,
    ArbitrageOpportunity,
)
from core.analyzer import OptionAnalyzer
from core.iv_calculator import IVCalculator

__all__ = [
    # Enums
    'CallOrPut',
    'Signal',
    # Models
    'OptionQuote',
    'FutureQuote',
    'Position',
    'AnalyzedOption',
    'StrategySignal',
    'ArbitrageOpportunity',
    # Analyzers
    'OptionAnalyzer',
    'IVCalculator',
]
```

- [ ] **Step 2: 提交**

```bash
git add core/__init__.py
git commit -m "feat(core): 完善业务层包导出"
```

---

## Task 6: 验证阶段完成

- [ ] **Step 1: 运行全部测试**

```bash
python3 -m pytest tests/ -v
```

- [ ] **Step 2: 检查代码结构**

```bash
ls -la core/
```

---

## 阶段 3 完成标准

- [x] core/ 目录创建完成
- [x] models.py 数据模型实现
- [x] iv_calculator.py IV 计算器实现
- [x] analyzer.py 期权分析器实现
- [x] 所有测试通过