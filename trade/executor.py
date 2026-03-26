# trade/executor.py
"""
订单执行模块。

提供订单生成、执行确认、盘口吃单等功能。
注意：此版本不依赖 TqSDK，仅生成订单指令。
TqSDK 相关代码应通过适配器模式注入。
"""
from typing import List, Optional, Dict, Callable, Any, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
import asyncio

from core.models import StrategySignal
from common.logger import StructuredLogger


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class Offset(str, Enum):
    """开平方向"""
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    CLOSETODAY = "CLOSETODAY"
    CLOSEYESTERDAY = "CLOSEYESTERDAY"


class Direction(str, Enum):
    """买卖方向"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Quote:
    """
    盘口行情模型。

    用于订单执行时的价格条件判断。
    """
    symbol: str
    last_price: float
    bid_price1: float
    ask_price1: float
    bid_volume1: int
    ask_volume1: int
    bid_price2: float = 0.0
    ask_price2: float = 0.0
    bid_volume2: int = 0
    ask_volume2: int = 0
    datetime: Optional[datetime] = None

    def is_valid(self) -> bool:
        """检查行情是否有效"""
        return not (
            math.isnan(self.bid_price1) or
            math.isnan(self.ask_price1)
        )

    def get_price(self, price_field: str) -> float:
        """获取指定价格字段"""
        return getattr(self, price_field, float('nan'))

    def get_volume(self, volume_field: str) -> int:
        """获取指定数量字段"""
        return getattr(self, volume_field, 0)


@dataclass
class Order:
    """订单"""
    symbol: str
    exchange_id: str
    direction: str  # BUY / SELL
    offset: str  # OPEN / CLOSE / CLOSETODAY
    volume: int
    price: Optional[float]
    order_type: OrderType
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = ""
    filled_volume: int = 0
    filled_price: float = 0.0
    created_at: datetime = None
    updated_at: datetime = None
    message: str = ""

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL)

    def is_complete(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED)

    def remaining_volume(self) -> int:
        return self.volume - self.filled_volume


@dataclass
class OrderResult:
    """订单执行结果"""
    order: Optional[Order]
    success: bool
    message: str = ""
    slippage: float = 0.0
    error_code: str = ""


@dataclass
class OrderCondition:
    """
    订单执行条件。

    用于盘口吃单时的条件判断。
    """
    price_field: str = "ask_price1"  # 监控的价格字段
    target_price: Optional[float] = None  # 目标价格 (None 表示不检查价格)
    price_operator: str = "=="  # ==, <=, >=, <, >
    volume_field: str = "ask_volume1"  # 监控的数量字段
    target_volume: Optional[int] = None  # 目标数量 (None 表示不检查数量)
    volume_operator: str = ">="  # ==, >=, <=, >, <

    def check_price(self, current_price: float) -> tuple[bool, str]:
        """
        检查价格条件。

        Args:
            current_price: 当前价格

        Returns:
            (是否满足, 消息)
        """
        if self.target_price is None:
            return True, "价格条件未设置，跳过检查"

        if math.isnan(current_price):
            return False, f"价格无效 (NaN)"

        if self.price_operator == "==":
            met = current_price == self.target_price
        elif self.price_operator == "<=":
            met = current_price <= self.target_price
        elif self.price_operator == ">=":
            met = current_price >= self.target_price
        elif self.price_operator == "<":
            met = current_price < self.target_price
        elif self.price_operator == ">":
            met = current_price > self.target_price
        else:
            return False, f"未知的价格操作符: {self.price_operator}"

        if met:
            return True, f"价格满足: {current_price} {self.price_operator} {self.target_price}"
        else:
            return False, f"价格不满足: {current_price} {self.price_operator} {self.target_price}"

    def check_volume(self, current_volume: int) -> tuple[bool, str]:
        """
        检查数量条件。

        Args:
            current_volume: 当前数量

        Returns:
            (是否满足, 消息)
        """
        if self.target_volume is None:
            return True, "数量条件未设置，跳过检查"

        if self.volume_operator == "==":
            met = current_volume == self.target_volume
        elif self.volume_operator == ">=":
            met = current_volume >= self.target_volume
        elif self.volume_operator == "<=":
            met = current_volume <= self.target_volume
        elif self.volume_operator == ">":
            met = current_volume > self.target_volume
        elif self.volume_operator == "<":
            met = current_volume < self.target_volume
        else:
            return False, f"未知的数量操作符: {self.volume_operator}"

        if met:
            return True, f"数量满足: {current_volume} {self.volume_operator} {self.target_volume}"
        else:
            return False, f"数量不满足: {current_volume} {self.volume_operator} {self.target_volume}"

    def check(self, quote: Quote) -> tuple[bool, str, str]:
        """
        检查所有条件。

        Args:
            quote: 盘口行情

        Returns:
            (是否满足, 价格消息, 数量消息)
        """
        current_price = quote.get_price(self.price_field)
        current_volume = quote.get_volume(self.volume_field)

        price_met, price_msg = self.check_price(current_price)

        if not price_met:
            return False, price_msg, "价格条件不满足，跳过数量检查"

        volume_met, volume_msg = self.check_volume(current_volume)

        return price_met and volume_met, price_msg, volume_msg


@dataclass
class PositionInfo:
    """
    持仓信息（用于平仓决策）。

    简化的持仓模型，用于 smart_offset 计算。
    """
    volume_long: int = 0
    volume_short: int = 0
    volume_long_today: int = 0
    volume_short_today: int = 0
    volume_long_his: int = 0
    volume_short_his: int = 0


def get_smart_offset(
    symbol: str,
    position: Optional[PositionInfo],
    direction: str,
    requested_offset: str
) -> str:
    """
    智能获取 Offset，适配交易所逻辑（特别是上期所平今/平昨）。

    Args:
        symbol: 合约代码 (如 SHFE.au2406C480)
        position: 持仓信息对象
        direction: 下单方向 (BUY/SELL)
        requested_offset: 请求的开平操作 (OPEN/CLOSE)

    Returns:
        最终的 offset 值

    Example:
        >>> position = PositionInfo(volume_long_today=5)
        >>> get_smart_offset("SHFE.au2406C480", position, "SELL", "CLOSE")
        'CLOSETODAY'
    """
    if requested_offset == Offset.OPEN or requested_offset == "OPEN":
        return Offset.OPEN.value

    if position is None:
        return Offset.CLOSE.value

    # 解析交易所
    parts = symbol.split('.')
    exchange = parts[0] if len(parts) > 1 else ""

    # 上期所和上期能源需要区分平今平昨
    if exchange in ['SHFE', 'INE']:
        # 如果是平仓
        # BUY (平空) -> 检查 short position
        # SELL (平多) -> 检查 long position
        if direction == Direction.BUY or direction == "BUY":
            pos_today = getattr(position, 'volume_short_today', 0) or 0
        else:
            pos_today = getattr(position, 'volume_long_today', 0) or 0

        if pos_today > 0:
            return Offset.CLOSETODAY.value

    return Offset.CLOSE.value


def infer_direction_from_price_field(price_field: str) -> Optional[str]:
    """
    根据价格字段自动推断交易方向。

    Args:
        price_field: 价格字段名 (ask_price1 / bid_price1)

    Returns:
        推断的方向 (BUY/SELL/None)

    Example:
        >>> infer_direction_from_price_field("ask_price1")
        'BUY'
        >>> infer_direction_from_price_field("bid_price1")
        'SELL'
    """
    if "ask" in price_field.lower():
        return Direction.BUY.value
    elif "bid" in price_field.lower():
        return Direction.SELL.value
    return None


class OrderExecutor:
    """
    订单执行器。

    生成订单指令，支持盘口吃单逻辑。
    实际执行需要外部系统完成（如 TqSDK 适配器）。

    Example:
        >>> executor = OrderExecutor()
        >>> order = executor.create_order(signal)
        >>> result = executor.execute_with_condition(order, quote, condition)
    """

    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger("executor")
        self._orders: Dict[str, Order] = {}
        self._order_counter = 0

        # 执行器回调（由外部注入，如 TqSDK 适配器）
        self._submit_callback: Optional[Callable[[Order], Awaitable[OrderResult]]] = None
        self._cancel_callback: Optional[Callable[[Order], Awaitable[OrderResult]]] = None

    def set_submit_callback(self, callback: Callable[[Order], Awaitable[OrderResult]]):
        """
        设置订单提交回调。

        Args:
            callback: 异步回调函数，接收 Order，返回 OrderResult
        """
        self._submit_callback = callback

    def set_cancel_callback(self, callback: Callable[[Order], Awaitable[OrderResult]]):
        """
        设置订单取消回调。

        Args:
            callback: 异步回调函数，接收 Order，返回 OrderResult
        """
        self._cancel_callback = callback

    def create_order(
        self,
        symbol: str,
        direction: str,
        offset: str,
        volume: int,
        price: Optional[float] = None,
        exchange_id: str = "SHFE",
        order_type: OrderType = OrderType.LIMIT,
    ) -> Order:
        """
        创建订单。

        Args:
            symbol: 合约代码
            direction: 方向 (BUY/SELL)
            offset: 开平 (OPEN/CLOSE/CLOSETODAY)
            volume: 数量
            price: 价格 (限价单必填)
            exchange_id: 交易所代码
            order_type: 订单类型

        Returns:
            订单对象
        """
        self._order_counter += 1
        order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{self._order_counter:04d}"

        order = Order(
            symbol=symbol,
            exchange_id=exchange_id,
            direction=direction,
            offset=offset,
            volume=volume,
            price=price,
            order_type=order_type,
            order_id=order_id,
        )

        self._orders[order_id] = order
        self.logger.info(
            f"创建订单: {order_id}",
            symbol=symbol,
            direction=direction,
            offset=offset,
            volume=volume,
            price=price,
        )

        return order

    def create_order_from_signal(
        self,
        signal: StrategySignal,
        exchange_id: str = "SHFE",
        order_type: OrderType = OrderType.LIMIT,
        offset: str = "OPEN",
    ) -> Order:
        """
        根据信号创建订单。

        Args:
            signal: 策略信号
            exchange_id: 交易所代码
            order_type: 订单类型
            offset: 开平方向

        Returns:
            订单对象
        """
        return self.create_order(
            symbol=signal.symbol,
            direction=signal.direction,
            offset=offset,
            volume=signal.volume,
            price=signal.price,
            exchange_id=exchange_id,
            order_type=order_type,
        )

    def create_smart_close_order(
        self,
        symbol: str,
        direction: str,
        volume: int,
        position: Optional[PositionInfo],
        price: Optional[float] = None,
        exchange_id: str = "SHFE",
    ) -> Order:
        """
        创建智能平仓订单（自动处理平今平昨）。

        Args:
            symbol: 合约代码
            direction: 方向 (BUY/SELL)
            volume: 数量
            position: 持仓信息
            price: 价格
            exchange_id: 交易所代码

        Returns:
            订单对象
        """
        smart_offset = get_smart_offset(symbol, position, direction, "CLOSE")

        return self.create_order(
            symbol=symbol,
            direction=direction,
            offset=smart_offset,
            volume=volume,
            price=price,
            exchange_id=exchange_id,
        )

    def create_orders(
        self,
        signals: List[StrategySignal],
        exchange_id: str = "SHFE",
    ) -> List[Order]:
        """批量创建订单"""
        return [self.create_order_from_signal(s, exchange_id) for s in signals]

    async def submit_order(self, order: Order) -> OrderResult:
        """
        提交订单。

        如果设置了提交回调，则调用回调执行；
        否则仅更新状态为 SUBMITTED。

        Args:
            order: 订单对象

        Returns:
            执行结果
        """
        if self._submit_callback:
            result = await self._submit_callback(order)
            if result.success and result.order:
                order.status = result.order.status
                order.filled_volume = result.order.filled_volume
                order.filled_price = result.order.filled_price
            return result

        # 无回调时仅更新状态
        order.status = OrderStatus.SUBMITTED
        order.updated_at = datetime.now()

        self.logger.info(f"订单已提交: {order.order_id}")

        return OrderResult(
            order=order,
            success=True,
            message="订单已提交",
        )

    def submit_order_sync(self, order: Order) -> OrderResult:
        """
        同步提交订单（简化版，用于测试和简单场景）。

        仅更新订单状态为 SUBMITTED，不执行实际提交。

        Args:
            order: 订单对象

        Returns:
            执行结果
        """
        order.status = OrderStatus.SUBMITTED
        order.updated_at = datetime.now()
        if not order.order_id:
            self._order_counter += 1
            order.order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{self._order_counter:04d}"
        self._orders[order.order_id] = order
        self.logger.info(f"订单已提交: {order.order_id}")
        return OrderResult(
            order=order,
            success=True,
            message="订单已提交",
        )

    async def submit_and_wait(
        self,
        order: Order,
        timeout_seconds: float = 5.0,
        check_interval: float = 0.5,
    ) -> OrderResult:
        """
        提交订单并等待成交。

        Args:
            order: 订单对象
            timeout_seconds: 超时时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            执行结果
        """
        result = await self.submit_order(order)

        if not result.success:
            return result

        # 等待成交
        check_count = 0
        max_checks = int(timeout_seconds / check_interval)

        while check_count < max_checks:
            await asyncio.sleep(check_interval)
            check_count += 1

            if order.is_complete():
                break

        if order.status == OrderStatus.FILLED:
            return OrderResult(
                order=order,
                success=True,
                message="订单已完全成交",
            )
        else:
            return OrderResult(
                order=order,
                success=False,
                message=f"订单未完全成交，当前状态: {order.status}",
            )

    def check_condition(
        self,
        quote: Quote,
        condition: OrderCondition,
    ) -> tuple[bool, Dict[str, str]]:
        """
        检查盘口条件。

        Args:
            quote: 盘口行情
            condition: 执行条件

        Returns:
            (是否满足, 各项检查消息)
        """
        if not quote.is_valid():
            return False, {"error": "行情数据无效"}

        met, price_msg, volume_msg = condition.check(quote)

        return met, {
            "price": price_msg,
            "volume": volume_msg,
        }

    async def execute_with_condition(
        self,
        order: Order,
        quote: Quote,
        condition: OrderCondition,
        auto_adjust_price: bool = True,
    ) -> OrderResult:
        """
        根据条件执行订单（盘口吃单）。

        Args:
            order: 订单对象
            quote: 盘口行情
            condition: 执行条件
            auto_adjust_price: 是否自动调整价格为盘口价格

        Returns:
            执行结果
        """
        # 检查条件
        met, messages = self.check_condition(quote, condition)

        self.logger.info(f"条件检查结果:")
        self.logger.info(f"  价格: {messages.get('price', 'N/A')}")
        self.logger.info(f"  数量: {messages.get('volume', 'N/A')}")

        if not met:
            self.logger.warning(f"盘口条件不满足，不执行订单")
            return OrderResult(
                order=order,
                success=False,
                message=f"条件不满足: {messages}",
            )

        # 自动调整价格
        if auto_adjust_price:
            if order.direction == Direction.BUY.value:
                order.price = quote.ask_price1
            else:
                order.price = quote.bid_price1

        self.logger.info(
            f"条件满足，执行订单: {order.symbol} {order.direction} {order.offset} "
            f"{order.volume}手 @ {order.price}"
        )

        return await self.submit_order(order)

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

    def partial_fill(
        self,
        order: Order,
        filled_volume: int,
        filled_price: float,
    ) -> OrderResult:
        """
        部分成交。

        Args:
            order: 订单对象
            filled_volume: 本次成交数量
            filled_price: 本次成交价格
        """
        total_filled = order.filled_volume + filled_volume
        # 计算加权平均成交价
        if order.filled_volume > 0:
            avg_price = (
                (order.filled_price * order.filled_volume + filled_price * filled_volume)
                / total_filled
            )
        else:
            avg_price = filled_price

        order.filled_volume = total_filled
        order.filled_price = avg_price
        order.status = OrderStatus.PARTIAL
        order.updated_at = datetime.now()

        self.logger.info(
            f"订单部分成交: {order.order_id}",
            filled_volume=filled_volume,
            filled_price=filled_price,
            total_filled=total_filled,
            remaining=order.remaining_volume(),
        )

        return OrderResult(
            order=order,
            success=True,
            message=f"部分成交 {filled_volume}手",
        )

    async def cancel_order(self, order: Order, reason: str = "") -> OrderResult:
        """
        取消订单。

        Args:
            order: 订单对象
            reason: 取消原因
        """
        if not order.is_active():
            return OrderResult(
                order=order,
                success=False,
                message="订单不可取消",
            )

        if self._cancel_callback:
            result = await self._cancel_callback(order)
            if result.success:
                order.status = OrderStatus.CANCELLED
                order.message = reason
            return result

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now()
        order.message = reason

        self.logger.info(f"订单已取消: {order.order_id}, 原因: {reason}")

        return OrderResult(
            order=order,
            success=True,
            message=f"订单已取消: {reason}",
        )

    def cancel_order_sync(self, order: Order, reason: str = "") -> OrderResult:
        """
        同步取消订单（简化版，用于测试和简单场景）。

        Args:
            order: 订单对象
            reason: 取消原因
        """
        if not order.is_active():
            return OrderResult(
                order=order,
                success=False,
                message="订单不可取消",
            )

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now()
        order.message = reason

        self.logger.info(f"订单已取消: {order.order_id}, 原因: {reason}")

        return OrderResult(
            order=order,
            success=True,
            message=f"订单已取消: {reason}",
        )

    def reject_order(self, order: Order, reason: str) -> OrderResult:
        """
        拒绝订单。

        Args:
            order: 订单对象
            reason: 拒绝原因
        """
        order.status = OrderStatus.REJECTED
        order.updated_at = datetime.now()
        order.message = reason

        self.logger.warning(f"订单被拒绝: {order.order_id}, 原因: {reason}")

        return OrderResult(
            order=order,
            success=False,
            message=f"订单被拒绝: {reason}",
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

    def get_filled_orders(self) -> List[Order]:
        """获取已成交订单"""
        return [o for o in self._orders.values() if o.status == OrderStatus.FILLED]

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """获取指定合约的订单"""
        return [o for o in self._orders.values() if o.symbol == symbol]

    def clear_history(self, keep_active: bool = True):
        """
        清理历史订单。

        Args:
            keep_active: 是否保留活跃订单
        """
        if keep_active:
            self._orders = {
                k: v for k, v in self._orders.items() if v.is_active()
            }
        else:
            self._orders.clear()

        self.logger.info(f"已清理历史订单")


class TqSdkExecutorAdapter:
    """
    TqSDK 执行器适配器。

    将 TqSDK 的 API 适配到 OrderExecutor。
    提供实际的订单执行能力。

    Example:
        >>> from tqsdk import TqApi, TqAuth
        >>> api = TqApi(auth=TqAuth('user', 'pass'))
        >>> adapter = TqSdkExecutorAdapter(api)
        >>> executor = OrderExecutor()
        >>> executor.set_submit_callback(adapter.submit)
    """

    def __init__(self, api, logger: Optional[StructuredLogger] = None):
        """
        初始化适配器。

        Args:
            api: TqApi 实例
            logger: 日志器
        """
        self.api = api
        self.logger = logger or StructuredLogger("tqsdk_adapter")
        self._orders: Dict[str, Any] = {}  # TqSDK order 对象缓存

    async def submit(self, order: Order) -> OrderResult:
        """
        提交订单到 TqSDK。

        Args:
            order: 订单对象

        Returns:
            执行结果
        """
        try:
            tq_order = self.api.insert_order(
                symbol=order.symbol,
                direction=order.direction,
                offset=order.offset,
                volume=order.volume,
                limit_price=order.price,
            )

            self._orders[order.order_id] = tq_order

            self.logger.info(
                f"TqSDK 订单已提交",
                order_id=order.order_id,
                tq_order_id=tq_order.order_id,
            )

            # 更新订单状态
            order.status = OrderStatus.SUBMITTED
            order.order_id = tq_order.order_id  # 使用 TqSDK 的 order_id

            return OrderResult(
                order=order,
                success=True,
                message="订单已提交到 TqSDK",
            )

        except Exception as e:
            self.logger.error(f"TqSDK 提交订单失败: {e}")

            return OrderResult(
                order=order,
                success=False,
                message=str(e),
                error_code="TQSDK_ERROR",
            )

    async def cancel(self, order: Order) -> OrderResult:
        """
        取消订单。

        Args:
            order: 订单对象

        Returns:
            执行结果
        """
        tq_order = self._orders.get(order.order_id)

        if tq_order is None:
            return OrderResult(
                order=order,
                success=False,
                message="未找到对应的 TqSDK 订单",
            )

        try:
            self.api.cancel_order(tq_order)

            order.status = OrderStatus.CANCELLED

            return OrderResult(
                order=order,
                success=True,
                message="订单已取消",
            )

        except Exception as e:
            self.logger.error(f"TqSDK 取消订单失败: {e}")

            return OrderResult(
                order=order,
                success=False,
                message=str(e),
            )

    def sync_order_status(self, order: Order) -> Order:
        """
        同步订单状态。

        从 TqSDK 订单对象同步状态到 Order 对象。

        Args:
            order: 订单对象

        Returns:
            更新后的订单对象
        """
        tq_order = self._orders.get(order.order_id)

        if tq_order is None:
            return order

        # 同步成交信息
        order.filled_volume = tq_order.volume_orign - tq_order.volume_left
        order.filled_price = tq_order.limit_price  # 简化处理

        # 同步状态
        if tq_order.status == "FINISHED":
            if order.filled_volume == order.volume:
                order.status = OrderStatus.FILLED
            else:
                order.status = OrderStatus.CANCELLED
        elif tq_order.status == "ALIVE":
            if order.filled_volume > 0:
                order.status = OrderStatus.PARTIAL
            else:
                order.status = OrderStatus.SUBMITTED

        return order

    async def get_quote(self, symbol: str) -> Quote:
        """
        获取盘口行情。

        Args:
            symbol: 合约代码

        Returns:
            Quote 对象
        """
        tq_quote = await self.api.get_quote(symbol)

        return Quote(
            symbol=symbol,
            last_price=tq_quote.last_price,
            bid_price1=tq_quote.bid_price1,
            ask_price1=tq_quote.ask_price1,
            bid_volume1=tq_quote.bid_volume1,
            ask_volume1=tq_quote.ask_volume1,
            bid_price2=tq_quote.bid_price2,
            ask_price2=tq_quote.ask_price2,
            bid_volume2=tq_quote.bid_volume2,
            ask_volume2=tq_quote.ask_volume2,
        )

    def get_position_info(self, symbol: str) -> PositionInfo:
        """
        获取持仓信息。

        Args:
            symbol: 合约代码

        Returns:
            PositionInfo 对象
        """
        tq_position = self.api.get_position(symbol)

        return PositionInfo(
            volume_long=tq_position.pos_long,
            volume_short=tq_position.pos_short,
            volume_long_today=tq_position.pos_long_today,
            volume_short_today=tq_position.pos_short_today,
            volume_long_his=tq_position.pos_long_his,
            volume_short_his=tq_position.pos_short_his,
        )