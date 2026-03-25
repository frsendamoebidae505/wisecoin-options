"""
WiseCoin 交易层。

提供持仓管理、订单执行、风控检查等功能。
"""

from trade.position import (
    BasePositionManager,
    PositionManager,
    TargetConfig,
    TargetHit,
)
from trade.position_mock import (
    MockPosition,
    MockPositionManager,
    TradeRecord,
)
from trade.executor import (
    Order,
    OrderExecutor,
    OrderResult,
    OrderStatus,
    OrderType,
)
from trade.risk import (
    RiskChecker,
    RiskCheckResult,
    RiskConfig,
)

__all__ = [
    # Position management
    'BasePositionManager',
    'PositionManager',
    'TargetConfig',
    'TargetHit',
    # Mock trading
    'MockPosition',
    'MockPositionManager',
    'TradeRecord',
    # Order execution
    'Order',
    'OrderExecutor',
    'OrderResult',
    'OrderStatus',
    'OrderType',
    # Risk management
    'RiskChecker',
    'RiskCheckResult',
    'RiskConfig',
]