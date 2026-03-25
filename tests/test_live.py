# tests/test_live.py
"""
LiveMonitor 单元测试。
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
import time

from cli.live import (
    LiveMonitor,
    MonitorStatus,
    MonitorEvent,
)
from core.models import Position, StrategySignal
from trade.position import PositionManager, TargetHit, TargetConfig
from trade.executor import OrderExecutor, Order, OrderType, OrderStatus
from trade.risk import RiskChecker, RiskConfig, RiskCheckResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def monitor():
    """创建监控器实例"""
    return LiveMonitor(check_interval=1)


@pytest.fixture
def position_manager():
    """创建持仓管理器实例"""
    return PositionManager()


@pytest.fixture
def order_executor():
    """创建订单执行器实例"""
    return OrderExecutor()


@pytest.fixture
def risk_checker():
    """创建风控检查器实例"""
    config = RiskConfig(
        max_position_per_symbol=20,
        max_total_positions=50,
        max_margin_usage=0.8,
        min_account_balance=50000,
    )
    return RiskChecker(config)


@pytest.fixture
def sample_position():
    """创建示例持仓"""
    return Position(
        symbol="SHFE.au2406C480",
        exchange_id="SHFE",
        direction="LONG",
        volume=10,
        avg_price=15.0,
        current_price=16.0,
        unrealized_pnl=1000.0,
        margin=5000.0,
    )


@pytest.fixture
def sample_signal():
    """创建示例信号"""
    return StrategySignal(
        symbol="SHFE.au2406C480",
        direction="BUY",
        volume=2,
        price=16.0,
        score=0.85,
        strategy_type="TEST",
        reasons=["测试信号"],
    )


# =============================================================================
# MonitorEvent Tests
# =============================================================================

class TestMonitorEvent:
    """MonitorEvent 测试类"""

    def test_monitor_event_creation(self):
        """测试监控事件创建"""
        event = MonitorEvent(
            event_type="TARGET_HIT",
            timestamp=datetime.now(),
            data={"symbol": "SHFE.au2406C480", "price": 16.0},
            message="目标触发",
        )

        assert event.event_type == "TARGET_HIT"
        assert event.message == "目标触发"
        assert event.data["symbol"] == "SHFE.au2406C480"

    def test_monitor_event_default_message(self):
        """测试监控事件默认消息"""
        event = MonitorEvent(
            event_type="ERROR",
            timestamp=datetime.now(),
            data={"error": "test"},
        )

        assert event.message == ""

    def test_monitor_event_data_types(self):
        """测试监控事件数据类型"""
        event = MonitorEvent(
            event_type="ORDER_CREATED",
            timestamp=datetime.now(),
            data={
                "order_id": "ORD001",
                "symbol": "SHFE.au2406C480",
                "price": 16.0,
                "volume": 10,
            },
        )

        assert isinstance(event.data, dict)
        assert isinstance(event.timestamp, datetime)


# =============================================================================
# LiveMonitor Creation Tests
# =============================================================================

class TestLiveMonitorCreation:
    """LiveMonitor 创建测试类"""

    def test_create_monitor_default(self):
        """测试使用默认参数创建监控器"""
        monitor = LiveMonitor()

        assert monitor.check_interval == 10
        assert monitor.status == MonitorStatus.STOPPED

    def test_create_monitor_custom_interval(self):
        """测试使用自定义间隔创建监控器"""
        monitor = LiveMonitor(check_interval=5)

        assert monitor.check_interval == 5

    def test_create_monitor_status_stopped(self, monitor):
        """测试新创建的监控器状态为停止"""
        assert monitor.status == MonitorStatus.STOPPED


# =============================================================================
# Set Components Tests
# =============================================================================

class TestLiveMonitorSetComponents:
    """LiveMonitor 组件设置测试类"""

    def test_set_position_manager(self, monitor, position_manager):
        """测试设置持仓管理器"""
        monitor.set_position_manager(position_manager)

        assert monitor._position_manager is position_manager

    def test_set_order_executor(self, monitor, order_executor):
        """测试设置订单执行器"""
        monitor.set_order_executor(order_executor)

        assert monitor._order_executor is order_executor

    def test_set_risk_checker(self, monitor, risk_checker):
        """测试设置风控检查器"""
        monitor.set_risk_checker(risk_checker)

        assert monitor._risk_checker is risk_checker


# =============================================================================
# Status Transitions Tests
# =============================================================================

class TestLiveMonitorStatusTransitions:
    """LiveMonitor 状态转换测试类"""

    def test_start_monitor(self, monitor):
        """测试启动监控器"""
        monitor.start()

        assert monitor.status == MonitorStatus.RUNNING

        # 清理
        monitor.stop()

    def test_stop_monitor(self, monitor):
        """测试停止监控器"""
        monitor.start()
        monitor.stop()

        assert monitor.status == MonitorStatus.STOPPED

    def test_pause_monitor(self, monitor):
        """测试暂停监控器"""
        monitor.start()
        monitor.pause()

        assert monitor.status == MonitorStatus.PAUSED

        # 清理
        monitor.stop()

    def test_resume_monitor(self, monitor):
        """测试恢复监控器"""
        monitor.start()
        monitor.pause()
        monitor.resume()

        assert monitor.status == MonitorStatus.RUNNING

        # 清理
        monitor.stop()

    def test_start_when_already_running(self, monitor):
        """测试已在运行时再次启动"""
        monitor.start()
        monitor.start()  # 应该忽略

        assert monitor.status == MonitorStatus.RUNNING

        # 清理
        monitor.stop()

    def test_stop_when_not_running(self, monitor):
        """测试未运行时停止"""
        monitor.stop()  # 应该不做任何事

        assert monitor.status == MonitorStatus.STOPPED

    def test_pause_when_not_running(self, monitor):
        """测试未运行时暂停"""
        monitor.pause()  # 应该不做任何事

        assert monitor.status == MonitorStatus.STOPPED

    def test_resume_when_not_paused(self, monitor):
        """测试未暂停时恢复"""
        monitor.resume()  # 应该不做任何事

        assert monitor.status == MonitorStatus.STOPPED


# =============================================================================
# Process Signal Tests
# =============================================================================

class TestLiveMonitorProcessSignal:
    """LiveMonitor 信号处理测试类"""

    def test_process_signal_with_risk_check_passed(
        self, monitor, position_manager, order_executor, risk_checker,
        sample_signal, sample_position
    ):
        """测试通过风控检查的信号处理"""
        monitor.set_position_manager(position_manager)
        monitor.set_order_executor(order_executor)
        monitor.set_risk_checker(risk_checker)

        positions = [sample_position]
        account_balance = 100000.0
        used_margin = 5000.0

        order = monitor.process_signal(
            sample_signal, positions, account_balance, used_margin
        )

        assert order is not None
        assert isinstance(order, Order)
        assert order.symbol == sample_signal.symbol
        assert order.direction == sample_signal.direction

    def test_process_signal_without_risk_checker(
        self, monitor, position_manager, order_executor,
        sample_signal, sample_position
    ):
        """测试无风控检查器的信号处理"""
        monitor.set_position_manager(position_manager)
        monitor.set_order_executor(order_executor)
        # 不设置风控检查器

        positions = [sample_position]
        account_balance = 100000.0
        used_margin = 5000.0

        order = monitor.process_signal(
            sample_signal, positions, account_balance, used_margin
        )

        assert order is not None

    def test_process_signal_risk_check_failed(
        self, monitor, position_manager, order_executor, risk_checker,
        sample_signal, sample_position
    ):
        """测试风控检查失败的信号处理"""
        monitor.set_position_manager(position_manager)
        monitor.set_order_executor(order_executor)
        monitor.set_risk_checker(risk_checker)

        positions = [sample_position]
        # 设置极低余额以触发风控失败
        account_balance = 1000.0
        used_margin = 500.0

        order = monitor.process_signal(
            sample_signal, positions, account_balance, used_margin
        )

        assert order is None

    def test_process_signal_without_order_executor(
        self, monitor, position_manager, risk_checker,
        sample_signal, sample_position
    ):
        """测试无订单执行器的信号处理"""
        monitor.set_position_manager(position_manager)
        monitor.set_risk_checker(risk_checker)
        # 不设置订单执行器

        positions = [sample_position]
        account_balance = 100000.0
        used_margin = 5000.0

        order = monitor.process_signal(
            sample_signal, positions, account_balance, used_margin
        )

        assert order is None


# =============================================================================
# Event Logging Tests
# =============================================================================

class TestLiveMonitorEventLogging:
    """LiveMonitor 事件日志测试类"""

    def test_log_event(self, monitor):
        """测试记录事件"""
        monitor._log_event(
            "TEST_EVENT",
            {"key": "value"},
            "测试事件",
        )

        events = monitor.get_events()
        assert len(events) == 1
        assert events[0].event_type == "TEST_EVENT"
        assert events[0].message == "测试事件"
        assert events[0].data["key"] == "value"

    def test_get_events_with_limit(self, monitor):
        """测试获取事件记录带限制"""
        for i in range(5):
            monitor._log_event("EVENT", {"index": i}, f"事件{i}")

        events = monitor.get_events(limit=3)
        assert len(events) == 3
        assert events[0].data["index"] == 2
        assert events[2].data["index"] == 4

    def test_get_recent_events_by_type(self, monitor):
        """测试按类型获取最近事件"""
        monitor._log_event("TARGET_HIT", {"symbol": "A"}, "目标A")
        monitor._log_event("ORDER_CREATED", {"order_id": "1"}, "订单1")
        monitor._log_event("TARGET_HIT", {"symbol": "B"}, "目标B")

        events = monitor.get_recent_events(event_type="TARGET_HIT")
        assert len(events) == 2
        assert all(e.event_type == "TARGET_HIT" for e in events)

    def test_event_list_truncation(self, monitor):
        """测试事件列表截断（超过100个）"""
        for i in range(110):
            monitor._log_event("EVENT", {"index": i}, f"事件{i}")

        assert len(monitor._events) == 100
        assert monitor._events[0].data["index"] == 10


# =============================================================================
# Target Hit Tests
# =============================================================================

class TestLiveMonitorTargetHit:
    """LiveMonitor 目标触发测试类"""

    def test_check_targets_no_position_manager(self, monitor):
        """测试无持仓管理器时检查目标"""
        # 不设置持仓管理器
        monitor._check_targets()  # 应该不报错

    def test_target_hit_callback(self, monitor, position_manager, sample_position):
        """测试目标触发回调"""
        monitor.set_position_manager(position_manager)

        # 设置目标
        position_manager.update_positions([sample_position])
        position_manager.set_target(
            symbol=sample_position.symbol,
            take_profit=15.5,  # 当前价格16.0高于止盈价
        )

        # 记录回调调用
        callback_hits = []
        def callback(hit):
            callback_hits.append(hit)

        monitor.on_target_hit(callback)

        # 执行检查
        monitor._check_targets()

        assert len(callback_hits) == 1
        assert callback_hits[0].symbol == sample_position.symbol
        assert callback_hits[0].hit_type == "TAKE_PROFIT"

    def test_check_targets_creates_event(self, monitor, position_manager, sample_position):
        """测试检查目标创建事件"""
        monitor.set_position_manager(position_manager)

        position_manager.update_positions([sample_position])
        position_manager.set_target(
            symbol=sample_position.symbol,
            take_profit=15.5,
        )

        monitor._check_targets()

        events = monitor.get_events()
        assert len(events) == 1
        assert events[0].event_type == "TARGET_HIT"

    def test_no_target_hit(self, monitor, position_manager, sample_position):
        """测试没有目标触发的情况"""
        monitor.set_position_manager(position_manager)

        position_manager.update_positions([sample_position])
        position_manager.set_target(
            symbol=sample_position.symbol,
            take_profit=20.0,  # 高于当前价格，不会触发
        )

        monitor._check_targets()

        events = monitor.get_events()
        assert len(events) == 0


# =============================================================================
# Monitor Loop Tests
# =============================================================================

class TestLiveMonitorLoop:
    """LiveMonitor 循环测试类"""

    def test_monitor_loop_runs(self, monitor, position_manager, sample_position):
        """测试监控循环运行"""
        monitor.set_position_manager(position_manager)

        position_manager.update_positions([sample_position])
        position_manager.set_target(
            symbol=sample_position.symbol,
            take_profit=15.5,
        )

        monitor.start()

        # 等待循环执行
        time.sleep(1.5)

        # 应该有事件记录
        events = monitor.get_events()
        assert len(events) > 0

        monitor.stop()

    def test_monitor_loop_handles_exception(self, monitor):
        """测试监控循环异常处理"""
        # 创建一个会在 check_targets 时抛出异常的 mock
        mock_manager = MagicMock()
        mock_manager.check_targets.side_effect = Exception("测试异常")

        monitor.set_position_manager(mock_manager)
        monitor.start()

        # 等待循环执行
        time.sleep(1.5)

        # 应该记录错误事件
        events = monitor.get_events()
        error_events = [e for e in events if e.event_type == "ERROR"]
        assert len(error_events) > 0
        assert "测试异常" in error_events[0].message

        monitor.stop()

    def test_monitor_stops_cleanly(self, monitor):
        """测试监控器干净停止"""
        monitor.start()
        time.sleep(0.5)
        monitor.stop()

        assert monitor.status == MonitorStatus.STOPPED


# =============================================================================
# Callback Registration Tests
# =============================================================================

class TestLiveMonitorCallbacks:
    """LiveMonitor 回调测试类"""

    def test_on_target_hit_registration(self, monitor):
        """测试目标触发回调注册"""
        def callback(hit):
            pass

        monitor.on_target_hit(callback)

        assert monitor._on_target_hit is callback

    def test_on_signal_registration(self, monitor):
        """测试信号回调注册"""
        def callback(signal):
            pass

        monitor.on_signal(callback)

        assert monitor._on_signal is callback