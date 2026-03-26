# core/analyzer.py
"""
WiseCoin Options 分析器模块。

提供期权多因子分析、评分筛选等核心计算功能。

包含：
- 期权基础指标计算（杠杆、时间价值、价值度等）
- 虚实幅度和档位分类
- 保证金和收益率计算
- P/C Ratio 分析
- 最大痛点计算
- 交易类型分类（方向型 vs 波动率型）
- 多因子评分系统
"""
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from core.models import OptionQuote, AnalyzedOption, Signal, CallOrPut


class IntrinsicLevel(str, Enum):
    """虚实档位枚举。"""
    DEEP_ITM = "深度实值"
    MODERATE_ITM = "中度实值"
    ATM_NEAR = "平值附近"
    MODERATE_OTM = "中度虚值"
    DEEP_OTM = "深度虚值"


class TradingType(str, Enum):
    """交易类型枚举。"""
    DIRECTIONAL = "方向型"
    VOLATILITY = "波动率型"
    MIXED = "混合型"
    UNKNOWN = "未知"


@dataclass
class OptionMetrics:
    """
    期权综合指标。

    包含期权的各项计算指标。
    """
    symbol: str
    underlying: str
    call_or_put: CallOrPut
    strike_price: float
    option_price: float
    underlying_price: float

    # 虚实度指标
    intrinsic_degree: float = 0.0  # 虚实幅度(%)
    intrinsic_level: IntrinsicLevel = IntrinsicLevel.ATM_NEAR
    is_itm: bool = False

    # 价值指标
    intrinsic_value: float = 0.0  # 内在价值
    time_value: float = 0.0  # 时间价值
    time_value_ratio: float = 0.0  # 时间价值占比(%)
    premium_rate: float = 0.0  # 溢价率(%)

    # 杠杆收益指标
    leverage: float = 0.0
    profit_rate: float = 0.0  # 收益率(%)
    annual_profit_rate: float = 0.0  # 年化收益率(%)

    # 保证金指标
    margin: float = 0.0  # 卖方保证金
    underlying_margin: float = 0.0  # 标的期货保证金
    leverage_profit: float = 0.0  # 杠杆收益(%)
    annual_leverage_profit: float = 0.0  # 杠杆年化(%)

    # 其他指标
    moneyness: float = 0.0  # 价值度
    expire_days: int = 0  # 剩余天数
    multiplier: float = 1.0  # 合约乘数


@dataclass
class UnderlyingAnalysis:
    """
    标的分析结果。

    包含单个标的的多维度分析数据。
    """
    underlying: str
    underlying_price: float

    # 合约统计
    num_contracts: int = 0
    num_calls: int = 0
    num_puts: int = 0

    # 持仓成交
    total_oi: int = 0
    total_volume: int = 0
    call_oi: int = 0
    put_oi: int = 0
    call_volume: int = 0
    put_volume: int = 0

    # 持仓变化
    oi_change: int = 0
    call_oi_change: int = 0
    put_oi_change: int = 0

    # 资金
    settled_capital: float = 0.0  # 沉淀资金(亿)
    traded_capital: float = 0.0  # 成交资金(亿)
    call_settled_capital: float = 0.0
    put_settled_capital: float = 0.0

    # P/C Ratio
    pcr_oi: float = 0.0  # PCR(持仓)
    pcr_volume: float = 0.0  # PCR(成交)
    pcr_capital: float = 0.0  # PCR(资金)

    # 最大痛点
    max_pain: float = 0.0
    max_pain_distance: float = 0.0  # 痛点距离(%)

    # 流动性
    avg_turnover: float = 0.0  # 平均换手率(%)
    avg_spread_pct: float = 0.0  # 平均价差(%)
    avg_expire_days: float = 0.0  # 平均剩余天数

    # 评分
    liquidity_score: float = 0.0
    activity_score: float = 0.0
    sentiment: int = 0  # 情绪倾向 (-100 ~ 100)
    composite_score: float = 0.0

    # 交易类型
    trading_type: TradingType = TradingType.UNKNOWN
    trading_subtype: str = ""
    type_confidence: float = 0.0


class OptionAnalyzer:
    """
    期权分析器。

    计算期权基础指标：杠杆、时间价值、价值度等。

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
                iv=quote.iv,
                score=0.0,
                signal=Signal.HOLD,
                reasons=reasons
            )
            results.append(analyzed)

        return results

    def analyze_single(
        self,
        quote: OptionQuote,
        future_price: float,
        multiplier: float = 1.0,
        margin_ratio: float = 15.0,
        expire_days: int = 30
    ) -> OptionMetrics:
        """
        分析单个期权，返回完整指标。

        Args:
            quote: 期权行情。
            future_price: 标的期货价格。
            multiplier: 合约乘数。
            margin_ratio: 保证金率(%)。
            expire_days: 剩余天数。

        Returns:
            期权综合指标。
        """
        metrics = OptionMetrics(
            symbol=quote.symbol,
            underlying=quote.underlying,
            call_or_put=quote.call_or_put,
            strike_price=quote.strike_price,
            option_price=quote.last_price,
            underlying_price=future_price,
            multiplier=multiplier,
            expire_days=expire_days
        )

        # 计算虚实度
        self._calc_intrinsic_degree(metrics, future_price)

        # 计算价值分解
        self._calc_value_decomposition(metrics, future_price)

        # 计算保证金
        self._calc_margin(metrics, future_price, multiplier, margin_ratio)

        # 计算杠杆收益
        self._calc_leverage_profit(metrics, future_price, expire_days)

        # 计算价值度
        metrics.moneyness = self._calculate_moneyness(quote, future_price)

        return metrics

    def _calculate_itm(self, option: OptionQuote, future_price: float) -> bool:
        """计算期权是否实值。"""
        if option.call_or_put == CallOrPut.CALL:
            return future_price > option.strike_price
        else:
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
        """计算时间价值。时间价值 = 期权价格 - 内在价值"""
        intrinsic_value = self._calculate_intrinsic_value(option, future_price)
        return option.last_price - intrinsic_value

    def _calculate_intrinsic_value(
        self,
        option: OptionQuote,
        future_price: float
    ) -> float:
        """计算内在价值。"""
        if option.call_or_put == CallOrPut.CALL:
            intrinsic = future_price - option.strike_price
        else:
            intrinsic = option.strike_price - future_price
        return max(intrinsic, 0.0)

    def _calculate_moneyness(
        self,
        option: OptionQuote,
        future_price: float
    ) -> float:
        """计算价值度（Moneyness）。价值度 = 期货价格 / 行权价"""
        if option.strike_price <= 0:
            return 0.0
        return future_price / option.strike_price

    def _calc_intrinsic_degree(self, metrics: OptionMetrics, future_price: float) -> None:
        """
        计算虚实幅度和档位。

        虚实幅度 = (标的价格 - 行权价) / 标的价格 * 100 (CALL)
                 = (行权价 - 标的价格) / 标的价格 * 100 (PUT)
        """
        if future_price <= 0:
            return

        strike = metrics.strike_price

        if metrics.call_or_put == CallOrPut.CALL:
            metrics.intrinsic_degree = (future_price - strike) / future_price * 100
        else:
            metrics.intrinsic_degree = (strike - future_price) / future_price * 100

        # 判断虚实
        metrics.is_itm = metrics.intrinsic_degree > 0

        # 虚实档位分类
        degree = metrics.intrinsic_degree
        if degree > 20:
            metrics.intrinsic_level = IntrinsicLevel.DEEP_ITM
        elif degree > 10:
            metrics.intrinsic_level = IntrinsicLevel.MODERATE_ITM
        elif degree >= -10:
            metrics.intrinsic_level = IntrinsicLevel.ATM_NEAR
        elif degree >= -20:
            metrics.intrinsic_level = IntrinsicLevel.MODERATE_OTM
        else:
            metrics.intrinsic_level = IntrinsicLevel.DEEP_OTM

    def _calc_value_decomposition(self, metrics: OptionMetrics, future_price: float) -> None:
        """计算价值分解（内在价值、时间价值、溢价率）。"""
        strike = metrics.strike_price

        # 内在价值
        if metrics.call_or_put == CallOrPut.CALL:
            metrics.intrinsic_value = max(0, future_price - strike)
            # 溢价率 = (行权价 + 期权价 - 标的价) / 标的价 * 100
            metrics.premium_rate = (strike + metrics.option_price - future_price) / future_price * 100
        else:
            metrics.intrinsic_value = max(0, strike - future_price)
            # 溢价率 = (标的价 + 期权价 - 行权价) / 标的价 * 100
            metrics.premium_rate = (future_price + metrics.option_price - strike) / future_price * 100

        # 时间价值
        metrics.time_value = max(0, metrics.option_price - metrics.intrinsic_value)

        # 时间价值占比
        if metrics.option_price > 0:
            metrics.time_value_ratio = metrics.time_value / metrics.option_price * 100

    def _calc_margin(
        self,
        metrics: OptionMetrics,
        future_price: float,
        multiplier: float,
        margin_ratio: float
    ) -> None:
        """
        计算保证金。

        公式：
        标的期货保证金 = 标的现价 * 期货合约乘数 * 期货保证金率%
        保证金 = 期权价*合约乘数 + max(标的期货保证金 - 虚值额/2, 标的期货保证金/2)
        """
        # 标的期货保证金
        metrics.underlying_margin = future_price * multiplier * (margin_ratio / 100)

        # 虚值额
        if metrics.call_or_put == CallOrPut.CALL:
            otm_value = max((metrics.strike_price - future_price) * multiplier, 0)
        else:
            otm_value = max((future_price - metrics.strike_price) * multiplier, 0)

        # 卖方保证金
        metrics.margin = (
            metrics.option_price * multiplier +
            max(metrics.underlying_margin - otm_value / 2, metrics.underlying_margin / 2)
        )

    def _calc_leverage_profit(
        self,
        metrics: OptionMetrics,
        future_price: float,
        expire_days: int
    ) -> None:
        """计算杠杆收益指标。"""
        # 收益率
        if future_price > 0:
            metrics.profit_rate = metrics.option_price / future_price * 100

        # 年化收益率
        if expire_days > 0:
            metrics.annual_profit_rate = metrics.profit_rate / expire_days * 365

        # 杠杆收益
        if metrics.margin > 0:
            metrics.leverage_profit = metrics.option_price * metrics.multiplier / metrics.margin * 100

        # 杠杆年化
        if expire_days > 0:
            metrics.annual_leverage_profit = metrics.leverage_profit / expire_days * 365

        # 杠杆倍数
        if metrics.option_price > 0:
            metrics.leverage = future_price / metrics.option_price

    def _build_reasons(
        self,
        option: OptionQuote,
        is_itm: bool,
        leverage: float,
        time_value: float,
        moneyness: float
    ) -> List[str]:
        """构建分析原因列表。"""
        reasons = []

        if is_itm:
            reasons.append("实值期权")
        else:
            reasons.append("虚值期权")

        reasons.append(f"杠杆: {leverage:.2f}倍")
        reasons.append(f"时间价值: {time_value:.2f}")
        reasons.append(f"价值度: {moneyness:.3f}")

        option_type = "看涨" if option.call_or_put == CallOrPut.CALL else "看跌"
        reasons.append(f"类型: {option_type}")

        return reasons


class OptionScorer:
    """
    期权评分器。

    提供期权多因子评分、筛选功能。

    Example:
        >>> scorer = OptionScorer()
        >>> scored = scorer.score(analyzed_options)
    """

    def score(
        self,
        analyzed_options: List[AnalyzedOption]
    ) -> List[AnalyzedOption]:
        """
        对分析后的期权进行评分。

        Args:
            analyzed_options: 分析后的期权列表。

        Returns:
            评分后的期权列表。
        """
        for analyzed in analyzed_options:
            score = self._calculate_score(analyzed)
            analyzed.score = score

            # 根据评分生成信号
            analyzed.signal = self._generate_signal(score)

        return analyzed_options

    def _calculate_score(self, analyzed: AnalyzedOption) -> float:
        """
        计算综合评分。

        评分因子：
        - 杠杆倍数 (0-30分)
        - 时间价值占比 (0-20分)
        - 流动性 (0-30分)
        - 实值程度 (0-20分)
        """
        score = 0.0

        # 杠杆评分 (杠杆适中为佳，太高太低都不好)
        leverage = analyzed.leverage
        if 5 <= leverage <= 20:
            score += 30
        elif 3 <= leverage < 5 or 20 < leverage <= 30:
            score += 20
        elif leverage > 30:
            score += 10

        # 时间价值评分 (时间价值适中为佳)
        if analyzed.option.last_price > 0:
            time_value_ratio = analyzed.time_value / analyzed.option.last_price
            if 0.3 <= time_value_ratio <= 0.6:
                score += 20
            elif 0.2 <= time_value_ratio < 0.3 or 0.6 < time_value_ratio <= 0.8:
                score += 15
            else:
                score += 10

        # 流动性评分
        volume = analyzed.option.volume
        oi = analyzed.option.open_interest
        if volume > 1000 and oi > 1000:
            score += 30
        elif volume > 500 and oi > 500:
            score += 20
        elif volume > 100 and oi > 100:
            score += 10

        # 实值程度评分
        if analyzed.is_itm:
            score += 20
        else:
            # 轻微虚值也有价值
            if analyzed.moneyness > 0.9:
                score += 15
            elif analyzed.moneyness > 0.8:
                score += 10

        return min(score, 100.0)

    def _generate_signal(self, score: float) -> Signal:
        """根据评分生成交易信号。"""
        if score >= 70:
            return Signal.BUY
        elif score <= 30:
            return Signal.SELL
        else:
            return Signal.HOLD

    def filter_by_score(
        self,
        analyzed_options: List[AnalyzedOption],
        min_score: float = 50.0
    ) -> List[AnalyzedOption]:
        """
        根据评分筛选期权。

        Args:
            analyzed_options: 分析后的期权列表。
            min_score: 最低评分阈值。

        Returns:
            筛选后的期权列表。
        """
        return [opt for opt in analyzed_options if opt.score >= min_score]


class OptionTradingClassifier:
    """
    期权交易类型分类器。

    区分「方向型交易」vs「波动率交易」。

    【方向型期权判断标准】:
    - CALL 与 PUT 明显单边增仓（一方增仓幅度超过另一方的2倍以上）
    - PCR 极端（<0.5 极度看多 或 >1.5 极度看空）

    【波动率型期权判断标准】:
    - CALL & PUT 同时增仓（双向增仓，比例接近 0.5-2.0 之间）
    - 成交放大但 PCR 接近 1（0.8-1.2范围）
    """

    # 单边判断阈值
    SINGLE_SIDE_THRESHOLD = 0.65

    def classify(
        self,
        call_oi_change: int,
        put_oi_change: int,
        pcr: float,
        volume_ratio: float = 1.0
    ) -> Tuple[TradingType, str, float]:
        """
        分类期权交易类型。

        Args:
            call_oi_change: CALL持仓变化量。
            put_oi_change: PUT持仓变化量。
            pcr: P/C Ratio (持仓)。
            volume_ratio: 成交量比率 (当前成交量/平均成交量)。

        Returns:
            (交易类型, 类型细分, 置信度)
        """
        # 归一化变化量
        total_oi_change = abs(call_oi_change) + abs(put_oi_change)
        if total_oi_change == 0:
            return (TradingType.UNKNOWN, '无明显变化', 0)

        call_ratio = call_oi_change / total_oi_change if total_oi_change > 0 else 0.5
        put_ratio = put_oi_change / total_oi_change if total_oi_change > 0 else 0.5

        # 双向增仓判断
        both_increasing = call_oi_change > 0 and put_oi_change > 0
        both_decreasing = call_oi_change < 0 and put_oi_change < 0

        # PCR极端值判断
        pcr_extreme_bullish = pcr < 0.5
        pcr_extreme_bearish = pcr > 1.5
        pcr_neutral = 0.8 <= pcr <= 1.2

        # 分类逻辑
        if both_increasing and pcr_neutral and volume_ratio >= 1.2:
            # 双向增仓 + PCR中性 + 成交放大 -> 波动率交易
            confidence = min(100, 60 + (1 - abs(1 - pcr)) * 40)
            if abs(call_oi_change - put_oi_change) / max(call_oi_change, put_oi_change, 1) < 0.3:
                return (TradingType.VOLATILITY, '跨式/宽跨式建仓', confidence)
            else:
                return (TradingType.VOLATILITY, '不对称波动率', confidence * 0.8)

        elif pcr_extreme_bullish and call_oi_change > put_oi_change:
            confidence = min(100, 70 + (0.5 - pcr) * 60)
            return (TradingType.DIRECTIONAL, '强烈看多', confidence)

        elif pcr_extreme_bearish and put_oi_change > call_oi_change:
            confidence = min(100, 70 + (pcr - 1.5) * 40)
            return (TradingType.DIRECTIONAL, '强烈看空', confidence)

        elif abs(call_ratio) > self.SINGLE_SIDE_THRESHOLD and call_oi_change > 0:
            confidence = 50 + call_ratio * 50
            return (TradingType.DIRECTIONAL, '看多增仓', confidence)

        elif abs(put_ratio) > self.SINGLE_SIDE_THRESHOLD and put_oi_change > 0:
            confidence = 50 + put_ratio * 50
            return (TradingType.DIRECTIONAL, '看空增仓', confidence)

        elif both_decreasing:
            if pcr_neutral:
                return (TradingType.VOLATILITY, '跨式/宽跨式平仓', 60)
            else:
                return (TradingType.DIRECTIONAL, '获利了结', 50)

        elif both_increasing:
            if pcr < 0.8:
                return (TradingType.MIXED, '偏多波动率', 50)
            elif pcr > 1.2:
                return (TradingType.MIXED, '偏空波动率', 50)
            else:
                return (TradingType.VOLATILITY, '建仓中', 55)

        else:
            return (TradingType.UNKNOWN, '信号不明确', 30)


class MaxPainCalculator:
    """
    最大痛点计算器。

    最大痛点是期权到期时，使所有期权买方损失最大（即卖方收益最大）的标的价格。
    """

    def calculate(
        self,
        options: List[Dict],
        strikes: Optional[List[float]] = None
    ) -> float:
        """
        计算最大痛点。

        Args:
            options: 期权列表，每个期权包含:
                - strike: 行权价
                - open_interest: 持仓量
                - multiplier: 合约乘数
                - call_or_put: 期权类型 ('CALL' 或 'PUT')
            strikes: 可选的测试行权价列表，如果不提供则从期权中提取。

        Returns:
            最大痛点价格。
        """
        if not options:
            return 0.0

        # 提取行权价
        if strikes is None:
            strikes = list(set(opt.get('strike', 0) for opt in options))
            strikes = [s for s in strikes if s > 0]

        if not strikes:
            return 0.0

        min_pain = float('inf')
        max_pain_strike = 0.0

        for test_price in strikes:
            total_pain = 0.0

            for opt in options:
                strike = opt.get('strike', 0)
                oi = opt.get('open_interest', 0)
                multiplier = opt.get('multiplier', 1)
                opt_type = opt.get('call_or_put', 'CALL')

                if opt_type == 'CALL':
                    itm = max(0, test_price - strike)
                else:
                    itm = max(0, strike - test_price)

                total_pain += oi * itm * multiplier

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_price

        return max_pain_strike


class PCRAnalyzer:
    """
    P/C Ratio 分析器。

    分析期权市场的多空情绪。
    """

    def calculate_pcr(
        self,
        put_metric: float,
        call_metric: float
    ) -> float:
        """
        计算P/C Ratio。

        Args:
            put_metric: PUT指标值（持仓、成交或资金）。
            call_metric: CALL指标值。

        Returns:
            P/C Ratio。
        """
        if call_metric <= 0:
            return 0.0
        return put_metric / call_metric

    def interpret_pcr(self, pcr: float) -> str:
        """
        解读PCR含义。

        Args:
            pcr: P/C Ratio。

        Returns:
            情绪解读字符串。
        """
        if pcr < 0.5:
            return '极度看多'
        elif pcr < 0.7:
            return '看多'
        elif pcr < 0.9:
            return '偏多'
        elif pcr < 1.1:
            return '中性'
        elif pcr < 1.3:
            return '偏空'
        elif pcr < 1.5:
            return '看空'
        else:
            return '极度看空'

    def calculate_sentiment(self, pcr: float) -> int:
        """
        计算情绪倾向值。

        Args:
            pcr: P/C Ratio (持仓)。

        Returns:
            情绪倾向 (-100 极度看空, 0 中性, 100 极度看多)。
        """
        if pcr < 0.5:
            return 80
        elif pcr < 0.7:
            return 50
        elif pcr < 0.9:
            return 20
        elif pcr < 1.0:
            return 0
        elif pcr < 1.2:
            return -20
        elif pcr < 1.5:
            return -50
        else:
            return -80


class UnderlyingAnalyzer:
    """
    标的分析器。

    对单个标的进行多维度分析。
    """

    def __init__(self):
        self.pcr_analyzer = PCRAnalyzer()
        self.trading_classifier = OptionTradingClassifier()
        self.max_pain_calculator = MaxPainCalculator()

    def analyze(
        self,
        options: List[Dict],
        underlying_price: float
    ) -> UnderlyingAnalysis:
        """
        分析单个标的。

        Args:
            options: 该标的的所有期权数据列表，每个期权包含:
                - symbol: 合约代码
                - call_or_put: 期权类型
                - strike: 行权价
                - last_price: 最新价
                - volume: 成交量
                - open_interest: 持仓量
                - pre_oi: 昨日持仓
                - multiplier: 合约乘数
                - expire_days: 剩余天数
            underlying_price: 标的价格。

        Returns:
            标的分析结果。
        """
        if not options:
            return UnderlyingAnalysis(underlying='', underlying_price=underlying_price)

        # 分类CALL和PUT
        calls = [opt for opt in options if opt.get('call_or_put') == 'CALL']
        puts = [opt for opt in options if opt.get('call_or_put') == 'PUT']

        # 基础统计
        result = UnderlyingAnalysis(
            underlying=options[0].get('underlying', ''),
            underlying_price=underlying_price,
            num_contracts=len(options),
            num_calls=len(calls),
            num_puts=len(puts)
        )

        # 持仓成交统计
        result.total_oi = sum(opt.get('open_interest', 0) for opt in options)
        result.total_volume = sum(opt.get('volume', 0) for opt in options)
        result.call_oi = sum(opt.get('open_interest', 0) for opt in calls)
        result.put_oi = sum(opt.get('open_interest', 0) for opt in puts)
        result.call_volume = sum(opt.get('volume', 0) for opt in calls)
        result.put_volume = sum(opt.get('volume', 0) for opt in puts)

        # 持仓变化
        result.call_oi_change = sum(
            opt.get('open_interest', 0) - opt.get('pre_oi', 0)
            for opt in calls
        )
        result.put_oi_change = sum(
            opt.get('open_interest', 0) - opt.get('pre_oi', 0)
            for opt in puts
        )
        result.oi_change = result.call_oi_change + result.put_oi_change

        # 资金统计 (亿)
        def calc_capital(opts):
            return sum(
                opt.get('open_interest', 0) * opt.get('last_price', 0) * opt.get('multiplier', 1)
                for opt in opts
            ) / 1e8

        result.settled_capital = calc_capital(options)
        result.traded_capital = sum(
            opt.get('volume', 0) * opt.get('last_price', 0) * opt.get('multiplier', 1)
            for opt in options
        ) / 1e8
        result.call_settled_capital = calc_capital(calls)
        result.put_settled_capital = calc_capital(puts)

        # PCR计算
        result.pcr_oi = self.pcr_analyzer.calculate_pcr(result.put_oi, result.call_oi)
        result.pcr_volume = self.pcr_analyzer.calculate_pcr(result.put_volume, result.call_volume)
        result.pcr_capital = self.pcr_analyzer.calculate_pcr(
            result.put_settled_capital, result.call_settled_capital
        )

        # 最大痛点
        result.max_pain = self.max_pain_calculator.calculate(options)
        if underlying_price > 0 and result.max_pain > 0:
            result.max_pain_distance = (result.max_pain - underlying_price) / underlying_price * 100

        # 平均指标
        if options:
            result.avg_turnover = sum(
                opt.get('volume', 0) / max(opt.get('open_interest', 1), 1) * 100
                for opt in options
            ) / len(options)
            result.avg_expire_days = sum(
                opt.get('expire_days', 0) for opt in options
            ) / len(options)

        # 评分计算
        result.liquidity_score = min(100, (result.total_volume / 1000 + result.avg_turnover * 2))
        result.activity_score = abs(result.oi_change) / max(result.total_oi, 1) * 100
        result.sentiment = self.pcr_analyzer.calculate_sentiment(result.pcr_oi)

        result.composite_score = (
            result.liquidity_score * 0.3 +
            result.activity_score * 0.2 +
            80 * 0.2 +  # 价差评分简化
            min(100, result.settled_capital * 10) * 0.3
        )

        # 交易类型分类
        avg_volume = result.total_volume / len(options) if options else 1
        volume_ratio = result.total_volume / max(avg_volume, 1)
        trading_type, subtype, confidence = self.trading_classifier.classify(
            result.call_oi_change, result.put_oi_change, result.pcr_oi, volume_ratio
        )
        result.trading_type = trading_type
        result.trading_subtype = subtype
        result.type_confidence = confidence

        return result


def main():
    """命令行入口函数 - 演示模块功能"""
    print("=" * 60)
    print("WiseCoin 期权分析器模块")
    print("=" * 60)

    # 显示可用类
    print("\n可用类:")
    print("  - OptionAnalyzer: 期权多因子分析")
    print("  - PCRAnalyzer: P/C Ratio 分析")
    print("  - MaxPainCalculator: 最大痛点计算")
    print("  - OptionScorer: 期权评分器")
    print("  - OptionTradingClassifier: 交易类型分类器")
    print("  - UnderlyingAnalyzer: 标的分析器")

    print("\n使用示例:")
    print("  from core.analyzer import OptionAnalyzer")
    print("  analyzer = OptionAnalyzer()")
    print("  result = analyzer.analyze_option(option, future_price)")

    print("\n详细文档: docs/迁移对应表.md")
    print("=" * 60)


if __name__ == "__main__":
    main()

