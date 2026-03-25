"""
WiseCoin 数据模型模块。

定义期权、期货、持仓等核心数据结构。
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
        """判断是否实值"""
        if self.call_or_put == CallOrPut.CALL:
            return underlying_price > self.strike_price
        else:
            return underlying_price < self.strike_price

    def time_to_expiry(self, as_of: date = None) -> float:
        """计算剩余时间（年）"""
        as_of = as_of or date.today()
        days = (self.expire_date - as_of).days
        return max(days / 365.0, 0.0)


@dataclass
class FutureQuote:
    """期货行情模型。"""
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
    """持仓模型。"""
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
        return self.current_price * self.volume


@dataclass
class AnalyzedOption:
    """
    分析后的期权。

    Attributes:
        option: 原始期权行情
        is_itm: 是否实值
        leverage: 杠杆倍数
        time_value: 时间价值
        moneyness: 价值度
        iv: 隐含波动率
        score: 综合评分
        signal: 交易信号
        reasons: 分析原因列表
    """
    option: OptionQuote
    is_itm: bool
    leverage: float
    time_value: float
    moneyness: float
    iv: Optional[float] = None
    score: float = 0.0
    signal: Signal = Signal.HOLD
    reasons: List[str] = field(default_factory=list)


@dataclass
class StrategySignal:
    """策略信号。"""
    symbol: str
    direction: str
    volume: int
    price: Optional[float]
    score: float
    strategy_type: str
    reasons: List[str] = field(default_factory=list)


@dataclass
class ArbitrageOpportunity:
    """套利机会。"""
    opportunity_type: str
    legs: List[dict]
    expected_profit: float
    risk_level: str
    confidence: float