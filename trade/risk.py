# trade/risk.py
"""
风控检查模块。

提供交易前的风险检查，防止过度交易。
"""
from typing import List, Optional, Dict
from dataclasses import dataclass

from core.models import Position, StrategySignal
from common.logger import StructuredLogger
from common.exceptions import RiskCheckError


@dataclass
class RiskConfig:
    """风控配置"""
    max_position_per_symbol: int = 10      # 单合约最大持仓
    max_total_positions: int = 50           # 总持仓数量上限
    max_margin_usage: float = 0.8           # 最大保证金使用率
    max_single_order_value: float = 100000  # 单笔订单最大金额
    max_daily_trades: int = 100             # 每日最大交易次数
    min_account_balance: float = 50000      # 最低账户余额


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    passed: bool
    signal: StrategySignal
    violations: List[str]
    warnings: List[str]

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class RiskChecker:
    """
    风控检查器。

    在订单执行前进行风险检查。

    Example:
        >>> checker = RiskChecker(config)
        >>> result = checker.check(signal, positions, account)
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        logger: Optional[StructuredLogger] = None,
    ):
        self.config = config or RiskConfig()
        self.logger = logger or StructuredLogger("risk")
        self._daily_trade_count = 0
        self._trade_date = None

    def check(
        self,
        signal: StrategySignal,
        positions: List[Position],
        account_balance: float,
        used_margin: float,
    ) -> RiskCheckResult:
        """
        执行风控检查。

        Args:
            signal: 交易信号
            positions: 当前持仓列表
            account_balance: 账户余额
            used_margin: 已用保证金

        Returns:
            风控检查结果
        """
        violations = []
        warnings = []

        # 1. 检查账户余额
        if account_balance < self.config.min_account_balance:
            violations.append(f"账户余额不足: {account_balance:.2f} < {self.config.min_account_balance}")

        # 2. 检查单合约持仓限制
        position_map = {p.symbol: p for p in positions}
        current_vol = position_map.get(signal.symbol, None)
        current_volume = current_vol.volume if current_vol else 0

        if signal.direction == "BUY":
            new_volume = current_volume + signal.volume
            if new_volume > self.config.max_position_per_symbol:
                violations.append(
                    f"单合约持仓超限: {new_volume} > {self.config.max_position_per_symbol}"
                )

        # 3. 检查总持仓数量
        total_positions = len([p for p in positions if p.volume > 0])
        if signal.direction == "BUY" and signal.symbol not in position_map:
            if total_positions >= self.config.max_total_positions:
                violations.append(
                    f"总持仓数量超限: {total_positions} >= {self.config.max_total_positions}"
                )

        # 4. 检查保证金使用率
        order_value = (signal.price or 0) * signal.volume
        new_margin_usage = (used_margin + order_value * 0.1) / account_balance if account_balance > 0 else 1.0

        if new_margin_usage > self.config.max_margin_usage:
            violations.append(
                f"保证金使用率超限: {new_margin_usage:.2%} > {self.config.max_margin_usage:.2%}"
            )
        elif new_margin_usage > self.config.max_margin_usage * 0.9:
            warnings.append(
                f"保证金使用率警告: {new_margin_usage:.2%}"
            )

        # 5. 检查单笔订单金额
        if order_value > self.config.max_single_order_value:
            violations.append(
                f"单笔订单金额超限: {order_value:.2f} > {self.config.max_single_order_value}"
            )

        # 6. 检查每日交易次数
        if self._daily_trade_count >= self.config.max_daily_trades:
            violations.append(
                f"每日交易次数超限: {self._daily_trade_count} >= {self.config.max_daily_trades}"
            )

        # 记录检查结果
        if violations:
            self.logger.warning(
                f"风控检查未通过",
                symbol=signal.symbol,
                violations=violations,
            )
        elif warnings:
            self.logger.info(
                f"风控检查通过（有警告）",
                symbol=signal.symbol,
                warnings=warnings,
            )
        else:
            self.logger.info(f"风控检查通过", symbol=signal.symbol)

        return RiskCheckResult(
            passed=len(violations) == 0,
            signal=signal,
            violations=violations,
            warnings=warnings,
        )

    def check_batch(
        self,
        signals: List[StrategySignal],
        positions: List[Position],
        account_balance: float,
        used_margin: float,
    ) -> List[RiskCheckResult]:
        """批量检查"""
        return [
            self.check(s, positions, account_balance, used_margin)
            for s in signals
        ]

    def record_trade(self):
        """记录交易次数"""
        from datetime import date
        today = date.today()

        if self._trade_date != today:
            self._trade_date = today
            self._daily_trade_count = 0

        self._daily_trade_count += 1

    def reset_daily_count(self):
        """重置每日交易计数"""
        self._daily_trade_count = 0

    def get_remaining_trades(self) -> int:
        """获取剩余可交易次数"""
        return max(0, self.config.max_daily_trades - self._daily_trade_count)