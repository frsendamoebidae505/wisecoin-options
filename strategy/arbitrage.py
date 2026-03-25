# strategy/arbitrage.py
"""
套利机会识别模块。

识别期权套利机会：转换套利、跨式套利、日历套利等。
"""
from typing import List, Dict, Optional
from dataclasses import dataclass

from core.models import OptionQuote, CallOrPut, ArbitrageOpportunity


class ArbitrageDetector:
    """
    套利机会检测器。

    检测常见的期权套利策略机会。

    Example:
        >>> detector = ArbitrageDetector()
        >>> opportunities = detector.detect(options, future_price)
    """

    def __init__(
        self,
        min_profit_threshold: float = 10.0,
        min_confidence: float = 0.7,
    ):
        """
        初始化检测器。

        Args:
            min_profit_threshold: 最小预期收益阈值（点数）
            min_confidence: 最小置信度阈值
        """
        self.min_profit_threshold = min_profit_threshold
        self.min_confidence = min_confidence

    def detect(
        self,
        options: List[OptionQuote],
        future_price: float,
    ) -> List[ArbitrageOpportunity]:
        """
        检测套利机会。

        Args:
            options: 期权列表（需包含同一标的的 CALL 和 PUT）
            future_price: 标的期货价格

        Returns:
            检测到的套利机会列表
        """
        opportunities = []

        # 检测转换套利
        opportunities.extend(self._detect_conversion(options, future_price))

        # 检测跨式套利
        opportunities.extend(self._detect_straddle(options, future_price))

        return opportunities

    def _detect_conversion(
        self,
        options: List[OptionQuote],
        future_price: float,
    ) -> List[ArbitrageOpportunity]:
        """
        检测转换套利机会。

        转换套利：买入看跌 + 卖出看涨（同行权价）
        当 Call - Put > Future - Strike 时存在套利空间

        反向转换套利：买入看涨 + 卖出看跌（同行权价）
        当 Put - Call > Strike - Future 时存在套利空间
        """
        opportunities = []

        # 按行权价分组，找到同行权价的 CALL 和 PUT
        options_by_strike: Dict[float, Dict[str, OptionQuote]] = {}

        for opt in options:
            strike = opt.strike_price
            if strike not in options_by_strike:
                options_by_strike[strike] = {}

            key = 'CALL' if opt.call_or_put == CallOrPut.CALL else 'PUT'
            # 优先使用已有期权，或者选择价格更优的
            if key not in options_by_strike[strike]:
                options_by_strike[strike][key] = opt

        # 检查每个行权价的套利机会
        for strike, opt_dict in options_by_strike.items():
            if 'CALL' not in opt_dict or 'PUT' not in opt_dict:
                continue

            call_opt = opt_dict['CALL']
            put_opt = opt_dict['PUT']

            # 使用买一价和卖一价进行计算
            call_mid = (call_opt.bid_price + call_opt.ask_price) / 2
            put_mid = (put_opt.bid_price + put_opt.ask_price) / 2

            # 转换套利条件: Call - Put > Future - Strike
            # 即：卖CALL收权利金 - 买PUT付权利金 > 标的价格 - 行权价
            call_put_spread = call_mid - put_mid
            future_strike_spread = future_price - strike

            conversion_profit = call_put_spread - future_strike_spread

            if conversion_profit > self.min_profit_threshold:
                legs = [
                    {
                        'action': 'SELL',
                        'type': 'CALL',
                        'strike': strike,
                        'price': call_mid,
                        'symbol': call_opt.symbol,
                    },
                    {
                        'action': 'BUY',
                        'type': 'PUT',
                        'strike': strike,
                        'price': put_mid,
                        'symbol': put_opt.symbol,
                    },
                    {
                        'action': 'BUY',
                        'type': 'FUTURE',
                        'price': future_price,
                    },
                ]
                opportunity = ArbitrageOpportunity(
                    opportunity_type='CONVERSION',
                    legs=legs,
                    expected_profit=conversion_profit,
                    risk_level=self._calculate_risk_level('CONVERSION', legs),
                    confidence=0.85,  # 转换套利置信度较高
                )
                opportunities.append(opportunity)

            # 反向转换套利条件: Put - Call > Strike - Future
            reverse_conversion_profit = put_mid - call_mid - (strike - future_price)

            if reverse_conversion_profit > self.min_profit_threshold:
                legs = [
                    {
                        'action': 'BUY',
                        'type': 'CALL',
                        'strike': strike,
                        'price': call_mid,
                        'symbol': call_opt.symbol,
                    },
                    {
                        'action': 'SELL',
                        'type': 'PUT',
                        'strike': strike,
                        'price': put_mid,
                        'symbol': put_opt.symbol,
                    },
                    {
                        'action': 'SELL',
                        'type': 'FUTURE',
                        'price': future_price,
                    },
                ]
                opportunity = ArbitrageOpportunity(
                    opportunity_type='REVERSE_CONVERSION',
                    legs=legs,
                    expected_profit=reverse_conversion_profit,
                    risk_level=self._calculate_risk_level('REVERSE_CONVERSION', legs),
                    confidence=0.85,
                )
                opportunities.append(opportunity)

        return opportunities

    def _detect_straddle(
        self,
        options: List[OptionQuote],
        future_price: float,
    ) -> List[ArbitrageOpportunity]:
        """
        检测跨式套利机会。

        当 IV 极高或极低时，可能存在跨式套利机会：
        - IV 极高：卖出跨式（卖CALL + 卖PUT）
        - IV 极低：买入跨式（买CALL + 买PUT）
        """
        opportunities = []

        # 找到接近平值的期权
        atm_threshold = 0.02  # 2% 以内视为平值

        atm_calls = []
        atm_puts = []

        for opt in options:
            moneyness = abs(opt.strike_price - future_price) / future_price
            if moneyness <= atm_threshold:
                if opt.call_or_put == CallOrPut.CALL:
                    atm_calls.append(opt)
                else:
                    atm_puts.append(opt)

        if not atm_calls or not atm_puts:
            return opportunities

        # 选择最接近平值的期权
        atm_call = min(atm_calls, key=lambda x: abs(x.strike_price - future_price))
        atm_put = min(atm_puts, key=lambda x: abs(x.strike_price - future_price))

        call_mid = (atm_call.bid_price + atm_call.ask_price) / 2
        put_mid = (atm_put.bid_price + atm_put.ask_price) / 2

        total_premium = call_mid + put_mid

        # 检查 IV 水平判断套利机会
        call_iv = atm_call.iv
        put_iv = atm_put.iv

        if call_iv is not None and put_iv is not None:
            avg_iv = (call_iv + put_iv) / 2

            # IV 极高阈值（例如 > 30%）
            high_iv_threshold = 0.30
            # IV 极低阈值（例如 < 10%）
            low_iv_threshold = 0.10

            # 高 IV 时卖出跨式
            if avg_iv > high_iv_threshold:
                expected_profit = total_premium * 0.5  # 预期收益为权利金的 50%

                if expected_profit > self.min_profit_threshold:
                    legs = [
                        {
                            'action': 'SELL',
                            'type': 'CALL',
                            'strike': atm_call.strike_price,
                            'price': call_mid,
                            'symbol': atm_call.symbol,
                            'iv': call_iv,
                        },
                        {
                            'action': 'SELL',
                            'type': 'PUT',
                            'strike': atm_put.strike_price,
                            'price': put_mid,
                            'symbol': atm_put.symbol,
                            'iv': put_iv,
                        },
                    ]
                    # IV 越高，置信度越高
                    confidence = min(0.5 + (avg_iv - high_iv_threshold) * 2, 0.95)

                    opportunity = ArbitrageOpportunity(
                        opportunity_type='SHORT_STRADDLE',
                        legs=legs,
                        expected_profit=expected_profit,
                        risk_level=self._calculate_risk_level('SHORT_STRADDLE', legs),
                        confidence=confidence,
                    )
                    opportunities.append(opportunity)

            # 低 IV 时买入跨式
            elif avg_iv < low_iv_threshold:
                expected_profit = total_premium * 0.3  # 预期潜在收益

                if expected_profit > self.min_profit_threshold:
                    legs = [
                        {
                            'action': 'BUY',
                            'type': 'CALL',
                            'strike': atm_call.strike_price,
                            'price': call_mid,
                            'symbol': atm_call.symbol,
                            'iv': call_iv,
                        },
                        {
                            'action': 'BUY',
                            'type': 'PUT',
                            'strike': atm_put.strike_price,
                            'price': put_mid,
                            'symbol': atm_put.symbol,
                            'iv': put_iv,
                        },
                    ]
                    # IV 越低，置信度越高
                    confidence = min(0.5 + (low_iv_threshold - avg_iv) * 5, 0.90)

                    opportunity = ArbitrageOpportunity(
                        opportunity_type='LONG_STRADDLE',
                        legs=legs,
                        expected_profit=expected_profit,
                        risk_level=self._calculate_risk_level('LONG_STRADDLE', legs),
                        confidence=confidence,
                    )
                    opportunities.append(opportunity)

        return opportunities

    def _calculate_risk_level(self, opportunity_type: str, legs: List[dict]) -> str:
        """
        计算风险等级。

        Args:
            opportunity_type: 套利类型
            legs: 套利腿列表

        Returns:
            风险等级: LOW, MEDIUM, HIGH
        """
        risk_mapping = {
            'CONVERSION': 'LOW',
            'REVERSE_CONVERSION': 'LOW',
            'SHORT_STRADDLE': 'HIGH',  # 卖出跨式风险较高
            'LONG_STRADDLE': 'MEDIUM',  # 买入跨式风险中等
        }

        return risk_mapping.get(opportunity_type, 'MEDIUM')