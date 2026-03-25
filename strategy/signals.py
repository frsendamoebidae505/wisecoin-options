# strategy/signals.py
"""
交易信号生成模块。

基于分析结果生成具体的交易信号。
"""
from typing import List, Optional
from datetime import date

from core.models import (
    AnalyzedOption,
    Signal,
    StrategySignal,
    OptionQuote,
    CallOrPut,
)


class SignalGenerator:
    """
    交易信号生成器。

    根据评分和持仓情况生成具体的交易信号。

    Example:
        >>> generator = SignalGenerator()
        >>> signals = generator.generate(analyzed_options, current_positions)
    """

    def __init__(
        self,
        max_position_per_symbol: int = 10,
        min_score_to_buy: float = 70.0,
        max_score_to_sell: float = 30.0,
    ):
        """
        初始化生成器。

        Args:
            max_position_per_symbol: 单合约最大持仓
            min_score_to_buy: 买入最低评分
            max_score_to_sell: 卖出最高评分
        """
        self.max_position_per_symbol = max_position_per_symbol
        self.min_score_to_buy = min_score_to_buy
        self.max_score_to_sell = max_score_to_sell

    def generate(
        self,
        analyzed_options: List[AnalyzedOption],
        current_positions: Optional[List[dict]] = None,
    ) -> List[StrategySignal]:
        """
        生成交易信号。

        Args:
            analyzed_options: 已评分的期权列表
            current_positions: 当前持仓列表（可选）

        Returns:
            交易信号列表
        """
        signals = []
        position_symbols = {p['symbol']: p for p in (current_positions or [])}

        for analyzed in analyzed_options:
            # 跳过评分过低的
            if analyzed.score < self.min_score_to_buy:
                continue

            # 检查是否已持仓
            current_vol = position_symbols.get(analyzed.option.symbol, {}).get('volume', 0)

            # 计算建议数量
            volume = self._calculate_volume(analyzed, current_vol)

            if volume > 0:
                signal = StrategySignal(
                    symbol=analyzed.option.symbol,
                    direction="BUY",
                    volume=volume,
                    price=analyzed.option.ask_price,  # 买入用卖一价
                    score=analyzed.score,
                    strategy_type="评分买入",
                    reasons=analyzed.reasons.copy(),
                )
                signals.append(signal)

        return signals

    def generate_exit_signals(
        self,
        analyzed_options: List[AnalyzedOption],
        current_positions: List[dict],
    ) -> List[StrategySignal]:
        """
        生成平仓信号。

        对于评分过低或触及止损的持仓生成卖出信号。
        """
        signals = []
        position_map = {p['symbol']: p for p in current_positions}

        for analyzed in analyzed_options:
            if analyzed.option.symbol not in position_map:
                continue

            # 评分过低则建议卖出
            if analyzed.score < self.max_score_to_sell:
                pos = position_map[analyzed.option.symbol]
                signal = StrategySignal(
                    symbol=analyzed.option.symbol,
                    direction="SELL",
                    volume=pos['volume'],
                    price=analyzed.option.bid_price,  # 卖出用买一价
                    score=analyzed.score,
                    strategy_type="评分卖出",
                    reasons=[f"评分过低: {analyzed.score:.1f}"],
                )
                signals.append(signal)

        return signals

    def _calculate_volume(
        self,
        analyzed: AnalyzedOption,
        current_volume: int,
    ) -> int:
        """计算建议开仓数量"""
        remaining = self.max_position_per_symbol - current_volume
        if remaining <= 0:
            return 0

        # 根据评分决定数量
        if analyzed.score >= 90:
            return min(remaining, 5)
        elif analyzed.score >= 80:
            return min(remaining, 3)
        elif analyzed.score >= 70:
            return min(remaining, 2)
        return 1