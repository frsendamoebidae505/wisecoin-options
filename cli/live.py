# cli/live.py
"""
实时监控模块。

提供实时行情监控和自动交易功能。
"""
from typing import List, Optional, Callable, Dict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import threading
import time

from core.models import Position, StrategySignal
from trade.position import PositionManager, TargetHit
from trade.executor import OrderExecutor, Order
from trade.risk import RiskChecker
from common.logger import StructuredLogger


class MonitorStatus(str, Enum):
    """监控状态"""
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


@dataclass
class MonitorEvent:
    """监控事件"""
    event_type: str  # TARGET_HIT, SIGNAL_GENERATED, ORDER_FILLED, ERROR
    timestamp: datetime
    data: dict
    message: str = ""


class LiveMonitor:
    """
    实时监控器。

    监控持仓目标、生成信号、执行订单。

    Example:
        >>> monitor = LiveMonitor()
        >>> monitor.set_position_manager(manager)
        >>> monitor.start()
    """

    def __init__(
        self,
        check_interval: int = 10,
        logger: Optional[StructuredLogger] = None,
    ):
        """
        初始化监控器。

        Args:
            check_interval: 检查间隔（秒）
            logger: 日志器
        """
        self.check_interval = check_interval
        self.logger = logger or StructuredLogger("live")

        self._status = MonitorStatus.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 组件（外部注入）
        self._position_manager: Optional[PositionManager] = None
        self._order_executor: Optional[OrderExecutor] = None
        self._risk_checker: Optional[RiskChecker] = None

        # 回调
        self._on_target_hit: Optional[Callable] = None
        self._on_signal: Optional[Callable] = None

        # 事件记录
        self._events: List[MonitorEvent] = []

    def set_position_manager(self, manager: PositionManager):
        """设置持仓管理器"""
        self._position_manager = manager

    def set_order_executor(self, executor: OrderExecutor):
        """设置订单执行器"""
        self._order_executor = executor

    def set_risk_checker(self, checker: RiskChecker):
        """设置风控检查器"""
        self._risk_checker = checker

    def on_target_hit(self, callback: Callable):
        """注册目标触发回调"""
        self._on_target_hit = callback

    def on_signal(self, callback: Callable):
        """注册信号生成回调"""
        self._on_signal = callback

    def start(self):
        """启动监控"""
        if self._status == MonitorStatus.RUNNING:
            self.logger.warning("监控器已在运行")
            return

        self._status = MonitorStatus.RUNNING
        self._stop_event.clear()

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self.logger.info("监控器已启动")

    def stop(self):
        """停止监控"""
        if self._status != MonitorStatus.RUNNING:
            return

        self._status = MonitorStatus.STOPPED
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5)

        self.logger.info("监控器已停止")

    def pause(self):
        """暂停监控"""
        if self._status == MonitorStatus.RUNNING:
            self._status = MonitorStatus.PAUSED
            self.logger.info("监控器已暂停")

    def resume(self):
        """恢复监控"""
        if self._status == MonitorStatus.PAUSED:
            self._status = MonitorStatus.RUNNING
            self.logger.info("监控器已恢复")

    def _run_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            if self._status == MonitorStatus.RUNNING:
                try:
                    self._check_targets()
                except Exception as e:
                    self._log_event("ERROR", {"error": str(e)}, f"检查异常: {e}")

            time.sleep(self.check_interval)

    def _check_targets(self):
        """检查持仓目标"""
        if not self._position_manager:
            return

        hits = self._position_manager.check_targets()

        for hit in hits:
            self._log_event(
                "TARGET_HIT",
                {
                    "symbol": hit.symbol,
                    "type": hit.hit_type,
                    "price": hit.current_price,
                },
                f"目标触发: {hit.symbol} {hit.hit_type}",
            )

            if self._on_target_hit:
                self._on_target_hit(hit)

    def process_signal(self, signal: StrategySignal, positions: List[Position],
                       account_balance: float, used_margin: float) -> Optional[Order]:
        """
        处理交易信号。

        Args:
            signal: 交易信号
            positions: 当前持仓
            account_balance: 账户余额
            used_margin: 已用保证金

        Returns:
            订单对象（如果通过风控）
        """
        # 风控检查
        if self._risk_checker:
            result = self._risk_checker.check(
                signal, positions, account_balance, used_margin
            )
            if not result.passed:
                self._log_event(
                    "RISK_CHECK_FAILED",
                    {"violations": result.violations},
                    f"风控检查未通过: {result.violations}",
                )
                return None

        # 创建订单
        if self._order_executor:
            order = self._order_executor.create_order(signal)

            self._log_event(
                "ORDER_CREATED",
                {"order_id": order.order_id, "symbol": signal.symbol},
                f"订单创建: {order.order_id}",
            )

            return order

        return None

    def _log_event(self, event_type: str, data: dict, message: str = ""):
        """记录事件"""
        event = MonitorEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            data=data,
            message=message,
        )
        self._events.append(event)

        # 只保留最近100个事件
        if len(self._events) > 100:
            self._events = self._events[-100:]

        self.logger.info(message, **data)

    def get_events(self, limit: int = 20) -> List[MonitorEvent]:
        """获取事件记录"""
        return self._events[-limit:]

    def get_recent_events(self, event_type: str = None, limit: int = 10) -> List[MonitorEvent]:
        """获取特定类型的最近事件"""
        events = self._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    @property
    def status(self) -> MonitorStatus:
        return self._status