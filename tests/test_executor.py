# tests/test_executor.py
"""订单执行模块测试"""
import pytest
from datetime import datetime

from trade.executor import (
    OrderExecutor,
    Order,
    OrderResult,
    OrderStatus,
    OrderType,
)
from core.models import StrategySignal


class TestOrder:
    """Order 数据类测试"""

    def test_order_creation(self):
        """测试订单创建"""
        order = Order(
            symbol="au2406C480",
            exchange_id="SHFE",
            direction="BUY",
            volume=1,
            price=15.0,
            order_type=OrderType.LIMIT,
        )

        assert order.symbol == "au2406C480"
        assert order.exchange_id == "SHFE"
        assert order.direction == "BUY"
        assert order.volume == 1
        assert order.price == 15.0
        assert order.order_type == OrderType.LIMIT
        assert order.status == OrderStatus.PENDING
        assert order.order_id == ""
        assert order.filled_volume == 0
        assert order.filled_price == 0.0

    def test_order_auto_timestamp(self):
        """测试订单自动设置时间戳"""
        before = datetime.now()
        order = Order(
            symbol="au2406C480",
            exchange_id="SHFE",
            direction="BUY",
            volume=1,
            price=15.0,
            order_type=OrderType.LIMIT,
        )
        after = datetime.now()

        assert order.created_at is not None
        assert order.updated_at is not None
        assert before <= order.created_at <= after

    def test_order_is_active(self):
        """测试订单活跃状态判断"""
        order = Order(
            symbol="au2406C480",
            exchange_id="SHFE",
            direction="BUY",
            volume=1,
            price=15.0,
            order_type=OrderType.LIMIT,
        )

        assert order.is_active() is True

        order.status = OrderStatus.SUBMITTED
        assert order.is_active() is True

        order.status = OrderStatus.FILLED
        assert order.is_active() is False

        order.status = OrderStatus.CANCELLED
        assert order.is_active() is False

        order.status = OrderStatus.REJECTED
        assert order.is_active() is False

    def test_order_is_complete(self):
        """测试订单完成状态判断"""
        order = Order(
            symbol="au2406C480",
            exchange_id="SHFE",
            direction="BUY",
            volume=1,
            price=15.0,
            order_type=OrderType.LIMIT,
        )

        assert order.is_complete() is False

        order.status = OrderStatus.SUBMITTED
        assert order.is_complete() is False

        order.status = OrderStatus.FILLED
        assert order.is_complete() is True

        order.status = OrderStatus.CANCELLED
        assert order.is_complete() is True

        order.status = OrderStatus.REJECTED
        assert order.is_complete() is True


class TestOrderExecutor:
    """OrderExecutor 测试"""

    @pytest.fixture
    def executor(self):
        """创建执行器实例"""
        return OrderExecutor()

    @pytest.fixture
    def sample_signal(self):
        """创建示例策略信号"""
        return StrategySignal(
            symbol="au2406C480",
            direction="BUY",
            volume=2,
            price=15.5,
            score=0.85,
            strategy_type="volatility",
            reasons=["IV低", "Delta合适"],
        )

    def test_create_executor(self, executor):
        """测试创建执行器"""
        assert executor is not None
        assert executor._orders == {}
        assert executor._order_counter == 0

    def test_create_order_from_signal(self, executor, sample_signal):
        """测试从信号创建订单"""
        order = executor.create_order(sample_signal)

        assert order.symbol == "au2406C480"
        assert order.exchange_id == "SHFE"
        assert order.direction == "BUY"
        assert order.volume == 2
        assert order.price == 15.5
        assert order.order_type == OrderType.LIMIT
        assert order.status == OrderStatus.PENDING
        assert order.order_id != ""
        assert order.order_id.startswith("ORD")

    def test_create_order_with_market_type(self, executor, sample_signal):
        """测试创建市价订单"""
        order = executor.create_order(
            sample_signal,
            order_type=OrderType.MARKET
        )

        assert order.order_type == OrderType.MARKET

    def test_create_order_with_custom_exchange(self, executor, sample_signal):
        """测试创建指定交易所的订单"""
        order = executor.create_order(
            sample_signal,
            exchange_id="DCE"
        )

        assert order.exchange_id == "DCE"

    def test_order_stored_in_executor(self, executor, sample_signal):
        """测试订单存储在执行器中"""
        order = executor.create_order(sample_signal)

        assert order.order_id in executor._orders
        assert executor.get_order(order.order_id) == order

    def test_order_id_increments(self, executor, sample_signal):
        """测试订单ID递增"""
        order1 = executor.create_order(sample_signal)
        order2 = executor.create_order(sample_signal)
        order3 = executor.create_order(sample_signal)

        assert executor._order_counter == 3
        # 验证ID不同
        assert order1.order_id != order2.order_id
        assert order2.order_id != order3.order_id

    def test_create_orders_batch(self, executor):
        """测试批量创建订单"""
        signals = [
            StrategySignal(
                symbol="au2406C480",
                direction="BUY",
                volume=1,
                price=15.0,
                score=0.8,
                strategy_type="volatility",
            ),
            StrategySignal(
                symbol="au2406C460",
                direction="BUY",
                volume=2,
                price=20.0,
                score=0.9,
                strategy_type="volatility",
            ),
            StrategySignal(
                symbol="au2406C500",
                direction="SELL",
                volume=1,
                price=5.0,
                score=0.7,
                strategy_type="delta_neutral",
            ),
        ]

        orders = executor.create_orders(signals)

        assert len(orders) == 3
        assert orders[0].symbol == "au2406C480"
        assert orders[1].symbol == "au2406C460"
        assert orders[2].symbol == "au2406C500"
        assert executor._order_counter == 3


class TestOrderStatusTransitions:
    """订单状态转换测试"""

    @pytest.fixture
    def executor(self):
        """创建执行器实例"""
        return OrderExecutor()

    @pytest.fixture
    def sample_order(self):
        """创建示例订单"""
        return Order(
            symbol="au2406C480",
            exchange_id="SHFE",
            direction="BUY",
            volume=1,
            price=15.0,
            order_type=OrderType.LIMIT,
        )

    @pytest.fixture
    def sample_signal(self):
        """创建示例策略信号"""
        return StrategySignal(
            symbol="au2406C480",
            direction="BUY",
            volume=2,
            price=15.5,
            score=0.85,
            strategy_type="volatility",
            reasons=["IV低", "Delta合适"],
        )

    def test_submit_order(self, executor, sample_order):
        """测试提交订单"""
        result = executor.submit_order(sample_order)

        assert result.success is True
        assert result.message == "订单已提交"
        assert sample_order.status == OrderStatus.SUBMITTED

    def test_fill_order(self, executor, sample_order):
        """测试订单成交"""
        executor.submit_order(sample_order)
        result = executor.fill_order(
            sample_order,
            filled_volume=1,
            filled_price=15.2
        )

        assert result.success is True
        assert result.message == "订单已成交"
        assert sample_order.status == OrderStatus.FILLED
        assert sample_order.filled_volume == 1
        assert sample_order.filled_price == 15.2

    def test_fill_order_slippage(self, executor, sample_order):
        """测试订单成交滑点计算"""
        sample_order.price = 15.0
        executor.submit_order(sample_order)
        result = executor.fill_order(
            sample_order,
            filled_volume=1,
            filled_price=15.5
        )

        assert result.slippage == 0.5

    def test_fill_order_no_slippage_for_market_order(self, executor):
        """测试市价单成交无滑点计算"""
        market_order = Order(
            symbol="au2406C480",
            exchange_id="SHFE",
            direction="BUY",
            volume=1,
            price=None,  # 市价单无价格
            order_type=OrderType.MARKET,
        )
        executor.submit_order(market_order)
        result = executor.fill_order(
            market_order,
            filled_volume=1,
            filled_price=15.5
        )

        assert result.slippage == 0.0

    def test_cancel_active_order(self, executor, sample_order):
        """测试取消活跃订单"""
        executor.submit_order(sample_order)
        result = executor.cancel_order(sample_order, reason="用户取消")

        assert result.success is True
        assert "订单已取消" in result.message
        assert sample_order.status == OrderStatus.CANCELLED

    def test_cancel_pending_order(self, executor, sample_order):
        """测试取消待处理订单"""
        result = executor.cancel_order(sample_order, reason="用户取消")

        assert result.success is True
        assert sample_order.status == OrderStatus.CANCELLED

    def test_cancel_filled_order_fails(self, executor, sample_order):
        """测试取消已成交订单失败"""
        executor.submit_order(sample_order)
        executor.fill_order(sample_order, 1, 15.0)

        result = executor.cancel_order(sample_order, reason="尝试取消")

        assert result.success is False
        assert result.message == "订单不可取消"

    def test_cancel_cancelled_order_fails(self, executor, sample_order):
        """测试取消已取消订单失败"""
        executor.cancel_order(sample_order, reason="第一次取消")

        result = executor.cancel_order(sample_order, reason="再次取消")

        assert result.success is False
        assert result.message == "订单不可取消"

    def test_full_order_lifecycle(self, executor, sample_signal):
        """测试完整订单生命周期"""
        # 1. 创建订单
        order = executor.create_order(sample_signal)
        assert order.status == OrderStatus.PENDING
        assert order.is_active() is True
        assert order.is_complete() is False

        # 2. 提交订单
        result = executor.submit_order(order)
        assert result.success is True
        assert order.status == OrderStatus.SUBMITTED
        assert order.is_active() is True
        assert order.is_complete() is False

        # 3. 成交订单
        result = executor.fill_order(order, filled_volume=1, filled_price=15.6)
        assert result.success is True
        assert order.status == OrderStatus.FILLED
        assert order.is_active() is False
        assert order.is_complete() is True


class TestOrderFiltering:
    """订单过滤测试"""

    @pytest.fixture
    def executor(self):
        """创建执行器实例"""
        return OrderExecutor()

    def test_get_active_orders(self, executor):
        """测试获取活跃订单"""
        signal1 = StrategySignal(
            symbol="au2406C480",
            direction="BUY",
            volume=1,
            price=15.0,
            score=0.8,
            strategy_type="test",
        )
        signal2 = StrategySignal(
            symbol="au2406C460",
            direction="SELL",
            volume=1,
            price=20.0,
            score=0.9,
            strategy_type="test",
        )
        signal3 = StrategySignal(
            symbol="au2406C500",
            direction="BUY",
            volume=1,
            price=5.0,
            score=0.7,
            strategy_type="test",
        )

        order1 = executor.create_order(signal1)
        order2 = executor.create_order(signal2)
        order3 = executor.create_order(signal3)

        # 所有订单都是 PENDING，应该全部活跃
        active_orders = executor.get_active_orders()
        assert len(active_orders) == 3

        # 提交并成交 order1
        executor.submit_order(order1)
        executor.fill_order(order1, 1, 15.0)

        active_orders = executor.get_active_orders()
        assert len(active_orders) == 2
        assert order1 not in active_orders
        assert order2 in active_orders
        assert order3 in active_orders

        # 取消 order2
        executor.cancel_order(order2)

        active_orders = executor.get_active_orders()
        assert len(active_orders) == 1
        assert order3 in active_orders

    def test_get_pending_orders(self, executor):
        """测试获取待处理订单"""
        signal1 = StrategySignal(
            symbol="au2406C480",
            direction="BUY",
            volume=1,
            price=15.0,
            score=0.8,
            strategy_type="test",
        )
        signal2 = StrategySignal(
            symbol="au2406C460",
            direction="SELL",
            volume=1,
            price=20.0,
            score=0.9,
            strategy_type="test",
        )

        order1 = executor.create_order(signal1)
        order2 = executor.create_order(signal2)

        # 所有订单都是 PENDING
        pending_orders = executor.get_pending_orders()
        assert len(pending_orders) == 2

        # 提交 order1
        executor.submit_order(order1)

        pending_orders = executor.get_pending_orders()
        assert len(pending_orders) == 1
        assert order1 not in pending_orders
        assert order2 in pending_orders

    def test_get_order_by_id(self, executor):
        """测试通过ID获取订单"""
        signal = StrategySignal(
            symbol="au2406C480",
            direction="BUY",
            volume=1,
            price=15.0,
            score=0.8,
            strategy_type="test",
        )

        order = executor.create_order(signal)

        found_order = executor.get_order(order.order_id)
        assert found_order == order

        not_found = executor.get_order("INVALID_ID")
        assert not_found is None


class TestOrderResult:
    """OrderResult 测试"""

    def test_order_result_creation(self):
        """测试订单结果创建"""
        order = Order(
            symbol="au2406C480",
            exchange_id="SHFE",
            direction="BUY",
            volume=1,
            price=15.0,
            order_type=OrderType.LIMIT,
        )

        result = OrderResult(
            order=order,
            success=True,
            message="订单已提交",
            slippage=0.5,
        )

        assert result.order == order
        assert result.success is True
        assert result.message == "订单已提交"
        assert result.slippage == 0.5

    def test_order_result_defaults(self):
        """测试订单结果默认值"""
        order = Order(
            symbol="au2406C480",
            exchange_id="SHFE",
            direction="BUY",
            volume=1,
            price=15.0,
            order_type=OrderType.LIMIT,
        )

        result = OrderResult(order=order, success=True)

        assert result.message == ""
        assert result.slippage == 0.0