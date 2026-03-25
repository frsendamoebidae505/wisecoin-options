# trade/executor.py
"""
订单执行模块。

提供订单生成、执行确认等功能。
注意：此版本不依赖 TqSDK，仅生成订单指令。
"""
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.models import StrategySignal
from common.logger import StructuredLogger


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class Order:
    """订单"""
    symbol: str
    exchange_id: str
    direction: str  # BUY / SELL
    volume: int
    price: Optional[float]
    order_type: OrderType
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = ""
    filled_volume: int = 0
    filled_price: float = 0.0
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED)

    def is_complete(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED)


@dataclass
class OrderResult:
    """订单执行结果"""
    order: Order
    success: bool
    message: str = ""
    slippage: float = 0.0


class OrderExecutor:
    """
    订单执行器。

    生成订单指令，不直接连接交易所。
    实际执行需要外部系统完成。

    Example:
        >>> executor = OrderExecutor()
        >>> order = executor.create_order(signal)
    """

    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger("executor")
        self._orders: Dict[str, Order] = {}
        self._order_counter = 0

    def create_order(
        self,
        signal: StrategySignal,
        exchange_id: str = "SHFE",
        order_type: OrderType = OrderType.LIMIT,
    ) -> Order:
        """
        根据信号创建订单。

        Args:
            signal: 策略信号
            exchange_id: 交易所代码
            order_type: 订单类型

        Returns:
            订单对象
        """
        self._order_counter += 1
        order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{self._order_counter:04d}"

        order = Order(
            symbol=signal.symbol,
            exchange_id=exchange_id,
            direction=signal.direction,
            volume=signal.volume,
            price=signal.price,
            order_type=order_type,
            order_id=order_id,
        )

        self._orders[order_id] = order
        self.logger.info(
            f"创建订单: {order_id}",
            symbol=signal.symbol,
            direction=signal.direction,
            volume=signal.volume,
            price=signal.price,
        )

        return order

    def create_orders(
        self,
        signals: List[StrategySignal],
        exchange_id: str = "SHFE",
    ) -> List[Order]:
        """批量创建订单"""
        return [self.create_order(s, exchange_id) for s in signals]

    def submit_order(self, order: Order) -> OrderResult:
        """
        提交订单（模拟）。

        实际执行需要外部系统完成，此处仅更新状态。
        """
        order.status = OrderStatus.SUBMITTED
        order.updated_at = datetime.now()

        self.logger.info(f"订单已提交: {order.order_id}")

        return OrderResult(
            order=order,
            success=True,
            message="订单已提交",
        )

    def fill_order(
        self,
        order: Order,
        filled_volume: int,
        filled_price: float,
    ) -> OrderResult:
        """
        填充订单（外部调用）。

        Args:
            order: 订单对象
            filled_volume: 成交数量
            filled_price: 成交价格
        """
        order.filled_volume = filled_volume
        order.filled_price = filled_price
        order.status = OrderStatus.FILLED
        order.updated_at = datetime.now()

        # 计算滑点
        if order.price:
            slippage = abs(filled_price - order.price)
        else:
            slippage = 0.0

        self.logger.info(
            f"订单成交: {order.order_id}",
            filled_volume=filled_volume,
            filled_price=filled_price,
            slippage=slippage,
        )

        return OrderResult(
            order=order,
            success=True,
            message="订单已成交",
            slippage=slippage,
        )

    def cancel_order(self, order: Order, reason: str = "") -> OrderResult:
        """取消订单"""
        if not order.is_active():
            return OrderResult(
                order=order,
                success=False,
                message="订单不可取消",
            )

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now()

        self.logger.info(f"订单已取消: {order.order_id}, 原因: {reason}")

        return OrderResult(
            order=order,
            success=True,
            message=f"订单已取消: {reason}",
        )

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self._orders.get(order_id)

    def get_active_orders(self) -> List[Order]:
        """获取活跃订单"""
        return [o for o in self._orders.values() if o.is_active()]

    def get_pending_orders(self) -> List[Order]:
        """获取待处理订单"""
        return [o for o in self._orders.values() if o.status == OrderStatus.PENDING]