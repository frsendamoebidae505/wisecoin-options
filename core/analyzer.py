# core/analyzer.py
"""
WiseCoin Options 分析器模块。

提供期权基础指标计算功能，不包含评分和交易决策逻辑。
"""
from typing import List, Dict
from core.models import OptionQuote, AnalyzedOption, Signal, CallOrPut


class OptionAnalyzer:
    """
    期权分析器。

    计算期权基础指标：杠杆、时间价值、价值度等。
    不包含评分和交易决策逻辑。

    Example:
        >>> analyzer = OptionAnalyzer()
        >>> analyzed = analyzer.analyze(quotes, futures_prices)
    """

    def analyze(
        self,
        quotes: List[OptionQuote],
        futures_quotes: Dict[str, float]
    ) -> List[AnalyzedOption]:
        """
        分析期权列表。

        Args:
            quotes: 期权行情列表。
            futures_quotes: 期货价格字典，键为标的期货代码，值为期货价格。

        Returns:
            分析后的期权列表。

        Raises:
            KeyError: 如果找不到对应的期货价格。
        """
        results = []

        for quote in quotes:
            # 获取标的期货价格
            underlying = quote.underlying
            if underlying is None or underlying not in futures_quotes:
                # 跳过没有期货价格的期权
                continue

            future_price = futures_quotes[underlying]

            # 计算各项指标
            is_itm = self._calculate_itm(quote, future_price)
            leverage = self._calculate_leverage(quote, future_price)
            time_value = self._calculate_time_value(quote, future_price)
            moneyness = self._calculate_moneyness(quote, future_price)

            # 构建原因列表
            reasons = self._build_reasons(quote, is_itm, leverage, time_value, moneyness)

            # 创建分析结果
            analyzed = AnalyzedOption(
                option=quote,
                is_itm=is_itm,
                leverage=leverage,
                time_value=time_value,
                moneyness=moneyness,
                iv=None,  # 由 IV 计算模块填充
                score=0.0,  # 由策略模块填充
                signal=Signal.HOLD,
                reasons=reasons
            )
            results.append(analyzed)

        return results

    def _calculate_itm(self, option: OptionQuote, future_price: float) -> bool:
        """
        计算期权是否实值。

        Args:
            option: 期权行情。
            future_price: 标的期货价格。

        Returns:
            是否实值。
        """
        if option.call_or_put == CallOrPut.CALL:
            # 看涨期权：标的价格 > 行权价 时为实值
            return future_price > option.strike_price
        else:
            # 看跌期权：标的价格 < 行权价 时为实值
            return future_price < option.strike_price

    def _calculate_leverage(
        self,
        option: OptionQuote,
        future_price: float
    ) -> float:
        """
        计算杠杆倍数。

        简化计算：杠杆 = 期货价格 / 期权价格 * delta
        如果没有 delta，则使用 期货价格 / 期权价格。

        Args:
            option: 期权行情。
            future_price: 标的期货价格。

        Returns:
            杠杆倍数。
        """
        if option.last_price <= 0:
            return 0.0

        base_leverage = future_price / option.last_price

        if option.delta is not None and option.delta != 0:
            return base_leverage * abs(option.delta)

        return base_leverage

    def _calculate_time_value(
        self,
        option: OptionQuote,
        future_price: float
    ) -> float:
        """
        计算时间价值。

        时间价值 = 期权价格 - 内在价值

        Args:
            option: 期权行情。
            future_price: 标的期货价格。

        Returns:
            时间价值。
        """
        intrinsic_value = self._calculate_intrinsic_value(option, future_price)
        return option.last_price - intrinsic_value

    def _calculate_intrinsic_value(
        self,
        option: OptionQuote,
        future_price: float
    ) -> float:
        """
        计算内在价值。

        Args:
            option: 期权行情。
            future_price: 标的期货价格。

        Returns:
            内在价值。
        """
        if option.call_or_put == CallOrPut.CALL:
            # 看涨期权内在价值 = max(标的价 - 行权价, 0)
            intrinsic = future_price - option.strike_price
        else:
            # 看跌期权内在价值 = max(行权价 - 标的价, 0)
            intrinsic = option.strike_price - future_price

        return max(intrinsic, 0.0)

    def _calculate_moneyness(
        self,
        option: OptionQuote,
        future_price: float
    ) -> float:
        """
        计算价值度（Moneyness）。

        价值度 = 期货价格 / 行权价

        Args:
            option: 期权行情。
            future_price: 标的期货价格。

        Returns:
            价值度。
        """
        if option.strike_price <= 0:
            return 0.0

        return future_price / option.strike_price

    def _build_reasons(
        self,
        option: OptionQuote,
        is_itm: bool,
        leverage: float,
        time_value: float,
        moneyness: float
    ) -> List[str]:
        """
        构建分析原因列表。

        Args:
            option: 期权行情。
            is_itm: 是否实值。
            leverage: 杠杆倍数。
            time_value: 时间价值。
            moneyness: 价值度。

        Returns:
            分析原因列表。
        """
        reasons = []

        # 实值/虚值状态
        if is_itm:
            reasons.append("实值期权")
        else:
            reasons.append("虚值期权")

        # 杠杆信息
        reasons.append(f"杠杆: {leverage:.2f}倍")

        # 时间价值信息
        reasons.append(f"时间价值: {time_value:.2f}")

        # 价值度信息
        reasons.append(f"价值度: {moneyness:.3f}")

        # 期权类型
        option_type = "看涨" if option.call_or_put == CallOrPut.CALL else "看跌"
        reasons.append(f"类型: {option_type}")

        return reasons