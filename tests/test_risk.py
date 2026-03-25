# tests/test_risk.py
"""
RiskChecker 单元测试。
"""
import pytest
from datetime import date
from unittest.mock import patch

from trade.risk import RiskConfig, RiskChecker, RiskCheckResult
from core.models import Position, StrategySignal


class TestRiskConfig:
    """测试 RiskConfig 配置类。"""

    def test_default_config(self):
        """测试默认配置。"""
        config = RiskConfig()
        assert config.max_position_per_symbol == 10
        assert config.max_total_positions == 50
        assert config.max_margin_usage == 0.8
        assert config.max_single_order_value == 100000
        assert config.max_daily_trades == 100
        assert config.min_account_balance == 50000

    def test_custom_config(self):
        """测试自定义配置。"""
        config = RiskConfig(
            max_position_per_symbol=20,
            max_total_positions=100,
            max_margin_usage=0.9,
            max_single_order_value=200000,
            max_daily_trades=50,
            min_account_balance=100000,
        )
        assert config.max_position_per_symbol == 20
        assert config.max_total_positions == 100
        assert config.max_margin_usage == 0.9
        assert config.max_single_order_value == 200000
        assert config.max_daily_trades == 50
        assert config.min_account_balance == 100000


class TestRiskCheckResult:
    """测试 RiskCheckResult 结果类。"""

    def test_has_warnings_true(self):
        """测试 has_warnings 属性为 True。"""
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=1,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        result = RiskCheckResult(
            passed=True,
            signal=signal,
            violations=[],
            warnings=["警告信息"],
        )
        assert result.has_warnings is True

    def test_has_warnings_false(self):
        """测试 has_warnings 属性为 False。"""
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=1,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        result = RiskCheckResult(
            passed=True,
            signal=signal,
            violations=[],
            warnings=[],
        )
        assert result.has_warnings is False


class TestRiskChecker:
    """测试 RiskChecker 类。"""

    def test_risk_checker_creation_default(self):
        """测试使用默认配置创建 RiskChecker。"""
        checker = RiskChecker()
        assert checker.config.max_position_per_symbol == 10
        assert checker._daily_trade_count == 0

    def test_risk_checker_creation_custom(self):
        """测试使用自定义配置创建 RiskChecker。"""
        config = RiskConfig(max_position_per_symbol=20)
        checker = RiskChecker(config=config)
        assert checker.config.max_position_per_symbol == 20

    def test_check_passes_for_valid_signal(self):
        """测试有效信号通过检查。"""
        checker = RiskChecker()
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=1,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        positions = []
        account_balance = 100000.0
        used_margin = 10000.0

        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is True
        assert len(result.violations) == 0
        assert len(result.warnings) == 0

    def test_check_fails_insufficient_balance(self):
        """测试余额不足检查失败。"""
        config = RiskConfig(min_account_balance=50000)
        checker = RiskChecker(config=config)
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=1,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        positions = []
        account_balance = 30000.0  # 低于最低余额
        used_margin = 1000.0

        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is False
        assert any("账户余额不足" in v for v in result.violations)

    def test_check_fails_position_limit_exceeded(self):
        """测试单合约持仓超限检查失败。"""
        config = RiskConfig(max_position_per_symbol=10)
        checker = RiskChecker(config=config)
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=5,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        # 已有 8 手持仓
        positions = [
            Position(
                symbol="SHFE.au2406C480",
                exchange_id="SHFE",
                direction="LONG",
                volume=8,
                avg_price=100.0,
                current_price=100.0,
                unrealized_pnl=0.0,
                margin=8000.0,
            )
        ]
        account_balance = 100000.0
        used_margin = 8000.0

        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is False
        assert any("单合约持仓超限" in v for v in result.violations)

    def test_check_fails_total_positions_exceeded(self):
        """测试总持仓数量超限检查失败。"""
        config = RiskConfig(max_total_positions=3)
        checker = RiskChecker(config=config)
        signal = StrategySignal(
            symbol="SHFE.au2406C500",
            direction="BUY",
            volume=1,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        # 已有 3 个持仓
        positions = [
            Position(
                symbol=f"SHFE.au2406C{i}80",
                exchange_id="SHFE",
                direction="LONG",
                volume=1,
                avg_price=100.0,
                current_price=100.0,
                unrealized_pnl=0.0,
                margin=1000.0,
            )
            for i in [4, 5, 6]
        ]
        account_balance = 100000.0
        used_margin = 3000.0

        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is False
        assert any("总持仓数量超限" in v for v in result.violations)

    def test_check_fails_margin_usage_exceeded(self):
        """测试保证金使用率超限检查失败。"""
        config = RiskConfig(max_margin_usage=0.8, max_position_per_symbol=100)
        checker = RiskChecker(config=config)
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=10,
            price=500.0,  # 大额订单
            score=0.8,
            strategy_type="test",
        )
        positions = []
        account_balance = 50000.0
        used_margin = 38000.0  # 已使用较多保证金 (38000 + 500 = 38500) / 50000 = 0.77 < 0.8

        result = checker.check(signal, positions, account_balance, used_margin)

        # 调整参数使保证金超限
        # (38000 + 500) / 50000 = 0.77 < 0.8, 所以用更高的used_margin
        # 需要 (used_margin + order_value * 0.1) / account_balance > 0.8
        # (used_margin + 500) > 40000 -> used_margin > 39500

        # 重新测试
        used_margin = 40000.0  # (40000 + 500) / 50000 = 0.81 > 0.8
        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is False
        assert any("保证金使用率超限" in v for v in result.violations)

    def test_check_fails_daily_trade_limit(self):
        """测试每日交易次数超限检查失败。"""
        config = RiskConfig(max_daily_trades=5)
        checker = RiskChecker(config=config)
        checker._daily_trade_count = 5  # 已达上限

        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=1,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        positions = []
        account_balance = 100000.0
        used_margin = 1000.0

        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is False
        assert any("每日交易次数超限" in v for v in result.violations)

    def test_check_fails_single_order_value_exceeded(self):
        """测试单笔订单金额超限检查失败。"""
        config = RiskConfig(max_single_order_value=100000)
        checker = RiskChecker(config=config)
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=1000,
            price=150.0,  # 总金额 150000 > 100000
            score=0.8,
            strategy_type="test",
        )
        positions = []
        account_balance = 500000.0
        used_margin = 10000.0

        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is False
        assert any("单笔订单金额超限" in v for v in result.violations)

    def test_warning_for_near_margin_limit(self):
        """测试接近保证金限制时产生警告。"""
        config = RiskConfig(max_margin_usage=0.8)
        checker = RiskChecker(config=config)
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=10,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        positions = []
        account_balance = 100000.0
        # 警告阈值: 0.8 * 0.9 = 0.72
        # 需要: 0.72 < new_margin_usage <= 0.8
        # new_margin_usage = (used_margin + order_value * 0.1) / account_balance
        # order_value = 10 * 100 = 1000, order_value * 0.1 = 100
        # 需要: 0.72 < (used_margin + 100) / 100000 <= 0.8
        # 72000 < used_margin + 100 <= 80000
        # 71900 < used_margin <= 79900
        used_margin = 75000.0  # (75000 + 100) / 100000 = 0.751, 在警告范围内

        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is True  # 通过但有警告
        assert any("保证金使用率警告" in w for w in result.warnings)

    def test_batch_checking(self):
        """测试批量检查。"""
        checker = RiskChecker()
        signals = [
            StrategySignal(
                symbol="SHFE.au2406C480",
                direction="BUY",
                volume=1,
                price=100.0,
                score=0.8,
                strategy_type="test",
            ),
            StrategySignal(
                symbol="SHFE.au2406C500",
                direction="BUY",
                volume=2,
                price=80.0,
                score=0.7,
                strategy_type="test",
            ),
        ]
        positions = []
        account_balance = 100000.0
        used_margin = 1000.0

        results = checker.check_batch(signals, positions, account_balance, used_margin)

        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_record_trade(self):
        """测试记录交易次数。"""
        checker = RiskChecker()
        assert checker._daily_trade_count == 0

        checker.record_trade()
        assert checker._daily_trade_count == 1

        checker.record_trade()
        assert checker._daily_trade_count == 2

    def test_record_trade_resets_on_new_day(self):
        """测试新日期重置交易计数。"""
        checker = RiskChecker()
        checker._daily_trade_count = 50
        checker._trade_date = date(2024, 1, 1)

        with patch('datetime.date') as mock_date:
            mock_date.today.return_value = date(2024, 1, 2)
            checker.record_trade()

        assert checker._daily_trade_count == 1

    def test_reset_daily_count(self):
        """测试重置每日交易计数。"""
        checker = RiskChecker()
        checker._daily_trade_count = 50

        checker.reset_daily_count()

        assert checker._daily_trade_count == 0

    def test_get_remaining_trades(self):
        """测试获取剩余可交易次数。"""
        config = RiskConfig(max_daily_trades=100)
        checker = RiskChecker(config=config)
        checker._daily_trade_count = 30

        remaining = checker.get_remaining_trades()

        assert remaining == 70

    def test_get_remaining_trades_at_limit(self):
        """测试已达交易上限时的剩余次数。"""
        config = RiskConfig(max_daily_trades=100)
        checker = RiskChecker(config=config)
        checker._daily_trade_count = 100

        remaining = checker.get_remaining_trades()

        assert remaining == 0

    def test_get_remaining_trades_over_limit(self):
        """测试超过交易上限时的剩余次数（不应发生，但应安全处理）。"""
        config = RiskConfig(max_daily_trades=100)
        checker = RiskChecker(config=config)
        checker._daily_trade_count = 150  # 超过限制

        remaining = checker.get_remaining_trades()

        assert remaining == 0  # 不应为负数

    def test_sell_does_not_trigger_position_limit(self):
        """测试卖出操作不触发持仓限制检查。"""
        config = RiskConfig(max_position_per_symbol=10)
        checker = RiskChecker(config=config)
        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="SELL",  # 卖出方向
            volume=5,
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        # 已有 8 手持仓
        positions = [
            Position(
                symbol="SHFE.au2406C480",
                exchange_id="SHFE",
                direction="LONG",
                volume=8,
                avg_price=100.0,
                current_price=100.0,
                unrealized_pnl=0.0,
                margin=8000.0,
            )
        ]
        account_balance = 100000.0
        used_margin = 8000.0

        result = checker.check(signal, positions, account_balance, used_margin)

        # 卖出不应触发持仓限制
        assert not any("单合约持仓超限" in v for v in result.violations)

    def test_multiple_violations(self):
        """测试多个违规同时出现。"""
        config = RiskConfig(
            min_account_balance=50000,
            max_position_per_symbol=10,
            max_daily_trades=5,
        )
        checker = RiskChecker(config=config)
        checker._daily_trade_count = 5  # 已达上限

        signal = StrategySignal(
            symbol="SHFE.au2406C480",
            direction="BUY",
            volume=20,  # 超过持仓限制
            price=100.0,
            score=0.8,
            strategy_type="test",
        )
        positions = []
        account_balance = 30000.0  # 低于最低余额
        used_margin = 1000.0

        result = checker.check(signal, positions, account_balance, used_margin)

        assert result.passed is False
        assert len(result.violations) >= 2  # 至少两个违规