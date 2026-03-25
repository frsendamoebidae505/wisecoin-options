# tests/test_evaluator.py
"""策略评估器测试模块。"""
import pytest
from datetime import date

from core.models import OptionQuote, CallOrPut, Signal, AnalyzedOption
from strategy.evaluator import StrategyEvaluator, ScoringFactors


@pytest.fixture
def sample_option_quotes() -> list[OptionQuote]:
    """创建示例期权行情列表。"""
    return [
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
            delta=0.6,
            iv=0.18,
        ),
        OptionQuote(
            symbol="IO2504-C-6000",
            underlying="IO2504",
            exchange_id="CFFEX",
            strike_price=6000.0,
            call_or_put=CallOrPut.CALL,
            last_price=120.0,
            bid_price=118.0,
            ask_price=122.0,
            volume=300,
            open_interest=800,
            expire_date=date(2025, 4, 18),
            delta=0.5,
            iv=0.20,
        ),
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
            delta=0.2,
            iv=0.22,
        ),
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
            delta=-0.1,
            iv=0.19,
        ),
    ]


@pytest.fixture
def analyzed_options(sample_option_quotes: list[OptionQuote]) -> list[AnalyzedOption]:
    """创建分析后的期权列表。"""
    futures_price = 6000.0
    options = []
    for quote in sample_option_quotes:
        # 计算基本属性
        is_itm = quote.is_itm(futures_price)
        leverage = futures_price / quote.last_price * abs(quote.delta or 0.5)

        # 计算时间价值
        if quote.call_or_put == CallOrPut.CALL:
            intrinsic = max(0, futures_price - quote.strike_price)
        else:
            intrinsic = max(0, quote.strike_price - futures_price)
        time_value = quote.last_price - intrinsic

        # 计算价值度
        if quote.call_or_put == CallOrPut.CALL:
            moneyness = futures_price / quote.strike_price
        else:
            moneyness = quote.strike_price / futures_price

        options.append(AnalyzedOption(
            option=quote,
            is_itm=is_itm,
            leverage=leverage,
            time_value=time_value,
            moneyness=moneyness,
            iv=quote.iv,
        ))
    return options


class TestScoringFactors:
    """评分因子配置测试类。"""

    def test_default_factors(self):
        """测试默认因子权重。"""
        factors = ScoringFactors()
        assert factors.iv_weight == 0.25
        assert factors.leverage_weight == 0.20
        assert factors.liquidity_weight == 0.15
        assert factors.time_value_weight == 0.15
        assert factors.moneyness_weight == 0.25

    def test_custom_factors(self):
        """测试自定义因子权重。"""
        factors = ScoringFactors(
            iv_weight=0.3,
            leverage_weight=0.25,
            liquidity_weight=0.1,
            time_value_weight=0.1,
            moneyness_weight=0.25,
        )
        assert factors.iv_weight == 0.3
        assert factors.leverage_weight == 0.25


class TestStrategyEvaluator:
    """策略评估器测试类。"""

    def test_evaluator_creation_default(self):
        """测试使用默认配置创建评估器。"""
        evaluator = StrategyEvaluator()
        assert evaluator.factors is not None
        assert evaluator.factors.iv_weight == 0.25

    def test_evaluator_creation_custom_factors(self):
        """测试使用自定义因子创建评估器。"""
        custom_factors = ScoringFactors(iv_weight=0.4, moneyness_weight=0.1)
        evaluator = StrategyEvaluator(factors=custom_factors)
        assert evaluator.factors.iv_weight == 0.4
        assert evaluator.factors.moneyness_weight == 0.1

    def test_evaluate_returns_sorted_list(self, analyzed_options: list[AnalyzedOption]):
        """测试评估返回排序后的列表（最高分在前）。"""
        evaluator = StrategyEvaluator()
        results = evaluator.evaluate(analyzed_options, iv_reference=0.20)

        # 验证返回了相同数量的期权
        assert len(results) == len(analyzed_options)

        # 验证按分数降序排列
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_evaluate_assigns_scores(self, analyzed_options: list[AnalyzedOption]):
        """测试评估为每个期权分配评分。"""
        evaluator = StrategyEvaluator()
        results = evaluator.evaluate(analyzed_options, iv_reference=0.20)

        for result in results:
            assert result.score >= 0.0
            assert result.score <= 100.0

    def test_evaluate_assigns_signals(self, analyzed_options: list[AnalyzedOption]):
        """测试评估为每个期权分配信号。"""
        evaluator = StrategyEvaluator()
        results = evaluator.evaluate(analyzed_options, iv_reference=0.20)

        for result in results:
            assert result.signal in [Signal.BUY, Signal.SELL, Signal.HOLD]

    def test_empty_list_returns_empty(self):
        """测试空列表返回空结果。"""
        evaluator = StrategyEvaluator()
        results = evaluator.evaluate([], iv_reference=0.20)
        assert results == []


class TestIvScore:
    """IV 因子分数计算测试类。"""

    def test_iv_score_low_iv(self):
        """测试 IV 低于参考值时分数高。"""
        evaluator = StrategyEvaluator()

        # IV 显著偏低（<70%参考值）
        score = evaluator._calculate_iv_score(0.13, 0.20)  # 65% of reference
        assert score == 100.0

        # IV 偏低（约 85%参考值）
        score = evaluator._calculate_iv_score(0.17, 0.20)  # 85% of reference
        assert score == 80.0

    def test_iv_score_high_iv(self):
        """测试 IV 高于参考值时分数低。"""
        evaluator = StrategyEvaluator()

        # IV 偏高
        score = evaluator._calculate_iv_score(0.26, 0.20)
        assert score == 20.0

        # IV 显著偏高
        score = evaluator._calculate_iv_score(0.30, 0.20)
        assert score == 0.0

    def test_iv_score_missing_iv(self):
        """测试缺少 IV 时返回中性分数。"""
        evaluator = StrategyEvaluator()

        score = evaluator._calculate_iv_score(None, 0.20)
        assert score == 50.0

        score = evaluator._calculate_iv_score(0.20, None)
        assert score == 50.0

    def test_iv_score_invalid_reference(self):
        """测试无效参考值时返回中性分数。"""
        evaluator = StrategyEvaluator()

        score = evaluator._calculate_iv_score(0.20, 0.0)
        assert score == 50.0

        score = evaluator._calculate_iv_score(0.20, -0.1)
        assert score == 50.0


class TestLeverageScore:
    """杠杆因子分数计算测试类。"""

    def test_leverage_score_optimal_range(self):
        """测试杠杆在最佳区间分数高。"""
        evaluator = StrategyEvaluator()

        # 杠杆在 10-50 区间
        score = evaluator._calculate_leverage_score(20.0)
        assert score >= 60.0
        assert score <= 100.0

        score = evaluator._calculate_leverage_score(30.0)
        assert score >= 60.0
        assert score <= 100.0

    def test_leverage_score_low_leverage(self):
        """测试杠杆过低时分数低。"""
        evaluator = StrategyEvaluator()

        score = evaluator._calculate_leverage_score(2.0)
        assert score < 20.0

        score = evaluator._calculate_leverage_score(0.0)
        assert score == 0.0

    def test_leverage_score_high_leverage(self):
        """测试杠杆过高时分数降低。"""
        evaluator = StrategyEvaluator()

        # 杠杆在 50-100 区间
        score = evaluator._calculate_leverage_score(75.0)
        assert score < 100.0
        assert score > 0.0

        # 杠杆过高
        score = evaluator._calculate_leverage_score(150.0)
        assert score < 40.0


class TestLiquidityScore:
    """流动性因子分数计算测试类。"""

    def test_high_liquidity(self):
        """测试高流动性分数高。"""
        evaluator = StrategyEvaluator()

        score = evaluator._calculate_liquidity_score(500, 1000)
        assert score == 100.0

        score = evaluator._calculate_liquidity_score(300, 800)
        assert score > 70.0

    def test_low_liquidity(self):
        """测试低流动性分数低。"""
        evaluator = StrategyEvaluator()

        score = evaluator._calculate_liquidity_score(10, 50)
        assert score < 20.0

    def test_medium_liquidity(self):
        """测试中等流动性分数中等。"""
        evaluator = StrategyEvaluator()

        score = evaluator._calculate_liquidity_score(100, 200)
        assert score >= 30.0
        assert score <= 70.0


class TestTimeValueScore:
    """时间价值因子分数计算测试类。"""

    def test_low_time_value_ratio(self):
        """测试时间价值占比低时分数高。"""
        evaluator = StrategyEvaluator()

        # 时间价值占比 10%
        score = evaluator._calculate_time_value_score(10.0, 100.0)
        assert score >= 80.0

        # 时间价值占比 20%
        score = evaluator._calculate_time_value_score(20.0, 100.0)
        assert score >= 70.0

    def test_high_time_value_ratio(self):
        """测试时间价值占比高时分数低。"""
        evaluator = StrategyEvaluator()

        # 时间价值占比 90%
        score = evaluator._calculate_time_value_score(90.0, 100.0)
        assert score < 30.0

    def test_zero_option_price(self):
        """测试期权价格为零时的处理。"""
        evaluator = StrategyEvaluator()

        score = evaluator._calculate_time_value_score(10.0, 0.0)
        assert score == 50.0


class TestMoneynessScore:
    """价值度因子分数计算测试类。"""

    def test_atm_score_high(self):
        """测试平值期权分数高。"""
        evaluator = StrategyEvaluator()

        # 完全平值
        score = evaluator._calculate_moneyness_score(1.0, True)
        assert score == 100.0

        # 接近平值
        score = evaluator._calculate_moneyness_score(1.01, True)
        assert score >= 90.0

    def test_otm_itm_score_lower(self):
        """测试虚值/实值期权分数较低。"""
        evaluator = StrategyEvaluator()

        # 深度实值 Call
        score = evaluator._calculate_moneyness_score(1.3, True)
        assert score < 50.0

        # 深度虚值 Call
        score = evaluator._calculate_moneyness_score(0.7, True)
        assert score < 50.0

    def test_moneyness_for_put(self):
        """测试 Put 的价值度计算。"""
        evaluator = StrategyEvaluator()

        # 平值 Put
        score = evaluator._calculate_moneyness_score(1.0, False)
        assert score == 100.0

    def test_invalid_moneyness(self):
        """测试无效价值度的处理。"""
        evaluator = StrategyEvaluator()

        score = evaluator._calculate_moneyness_score(0.0, True)
        assert score == 0.0

        score = evaluator._calculate_moneyness_score(-1.0, True)
        assert score == 0.0


class TestSignalDetermination:
    """信号确定测试类。"""

    def test_buy_signal(self):
        """测试买入信号（分数 > 70）。"""
        evaluator = StrategyEvaluator()

        signal = evaluator._determine_signal(80.0)
        assert signal == Signal.BUY

        signal = evaluator._determine_signal(100.0)
        assert signal == Signal.BUY

        signal = evaluator._determine_signal(71.0)
        assert signal == Signal.BUY

    def test_sell_signal(self):
        """测试卖出信号（分数 < 30）。"""
        evaluator = StrategyEvaluator()

        signal = evaluator._determine_signal(20.0)
        assert signal == Signal.SELL

        signal = evaluator._determine_signal(0.0)
        assert signal == Signal.SELL

        signal = evaluator._determine_signal(29.0)
        assert signal == Signal.SELL

    def test_hold_signal(self):
        """测试持有信号（30 <= 分数 <= 70）。"""
        evaluator = StrategyEvaluator()

        signal = evaluator._determine_signal(50.0)
        assert signal == Signal.HOLD

        signal = evaluator._determine_signal(30.0)
        assert signal == Signal.HOLD

        signal = evaluator._determine_signal(70.0)
        assert signal == Signal.HOLD

    def test_boundary_values(self):
        """测试边界值。"""
        evaluator = StrategyEvaluator()

        # 70 应该是 HOLD（不是 > 70）
        signal = evaluator._determine_signal(70.0)
        assert signal == Signal.HOLD

        # 30 应该是 HOLD（不是 < 30）
        signal = evaluator._determine_signal(30.0)
        assert signal == Signal.HOLD

        # 69.99 应该是 HOLD
        signal = evaluator._determine_signal(70.01)
        assert signal == Signal.BUY

        # 29.99 应该是 SELL
        signal = evaluator._determine_signal(29.99)
        assert signal == Signal.SELL


class TestEdgeCases:
    """边缘情况测试类。"""

    def test_evaluate_without_iv_reference(self, analyzed_options: list[AnalyzedOption]):
        """测试没有 IV 参考值时的评估。"""
        evaluator = StrategyEvaluator()
        results = evaluator.evaluate(analyzed_options, iv_reference=None)

        # 应该仍然返回结果
        assert len(results) == len(analyzed_options)

        # 分数应该有效
        for result in results:
            assert result.score >= 0.0
            assert result.score <= 100.0

    def test_evaluate_with_custom_weights(self, analyzed_options: list[AnalyzedOption]):
        """测试使用自定义权重的评估。"""
        # 大幅增加 IV 权重
        factors = ScoringFactors(
            iv_weight=0.6,
            leverage_weight=0.1,
            liquidity_weight=0.1,
            time_value_weight=0.1,
            moneyness_weight=0.1,
        )
        evaluator = StrategyEvaluator(factors=factors)
        results = evaluator.evaluate(analyzed_options, iv_reference=0.20)

        assert len(results) == len(analyzed_options)

    def test_single_option(self, analyzed_options: list[AnalyzedOption]):
        """测试单个期权的评估。"""
        evaluator = StrategyEvaluator()
        single_option = [analyzed_options[0]]
        results = evaluator.evaluate(single_option, iv_reference=0.20)

        assert len(results) == 1
        assert results[0].score >= 0.0
        assert results[0].signal in [Signal.BUY, Signal.SELL, Signal.HOLD]

    def test_all_options_have_same_score(self, sample_option_quotes: list[OptionQuote]):
        """测试所有期权分数相同时的排序。"""
        evaluator = StrategyEvaluator()

        # 创建分数可能相同的期权
        analyzed = []
        for quote in sample_option_quotes:
            analyzed.append(AnalyzedOption(
                option=quote,
                is_itm=True,
                leverage=20.0,  # 相同杠杆
                time_value=50.0,  # 相同时间价值
                moneyness=1.0,  # 相同价值度
                iv=0.20,  # 相同 IV
            ))

        results = evaluator.evaluate(analyzed, iv_reference=0.20)

        # 应该返回相同数量的期权
        assert len(results) == len(analyzed)