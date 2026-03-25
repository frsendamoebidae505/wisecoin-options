# tests/test_models.py
"""数据模型模块测试"""
import pytest
from datetime import date, timedelta
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


# ============ Fixtures ============

@pytest.fixture
def sample_call_option():
    """创建示例看涨期权"""
    return OptionQuote(
        symbol="IO2504C4000",
        underlying="IF2504",
        exchange_id="CFFEX",
        strike_price=4000.0,
        call_or_put=CallOrPut.CALL,
        last_price=150.5,
        bid_price=150.0,
        ask_price=151.0,
        volume=1000,
        open_interest=5000,
        expire_date=date.today() + timedelta(days=30),
    )


@pytest.fixture
def sample_put_option():
    """创建示例看跌期权"""
    return OptionQuote(
        symbol="IO2504P4000",
        underlying="IF2504",
        exchange_id="CFFEX",
        strike_price=4000.0,
        call_or_put=CallOrPut.PUT,
        last_price=80.5,
        bid_price=80.0,
        ask_price=81.0,
        volume=800,
        open_interest=3000,
        expire_date=date.today() + timedelta(days=30),
    )


@pytest.fixture
def sample_future_quote():
    """创建示例期货行情"""
    return FutureQuote(
        symbol="IF2504",
        exchange_id="CFFEX",
        last_price=4050.0,
        bid_price=4049.8,
        ask_price=4050.2,
        volume=15000,
        open_interest=50000,
        high=4100.0,
        low=4000.0,
        pre_close=4020.0,
    )


@pytest.fixture
def sample_position():
    """创建示例持仓"""
    return Position(
        symbol="IF2504",
        exchange_id="CFFEX",
        direction="LONG",
        volume=2,
        avg_price=4000.0,
        current_price=4050.0,
        unrealized_pnl=10000.0,
        margin=200000.0,
    )


# ============ CallOrPut Enum Tests ============

class TestCallOrPut:
    """看涨看跌枚举测试"""

    def test_call_value(self):
        """测试CALL值"""
        assert CallOrPut.CALL.value == "CALL"

    def test_put_value(self):
        """测试PUT值"""
        assert CallOrPut.PUT.value == "PUT"

    def test_enum_count(self):
        """测试枚举数量"""
        assert len(CallOrPut) == 2

    def test_enum_is_string(self):
        """测试枚举是字符串类型"""
        assert isinstance(CallOrPut.CALL, str)
        assert CallOrPut.CALL == "CALL"


# ============ Signal Enum Tests ============

class TestSignal:
    """交易信号枚举测试"""

    def test_buy_value(self):
        """测试BUY值"""
        assert Signal.BUY.value == "BUY"

    def test_sell_value(self):
        """测试SELL值"""
        assert Signal.SELL.value == "SELL"

    def test_hold_value(self):
        """测试HOLD值"""
        assert Signal.HOLD.value == "HOLD"

    def test_enum_count(self):
        """测试枚举数量"""
        assert len(Signal) == 3

    def test_enum_is_string(self):
        """测试枚举是字符串类型"""
        assert isinstance(Signal.BUY, str)
        assert Signal.BUY == "BUY"


# ============ OptionQuote Tests ============

class TestOptionQuote:
    """期权行情模型测试"""

    def test_option_creation(self, sample_call_option):
        """测试期权创建"""
        assert sample_call_option.symbol == "IO2504C4000"
        assert sample_call_option.underlying == "IF2504"
        assert sample_call_option.exchange_id == "CFFEX"
        assert sample_call_option.strike_price == 4000.0
        assert sample_call_option.call_or_put == CallOrPut.CALL
        assert sample_call_option.last_price == 150.5
        assert sample_call_option.volume == 1000
        assert sample_call_option.open_interest == 5000

    def test_option_default_values(self, sample_call_option):
        """测试期权默认值"""
        assert sample_call_option.instrument_name == ""
        assert sample_call_option.margin == 0.0
        assert sample_call_option.delta is None
        assert sample_call_option.gamma is None
        assert sample_call_option.theta is None
        assert sample_call_option.vega is None
        assert sample_call_option.iv is None

    def test_option_with_greeks(self):
        """测试带Greeks的期权"""
        option = OptionQuote(
            symbol="IO2504C4000",
            underlying="IF2504",
            exchange_id="CFFEX",
            strike_price=4000.0,
            call_or_put=CallOrPut.CALL,
            last_price=150.5,
            bid_price=150.0,
            ask_price=151.0,
            volume=1000,
            open_interest=5000,
            expire_date=date.today() + timedelta(days=30),
            delta=0.5,
            gamma=0.001,
            theta=-5.0,
            vega=20.0,
            iv=0.25,
        )
        assert option.delta == 0.5
        assert option.gamma == 0.001
        assert option.theta == -5.0
        assert option.vega == 20.0
        assert option.iv == 0.25

    def test_is_itm_call_itm(self, sample_call_option):
        """测试看涨期权实值判断 - 实值"""
        # 行权价4000，标的价格4050，看涨期权为实值
        assert sample_call_option.is_itm(4050.0) is True

    def test_is_itm_call_otm(self, sample_call_option):
        """测试看涨期权实值判断 - 虚值"""
        # 行权价4000，标的价格3950，看涨期权为虚值
        assert sample_call_option.is_itm(3950.0) is False

    def test_is_itm_call_atm(self, sample_call_option):
        """测试看涨期权实值判断 - 平值"""
        # 行权价4000，标的价格4000，看涨期权为虚值（刚好不满足实值条件）
        assert sample_call_option.is_itm(4000.0) is False

    def test_is_itm_put_itm(self, sample_put_option):
        """测试看跌期权实值判断 - 实值"""
        # 行权价4000，标的价格3950，看跌期权为实值
        assert sample_put_option.is_itm(3950.0) is True

    def test_is_itm_put_otm(self, sample_put_option):
        """测试看跌期权实值判断 - 虚值"""
        # 行权价4000，标的价格4050，看跌期权为虚值
        assert sample_put_option.is_itm(4050.0) is False

    def test_is_itm_put_atm(self, sample_put_option):
        """测试看跌期权实值判断 - 平值"""
        # 行权价4000，标的价格4000，看跌期权为虚值（刚好不满足实值条件）
        assert sample_put_option.is_itm(4000.0) is False

    def test_time_to_expiry_future(self):
        """测试剩余时间计算 - 未来到期"""
        option = OptionQuote(
            symbol="IO2504C4000",
            underlying="IF2504",
            exchange_id="CFFEX",
            strike_price=4000.0,
            call_or_put=CallOrPut.CALL,
            last_price=150.5,
            bid_price=150.0,
            ask_price=151.0,
            volume=1000,
            open_interest=5000,
            expire_date=date.today() + timedelta(days=365),
        )
        # 约1年
        assert 0.99 < option.time_to_expiry() < 1.01

    def test_time_to_expiry_past(self):
        """测试剩余时间计算 - 已过期"""
        option = OptionQuote(
            symbol="IO2504C4000",
            underlying="IF2504",
            exchange_id="CFFEX",
            strike_price=4000.0,
            call_or_put=CallOrPut.CALL,
            last_price=150.5,
            bid_price=150.0,
            ask_price=151.0,
            volume=1000,
            open_interest=5000,
            expire_date=date.today() - timedelta(days=10),
        )
        # 已过期应返回0
        assert option.time_to_expiry() == 0.0

    def test_time_to_expiry_specific_date(self):
        """测试剩余时间计算 - 指定日期"""
        option = OptionQuote(
            symbol="IO2504C4000",
            underlying="IF2504",
            exchange_id="CFFEX",
            strike_price=4000.0,
            call_or_put=CallOrPut.CALL,
            last_price=150.5,
            bid_price=150.0,
            ask_price=151.0,
            volume=1000,
            open_interest=5000,
            expire_date=date(2025, 4, 18),
        )
        as_of = date(2025, 4, 1)
        # 17天后到期
        expected = 17 / 365.0
        assert abs(option.time_to_expiry(as_of) - expected) < 0.001


# ============ FutureQuote Tests ============

class TestFutureQuote:
    """期货行情模型测试"""

    def test_future_creation(self, sample_future_quote):
        """测试期货创建"""
        assert sample_future_quote.symbol == "IF2504"
        assert sample_future_quote.exchange_id == "CFFEX"
        assert sample_future_quote.last_price == 4050.0
        assert sample_future_quote.bid_price == 4049.8
        assert sample_future_quote.ask_price == 4050.2
        assert sample_future_quote.volume == 15000
        assert sample_future_quote.open_interest == 50000
        assert sample_future_quote.high == 4100.0
        assert sample_future_quote.low == 4000.0
        assert sample_future_quote.pre_close == 4020.0

    def test_future_spread(self, sample_future_quote):
        """测试期货买卖价差"""
        spread = sample_future_quote.ask_price - sample_future_quote.bid_price
        assert spread == pytest.approx(0.4)

    def test_future_price_change(self, sample_future_quote):
        """测试期货价格变动"""
        change = sample_future_quote.last_price - sample_future_quote.pre_close
        assert change == 30.0


# ============ Position Tests ============

class TestPosition:
    """持仓模型测试"""

    def test_position_creation(self, sample_position):
        """测试持仓创建"""
        assert sample_position.symbol == "IF2504"
        assert sample_position.exchange_id == "CFFEX"
        assert sample_position.direction == "LONG"
        assert sample_position.volume == 2
        assert sample_position.avg_price == 4000.0
        assert sample_position.current_price == 4050.0
        assert sample_position.unrealized_pnl == 10000.0
        assert sample_position.margin == 200000.0

    def test_position_default_values(self, sample_position):
        """测试持仓默认值"""
        assert sample_position.volume_today == 0

    def test_position_market_value(self, sample_position):
        """测试持仓市值计算"""
        # 当前价格 * 持仓量
        expected = 4050.0 * 2
        assert sample_position.market_value() == expected

    def test_short_position_market_value(self):
        """测试空头持仓市值计算"""
        position = Position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="SHORT",
            volume=3,
            avg_price=4100.0,
            current_price=4050.0,
            unrealized_pnl=15000.0,
            margin=300000.0,
        )
        expected = 4050.0 * 3
        assert position.market_value() == expected

    def test_position_with_volume_today(self):
        """测试带今仓量的持仓"""
        position = Position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=5,
            avg_price=4000.0,
            current_price=4050.0,
            unrealized_pnl=25000.0,
            margin=500000.0,
            volume_today=2,
        )
        assert position.volume_today == 2
        assert position.volume == 5


# ============ AnalyzedOption Tests ============

class TestAnalyzedOption:
    """分析后期权模型测试"""

    def test_analyzed_option_creation(self, sample_call_option):
        """测试分析后期权创建"""
        analyzed = AnalyzedOption(
            option=sample_call_option,
            is_itm=True,
            leverage=32.0,
            time_value=5.0,
            moneyness=1.02,
            iv=0.25,
        )
        assert analyzed.option == sample_call_option
        assert analyzed.is_itm == True
        assert analyzed.leverage == 32.0
        assert analyzed.time_value == 5.0
        assert analyzed.moneyness == 1.02
        assert analyzed.iv == 0.25
        assert analyzed.score == 0.0
        assert analyzed.signal == Signal.HOLD
        assert analyzed.reasons == []

    def test_analyzed_option_with_analysis(self, sample_call_option):
        """测试带分析结果的期权"""
        analyzed = AnalyzedOption(
            option=sample_call_option,
            is_itm=True,
            leverage=32.0,
            time_value=5.0,
            moneyness=1.02,
            iv=0.25,
            score=85.5,
            signal=Signal.BUY,
            reasons=["IV偏低", "Delta适中"],
        )
        assert analyzed.score == 85.5
        assert analyzed.signal == Signal.BUY
        assert len(analyzed.reasons) == 2


# ============ StrategySignal Tests ============

class TestStrategySignal:
    """策略信号模型测试"""

    def test_strategy_signal_creation(self):
        """测试策略信号创建"""
        signal = StrategySignal(
            symbol="IO2504C4000",
            direction="BUY",
            volume=2,
            price=150.5,
            score=80.0,
            strategy_type="IV套利",
        )
        assert signal.symbol == "IO2504C4000"
        assert signal.direction == "BUY"
        assert signal.volume == 2
        assert signal.price == 150.5
        assert signal.score == 80.0
        assert signal.strategy_type == "IV套利"
        assert signal.reasons == []

    def test_strategy_signal_with_reasons(self):
        """测试带原因的策略信号"""
        signal = StrategySignal(
            symbol="IO2504C4000",
            direction="SELL",
            volume=1,
            price=None,
            score=75.0,
            strategy_type="平仓",
            reasons=["达到止盈目标", "风险控制"],
        )
        assert signal.price is None
        assert len(signal.reasons) == 2


# ============ ArbitrageOpportunity Tests ============

class TestArbitrageOpportunity:
    """套利机会模型测试"""

    def test_arbitrage_opportunity_creation(self):
        """测试套利机会创建"""
        arb = ArbitrageOpportunity(
            opportunity_type="跨期套利",
            legs=[
                {"symbol": "IF2504", "direction": "BUY", "volume": 1},
                {"symbol": "IF2505", "direction": "SELL", "volume": 1},
            ],
            expected_profit=500.0,
            risk_level="LOW",
            confidence=0.85,
        )
        assert arb.opportunity_type == "跨期套利"
        assert len(arb.legs) == 2
        assert arb.expected_profit == 500.0
        assert arb.risk_level == "LOW"
        assert arb.confidence == 0.85

    def test_arbitrage_opportunity_single_leg(self):
        """测试单腿套利机会"""
        arb = ArbitrageOpportunity(
            opportunity_type="单边投机",
            legs=[{"symbol": "IO2504C4000", "direction": "BUY", "volume": 1}],
            expected_profit=200.0,
            risk_level="HIGH",
            confidence=0.6,
        )
        assert len(arb.legs) == 1
        assert arb.risk_level == "HIGH"