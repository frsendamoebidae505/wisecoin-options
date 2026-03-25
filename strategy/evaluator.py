# strategy/evaluator.py
"""
策略评估器模块。

基于多因子模型对期权进行评分和排序。
"""
from typing import List, Dict, Optional
from dataclasses import dataclass

from core.models import AnalyzedOption, Signal


@dataclass
class ScoringFactors:
    """评分因子权重配置"""
    iv_weight: float = 0.25        # IV 因子权重
    leverage_weight: float = 0.20   # 杠杆因子权重
    liquidity_weight: float = 0.15  # 流动性因子权重
    time_value_weight: float = 0.15 # 时间价值因子权重
    moneyness_weight: float = 0.25  # 价值度因子权重


class StrategyEvaluator:
    """
    策略评估器。

    基于多因子模型对期权进行综合评分。

    Example:
        >>> evaluator = StrategyEvaluator()
        >>> ranked = evaluator.evaluate(analyzed_options)
    """

    def __init__(self, factors: Optional[ScoringFactors] = None):
        self.factors = factors or ScoringFactors()

    def evaluate(
        self,
        analyzed_options: List[AnalyzedOption],
        iv_reference: Optional[float] = None,
    ) -> List[AnalyzedOption]:
        """
        评估期权并返回排序后的结果。

        Args:
            analyzed_options: 分析后的期权列表
            iv_reference: IV 参考值（用于 IV 因子计算）

        Returns:
            按评分降序排列的 AnalyzedOption 列表
        """
        if not analyzed_options:
            return []

        # 1. 计算每个因子的归一化分数并加权求和
        for analyzed in analyzed_options:
            iv_score = self._calculate_iv_score(analyzed.iv, iv_reference)
            leverage_score = self._calculate_leverage_score(analyzed.leverage)
            liquidity_score = self._calculate_liquidity_score(
                analyzed.option.volume,
                analyzed.option.open_interest
            )
            time_value_score = self._calculate_time_value_score(
                analyzed.time_value,
                analyzed.option.last_price
            )
            moneyness_score = self._calculate_moneyness_score(
                analyzed.moneyness,
                analyzed.option.call_or_put.value == "CALL"
            )

            # 加权求和
            total_score = (
                iv_score * self.factors.iv_weight +
                leverage_score * self.factors.leverage_weight +
                liquidity_score * self.factors.liquidity_weight +
                time_value_score * self.factors.time_value_weight +
                moneyness_score * self.factors.moneyness_weight
            )

            analyzed.score = round(total_score, 2)
            analyzed.signal = self._determine_signal(total_score)

        # 2. 按评分降序排列
        return sorted(analyzed_options, key=lambda x: x.score, reverse=True)

    def _calculate_iv_score(self, iv: Optional[float], reference: Optional[float]) -> float:
        """
        计算 IV 因子分数（IV 偏低时分数高）。

        IV 低于参考值时分数较高，因为买入期权时低IV更有利。
        如果没有IV或参考值，返回中性分数50。
        """
        if iv is None or reference is None or reference <= 0:
            return 50.0

        # 计算 IV 相对于参考值的偏离程度
        # IV 低于参考值时，分数越高
        iv_ratio = iv / reference

        if iv_ratio <= 0.7:  # IV 显著偏低
            return 100.0
        elif iv_ratio <= 0.85:  # IV 偏低
            return 80.0
        elif iv_ratio <= 1.0:  # IV 略低
            return 60.0
        elif iv_ratio <= 1.15:  # IV 略高
            return 40.0
        elif iv_ratio <= 1.3:  # IV 偏高
            return 20.0
        else:  # IV 显著偏高
            return 0.0

    def _calculate_leverage_score(self, leverage: float) -> float:
        """
        计算杠杆因子分数（杠杆适中时分数高）。

        杠杆在合理范围（如 10-50x）分数较高。
        过高或过低的杠杆都不理想。
        """
        if leverage <= 0:
            return 0.0

        if leverage < 5:  # 杠杆过低
            return leverage * 4.0  # 0-20分
        elif leverage < 10:  # 杠杆较低
            return 20.0 + (leverage - 5) * 8.0  # 20-60分
        elif leverage <= 50:  # 杠杆适中（最佳区间）
            return 60.0 + (leverage - 10) * 1.0  # 60-100分
        elif leverage <= 100:  # 杠杆较高
            return 100.0 - (leverage - 50) * 1.2  # 100-40分
        else:  # 杠杆过高
            return max(0.0, 40.0 - (leverage - 100) * 0.4)

    def _calculate_liquidity_score(self, volume: int, open_interest: int) -> float:
        """
        计算流动性因子分数。

        成交量和持仓量高则流动性好。
        """
        # 基于成交量的分数（权重60%）
        if volume >= 500:
            volume_score = 100.0
        elif volume >= 200:
            volume_score = 70.0 + (volume - 200) * 0.1
        elif volume >= 100:
            volume_score = 40.0 + (volume - 100) * 0.3
        elif volume >= 50:
            volume_score = 20.0 + (volume - 50) * 0.4
        else:
            volume_score = volume * 0.4

        # 基于持仓量的分数（权重40%）
        if open_interest >= 1000:
            oi_score = 100.0
        elif open_interest >= 500:
            oi_score = 70.0 + (open_interest - 500) * 0.06
        elif open_interest >= 200:
            oi_score = 40.0 + (open_interest - 200) * 0.1
        elif open_interest >= 100:
            oi_score = 20.0 + (open_interest - 100) * 0.2
        else:
            oi_score = open_interest * 0.2

        # 综合分数
        return volume_score * 0.6 + oi_score * 0.4

    def _calculate_time_value_score(self, time_value: float, option_price: float) -> float:
        """
        计算时间价值因子分数。

        时间价值占比较低时分数较高。
        """
        if option_price <= 0:
            return 50.0

        time_value_ratio = time_value / option_price

        if time_value_ratio <= 0.2:  # 时间价值占比较低
            return 100.0 - time_value_ratio * 100
        elif time_value_ratio <= 0.4:  # 时间价值占比适中
            return 80.0 - (time_value_ratio - 0.2) * 100
        elif time_value_ratio <= 0.6:  # 时间价值占比较高
            return 60.0 - (time_value_ratio - 0.4) * 100
        elif time_value_ratio <= 0.8:  # 时间价值占比很高
            return 40.0 - (time_value_ratio - 0.6) * 100
        else:  # 时间价值占比极高
            return max(0.0, 20.0 - (time_value_ratio - 0.8) * 100)

    def _calculate_moneyness_score(self, moneyness: float, is_call: bool) -> float:
        """
        计算价值度因子分数。

        接近平值（moneyness ~1.0）时分数较高。
        对于 Call: moneyness = 标的价格 / 行权价，>1 表示 ITM
        对于 Put: moneyness = 行权价 / 标的价格，>1 表示 ITM
        """
        if moneyness <= 0:
            return 0.0

        # 计算与平值的偏离程度
        deviation = abs(moneyness - 1.0)

        if deviation <= 0.02:  # 非常接近平值
            return 100.0
        elif deviation <= 0.05:  # 接近平值
            return 90.0 - deviation * 200
        elif deviation <= 0.10:  # 稍偏离平值
            return 80.0 - deviation * 300
        elif deviation <= 0.20:  # 明显偏离平值
            return 50.0 - deviation * 200
        else:  # 远离平值
            return max(10.0, 30.0 - deviation * 50)

    def _determine_signal(self, score: float) -> Signal:
        """
        根据评分确定交易信号。

        score > 70 -> BUY
        score < 30 -> SELL
        else -> HOLD
        """
        if score > 70:
            return Signal.BUY
        elif score < 30:
            return Signal.SELL
        else:
            return Signal.HOLD