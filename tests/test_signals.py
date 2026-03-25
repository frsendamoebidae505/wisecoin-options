# tests/test_signals.py
"""交易信号生成模块测试"""
import pytest
from datetime import date

from strategy.signals import SignalGenerator
from core.models import (
    AnalyzedOption,
    OptionQuote,
    Signal,
    CallOrPut,
)


@pytest.fixture
def sample_option_quote() -> OptionQuote:
    """创建示例期权行情"""
    return OptionQuote(
        symbol="IO2504C4100",
        underlying="IF2504",
        exchange_id="CFFEX",
        strike_price=4100.0,
        call_or_put=CallOrPut.CALL,
        last_price=85.6,
        bid_price=85.4,
        ask_price=85.8,
        volume=1000,
        open_interest=5000,
        expire_date=date(2025, 4, 19),
        instrument_name="IO2504C4100",
    )


@pytest.fixture
def sample_analyzed_option_high_score(sample_option_quote) -> AnalyzedOption:
    """创建高评分分析期权"""
    return AnalyzedOption(
        option=sample_option_quote,
        is_itm=True,
        leverage=5.2,
        time_value=12.5,
        moneyness=0.95,
        iv=18.5,
        score=92.0,
        signal=Signal.BUY,
        reasons=["高杠杆", "低IV", "实值"],
    )


@pytest.fixture
def sample_analyzed_option_medium_score(sample_option_quote) -> AnalyzedOption:
    """创建中等评分分析期权（低于默认买入阈值）"""
    return AnalyzedOption(
        option=sample_option_quote,
        is_itm=False,
        leverage=3.1,
        time_value=8.3,
        moneyness=1.05,
        iv=22.0,
        score=65.0,  # 低于默认买入阈值70
        signal=Signal.HOLD,
        reasons=["中等杠杆"],
    )


@pytest.fixture
def sample_analyzed_option_low_score(sample_option_quote) -> AnalyzedOption:
    """创建低评分分析期权"""
    return AnalyzedOption(
        option=sample_option_quote,
        is_itm=False,
        leverage=1.2,
        time_value=3.5,
        moneyness=1.15,
        iv=35.0,
        score=25.0,
        signal=Signal.SELL,
        reasons=["低杠杆", "高IV"],
    )


@pytest.fixture
def sample_positions() -> list:
    """创建示例持仓"""
    return [
        {"symbol": "IO2504C4100", "volume": 3, "avg_price": 80.0},
        {"symbol": "IO2504P4000", "volume": 5, "avg_price": 45.0},
    ]


class TestSignalGeneratorCreation:
    """信号生成器创建测试"""

    def test_create_with_defaults(self):
        """测试使用默认参数创建"""
        generator = SignalGenerator()
        assert generator.max_position_per_symbol == 10
        assert generator.min_score_to_buy == 70.0
        assert generator.max_score_to_sell == 30.0

    def test_create_with_custom_parameters(self):
        """测试使用自定义参数创建"""
        generator = SignalGenerator(
            max_position_per_symbol=20,
            min_score_to_buy=80.0,
            max_score_to_sell=20.0,
        )
        assert generator.max_position_per_symbol == 20
        assert generator.min_score_to_buy == 80.0
        assert generator.max_score_to_sell == 20.0


class TestSignalGeneration:
    """信号生成测试"""

    def test_generate_buy_signal_high_score(self, sample_analyzed_option_high_score):
        """测试高评分期权生成买入信号"""
        generator = SignalGenerator()
        signals = generator.generate([sample_analyzed_option_high_score])

        assert len(signals) == 1
        assert signals[0].symbol == "IO2504C4100"
        assert signals[0].direction == "BUY"
        assert signals[0].volume > 0
        assert signals[0].price == 85.8  # ask_price
        assert signals[0].score == 92.0
        assert signals[0].strategy_type == "评分买入"

    def test_no_signal_low_score(self, sample_analyzed_option_low_score):
        """测试低评分期权不生成信号"""
        generator = SignalGenerator()
        signals = generator.generate([sample_analyzed_option_low_score])

        assert len(signals) == 0

    def test_medium_score_below_threshold(self, sample_analyzed_option_medium_score):
        """测试中等评分（低于买入阈值）不生成信号"""
        generator = SignalGenerator(min_score_to_buy=80.0)
        signals = generator.generate([sample_analyzed_option_medium_score])

        assert len(signals) == 0

    def test_multiple_options_mixed_scores(
        self,
        sample_analyzed_option_high_score,
        sample_analyzed_option_medium_score,
        sample_analyzed_option_low_score,
    ):
        """测试多个混合评分的期权"""
        generator = SignalGenerator()
        signals = generator.generate([
            sample_analyzed_option_high_score,
            sample_analyzed_option_medium_score,
            sample_analyzed_option_low_score,
        ])

        # 只有高评分的生成信号
        assert len(signals) == 1
        assert signals[0].score >= 70.0

    def test_empty_analyzed_options(self):
        """测试空输入"""
        generator = SignalGenerator()
        signals = generator.generate([])

        assert len(signals) == 0

    def test_with_current_positions(self, sample_analyzed_option_high_score, sample_positions):
        """测试有持仓时的信号生成"""
        generator = SignalGenerator()
        signals = generator.generate(
            [sample_analyzed_option_high_score],
            current_positions=sample_positions,
        )

        # 已有3手，最大10手，还能买7手，高评分买5手
        assert len(signals) == 1
        assert signals[0].volume == 5


class TestPositionLimit:
    """持仓限制测试"""

    def test_position_at_limit(self, sample_analyzed_option_high_score):
        """测试持仓已达上限"""
        generator = SignalGenerator(max_position_per_symbol=10)
        positions = [{"symbol": "IO2504C4100", "volume": 10}]

        signals = generator.generate(
            [sample_analyzed_option_high_score],
            current_positions=positions,
        )

        assert len(signals) == 0

    def test_position_near_limit(self, sample_analyzed_option_high_score):
        """测试持仓接近上限"""
        generator = SignalGenerator(max_position_per_symbol=10)
        positions = [{"symbol": "IO2504C4100", "volume": 8}]

        signals = generator.generate(
            [sample_analyzed_option_high_score],
            current_positions=positions,
        )

        # 剩余2手，高评分买5手但只能买2手
        assert len(signals) == 1
        assert signals[0].volume == 2

    def test_no_current_positions(self, sample_analyzed_option_high_score):
        """测试无当前持仓"""
        generator = SignalGenerator()

        signals = generator.generate(
            [sample_analyzed_option_high_score],
            current_positions=None,
        )

        assert len(signals) == 1
        assert signals[0].volume == 5  # 高评分买5手


class TestExitSignalGeneration:
    """平仓信号生成测试"""

    def test_generate_exit_signal_low_score(self, sample_analyzed_option_low_score, sample_positions):
        """测试低评分持仓生成平仓信号"""
        generator = SignalGenerator()
        signals = generator.generate_exit_signals(
            [sample_analyzed_option_low_score],
            sample_positions,
        )

        assert len(signals) == 1
        assert signals[0].symbol == "IO2504C4100"
        assert signals[0].direction == "SELL"
        assert signals[0].volume == 3  # 持仓数量
        assert signals[0].price == 85.4  # bid_price
        assert signals[0].strategy_type == "评分卖出"

    def test_no_exit_signal_high_score(self, sample_analyzed_option_high_score, sample_positions):
        """测试高评分持仓不生成平仓信号"""
        generator = SignalGenerator()
        signals = generator.generate_exit_signals(
            [sample_analyzed_option_high_score],
            sample_positions,
        )

        assert len(signals) == 0

    def test_no_exit_signal_for_non_position(self, sample_analyzed_option_low_score):
        """测试非持仓期权不生成平仓信号"""
        generator = SignalGenerator()
        positions = [{"symbol": "IO2504P4000", "volume": 5}]

        signals = generator.generate_exit_signals(
            [sample_analyzed_option_low_score],
            positions,
        )

        assert len(signals) == 0

    def test_exit_signal_custom_threshold(self, sample_analyzed_option_medium_score, sample_positions):
        """测试自定义卖出阈值"""
        generator = SignalGenerator(max_score_to_sell=80.0)
        signals = generator.generate_exit_signals(
            [sample_analyzed_option_medium_score],
            sample_positions,
        )

        # 评分75低于阈值80，应生成卖出信号
        assert len(signals) == 1
        assert signals[0].direction == "SELL"

    def test_empty_positions_for_exit(self, sample_analyzed_option_low_score):
        """测试空持仓列表"""
        generator = SignalGenerator()
        signals = generator.generate_exit_signals(
            [sample_analyzed_option_low_score],
            [],
        )

        assert len(signals) == 0


class TestVolumeCalculation:
    """数量计算测试"""

    @pytest.fixture
    def generator(self):
        return SignalGenerator()

    @pytest.fixture
    def make_analyzed_option(self, sample_option_quote):
        """创建指定评分的分析期权"""
        def _make(score: float) -> AnalyzedOption:
            return AnalyzedOption(
                option=sample_option_quote,
                is_itm=True,
                leverage=3.0,
                time_value=10.0,
                moneyness=1.0,
                score=score,
                signal=Signal.BUY,
                reasons=["测试"],
            )
        return _make

    def test_volume_score_90_plus(self, generator, make_analyzed_option):
        """测试评分90+的数量"""
        analyzed = make_analyzed_option(95.0)
        volume = generator._calculate_volume(analyzed, 0)
        assert volume == 5

    def test_volume_score_80_to_89(self, generator, make_analyzed_option):
        """测试评分80-89的数量"""
        analyzed = make_analyzed_option(85.0)
        volume = generator._calculate_volume(analyzed, 0)
        assert volume == 3

    def test_volume_score_70_to_79(self, generator, make_analyzed_option):
        """测试评分70-79的数量"""
        analyzed = make_analyzed_option(72.0)
        volume = generator._calculate_volume(analyzed, 0)
        assert volume == 2

    def test_volume_score_below_70(self, generator, make_analyzed_option):
        """测试评分70以下的数量"""
        analyzed = make_analyzed_option(65.0)
        volume = generator._calculate_volume(analyzed, 0)
        assert volume == 1

    def test_volume_respects_remaining_capacity(self, generator, make_analyzed_option):
        """测试数量受剩余容量限制"""
        analyzed = make_analyzed_option(95.0)  # 正常买5手
        volume = generator._calculate_volume(analyzed, 8)  # 已有8手，剩2手
        assert volume == 2

    def test_volume_zero_when_full(self, generator, make_analyzed_option):
        """测试满仓时返回0"""
        analyzed = make_analyzed_option(95.0)
        volume = generator._calculate_volume(analyzed, 10)
        assert volume == 0

    def test_volume_zero_when_exceeded(self, generator, make_analyzed_option):
        """测试超仓时返回0"""
        analyzed = make_analyzed_option(95.0)
        volume = generator._calculate_volume(analyzed, 15)
        assert volume == 0


class TestSignalReasons:
    """信号原因测试"""

    def test_buy_signal_preserves_reasons(self, sample_analyzed_option_high_score):
        """测试买入信号保留原始原因"""
        generator = SignalGenerator()
        signals = generator.generate([sample_analyzed_option_high_score])

        assert len(signals) == 1
        assert signals[0].reasons == ["高杠杆", "低IV", "实值"]

    def test_exit_signal_includes_score_reason(self, sample_analyzed_option_low_score, sample_positions):
        """测试平仓信号包含评分原因"""
        generator = SignalGenerator()
        signals = generator.generate_exit_signals(
            [sample_analyzed_option_low_score],
            sample_positions,
        )

        assert len(signals) == 1
        assert "评分过低: 25.0" in signals[0].reasons