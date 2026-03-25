# tests/test_position.py
"""持仓管理模块测试"""
import pytest
from datetime import datetime

from core.models import Position
from trade.position import (
    TargetConfig,
    TargetHit,
    BasePositionManager,
    PositionManager,
)


class TestTargetConfig:
    """目标配置测试"""

    def test_create_target_config(self):
        """测试创建目标配置"""
        config = TargetConfig(
            symbol="SHFE.cu2405",
            target_price=75000.0,
            stop_loss=74000.0,
            take_profit=76000.0,
        )
        assert config.symbol == "SHFE.cu2405"
        assert config.target_price == 75000.0
        assert config.stop_loss == 74000.0
        assert config.take_profit == 76000.0
        assert isinstance(config.created_at, datetime)

    def test_target_config_auto_created_at(self):
        """测试自动设置创建时间"""
        before = datetime.now()
        config = TargetConfig(symbol="SHFE.cu2405")
        after = datetime.now()
        assert before <= config.created_at <= after

    def test_target_config_with_explicit_created_at(self):
        """测试显式设置创建时间"""
        explicit_time = datetime(2024, 1, 1, 12, 0, 0)
        config = TargetConfig(
            symbol="SHFE.cu2405",
            created_at=explicit_time,
        )
        assert config.created_at == explicit_time


class TestTargetHit:
    """目标触发事件测试"""

    @pytest.fixture
    def position(self):
        """创建测试持仓"""
        return Position(
            symbol="SHFE.cu2405",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=74500.0,
            current_price=75000.0,
            unrealized_pnl=5000.0,
            margin=50000.0,
        )

    def test_create_target_hit(self, position):
        """测试创建目标触发事件"""
        target = TargetConfig(
            symbol="SHFE.cu2405",
            stop_loss=74000.0,
        )
        hit = TargetHit(
            symbol="SHFE.cu2405",
            position=position,
            target=target,
            hit_type="STOP_LOSS",
            current_price=74000.0,
        )
        assert hit.symbol == "SHFE.cu2405"
        assert hit.hit_type == "STOP_LOSS"
        assert hit.current_price == 74000.0
        assert hit.position == position
        assert hit.target == target
        assert isinstance(hit.timestamp, datetime)

    def test_target_hit_auto_timestamp(self, position):
        """测试自动设置时间戳"""
        target = TargetConfig(symbol="SHFE.cu2405")
        before = datetime.now()
        hit = TargetHit(
            symbol="SHFE.cu2405",
            position=position,
            target=target,
            hit_type="TAKE_PROFIT",
            current_price=76000.0,
        )
        after = datetime.now()
        assert before <= hit.timestamp <= after


class TestPositionManager:
    """持仓管理器测试"""

    @pytest.fixture
    def manager(self):
        """创建持仓管理器"""
        return PositionManager()

    @pytest.fixture
    def sample_position(self):
        """创建示例持仓"""
        return Position(
            symbol="SHFE.cu2405",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=74500.0,
            current_price=75000.0,
            unrealized_pnl=5000.0,
            margin=50000.0,
        )

    def test_create_manager(self, manager):
        """测试创建持仓管理器"""
        assert manager is not None
        assert isinstance(manager, BasePositionManager)

    def test_update_and_get_positions(self, manager, sample_position):
        """测试更新和获取持仓"""
        # 初始状态为空
        assert manager.get_positions() == []
        assert manager.get_position("SHFE.cu2405") is None

        # 更新持仓
        manager.update_positions([sample_position])
        positions = manager.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "SHFE.cu2405"

        # 获取单个持仓
        pos = manager.get_position("SHFE.cu2405")
        assert pos is not None
        assert pos.symbol == "SHFE.cu2405"
        assert pos.volume == 10

    def test_update_positions_filters_zero_volume(self, manager):
        """测试更新持仓过滤零持仓"""
        pos1 = Position(
            symbol="SHFE.cu2405",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=74500.0,
            current_price=75000.0,
            unrealized_pnl=5000.0,
            margin=50000.0,
        )
        pos2 = Position(
            symbol="SHFE.cu2406",
            exchange_id="SHFE",
            direction="LONG",
            volume=0,  # 零持仓
            avg_price=74000.0,
            current_price=74500.0,
            unrealized_pnl=0.0,
            margin=0.0,
        )

        manager.update_positions([pos1, pos2])
        positions = manager.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "SHFE.cu2405"

    def test_set_and_get_target(self, manager):
        """测试设置和获取目标"""
        result = manager.set_target(
            symbol="SHFE.cu2405",
            target_price=76000.0,
            stop_loss=74000.0,
            take_profit=77000.0,
        )
        assert result is True

        target = manager.get_target("SHFE.cu2405")
        assert target is not None
        assert target.symbol == "SHFE.cu2405"
        assert target.target_price == 76000.0
        assert target.stop_loss == 74000.0
        assert target.take_profit == 77000.0

    def test_get_target_not_found(self, manager):
        """测试获取不存在目标"""
        target = manager.get_target("NONEXISTENT")
        assert target is None

    def test_check_targets_stop_loss(self, manager, sample_position):
        """测试检查止损触发"""
        # 设置止损目标（高于当前价格，触发止损）
        manager.set_target("SHFE.cu2405", stop_loss=75100.0)
        manager.update_positions([sample_position])

        # 当前价格低于止损价格，触发止损
        hits = manager.check_targets()
        assert len(hits) == 1
        assert hits[0].hit_type == "STOP_LOSS"
        assert hits[0].symbol == "SHFE.cu2405"
        assert hits[0].current_price == 75000.0

    def test_check_targets_stop_loss_not_triggered(self, manager, sample_position):
        """测试止损未触发"""
        # 设置止损价格低于当前价格
        manager.set_target("SHFE.cu2405", stop_loss=74000.0)
        manager.update_positions([sample_position])

        # 当前价格高于止损价格，不触发
        hits = manager.check_targets()
        assert len(hits) == 0

    def test_check_targets_take_profit(self, manager, sample_position):
        """测试检查止盈触发"""
        # 设置止盈目标（低于当前价格）
        manager.set_target("SHFE.cu2405", take_profit=74800.0)
        manager.update_positions([sample_position])

        hits = manager.check_targets()
        assert len(hits) == 1
        assert hits[0].hit_type == "TAKE_PROFIT"

    def test_check_targets_take_profit_not_triggered(self, manager, sample_position):
        """测试止盈未触发"""
        # 设置止盈价格高于当前价格
        manager.set_target("SHFE.cu2405", take_profit=76000.0)
        manager.update_positions([sample_position])

        hits = manager.check_targets()
        assert len(hits) == 0

    def test_check_targets_target_price(self, manager, sample_position):
        """测试检查目标价触发"""
        # 设置目标价格（低于当前价格）
        manager.set_target("SHFE.cu2405", target_price=74800.0)
        manager.update_positions([sample_position])

        hits = manager.check_targets()
        assert len(hits) == 1
        assert hits[0].hit_type == "TARGET"

    def test_check_targets_target_price_not_triggered(self, manager, sample_position):
        """测试目标价未触发"""
        # 设置目标价格高于当前价格
        manager.set_target("SHFE.cu2405", target_price=76000.0)
        manager.update_positions([sample_position])

        hits = manager.check_targets()
        assert len(hits) == 0

    def test_check_targets_no_position(self, manager):
        """测试没有持仓时不检查"""
        manager.set_target("SHFE.cu2405", stop_loss=74000.0)
        # 没有更新持仓

        hits = manager.check_targets()
        assert len(hits) == 0

    def test_check_targets_multiple_positions(self, manager):
        """测试多个持仓目标检查"""
        pos1 = Position(
            symbol="SHFE.cu2405",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=74500.0,
            current_price=74000.0,  # 触发止损
            unrealized_pnl=-5000.0,
            margin=50000.0,
        )
        pos2 = Position(
            symbol="SHFE.cu2406",
            exchange_id="SHFE",
            direction="LONG",
            volume=5,
            avg_price=75000.0,
            current_price=76000.0,  # 触发目标
            unrealized_pnl=5000.0,
            margin=40000.0,
        )

        manager.set_target("SHFE.cu2405", stop_loss=74100.0)
        manager.set_target("SHFE.cu2406", target_price=75500.0)
        manager.update_positions([pos1, pos2])

        hits = manager.check_targets()
        assert len(hits) == 2
        hit_types = {h.hit_type for h in hits}
        assert "STOP_LOSS" in hit_types
        assert "TARGET" in hit_types

    def test_get_total_margin(self, manager):
        """测试获取总保证金"""
        pos1 = Position(
            symbol="SHFE.cu2405",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=74500.0,
            current_price=75000.0,
            unrealized_pnl=5000.0,
            margin=50000.0,
        )
        pos2 = Position(
            symbol="SHFE.cu2406",
            exchange_id="SHFE",
            direction="LONG",
            volume=5,
            avg_price=75000.0,
            current_price=75500.0,
            unrealized_pnl=2500.0,
            margin=40000.0,
        )

        manager.update_positions([pos1, pos2])
        total_margin = manager.get_total_margin()
        assert total_margin == 90000.0

    def test_get_total_unrealized_pnl(self, manager):
        """测试获取总未实现盈亏"""
        pos1 = Position(
            symbol="SHFE.cu2405",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=74500.0,
            current_price=75000.0,
            unrealized_pnl=5000.0,
            margin=50000.0,
        )
        pos2 = Position(
            symbol="SHFE.cu2406",
            exchange_id="SHFE",
            direction="LONG",
            volume=5,
            avg_price=75000.0,
            current_price=75500.0,
            unrealized_pnl=2500.0,
            margin=40000.0,
        )

        manager.update_positions([pos1, pos2])
        total_pnl = manager.get_total_unrealized_pnl()
        assert total_pnl == 7500.0

    def test_remove_target(self, manager):
        """测试移除目标"""
        manager.set_target("SHFE.cu2405", stop_loss=74000.0)
        assert manager.get_target("SHFE.cu2405") is not None

        result = manager.remove_target("SHFE.cu2405")
        assert result is True
        assert manager.get_target("SHFE.cu2405") is None

    def test_remove_target_not_found(self, manager):
        """测试移除不存在的目标"""
        result = manager.remove_target("NONEXISTENT")
        assert result is False

    def test_empty_manager_totals(self, manager):
        """测试空管理器的总计值"""
        assert manager.get_total_margin() == 0.0
        assert manager.get_total_unrealized_pnl() == 0.0

    def test_stop_loss_priority_over_take_profit(self, manager):
        """测试止损优先于止盈检查"""
        # 创建一个价格触发止损的持仓
        position = Position(
            symbol="SHFE.cu2405",
            exchange_id="SHFE",
            direction="LONG",
            volume=10,
            avg_price=75000.0,
            current_price=74000.0,  # 价格下跌
            unrealized_pnl=-10000.0,
            margin=50000.0,
        )

        # 同时设置止损和止盈
        manager.set_target(
            "SHFE.cu2405",
            stop_loss=74100.0,  # 当前价格低于止损价，触发
            take_profit=73000.0,  # 当前价格高于止盈价，也会触发
        )
        manager.update_positions([position])

        hits = manager.check_targets()
        # 止损检查优先（使用 elif）
        assert len(hits) == 1
        assert hits[0].hit_type == "STOP_LOSS"