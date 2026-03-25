# tests/test_analyzer.py
"""期权分析器测试模块。"""
import pytest
from datetime import date
from core.models import OptionQuote, CallOrPut, Signal
from core.analyzer import OptionAnalyzer


@pytest.fixture
def sample_options() -> list[OptionQuote]:
    """创建示例期权列表。"""
    return [
        # ITM Call: 行权价 5800, 标的价格 6000
        OptionQuote(
            symbol="IO2504-C-5800",
            underlying="IO2504",
            exchange_id="CFFEX",
            strike_price=5800.0,
            call_or_put=CallOrPut.CALL,
            last_price=250.0,
            bid_price=248.0,
            ask_price=252.0,
            volume=100,
            open_interest=500,
            expire_date=date(2025, 4, 18),
            delta=0.6
        ),
        # OTM Call: 行权价 6200, 标的价格 6000
        OptionQuote(
            symbol="IO2504-C-6200",
            underlying="IO2504",
            exchange_id="CFFEX",
            strike_price=6200.0,
            call_or_put=CallOrPut.CALL,
            last_price=50.0,
            bid_price=48.0,
            ask_price=52.0,
            volume=200,
            open_interest=300,
            expire_date=date(2025, 4, 18),
            delta=0.2
        ),
        # ITM Put: 行权价 6200, 标的价格 6000
        OptionQuote(
            symbol="IO2504-P-6200",
            underlying="IO2504",
            exchange_id="CFFEX",
            strike_price=6200.0,
            call_or_put=CallOrPut.PUT,
            last_price=220.0,
            bid_price=218.0,
            ask_price=222.0,
            volume=150,
            open_interest=400,
            expire_date=date(2025, 4, 18),
            delta=-0.5
        ),
        # OTM Put: 行权价 5800, 标的价格 6000
        OptionQuote(
            symbol="IO2504-P-5800",
            underlying="IO2504",
            exchange_id="CFFEX",
            strike_price=5800.0,
            call_or_put=CallOrPut.PUT,
            last_price=30.0,
            bid_price=28.0,
            ask_price=32.0,
            volume=180,
            open_interest=350,
            expire_date=date(2025, 4, 18),
            delta=-0.1
        ),
    ]


@pytest.fixture
def futures_prices() -> dict[str, float]:
    """创建期货价格字典。"""
    return {
        "IO2504": 6000.0,
    }


class TestOptionAnalyzer:
    """期权分析器测试类。"""

    def test_analyzer_creation(self):
        """测试分析器创建。"""
        analyzer = OptionAnalyzer()
        assert analyzer is not None

    def test_analyze_basic(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试基本分析功能。"""
        analyzer = OptionAnalyzer()
        results = analyzer.analyze(sample_options, futures_prices)

        assert len(results) == 4
        for result in results:
            assert result.is_itm is not None
            assert result.leverage >= 0
            assert result.signal == Signal.HOLD
            assert result.score == 0.0
            assert result.iv is None
            assert len(result.reasons) > 0

    def test_itm_detection(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试实值/虚值检测。"""
        analyzer = OptionAnalyzer()
        results = analyzer.analyze(sample_options, futures_prices)

        # 找到 ITM Call (行权价 5800, 标的 6000)
        itm_call = next(r for r in results if r.option.symbol == "IO2504-C-5800")
        assert itm_call.is_itm is True
        assert "实值" in " ".join(itm_call.reasons)

        # 找到 OTM Call (行权价 6200, 标的 6000)
        otm_call = next(r for r in results if r.option.symbol == "IO2504-C-6200")
        assert otm_call.is_itm is False
        assert "虚值" in " ".join(otm_call.reasons)

        # 找到 ITM Put (行权价 6200, 标的 6000)
        itm_put = next(r for r in results if r.option.symbol == "IO2504-P-6200")
        assert itm_put.is_itm is True
        assert "实值" in " ".join(itm_put.reasons)

        # 找到 OTM Put (行权价 5800, 标的 6000)
        otm_put = next(r for r in results if r.option.symbol == "IO2504-P-5800")
        assert otm_put.is_itm is False
        assert "虚值" in " ".join(otm_put.reasons)

    def test_leverage_calculation_positive(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试杠杆计算为正值。"""
        analyzer = OptionAnalyzer()
        results = analyzer.analyze(sample_options, futures_prices)

        for result in results:
            assert result.leverage > 0, f"Leverage should be positive for {result.option.symbol}"

    def test_leverage_with_delta(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试带 delta 的杠杆计算。"""
        analyzer = OptionAnalyzer()
        results = analyzer.analyze(sample_options, futures_prices)

        # ITM Call with delta 0.6
        itm_call = next(r for r in results if r.option.symbol == "IO2504-C-5800")
        # 杠杆 = 6000 / 250 * 0.6 = 14.4
        expected_leverage = 6000.0 / 250.0 * 0.6
        assert abs(itm_call.leverage - expected_leverage) < 0.01

    def test_time_value_calculation(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试时间价值计算。"""
        analyzer = OptionAnalyzer()
        results = analyzer.analyze(sample_options, futures_prices)

        # ITM Call: 行权价 5800, 标的 6000, 价格 250
        # 内在价值 = 6000 - 5800 = 200
        # 时间价值 = 250 - 200 = 50
        itm_call = next(r for r in results if r.option.symbol == "IO2504-C-5800")
        assert abs(itm_call.time_value - 50.0) < 0.01

        # OTM Call: 行权价 6200, 标的 6000, 价格 50
        # 内在价值 = 0
        # 时间价值 = 50 - 0 = 50
        otm_call = next(r for r in results if r.option.symbol == "IO2504-C-6200")
        assert abs(otm_call.time_value - 50.0) < 0.01

    def test_moneyness_calculation(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试价值度计算。"""
        analyzer = OptionAnalyzer()
        results = analyzer.analyze(sample_options, futures_prices)

        # ITM Call: 行权价 5800, 标的 6000
        # 价值度 = 6000 / 5800 = 1.034...
        itm_call = next(r for r in results if r.option.symbol == "IO2504-C-5800")
        expected_moneyness = 6000.0 / 5800.0
        assert abs(itm_call.moneyness - expected_moneyness) < 0.001

    def test_missing_future_price(self, sample_options: list[OptionQuote]):
        """测试缺少期货价格时跳过期权。"""
        analyzer = OptionAnalyzer()
        # 空的期货价格字典
        results = analyzer.analyze(sample_options, {})
        assert len(results) == 0

    def test_reasons_format(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试原因列表格式。"""
        analyzer = OptionAnalyzer()
        results = analyzer.analyze(sample_options, futures_prices)

        for result in results:
            reasons_text = " ".join(result.reasons)
            # 应该包含杠杆信息
            assert "杠杆" in reasons_text
            # 应该包含时间价值信息
            assert "时间价值" in reasons_text
            # 应该包含价值度信息
            assert "价值度" in reasons_text
            # 应该包含类型信息
            assert "类型" in reasons_text