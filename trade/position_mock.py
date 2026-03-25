"""
模拟持仓管理模块。

用于策略回测和模拟交易，不依赖真实账户。
"""
from typing import List, Optional, Dict
from datetime import datetime
from dataclasses import dataclass, field

from trade.position import BasePositionManager, TargetConfig, TargetHit
from core.models import Position


@dataclass
class MockPosition:
    """模拟持仓"""
    symbol: str
    exchange_id: str
    direction: str  # LONG / SHORT
    volume: int
    avg_price: float
    margin: float
    open_time: datetime = None
    current_price: float = 0.0

    def __post_init__(self):
        if self.open_time is None:
            self.open_time = datetime.now()

    def unrealized_pnl(self) -> float:
        """计算未实现盈亏"""
        if self.direction == "LONG":
            return (self.current_price - self.avg_price) * self.volume
        else:
            return (self.avg_price - self.current_price) * self.volume

    def to_position(self) -> Position:
        """转换为 Position 模型"""
        return Position(
            symbol=self.symbol,
            exchange_id=self.exchange_id,
            direction=self.direction,
            volume=self.volume,
            avg_price=self.avg_price,
            current_price=self.current_price,
            unrealized_pnl=self.unrealized_pnl(),
            margin=self.margin,
        )


@dataclass
class TradeRecord:
    """交易记录"""
    action: str  # OPEN / CLOSE
    symbol: str
    direction: str
    volume: int
    price: float
    timestamp: datetime
    pnl: float = 0.0


class MockPositionManager(BasePositionManager):
    """
    模拟持仓管理器。

    用于策略回测，管理虚拟账户资金和持仓。

    Attributes:
        initial_capital: 初始资金
        current_capital: 当前可用资金
        positions: 模拟持仓字典
        trade_history: 交易记录列表
    """

    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, MockPosition] = {}
        self.trade_history: List[TradeRecord] = []
        self._margin_rate = 0.1  # 保证金率 10%

    def get_positions(self) -> List[Position]:
        """获取所有模拟持仓"""
        return [p.to_position() for p in self.positions.values() if p.volume > 0]

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定合约持仓"""
        mock_pos = self.positions.get(symbol)
        if mock_pos and mock_pos.volume > 0:
            return mock_pos.to_position()
        return None

    def open_position(
        self,
        symbol: str,
        exchange_id: str,
        direction: str,
        volume: int,
        price: float,
        timestamp: datetime = None,
    ) -> bool:
        """
        开仓。

        Args:
            symbol: 合约代码
            exchange_id: 交易所代码
            direction: 方向 (LONG/SHORT)
            volume: 数量
            price: 开仓价格
            timestamp: 时间戳

        Returns:
            是否成功开仓
        """
        margin = self._calculate_margin(price, volume)
        if margin > self.current_capital:
            return False

        self.current_capital -= margin

        if symbol in self.positions:
            # 加仓
            existing = self.positions[symbol]
            total_volume = existing.volume + volume
            total_cost = existing.avg_price * existing.volume + price * volume
            existing.avg_price = total_cost / total_volume
            existing.volume = total_volume
            existing.margin += margin
        else:
            self.positions[symbol] = MockPosition(
                symbol=symbol,
                exchange_id=exchange_id,
                direction=direction,
                volume=volume,
                avg_price=price,
                margin=margin,
                open_time=timestamp or datetime.now(),
                current_price=price,
            )

        self.trade_history.append(TradeRecord(
            action='OPEN',
            symbol=symbol,
            direction=direction,
            volume=volume,
            price=price,
            timestamp=timestamp or datetime.now(),
        ))

        return True

    def close_position(
        self,
        symbol: str,
        volume: int,
        price: float,
        timestamp: datetime = None,
    ) -> Optional[float]:
        """
        平仓。

        Args:
            symbol: 合约代码
            volume: 平仓数量
            price: 平仓价格
            timestamp: 时间戳

        Returns:
            平仓盈亏，失败返回 None
        """
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        if volume > pos.volume:
            volume = pos.volume

        # 计算盈亏
        if pos.direction == "LONG":
            pnl = (price - pos.avg_price) * volume
        else:
            pnl = (pos.avg_price - price) * volume

        # 释放保证金
        margin_released = pos.margin * volume / pos.volume
        self.current_capital += margin_released + pnl

        # 更新持仓
        pos.volume -= volume
        pos.margin -= margin_released

        if pos.volume <= 0:
            del self.positions[symbol]

        self.trade_history.append(TradeRecord(
            action='CLOSE',
            symbol=symbol,
            direction=pos.direction,
            volume=volume,
            price=price,
            timestamp=timestamp or datetime.now(),
            pnl=pnl,
        ))

        return pnl

    def update_prices(self, prices: Dict[str, float]):
        """更新持仓价格"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price

    def _calculate_margin(self, price: float, volume: int) -> float:
        """计算保证金"""
        return price * volume * self._margin_rate

    def set_target(self, symbol: str, target_price: float = None,
                   stop_loss: float = None, take_profit: float = None) -> bool:
        """模拟环境不支持目标设置"""
        return False

    def check_targets(self) -> List[TargetHit]:
        """模拟环境不支持目标检查"""
        return []

    def get_total_pnl(self) -> float:
        """获取累计盈亏"""
        return sum(t.pnl for t in self.trade_history if t.action == 'CLOSE')

    def get_statistics(self) -> dict:
        """获取交易统计"""
        closed_trades = [t for t in self.trade_history if t.action == 'CLOSE']
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl < 0]

        return {
            'total_trades': len(closed_trades),
            'win_count': len(wins),
            'loss_count': len(losses),
            'win_rate': len(wins) / len(closed_trades) if closed_trades else 0,
            'total_pnl': self.get_total_pnl(),
            'current_capital': self.current_capital,
            'return_rate': (self.current_capital - self.initial_capital) / self.initial_capital,
        }