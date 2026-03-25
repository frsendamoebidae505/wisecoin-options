# tests/test_position_mock.py
"""模拟持仓管理模块测试"""
import pytest
from datetime import datetime

from trade.position_mock import MockPosition, MockPositionManager, TradeRecord
from core.models import Position


# ============ Fixtures ============

@pytest.fixture
def manager():
    """创建模拟持仓管理器"""
    return MockPositionManager(initial_capital=1000000.0)


@pytest.fixture
def manager_with_position(manager):
    """创建带有一个持仓的管理器"""
    manager.open_position(
        symbol="IF2504",
        exchange_id="CFFEX",
        direction="LONG",
        volume=2,
        price=4000.0,
    )
    return manager


# ============ MockPosition Tests ============

class TestMockPosition:
    """模拟持仓测试"""

    def test_mock_position_creation(self):
        """测试模拟持仓创建"""
        pos = MockPosition(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            avg_price=4000.0,
            margin=80000.0,
        )
        assert pos.symbol == "IF2504"
        assert pos.exchange_id == "CFFEX"
        assert pos.direction == "LONG"
        assert pos.volume == 2
        assert pos.avg_price == 4000.0
        assert pos.margin == 80000.0
        assert pos.open_time is not None
        assert pos.current_price == 0.0

    def test_mock_position_with_open_time(self):
        """测试指定开仓时间的持仓"""
        open_time = datetime(2025, 4, 1, 9, 30, 0)
        pos = MockPosition(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            avg_price=4000.0,
            margin=80000.0,
            open_time=open_time,
        )
        assert pos.open_time == open_time

    def test_unrealized_pnl_long_profit(self):
        """测试多头持仓未实现盈亏 - 盈利"""
        pos = MockPosition(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            avg_price=4000.0,
            margin=80000.0,
            current_price=4050.0,
        )
        # (4050 - 4000) * 2 = 100
        assert pos.unrealized_pnl() == 100.0

    def test_unrealized_pnl_long_loss(self):
        """测试多头持仓未实现盈亏 - 亏损"""
        pos = MockPosition(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            avg_price=4000.0,
            margin=80000.0,
            current_price=3950.0,
        )
        # (3950 - 4000) * 2 = -100
        assert pos.unrealized_pnl() == -100.0

    def test_unrealized_pnl_short_profit(self):
        """测试空头持仓未实现盈亏 - 盈利"""
        pos = MockPosition(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="SHORT",
            volume=2,
            avg_price=4000.0,
            margin=80000.0,
            current_price=3950.0,
        )
        # (4000 - 3950) * 2 = 100
        assert pos.unrealized_pnl() == 100.0

    def test_unrealized_pnl_short_loss(self):
        """测试空头持仓未实现盈亏 - 亏损"""
        pos = MockPosition(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="SHORT",
            volume=2,
            avg_price=4000.0,
            margin=80000.0,
            current_price=4050.0,
        )
        # (4000 - 4050) * 2 = -100
        assert pos.unrealized_pnl() == -100.0

    def test_to_position(self):
        """测试转换为 Position 模型"""
        pos = MockPosition(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            avg_price=4000.0,
            margin=80000.0,
            current_price=4050.0,
        )
        position = pos.to_position()
        assert isinstance(position, Position)
        assert position.symbol == "IF2504"
        assert position.exchange_id == "CFFEX"
        assert position.direction == "LONG"
        assert position.volume == 2
        assert position.avg_price == 4000.0
        assert position.current_price == 4050.0
        assert position.unrealized_pnl == 100.0
        assert position.margin == 80000.0


# ============ TradeRecord Tests ============

class TestTradeRecord:
    """交易记录测试"""

    def test_trade_record_creation(self):
        """测试交易记录创建"""
        record = TradeRecord(
            action='OPEN',
            symbol="IF2504",
            direction="LONG",
            volume=2,
            price=4000.0,
            timestamp=datetime.now(),
        )
        assert record.action == 'OPEN'
        assert record.symbol == "IF2504"
        assert record.direction == "LONG"
        assert record.volume == 2
        assert record.price == 4000.0
        assert record.pnl == 0.0

    def test_trade_record_with_pnl(self):
        """测试带盈亏的交易记录"""
        record = TradeRecord(
            action='CLOSE',
            symbol="IF2504",
            direction="LONG",
            volume=2,
            price=4050.0,
            timestamp=datetime.now(),
            pnl=100.0,
        )
        assert record.action == 'CLOSE'
        assert record.pnl == 100.0


# ============ MockPositionManager Tests ============

class TestMockPositionManager:
    """模拟持仓管理器测试"""

    def test_manager_creation(self, manager):
        """测试管理器创建"""
        assert manager.initial_capital == 1000000.0
        assert manager.current_capital == 1000000.0
        assert manager.positions == {}
        assert manager.trade_history == []

    def test_manager_creation_custom_capital(self):
        """测试自定义初始资金"""
        manager = MockPositionManager(initial_capital=500000.0)
        assert manager.initial_capital == 500000.0
        assert manager.current_capital == 500000.0


class TestOpenPosition:
    """开仓测试"""

    def test_open_position_success(self, manager):
        """测试成功开仓"""
        result = manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            price=4000.0,
        )
        assert result is True
        assert "IF2504" in manager.positions
        assert len(manager.trade_history) == 1

    def test_open_position_insufficient_capital(self, manager):
        """测试资金不足开仓失败"""
        # 尝试开仓需要的保证金超过初始资金
        result = manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=100000,  # 4000 * 100000 * 0.1 = 40,000,000 > 1,000,000
            price=4000.0,
        )
        assert result is False
        assert "IF2504" not in manager.positions
        assert len(manager.trade_history) == 0

    def test_open_position_margin_deduction(self, manager):
        """测试开仓扣除保证金"""
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            price=4000.0,
        )
        # 保证金 = 4000 * 2 * 0.1 = 800
        expected_margin = 4000.0 * 2 * 0.1
        assert manager.current_capital == 1000000.0 - expected_margin

    def test_open_position_record(self, manager):
        """测试开仓记录"""
        timestamp = datetime(2025, 4, 1, 9, 30, 0)
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            price=4000.0,
            timestamp=timestamp,
        )
        record = manager.trade_history[0]
        assert record.action == 'OPEN'
        assert record.symbol == "IF2504"
        assert record.direction == "LONG"
        assert record.volume == 2
        assert record.price == 4000.0
        assert record.timestamp == timestamp

    def test_add_to_existing_position(self, manager_with_position):
        """测试加仓"""
        manager = manager_with_position
        # 原持仓: 2手 @ 4000
        # 加仓: 1手 @ 4100
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=1,
            price=4100.0,
        )
        pos = manager.positions["IF2504"]
        assert pos.volume == 3
        # 加权平均价 = (4000 * 2 + 4100 * 1) / 3 = 4033.33...
        expected_avg = (4000.0 * 2 + 4100.0 * 1) / 3
        assert abs(pos.avg_price - expected_avg) < 0.01


class TestClosePosition:
    """平仓测试"""

    def test_close_position_success(self, manager_with_position):
        """测试成功平仓"""
        manager = manager_with_position
        pnl = manager.close_position(
            symbol="IF2504",
            volume=1,
            price=4050.0,
        )
        # 盈亏 = (4050 - 4000) * 1 = 50
        assert pnl == 50.0
        assert manager.positions["IF2504"].volume == 1

    def test_close_position_full(self, manager_with_position):
        """测试全部平仓"""
        manager = manager_with_position
        pnl = manager.close_position(
            symbol="IF2504",
            volume=2,
            price=4050.0,
        )
        # 盈亏 = (4050 - 4000) * 2 = 100
        assert pnl == 100.0
        assert "IF2504" not in manager.positions

    def test_close_position_not_exists(self, manager):
        """测试平仓不存在的持仓"""
        pnl = manager.close_position(
            symbol="IF2504",
            volume=1,
            price=4050.0,
        )
        assert pnl is None

    def test_close_position_short(self, manager):
        """测试空头平仓"""
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="SHORT",
            volume=2,
            price=4000.0,
        )
        pnl = manager.close_position(
            symbol="IF2504",
            volume=1,
            price=3950.0,
        )
        # 空头盈亏 = (4000 - 3950) * 1 = 50
        assert pnl == 50.0

    def test_close_position_margin_released(self, manager_with_position):
        """测试平仓释放保证金"""
        manager = manager_with_position
        initial_capital = manager.current_capital
        # 开仓保证金 = 4000 * 2 * 0.1 = 800
        # 平仓1手，释放一半保证金 + 盈亏
        pnl = manager.close_position(
            symbol="IF2504",
            volume=1,
            price=4050.0,
        )
        # 释放 400 (一半保证金) + 50 (盈亏) = 450
        expected_capital = initial_capital + 400 + 50
        assert manager.current_capital == expected_capital


class TestUpdatePrices:
    """更新价格测试"""

    def test_update_prices(self, manager_with_position):
        """测试更新持仓价格"""
        manager = manager_with_position
        manager.update_prices({"IF2504": 4050.0})
        assert manager.positions["IF2504"].current_price == 4050.0

    def test_update_prices_multiple(self, manager):
        """测试更新多个持仓价格"""
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=1,
            price=4000.0,
        )
        manager.open_position(
            symbol="IC2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=1,
            price=6000.0,
        )
        manager.update_prices({
            "IF2504": 4050.0,
            "IC2504": 6100.0,
        })
        assert manager.positions["IF2504"].current_price == 4050.0
        assert manager.positions["IC2504"].current_price == 6100.0


class TestGetPositions:
    """获取持仓测试"""

    def test_get_positions_empty(self, manager):
        """测试获取空持仓列表"""
        positions = manager.get_positions()
        assert positions == []

    def test_get_positions(self, manager_with_position):
        """测试获取持仓列表"""
        positions = manager_with_position.get_positions()
        assert len(positions) == 1
        assert isinstance(positions[0], Position)
        assert positions[0].symbol == "IF2504"

    def test_get_position(self, manager_with_position):
        """测试获取单个持仓"""
        position = manager_with_position.get_position("IF2504")
        assert position is not None
        assert position.symbol == "IF2504"

    def test_get_position_not_exists(self, manager):
        """测试获取不存在的持仓"""
        position = manager.get_position("IF2504")
        assert position is None


class TestTradeHistoryAndStatistics:
    """交易历史和统计测试"""

    def test_trade_history(self, manager):
        """测试交易历史记录"""
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            price=4000.0,
        )
        manager.close_position(
            symbol="IF2504",
            volume=2,
            price=4050.0,
        )
        assert len(manager.trade_history) == 2
        assert manager.trade_history[0].action == 'OPEN'
        assert manager.trade_history[1].action == 'CLOSE'

    def test_get_total_pnl(self, manager):
        """测试获取累计盈亏"""
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=2,
            price=4000.0,
        )
        manager.close_position(
            symbol="IF2504",
            volume=2,
            price=4050.0,
        )
        # 盈亏 = (4050 - 4000) * 2 = 100
        assert manager.get_total_pnl() == 100.0

    def test_get_statistics(self, manager):
        """测试获取交易统计"""
        # 第一笔交易盈利
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=1,
            price=4000.0,
        )
        manager.close_position(
            symbol="IF2504",
            volume=1,
            price=4050.0,
        )
        # 第二笔交易亏损
        manager.open_position(
            symbol="IC2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=1,
            price=6000.0,
        )
        manager.close_position(
            symbol="IC2504",
            volume=1,
            price=5950.0,
        )
        stats = manager.get_statistics()
        assert stats['total_trades'] == 2
        assert stats['win_count'] == 1
        assert stats['loss_count'] == 1

    def test_win_rate_calculation(self, manager):
        """测试胜率计算"""
        # 3笔盈利，2笔亏损
        for i, (open_price, close_price) in enumerate([
            (4000.0, 4050.0),  # 盈利
            (4000.0, 3950.0),  # 亏损
            (4000.0, 4100.0),  # 盈利
            (4000.0, 3900.0),  # 亏损
            (4000.0, 4200.0),  # 盈利
        ]):
            symbol = f"IF250{i}"
            manager.open_position(
                symbol=symbol,
                exchange_id="CFFEX",
                direction="LONG",
                volume=1,
                price=open_price,
            )
            manager.close_position(
                symbol=symbol,
                volume=1,
                price=close_price,
            )
        stats = manager.get_statistics()
        assert stats['win_count'] == 3
        assert stats['loss_count'] == 2
        assert stats['win_rate'] == pytest.approx(0.6)

    def test_win_rate_no_trades(self, manager):
        """测试无交易时的胜率"""
        stats = manager.get_statistics()
        assert stats['win_rate'] == 0

    def test_return_rate(self, manager):
        """测试收益率计算"""
        manager.open_position(
            symbol="IF2504",
            exchange_id="CFFEX",
            direction="LONG",
            volume=1,
            price=4000.0,
        )
        manager.close_position(
            symbol="IF2504",
            volume=1,
            price=4100.0,
        )
        # 盈亏 = 100
        # 收益率 = 100 / 1000000 = 0.0001
        stats = manager.get_statistics()
        assert stats['return_rate'] == pytest.approx(100.0 / 1000000.0)


class TestTargetMethods:
    """目标设置方法测试"""

    def test_set_target_returns_false(self, manager):
        """测试模拟环境不支持目标设置"""
        result = manager.set_target(
            symbol="IF2504",
            target_price=4100.0,
            stop_loss=3900.0,
            take_profit=4200.0,
        )
        assert result is False

    def test_check_targets_returns_empty(self, manager_with_position):
        """测试模拟环境不支持目标检查"""
        hits = manager_with_position.check_targets()
        assert hits == []