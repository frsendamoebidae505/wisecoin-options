# trade/position.py
"""
持仓管理模块。

提供持仓查询、目标管理、止盈止损功能。
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

from core.models import Position


@dataclass
class TargetConfig:
    """持仓目标配置"""
    symbol: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class TargetHit:
    """目标触发事件"""
    symbol: str
    position: Position
    target: TargetConfig
    hit_type: str  # STOP_LOSS, TAKE_PROFIT, TARGET
    current_price: float
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class BasePositionManager(ABC):
    """持仓管理器基类"""

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """获取当前持仓"""
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定合约持仓"""
        pass

    @abstractmethod
    def set_target(self, symbol: str, target_price: float = None,
                   stop_loss: float = None, take_profit: float = None) -> bool:
        """设置持仓目标"""
        pass

    @abstractmethod
    def check_targets(self) -> List[TargetHit]:
        """检查是否有持仓触及目标"""
        pass


class PositionManager(BasePositionManager):
    """
    持仓管理器。

    管理持仓目标和止盈止损配置。
    注意：此版本不依赖 TqSDK，仅管理配置。
    实际持仓数据需要从外部注入。

    Attributes:
        positions: 当前持仓字典（外部注入）
        targets: 目标配置字典
    """

    def __init__(self):
        self._positions: Dict[str, Position] = {}
        self._targets: Dict[str, TargetConfig] = {}

    def update_positions(self, positions: List[Position]):
        """更新持仓数据（外部调用）"""
        self._positions = {p.symbol: p for p in positions if p.volume > 0}

    def get_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self._positions.values())

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定合约持仓"""
        return self._positions.get(symbol)

    def set_target(self, symbol: str, target_price: float = None,
                   stop_loss: float = None, take_profit: float = None) -> bool:
        """设置持仓目标"""
        self._targets[symbol] = TargetConfig(
            symbol=symbol,
            target_price=target_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        return True

    def get_target(self, symbol: str) -> Optional[TargetConfig]:
        """获取目标配置"""
        return self._targets.get(symbol)

    def remove_target(self, symbol: str) -> bool:
        """移除目标配置"""
        if symbol in self._targets:
            del self._targets[symbol]
            return True
        return False

    def check_targets(self) -> List[TargetHit]:
        """检查持仓目标"""
        hits = []
        for symbol, target in self._targets.items():
            position = self._positions.get(symbol)
            if not position:
                continue

            current_price = position.current_price

            # 检查止损
            if target.stop_loss and current_price <= target.stop_loss:
                hits.append(TargetHit(
                    symbol=symbol,
                    position=position,
                    target=target,
                    hit_type='STOP_LOSS',
                    current_price=current_price,
                ))
            # 检查止盈
            elif target.take_profit and current_price >= target.take_profit:
                hits.append(TargetHit(
                    symbol=symbol,
                    position=position,
                    target=target,
                    hit_type='TAKE_PROFIT',
                    current_price=current_price,
                ))
            # 检查目标价
            elif target.target_price and current_price >= target.target_price:
                hits.append(TargetHit(
                    symbol=symbol,
                    position=position,
                    target=target,
                    hit_type='TARGET',
                    current_price=current_price,
                ))

        return hits

    def get_total_margin(self) -> float:
        """获取总保证金占用"""
        return sum(p.margin for p in self._positions.values())

    def get_total_unrealized_pnl(self) -> float:
        """获取总未实现盈亏"""
        return sum(p.unrealized_pnl for p in self._positions.values())