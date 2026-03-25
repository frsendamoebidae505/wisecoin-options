# tests/test_arbitrage.py
"""套利检测模块测试"""
import pytest
from datetime import date, timedelta

from core.models import OptionQuote, CallOrPut, ArbitrageOpportunity
from strategy.arbitrage import ArbitrageDetector


class TestArbitrageDetector:
    """套利检测器测试"""

    @pytest.fixture
    def detector(self):
        """创建默认检测器"""
        return ArbitrageDetector()

    @pytest.fixture
    def detector_custom_thresholds(self):
        """创建自定义阈值的检测器"""
        return ArbitrageDetector(min_profit_threshold=5.0, min_confidence=0.5)

    @pytest.fixture
    def sample_options(self):
        """创建样本期权列表（包含 CALL 和 PUT）"""
        expire_date = date.today() + timedelta(days=30)
        underlying = "IO2504"
        exchange_id = "CFFEX"

        options = [
            # 行权价 3800 的 CALL
            OptionQuote(
                symbol="IO2504-C-3800",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3800.0,
                call_or_put=CallOrPut.CALL,
                last_price=120.0,
                bid_price=119.0,
                ask_price=121.0,
                volume=1000,
                open_interest=5000,
                expire_date=expire_date,
                iv=0.18,
            ),
            # 行权价 3800 的 PUT
            OptionQuote(
                symbol="IO2504-P-3800",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3800.0,
                call_or_put=CallOrPut.PUT,
                last_price=80.0,
                bid_price=79.0,
                ask_price=81.0,
                volume=800,
                open_interest=4500,
                expire_date=expire_date,
                iv=0.17,
            ),
            # 行权价 3900 的 CALL
            OptionQuote(
                symbol="IO2504-C-3900",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3900.0,
                call_or_put=CallOrPut.CALL,
                last_price=70.0,
                bid_price=69.0,
                ask_price=71.0,
                volume=1200,
                open_interest=6000,
                expire_date=expire_date,
                iv=0.19,
            ),
            # 行权价 3900 的 PUT
            OptionQuote(
                symbol="IO2504-P-3900",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3900.0,
                call_or_put=CallOrPut.PUT,
                last_price=130.0,
                bid_price=129.0,
                ask_price=131.0,
                volume=900,
                open_interest=4800,
                expire_date=expire_date,
                iv=0.18,
            ),
            # 行权价 4000 的 CALL
            OptionQuote(
                symbol="IO2504-C-4000",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=4000.0,
                call_or_put=CallOrPut.CALL,
                last_price=35.0,
                bid_price=34.0,
                ask_price=36.0,
                volume=1500,
                open_interest=7000,
                expire_date=expire_date,
                iv=0.20,
            ),
            # 行权价 4000 的 PUT
            OptionQuote(
                symbol="IO2504-P-4000",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=4000.0,
                call_or_put=CallOrPut.PUT,
                last_price=195.0,
                bid_price=194.0,
                ask_price=196.0,
                volume=1100,
                open_interest=5500,
                expire_date=expire_date,
                iv=0.19,
            ),
        ]
        return options

    @pytest.fixture
    def options_with_high_iv(self):
        """创建高 IV 期权列表（用于跨式套利测试）"""
        expire_date = date.today() + timedelta(days=30)
        underlying = "IO2504"
        exchange_id = "CFFEX"

        options = [
            # 行权价 3850 的 CALL（高 IV）
            OptionQuote(
                symbol="IO2504-C-3850",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3850.0,
                call_or_put=CallOrPut.CALL,
                last_price=200.0,
                bid_price=198.0,
                ask_price=202.0,
                volume=1000,
                open_interest=5000,
                expire_date=expire_date,
                iv=0.35,  # 高 IV
            ),
            # 行权价 3850 的 PUT（高 IV）
            OptionQuote(
                symbol="IO2504-P-3850",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3850.0,
                call_or_put=CallOrPut.PUT,
                last_price=180.0,
                bid_price=178.0,
                ask_price=182.0,
                volume=800,
                open_interest=4500,
                expire_date=expire_date,
                iv=0.38,  # 高 IV
            ),
        ]
        return options

    @pytest.fixture
    def options_with_low_iv(self):
        """创建低 IV 期权列表（用于跨式套利测试）"""
        expire_date = date.today() + timedelta(days=30)
        underlying = "IO2504"
        exchange_id = "CFFEX"

        options = [
            # 行权价 3850 的 CALL（低 IV）
            OptionQuote(
                symbol="IO2504-C-3850",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3850.0,
                call_or_put=CallOrPut.CALL,
                last_price=50.0,
                bid_price=49.0,
                ask_price=51.0,
                volume=1000,
                open_interest=5000,
                expire_date=expire_date,
                iv=0.08,  # 低 IV
            ),
            # 行权价 3850 的 PUT（低 IV）
            OptionQuote(
                symbol="IO2504-P-3850",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3850.0,
                call_or_put=CallOrPut.PUT,
                last_price=45.0,
                bid_price=44.0,
                ask_price=46.0,
                volume=800,
                open_interest=4500,
                expire_date=expire_date,
                iv=0.07,  # 低 IV
            ),
        ]
        return options

    def test_create_detector_with_defaults(self, detector):
        """测试使用默认参数创建检测器"""
        assert detector is not None
        assert detector.min_profit_threshold == 10.0
        assert detector.min_confidence == 0.7

    def test_create_detector_with_custom_thresholds(self, detector_custom_thresholds):
        """测试使用自定义阈值创建检测器"""
        assert detector_custom_thresholds.min_profit_threshold == 5.0
        assert detector_custom_thresholds.min_confidence == 0.5

    def test_detect_conversion_arbitrage(self, detector, sample_options):
        """测试转换套利检测"""
        # 设置期货价格使其存在套利机会
        # 行权价 3800: Call ~120, Put ~80
        # Call - Put = 40
        # Future - Strike = 3850 - 3800 = 50
        # 利润 = 40 - 50 = -10 (无套利)
        #
        # 使用 Future = 3820
        # 行权价 3800: Call - Put = 40, Future - Strike = 20, 利润 = 20
        future_price = 3820.0

        opportunities = detector.detect(sample_options, future_price)

        # 应检测到转换套利机会
        conversion_opps = [o for o in opportunities if o.opportunity_type == 'CONVERSION']
        assert len(conversion_opps) > 0

        # 验证套利机会属性
        opp = conversion_opps[0]
        assert opp.opportunity_type == 'CONVERSION'
        assert opp.expected_profit > detector.min_profit_threshold
        assert opp.risk_level == 'LOW'
        assert opp.confidence >= detector.min_confidence
        assert len(opp.legs) == 3  # SELL CALL, BUY PUT, BUY FUTURE

    def test_detect_reverse_conversion_arbitrage(self, detector):
        """测试反向转换套利检测"""
        expire_date = date.today() + timedelta(days=30)
        underlying = "IO2504"
        exchange_id = "CFFEX"

        # 创建 Put 价格高于 Call 的情况（反向套利机会）
        options = [
            OptionQuote(
                symbol="IO2504-C-3800",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3800.0,
                call_or_put=CallOrPut.CALL,
                last_price=50.0,
                bid_price=49.0,
                ask_price=51.0,
                volume=1000,
                open_interest=5000,
                expire_date=expire_date,
                iv=0.15,
            ),
            OptionQuote(
                symbol="IO2504-P-3800",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3800.0,
                call_or_put=CallOrPut.PUT,
                last_price=120.0,
                bid_price=119.0,
                ask_price=121.0,
                volume=800,
                open_interest=4500,
                expire_date=expire_date,
                iv=0.25,
            ),
        ]

        # Future = 3850, Strike = 3800
        # Put - Call = 120 - 50 = 70
        # Strike - Future = 3800 - 3850 = -50
        # 利润 = 70 - (-50) = 120 (巨大套利机会)
        future_price = 3850.0

        opportunities = detector.detect(options, future_price)

        reverse_opps = [o for o in opportunities if o.opportunity_type == 'REVERSE_CONVERSION']
        assert len(reverse_opps) > 0

        opp = reverse_opps[0]
        assert opp.opportunity_type == 'REVERSE_CONVERSION'
        assert opp.expected_profit > 0
        assert opp.risk_level == 'LOW'

    def test_detect_straddle_arbitrage_high_iv(self, detector_custom_thresholds, options_with_high_iv):
        """检测高 IV 时的跨式套利机会"""
        future_price = 3850.0  # 接近行权价

        opportunities = detector_custom_thresholds.detect(options_with_high_iv, future_price)

        # 应检测到卖出跨式机会
        straddle_opps = [o for o in opportunities if o.opportunity_type == 'SHORT_STRADDLE']
        assert len(straddle_opps) > 0

        opp = straddle_opps[0]
        assert opp.opportunity_type == 'SHORT_STRADDLE'
        assert opp.risk_level == 'HIGH'
        assert len(opp.legs) == 2  # SELL CALL, SELL PUT

    def test_detect_straddle_arbitrage_low_iv(self, detector_custom_thresholds, options_with_low_iv):
        """检测低 IV 时的跨式套利机会"""
        future_price = 3850.0  # 接近行权价

        opportunities = detector_custom_thresholds.detect(options_with_low_iv, future_price)

        # 应检测到买入跨式机会
        straddle_opps = [o for o in opportunities if o.opportunity_type == 'LONG_STRADDLE']
        assert len(straddle_opps) > 0

        opp = straddle_opps[0]
        assert opp.opportunity_type == 'LONG_STRADDLE'
        assert opp.risk_level == 'MEDIUM'
        assert len(opp.legs) == 2  # BUY CALL, BUY PUT

    def test_no_opportunities_when_none_exist(self, detector):
        """测试无套利机会时的返回结果"""
        expire_date = date.today() + timedelta(days=30)
        underlying = "IO2504"
        exchange_id = "CFFEX"

        # 创建价格合理的期权（无套利空间）
        options = [
            OptionQuote(
                symbol="IO2504-C-3800",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3800.0,
                call_or_put=CallOrPut.CALL,
                last_price=100.0,
                bid_price=99.0,
                ask_price=101.0,
                volume=1000,
                open_interest=5000,
                expire_date=expire_date,
                iv=0.18,
            ),
            OptionQuote(
                symbol="IO2504-P-3800",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3800.0,
                call_or_put=CallOrPut.PUT,
                last_price=100.0,
                bid_price=99.0,
                ask_price=101.0,
                volume=800,
                open_interest=4500,
                expire_date=expire_date,
                iv=0.18,
            ),
        ]

        # 期货价格与行权价相同，Put-Call 平价成立，无套利机会
        future_price = 3800.0

        opportunities = detector.detect(options, future_price)

        # 不应检测到套利机会
        assert len(opportunities) == 0

    def test_empty_options_list(self, detector):
        """测试空期权列表的处理"""
        future_price = 3850.0
        options = []

        opportunities = detector.detect(options, future_price)

        assert opportunities == []

    def test_options_missing_call_or_put(self, detector):
        """测试只有 CALL 或只有 PUT 的情况"""
        expire_date = date.today() + timedelta(days=30)
        underlying = "IO2504"
        exchange_id = "CFFEX"

        # 只有 CALL
        call_only_options = [
            OptionQuote(
                symbol="IO2504-C-3800",
                underlying=underlying,
                exchange_id=exchange_id,
                strike_price=3800.0,
                call_or_put=CallOrPut.CALL,
                last_price=100.0,
                bid_price=99.0,
                ask_price=101.0,
                volume=1000,
                open_interest=5000,
                expire_date=expire_date,
                iv=0.18,
            ),
        ]

        future_price = 3800.0
        opportunities = detector.detect(call_only_options, future_price)

        # 无法进行转换套利（需要同行权价的 CALL 和 PUT）
        conversion_opps = [o for o in opportunities if o.opportunity_type in ('CONVERSION', 'REVERSE_CONVERSION')]
        assert len(conversion_opps) == 0

    def test_calculate_risk_level(self, detector):
        """测试风险等级计算"""
        # 直接测试风险等级映射
        legs = []

        assert detector._calculate_risk_level('CONVERSION', legs) == 'LOW'
        assert detector._calculate_risk_level('REVERSE_CONVERSION', legs) == 'LOW'
        assert detector._calculate_risk_level('SHORT_STRADDLE', legs) == 'HIGH'
        assert detector._calculate_risk_level('LONG_STRADDLE', legs) == 'MEDIUM'
        assert detector._calculate_risk_level('UNKNOWN', legs) == 'MEDIUM'

    def test_multiple_strike_prices(self, detector, sample_options):
        """测试多个行权价的套利检测"""
        future_price = 3820.0

        opportunities = detector.detect(sample_options, future_price)

        # 应检测到多个行权价的套利机会
        assert isinstance(opportunities, list)
        assert all(isinstance(o, ArbitrageOpportunity) for o in opportunities)

        # 验证每个机会都有必要的属性
        for opp in opportunities:
            assert hasattr(opp, 'opportunity_type')
            assert hasattr(opp, 'legs')
            assert hasattr(opp, 'expected_profit')
            assert hasattr(opp, 'risk_level')
            assert hasattr(opp, 'confidence')
            assert len(opp.legs) > 0