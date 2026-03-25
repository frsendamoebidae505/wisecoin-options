# tests/test_oneclick.py
"""一键分析模块测试"""
import pytest
from datetime import date
from typing import List

from cli.oneclick import OneClickAnalyzer, AnalysisResult
from core.models import OptionQuote, CallOrPut, Signal, AnalyzedOption
from common.logger import StructuredLogger


@pytest.fixture
def sample_options() -> List[OptionQuote]:
    """创建示例期权行情"""
    return [
        OptionQuote(
            symbol="SHFE.au2506C480",
            underlying="SHFE.au2506",
            exchange_id="SHFE",
            strike_price=480.0,
            call_or_put=CallOrPut.CALL,
            last_price=15.0,
            bid_price=14.5,
            ask_price=15.5,
            volume=100,
            open_interest=500,
            expire_date=date(2025, 6, 15),
            instrument_name="au2506C480",
            delta=0.5,
        ),
        OptionQuote(
            symbol="SHFE.au2506C500",
            underlying="SHFE.au2506",
            exchange_id="SHFE",
            strike_price=500.0,
            call_or_put=CallOrPut.CALL,
            last_price=10.0,
            bid_price=9.5,
            ask_price=10.5,
            volume=200,
            open_interest=800,
            expire_date=date(2025, 6, 15),
            instrument_name="au2506C500",
            delta=0.4,
        ),
        OptionQuote(
            symbol="SHFE.au2506P480",
            underlying="SHFE.au2506",
            exchange_id="SHFE",
            strike_price=480.0,
            call_or_put=CallOrPut.PUT,
            last_price=8.0,
            bid_price=7.5,
            ask_price=8.5,
            volume=150,
            open_interest=600,
            expire_date=date(2025, 6, 15),
            instrument_name="au2506P480",
            delta=-0.4,
        ),
        OptionQuote(
            symbol="SHFE.au2506P500",
            underlying="SHFE.au2506",
            exchange_id="SHFE",
            strike_price=500.0,
            call_or_put=CallOrPut.PUT,
            last_price=12.0,
            bid_price=11.5,
            ask_price=12.5,
            volume=80,
            open_interest=400,
            expire_date=date(2025, 6, 15),
            instrument_name="au2506P500",
            delta=-0.5,
        ),
    ]


@pytest.fixture
def futures_prices() -> dict:
    """创建示例期货价格映射"""
    return {
        "SHFE.au2506": 490.0,
    }


class TestOneClickAnalyzer:
    """一键分析器测试"""

    def test_create_analyzer(self):
        """测试创建分析器"""
        analyzer = OneClickAnalyzer()
        assert analyzer is not None
        assert analyzer.option_analyzer is not None
        assert analyzer.iv_calculator is not None
        assert analyzer.evaluator is not None
        assert analyzer.signal_generator is not None

    def test_create_analyzer_with_logger(self):
        """测试使用自定义日志器创建分析器"""
        logger = StructuredLogger("custom")
        analyzer = OneClickAnalyzer(logger=logger)
        assert analyzer.logger is logger

    def test_run_analysis(self, sample_options, futures_prices):
        """测试运行分析"""
        analyzer = OneClickAnalyzer()
        result = analyzer.run(sample_options, futures_prices)

        assert result is not None
        assert isinstance(result, AnalysisResult)
        assert result.total_options == 4
        assert len(result.analyzed_options) > 0
        assert result.timestamp is not None

    def test_analysis_result_properties(self, sample_options, futures_prices):
        """测试分析结果属性"""
        analyzer = OneClickAnalyzer()
        result = analyzer.run(sample_options, futures_prices)

        # 验证 buy_count 和 sell_count 属性
        buy_count = result.buy_count
        sell_count = result.sell_count

        assert isinstance(buy_count, int)
        assert isinstance(sell_count, int)
        assert buy_count >= 0
        assert sell_count >= 0

    def test_analysis_summary(self, sample_options, futures_prices):
        """测试分析结果摘要"""
        analyzer = OneClickAnalyzer()
        result = analyzer.run(sample_options, futures_prices)

        assert 'total_options' in result.summary
        assert 'analyzed_count' in result.summary
        assert 'avg_score' in result.summary
        assert 'max_score' in result.summary
        assert 'signal_count' in result.summary

        assert result.summary['total_options'] == 4
        assert result.summary['analyzed_count'] > 0

    def test_quick_analysis(self, sample_options, futures_prices):
        """测试快速分析"""
        analyzer = OneClickAnalyzer()
        top_n = 2
        results = analyzer.run_quick(sample_options, futures_prices, top_n=top_n)

        assert isinstance(results, list)
        assert len(results) <= top_n
        assert all(isinstance(r, AnalyzedOption) for r in results)

        # 验证结果是按评分排序的
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    def test_empty_options(self, futures_prices):
        """测试空期权列表"""
        analyzer = OneClickAnalyzer()
        result = analyzer.run([], futures_prices)

        assert result.total_options == 0
        assert len(result.analyzed_options) == 0
        assert len(result.top_signals) == 0
        assert result.buy_count == 0
        assert result.sell_count == 0

    def test_iv_calculation_integration(self, sample_options, futures_prices):
        """测试 IV 计算集成"""
        analyzer = OneClickAnalyzer()
        result = analyzer.run(sample_options, futures_prices)

        # 检查 IV 是否被计算
        for analyzed in result.analyzed_options:
            # IV 可能为 None（如果计算失败）或为 float
            if analyzed.iv is not None:
                assert isinstance(analyzed.iv, float)
                assert analyzed.iv > 0

    def test_signal_generation_integration(self, sample_options, futures_prices):
        """测试信号生成集成"""
        analyzer = OneClickAnalyzer()
        result = analyzer.run(sample_options, futures_prices)

        # 检查信号是否正确生成
        for analyzed in result.analyzed_options:
            assert analyzed.signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
            assert analyzed.score >= 0

    def test_top_signals_structure(self, sample_options, futures_prices):
        """测试顶部信号结构"""
        analyzer = OneClickAnalyzer()
        result = analyzer.run(sample_options, futures_prices)

        for signal in result.top_signals:
            assert 'symbol' in signal
            assert 'direction' in signal
            assert 'volume' in signal
            assert 'price' in signal
            assert 'score' in signal
            assert 'reasons' in signal

    def test_with_iv_reference(self, sample_options, futures_prices):
        """测试使用 IV 参考值"""
        analyzer = OneClickAnalyzer()
        iv_reference = 0.25  # 25% IV
        result = analyzer.run(sample_options, futures_prices, iv_reference=iv_reference)

        assert result is not None
        assert len(result.analyzed_options) > 0

    def test_missing_underlying_price(self, sample_options):
        """测试缺少标的价格的情况"""
        analyzer = OneClickAnalyzer()
        # 空的期货价格映射
        result = analyzer.run(sample_options, {})

        # 应该返回空结果，因为没有找到对应的期货价格
        assert len(result.analyzed_options) == 0

    def test_multiple_underlyings(self):
        """测试多个标的情况"""
        options = [
            OptionQuote(
                symbol="SHFE.au2506C480",
                underlying="SHFE.au2506",
                exchange_id="SHFE",
                strike_price=480.0,
                call_or_put=CallOrPut.CALL,
                last_price=15.0,
                bid_price=14.5,
                ask_price=15.5,
                volume=100,
                open_interest=500,
                expire_date=date(2025, 6, 15),
            ),
            OptionQuote(
                symbol="SHFE.ag2506C5000",
                underlying="SHFE.ag2506",
                exchange_id="SHFE",
                strike_price=5000.0,
                call_or_put=CallOrPut.CALL,
                last_price=100.0,
                bid_price=99.0,
                ask_price=101.0,
                volume=50,
                open_interest=300,
                expire_date=date(2025, 6, 15),
            ),
        ]
        futures_prices = {
            "SHFE.au2506": 490.0,
            "SHFE.ag2506": 5100.0,
        }

        analyzer = OneClickAnalyzer()
        result = analyzer.run(options, futures_prices)

        assert len(result.analyzed_options) == 2