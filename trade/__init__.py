"""
WiseCoin 交易层。

提供持仓管理、订单执行、风控检查等功能。

模块说明:
- position.py: 持仓管理、目标管理、止盈止损、期权定价、风险度量
- position_mock.py: 模拟持仓管理、持仓生成器
- executor.py: 订单执行
- risk.py: 风控检查
"""

from trade.position import (
    # 基础类
    BasePositionManager,
    PositionManager,
    TargetConfig,
    TargetHit,
    # 期权定价
    OptionPricer,
    # 价格模拟
    PriceSimulator,
    # 风险度量
    RiskMetrics,
    # 持仓分析
    PositionAnalyzer,
    # 工具函数
    get_variety_code,
    normalize_contract_code,
    is_index_underlying,
    # 配置常量
    NIGHT_TRADING_VARIETIES,
    MIN_MARGIN,
    MAX_MARGIN,
)
from trade.position_mock import (
    MockPosition,
    MockPositionManager,
    MockPositionGenerator,
    TradeRecord,
)
from trade.executor import (
    Order,
    OrderCondition,
    OrderExecutor,
    OrderResult,
    OrderStatus,
    OrderType,
    Offset,
    Direction,
    Quote,
    PositionInfo,
    get_smart_offset,
    infer_direction_from_price_field,
    TqSdkExecutorAdapter,
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
    # Option pricing
    'OptionPricer',
    # Price simulation
    'PriceSimulator',
    # Risk metrics
    'RiskMetrics',
    # Position analysis
    'PositionAnalyzer',
    # Utility functions
    'get_variety_code',
    'normalize_contract_code',
    'is_index_underlying',
    # Configuration constants
    'NIGHT_TRADING_VARIETIES',
    'MIN_MARGIN',
    'MAX_MARGIN',
    # Mock trading
    'MockPosition',
    'MockPositionManager',
    'MockPositionGenerator',
    'TradeRecord',
    # Order execution
    'Order',
    'OrderCondition',
    'OrderExecutor',
    'OrderResult',
    'OrderStatus',
    'OrderType',
    'Offset',
    'Direction',
    'Quote',
    'PositionInfo',
    'get_smart_offset',
    'infer_direction_from_price_field',
    'TqSdkExecutorAdapter',
    # Risk management
    'RiskChecker',
    'RiskCheckResult',
    'RiskConfig',
]