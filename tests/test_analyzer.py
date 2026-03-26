# tests/test_analyzer.py
"""期权分析器测试模块。"""
import pytest
from datetime import date
from core.models import OptionQuote, CallOrPut, Signal
from core.analyzer import (
    OptionAnalyzer,
    OptionScorer,
    OptionTradingClassifier,
    MaxPainCalculator,
    PCRAnalyzer,
    UnderlyingAnalyzer,
    OptionMetrics,
    IntrinsicLevel,
    TradingType,
)


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


class TestOptionScorer:
    """期权评分器测试类。"""

    def test_scorer_creation(self):
        """测试评分器创建。"""
        scorer = OptionScorer()
        assert scorer is not None

    def test_score_basic(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试基本评分功能。"""
        analyzer = OptionAnalyzer()
        scorer = OptionScorer()

        analyzed = analyzer.analyze(sample_options, futures_prices)
        scored = scorer.score(analyzed)

        assert len(scored) == 4
        for result in scored:
            assert 0 <= result.score <= 100
            assert result.signal in [Signal.BUY, Signal.SELL, Signal.HOLD]

    def test_filter_by_score(self, sample_options: list[OptionQuote], futures_prices: dict[str, float]):
        """测试评分筛选功能。"""
        analyzer = OptionAnalyzer()
        scorer = OptionScorer()

        analyzed = analyzer.analyze(sample_options, futures_prices)
        scored = scorer.score(analyzed)

        filtered = scorer.filter_by_score(scored, min_score=50.0)
        assert all(opt.score >= 50.0 for opt in filtered)


class TestOptionTradingClassifier:
    """交易类型分类器测试类。"""

    def test_classifier_creation(self):
        """测试分类器创建。"""
        classifier = OptionTradingClassifier()
        assert classifier is not None

    def test_directional_bullish(self):
        """测试方向型看多分类。"""
        classifier = OptionTradingClassifier()
        # PCR极端看多 + CALL增仓
        trading_type, subtype, confidence = classifier.classify(
            call_oi_change=100,
            put_oi_change=30,
            pcr=0.4,
            volume_ratio=1.5
        )
        assert trading_type == TradingType.DIRECTIONAL
        assert "看多" in subtype

    def test_directional_bearish(self):
        """测试方向型看空分类。"""
        classifier = OptionTradingClassifier()
        # PCR极端看空 + PUT增仓
        trading_type, subtype, confidence = classifier.classify(
            call_oi_change=30,
            put_oi_change=100,
            pcr=1.6,
            volume_ratio=1.5
        )
        assert trading_type == TradingType.DIRECTIONAL
        assert "看空" in subtype

    def test_volatility_type(self):
        """测试波动率型分类。"""
        classifier = OptionTradingClassifier()
        # 双向增仓 + PCR中性
        trading_type, subtype, confidence = classifier.classify(
            call_oi_change=100,
            put_oi_change=95,
            pcr=1.0,
            volume_ratio=1.5
        )
        assert trading_type == TradingType.VOLATILITY

    def test_no_change(self):
        """测试无明显变化情况。"""
        classifier = OptionTradingClassifier()
        trading_type, subtype, confidence = classifier.classify(
            call_oi_change=0,
            put_oi_change=0,
            pcr=1.0
        )
        assert trading_type == TradingType.UNKNOWN


class TestMaxPainCalculator:
    """最大痛点计算器测试类。"""

    def test_calculator_creation(self):
        """测试计算器创建。"""
        calc = MaxPainCalculator()
        assert calc is not None

    def test_calculate_basic(self):
        """测试基本最大痛点计算。"""
        calc = MaxPainCalculator()
        options = [
            {'strike': 100, 'open_interest': 100, 'multiplier': 1, 'call_or_put': 'CALL'},
            {'strike': 100, 'open_interest': 100, 'multiplier': 1, 'call_or_put': 'PUT'},
            {'strike': 110, 'open_interest': 50, 'multiplier': 1, 'call_or_put': 'CALL'},
            {'strike': 90, 'open_interest': 50, 'multiplier': 1, 'call_or_put': 'PUT'},
        ]
        max_pain = calc.calculate(options)
        assert max_pain > 0

    def test_empty_options(self):
        """测试空期权列表。"""
        calc = MaxPainCalculator()
        max_pain = calc.calculate([])
        assert max_pain == 0.0


class TestPCRAnalyzer:
    """PCR分析器测试类。"""

    def test_analyzer_creation(self):
        """测试分析器创建。"""
        analyzer = PCRAnalyzer()
        assert analyzer is not None

    def test_pcr_calculation(self):
        """测试PCR计算。"""
        analyzer = PCRAnalyzer()
        pcr = analyzer.calculate_pcr(150, 100)
        assert abs(pcr - 1.5) < 0.001

    def test_pcr_zero_call(self):
        """测试CALL为零时的PCR。"""
        analyzer = PCRAnalyzer()
        pcr = analyzer.calculate_pcr(100, 0)
        assert pcr == 0.0

    def test_interpret_pcr(self):
        """测试PCR解读。"""
        analyzer = PCRAnalyzer()
        assert "看多" in analyzer.interpret_pcr(0.6)
        assert "中性" in analyzer.interpret_pcr(1.0)
        assert "看空" in analyzer.interpret_pcr(1.4)

    def test_calculate_sentiment(self):
        """测试情绪倾向计算。"""
        analyzer = PCRAnalyzer()
        sentiment = analyzer.calculate_sentiment(0.6)
        assert sentiment > 0  # 看多情绪为正

        sentiment = analyzer.calculate_sentiment(1.4)
        assert sentiment < 0  # 看空情绪为负


class TestUnderlyingAnalyzer:
    """标的分析器测试类。"""

    def test_analyzer_creation(self):
        """测试分析器创建。"""
        analyzer = UnderlyingAnalyzer()
        assert analyzer is not None

    def test_analyze_basic(self):
        """测试基本标的分析。"""
        analyzer = UnderlyingAnalyzer()
        options = [
            {
                'symbol': 'IO2504-C-5000',
                'underlying': 'IO2504',
                'call_or_put': 'CALL',
                'strike': 5000,
                'last_price': 100,
                'volume': 1000,
                'open_interest': 5000,
                'pre_oi': 4500,
                'multiplier': 100,
                'expire_days': 30
            },
            {
                'symbol': 'IO2504-P-5000',
                'underlying': 'IO2504',
                'call_or_put': 'PUT',
                'strike': 5000,
                'last_price': 80,
                'volume': 800,
                'open_interest': 4000,
                'pre_oi': 3800,
                'multiplier': 100,
                'expire_days': 30
            }
        ]

        result = analyzer.analyze(options, underlying_price=5100)

        assert result.underlying == 'IO2504'
        assert result.num_contracts == 2
        assert result.total_oi == 9000
        assert result.call_oi == 5000
        assert result.put_oi == 4000
        assert 0 < result.pcr_oi < 1  # PUT < CALL

    def test_empty_options(self):
        """测试空期权列表。"""
        analyzer = UnderlyingAnalyzer()
        result = analyzer.analyze([], underlying_price=5000)
        assert result.underlying == ''


class TestOptionMetrics:
    """期权指标测试类。"""

    def test_metrics_creation(self):
        """测试指标创建。"""
        metrics = OptionMetrics(
            symbol='IO2504-C-5000',
            underlying='IO2504',
            call_or_put=CallOrPut.CALL,
            strike_price=5000.0,
            option_price=100.0,
            underlying_price=5100.0
        )
        assert metrics.symbol == 'IO2504-C-5000'
        assert metrics.intrinsic_degree == 0.0
        assert metrics.intrinsic_level == IntrinsicLevel.ATM_NEAR


class TestAnalyzeSingle:
    """单期权分析测试类。"""

    def test_analyze_single_call(self, sample_options: list[OptionQuote]):
        """测试单个看涨期权分析。"""
        analyzer = OptionAnalyzer()
        option = sample_options[0]  # ITM Call

        metrics = analyzer.analyze_single(
            quote=option,
            future_price=6000.0,
            multiplier=100,
            margin_ratio=15.0,
            expire_days=30
        )

        assert metrics.call_or_put == CallOrPut.CALL
        assert metrics.is_itm is True
        assert metrics.intrinsic_level == IntrinsicLevel.ATM_NEAR  # 3.45% 接近平值
        assert metrics.intrinsic_value == 200.0  # 6000 - 5800
        assert metrics.time_value == 50.0  # 250 - 200

    def test_analyze_single_put(self, sample_options: list[OptionQuote]):
        """测试单个看跌期权分析。"""
        analyzer = OptionAnalyzer()
        option = sample_options[2]  # ITM Put

        metrics = analyzer.analyze_single(
            quote=option,
            future_price=6000.0,
            multiplier=100,
            margin_ratio=15.0,
            expire_days=30
        )

        assert metrics.call_or_put == CallOrPut.PUT
        assert metrics.is_itm is True
        assert metrics.intrinsic_value == 200.0  # 6200 - 6000
        assert metrics.time_value == 20.0  # 220 - 200