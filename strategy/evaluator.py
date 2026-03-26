# strategy/evaluator.py
"""
策略评估器模块。

基于多因子模型对期权进行评分和排序。
支持波动率分析、市场状态评估、策略推荐等功能。
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from datetime import date, datetime

from core.models import AnalyzedOption, Signal


@dataclass
class ScoringFactors:
    """评分因子权重配置。"""
    iv_weight: float = 0.25        # IV 因子权重
    leverage_weight: float = 0.20   # 杠杆因子权重
    liquidity_weight: float = 0.15  # 流动性因子权重
    time_value_weight: float = 0.15 # 时间价值因子权重
    moneyness_weight: float = 0.25  # 价值度因子权重


@dataclass
class MarketState:
    """
    市场状态数据。

    包含标的现价、波动率、情绪、到期信息等。
    """
    underlying: str = ""
    expiry: str = ""
    underlying_price: float = 0.0
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    mid_price: Optional[float] = None

    # 波动率指标
    iv_atm: Optional[float] = None
    rv_atm: Optional[float] = None
    hv20: Optional[float] = None
    hv60: Optional[float] = None
    iv_rv_ratio: Optional[float] = None

    # 市场情绪
    futures_direction: str = ""
    futures_status: str = ""
    option_sentiment: str = ""
    pcr: float = 1.0

    # 痛点信息
    max_pain: Optional[float] = None
    pain_distance_pct: Optional[float] = None

    # 到期信息
    expiry_date: Optional[str] = None
    min_days_to_expiry: int = 0
    avg_days_to_expiry: float = 0.0
    exercise_style: str = "欧式"  # 欧式/美式

    # 资金信息
    futures_capital: float = 0.0
    option_capital: float = 0.0

    # 波动率曲面特征
    vol_skew: str = ""
    vol_term_structure: str = ""
    vol_kurtosis: str = ""
    vol_skewness: str = ""
    recommended_strategy: str = ""

    # 原始数据
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VolatilityFeatures:
    """波动率曲面特征。"""
    skew: str = "Flat"  # 倾斜方向: Call Skew / Put Skew / Flat
    skew_slope: Optional[float] = None
    term_structure: str = "Normal"  # 期限结构: Normal / Inverted / Steep
    term_spread: Optional[float] = None
    short_iv: Optional[float] = None
    long_iv: Optional[float] = None
    iv_rv_ratio: Optional[float] = None
    kurtosis: str = "Medium"
    skewness: str = "~0"
    market_sentiment: str = "窄幅震荡"
    recommended_strategy: str = ""
    recommended_contract: str = ""


@dataclass
class StrategyRecommendation:
    """策略推荐结果。"""
    strategy_type: str
    strategy_name: str
    score: float
    suitability: str  # HIGH / MEDIUM / LOW
    reasons: List[str]
    legs: List[Dict[str, Any]]
    risk_level: str
    expected_return: Optional[float] = None
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven: Optional[float] = None


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

        # 计算每个因子的归一化分数并加权求和
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

        # 按评分降序排列
        return sorted(analyzed_options, key=lambda x: x.score, reverse=True)

    def evaluate_dataframe(
        self,
        options_df: pd.DataFrame,
        market_state: Optional[MarketState] = None,
    ) -> pd.DataFrame:
        """
        对DataFrame格式的期权数据进行评分。

        Args:
            options_df: 期权数据DataFrame
            market_state: 市场状态

        Returns:
            添加了评分列的DataFrame
        """
        if options_df is None or options_df.empty:
            return options_df

        df = options_df.copy()
        iv_reference = market_state.iv_atm if market_state else None

        # 计算各因子分数
        df['iv_score'] = df.apply(
            lambda row: self._calculate_iv_score(
                row.get('隐含波动率', row.get('iv')),
                iv_reference
            ), axis=1
        )

        df['leverage_score'] = df.apply(
            lambda row: self._calculate_leverage_score(
                row.get('杠杆', row.get('leverage', 0))
            ), axis=1
        )

        df['liquidity_score'] = df.apply(
            lambda row: self._calculate_liquidity_score(
                row.get('成交量', row.get('volume', 0)),
                row.get('持仓量', row.get('open_interest', 0))
            ), axis=1
        )

        df['time_value_score'] = df.apply(
            lambda row: self._calculate_time_value_score(
                row.get('时间价值', row.get('time_value', 0)),
                row.get('期权价', row.get('last_price', 0))
            ), axis=1
        )

        # 计算moneyness
        if 'moneyness' not in df.columns:
            underlying_price = market_state.underlying_price if market_state else df.get('标的现价', 0)
            strike = df['行权价']
            is_call = df.get('期权类型', 'CALL').str.upper().str.contains('CALL|C')
            df['moneyness'] = np.where(
                is_call,
                underlying_price / strike,
                strike / underlying_price
            )

        df['moneyness_score'] = df.apply(
            lambda row: self._calculate_moneyness_score(
                row.get('moneyness', 1.0),
                'CALL' in str(row.get('期权类型', 'CALL')).upper()
            ), axis=1
        )

        # 计算总分
        df['total_score'] = (
            df['iv_score'] * self.factors.iv_weight +
            df['leverage_score'] * self.factors.leverage_weight +
            df['liquidity_score'] * self.factors.liquidity_weight +
            df['time_value_score'] * self.factors.time_value_weight +
            df['moneyness_score'] * self.factors.moneyness_weight
        ).round(2)

        # 确定信号
        df['signal'] = df['total_score'].apply(self._determine_signal_str)

        return df.sort_values('total_score', ascending=False)

    def get_market_state(
        self,
        underlying: str,
        expiry: str,
        options_df: pd.DataFrame,
        market_overview_df: Optional[pd.DataFrame] = None,
        futures_quotes_df: Optional[pd.DataFrame] = None,
    ) -> MarketState:
        """
        获取标的市场状态。

        Args:
            underlying: 标的合约
            expiry: 交割年月
            options_df: 期权数据
            market_overview_df: 市场概览数据
            futures_quotes_df: 期货行情数据

        Returns:
            市场状态对象
        """
        state = MarketState(underlying=underlying, expiry=expiry)

        # 从市场概览获取基础信息
        if market_overview_df is not None and not market_overview_df.empty:
            mask = market_overview_df.get('标的合约', '') == underlying
            if mask.any():
                row = market_overview_df[mask].iloc[0]
                state.futures_direction = row.get('期货方向', '')
                state.futures_status = row.get('期货状态', '')
                state.option_sentiment = row.get('期权情绪', '')
                state.pcr = float(row.get('期权PCR', 1.0) or 1.0)
                state.futures_capital = float(row.get('期货沉淀(亿)', 0) or 0)
                state.option_capital = float(row.get('期权沉淀(亿)', 0) or 0)
                state.max_pain = row.get('最大痛点')
                state.raw_data = row.to_dict()

        # 获取标的现价
        state.underlying_price = self._get_underlying_price(
            underlying, expiry, options_df, futures_quotes_df
        )

        # 计算ATM波动率指标
        vol_metrics = self._calc_atm_vol_metrics(options_df, state.underlying_price)
        state.iv_atm = vol_metrics.get('iv_atm')
        state.rv_atm = vol_metrics.get('rv_atm')
        state.hv20 = vol_metrics.get('hv20')
        state.hv60 = vol_metrics.get('hv60')
        state.iv_rv_ratio = vol_metrics.get('iv_rv_ratio')

        # 计算痛点距离
        if state.max_pain and state.underlying_price and state.max_pain > 0:
            state.pain_distance_pct = (state.underlying_price - state.max_pain) / state.max_pain * 100

        # 获取到期信息
        if '剩余天数' in options_df.columns:
            state.min_days_to_expiry = int(options_df['剩余天数'].min())
            state.avg_days_to_expiry = float(options_df['剩余天数'].mean())

        if '到期日' in options_df.columns:
            expiry_dates = options_df['到期日'].dropna()
            if not expiry_dates.empty:
                state.expiry_date = str(expiry_dates.iloc[0])

        # 获取行权方式
        if 'exercise_type' in options_df.columns:
            exercise = options_df['exercise_type'].iloc[0]
            state.exercise_style = '美式' if str(exercise).upper() == 'A' else '欧式'

        return state

    def get_volatility_features(
        self,
        underlying: str,
        vol_surface_df: Optional[pd.DataFrame] = None,
    ) -> VolatilityFeatures:
        """
        获取波动率曲面特征。

        Args:
            underlying: 标的合约
            vol_surface_df: 波动率曲面数据

        Returns:
            波动率特征对象
        """
        features = VolatilityFeatures()

        if vol_surface_df is None or vol_surface_df.empty:
            return features

        # 提取品种代码
        if '.' in underlying:
            symbol_code = underlying.split('.')[1].upper()
        else:
            symbol_code = underlying.upper()

        # 从波动率曲面中提取信息
        mask = vol_surface_df.get('品种代码', pd.Series()).str.upper() == symbol_code
        if not mask.any():
            mask = vol_surface_df.get('品种代码', pd.Series()).str.upper().str.contains(symbol_code[:2], na=False)

        if mask.any():
            row = vol_surface_df[mask].iloc[0]
            features.skew = row.get('倾斜方向', 'Flat')
            features.skew_slope = row.get('IV倾斜度')
            features.term_structure = row.get('期限结构', 'Normal')
            features.term_spread = row.get('期限结构差')
            features.short_iv = row.get('短期IV')
            features.long_iv = row.get('长期IV')
            features.iv_rv_ratio = row.get('IV/RV比率')
            features.kurtosis = row.get('峰度', 'Medium')
            features.skewness = row.get('偏度', '~0')
            features.market_sentiment = row.get('市场情绪', '窄幅震荡')
            features.recommended_strategy = row.get('推荐策略', '')
            features.recommended_contract = row.get('推荐合约', '')

        return features

    def recommend_strategies(
        self,
        market_state: MarketState,
        vol_features: Optional[VolatilityFeatures] = None,
    ) -> List[StrategyRecommendation]:
        """
        根据市场状态推荐策略。

        Args:
            market_state: 市场状态
            vol_features: 波动率特征

        Returns:
            推荐策略列表
        """
        recommendations = []

        # 方向性策略
        if '涨' in market_state.futures_direction or '偏多' in market_state.futures_direction:
            if market_state.iv_rv_ratio is None or market_state.iv_rv_ratio < 1.2:
                recommendations.append(StrategyRecommendation(
                    strategy_type="directional",
                    strategy_name="买入看涨期权",
                    score=80.0,
                    suitability="HIGH",
                    reasons=[
                        f"市场方向偏多 ({market_state.futures_direction})",
                        f"IV/RV比率适中 ({market_state.iv_rv_ratio:.2f})" if market_state.iv_rv_ratio else "IV适中",
                    ],
                    legs=[],
                    risk_level="MEDIUM",
                    max_loss="权利金",
                    max_profit="无限",
                ))

        if '跌' in market_state.futures_direction or '偏空' in market_state.futures_direction:
            if market_state.iv_rv_ratio is None or market_state.iv_rv_ratio < 1.2:
                recommendations.append(StrategyRecommendation(
                    strategy_type="directional",
                    strategy_name="买入看跌期权",
                    score=80.0,
                    suitability="HIGH",
                    reasons=[
                        f"市场方向偏空 ({market_state.futures_direction})",
                        f"IV/RV比率适中 ({market_state.iv_rv_ratio:.2f})" if market_state.iv_rv_ratio else "IV适中",
                    ],
                    legs=[],
                    risk_level="MEDIUM",
                    max_loss="权利金",
                    max_profit="高",
                ))

        # 波动率策略
        if vol_features:
            if "Call Skew" in vol_features.skew:
                recommendations.append(StrategyRecommendation(
                    strategy_type="volatility",
                    strategy_name="风险反转 (Risk Reversal)",
                    score=75.0,
                    suitability="HIGH",
                    reasons=[
                        "Call Skew明显，虚值Call相对便宜",
                        "适合买入虚值Call + 卖出虚值Put",
                    ],
                    legs=[],
                    risk_level="HIGH",
                ))

            if "Put Skew" in vol_features.skew:
                recommendations.append(StrategyRecommendation(
                    strategy_type="volatility",
                    strategy_name="反向风险反转",
                    score=75.0,
                    suitability="HIGH",
                    reasons=[
                        "Put Skew明显，虚值Put相对便宜",
                        "适合买入虚值Put + 卖出虚值Call",
                    ],
                    legs=[],
                    risk_level="HIGH",
                ))

            if "Inverted" in vol_features.term_structure:
                recommendations.append(StrategyRecommendation(
                    strategy_type="calendar",
                    strategy_name="日历价差",
                    score=70.0,
                    suitability="HIGH",
                    reasons=[
                        "期限结构倒挂，近月IV高于远月",
                        "适合卖出近月 + 买入远月",
                    ],
                    legs=[],
                    risk_level="LOW",
                ))

        # 中性策略
        if market_state.option_sentiment in ['中性', '震荡']:
            recommendations.append(StrategyRecommendation(
                strategy_type="neutral",
                strategy_name="铁鹰式价差",
                score=70.0,
                suitability="HIGH",
                reasons=[
                    "市场情绪中性，适合震荡市策略",
                    "赚取时间价值衰减",
                ],
                legs=[],
                risk_level="MEDIUM",
            ))

        # 排序
        recommendations.sort(key=lambda x: (-x.score, -{"HIGH": 3, "MEDIUM": 2, "LOW": 1}[x.suitability]))

        return recommendations

    def _get_underlying_price(
        self,
        underlying: str,
        expiry: str,
        options_df: pd.DataFrame,
        futures_quotes_df: Optional[pd.DataFrame] = None,
    ) -> float:
        """获取标的现价。"""
        # 优先从期货行情获取
        if futures_quotes_df is not None and not futures_quotes_df.empty:
            # 尝试匹配
            matches = futures_quotes_df[futures_quotes_df.get('instrument_id', '') == underlying]
            if len(matches) == 0:
                short_symbol = underlying.split('.')[-1]
                matches = futures_quotes_df[
                    futures_quotes_df.get('instrument_id', '').str.endswith('.' + short_symbol, na=False)
                ]
            if len(matches) > 0:
                row = matches.iloc[0]
                bid = row.get('bid_price1', 0)
                ask = row.get('ask_price1', 0)
                if bid and ask and bid > 0 and ask > 0:
                    return (bid + ask) / 2
                last = row.get('last_price', 0)
                if last and last > 0:
                    return last

        # 从期权数据获取
        if '标的现价' in options_df.columns:
            prices = options_df['标的现价'].dropna()
            if not prices.empty:
                return float(prices.median())

        return 0.0

    def _calc_atm_vol_metrics(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
    ) -> Dict[str, Optional[float]]:
        """计算ATM附近的波动率指标。"""
        metrics = {
            'iv_atm': None,
            'rv_atm': None,
            'hv20': None,
            'hv60': None,
            'iv_rv_ratio': None,
        }

        if options_df is None or options_df.empty or underlying_price <= 0:
            return metrics

        df = options_df.copy()
        df['strike_diff'] = (df['行权价'] - underlying_price).abs()
        df = df.sort_values('strike_diff').head(20)

        if df.empty:
            return metrics

        rep = df.iloc[0]

        iv = rep.get('隐含波动率', rep.get('iv'))
        rv = rep.get('近期波动率', rep.get('rv'))
        hv20 = rep.get('HV20')
        hv60 = rep.get('HV60')

        if iv is not None and not pd.isna(iv):
            metrics['iv_atm'] = float(iv)
        if rv is not None and not pd.isna(rv):
            metrics['rv_atm'] = float(rv)
        if hv20 is not None and not pd.isna(hv20):
            metrics['hv20'] = float(hv20)
        if hv60 is not None and not pd.isna(hv60):
            metrics['hv60'] = float(hv60)

        if metrics['iv_atm'] and metrics['rv_atm'] and metrics['rv_atm'] > 0:
            metrics['iv_rv_ratio'] = metrics['iv_atm'] / metrics['rv_atm']

        return metrics

    def _calculate_iv_score(self, iv: Optional[float], reference: Optional[float]) -> float:
        """计算 IV 因子分数（IV 偏低时分数高）。"""
        if iv is None or reference is None or reference <= 0:
            return 50.0

        iv_ratio = iv / reference

        if iv_ratio <= 0.7:
            return 100.0
        elif iv_ratio <= 0.85:
            return 80.0
        elif iv_ratio <= 1.0:
            return 60.0
        elif iv_ratio <= 1.15:
            return 40.0
        elif iv_ratio <= 1.3:
            return 20.0
        else:
            return 0.0

    def _calculate_leverage_score(self, leverage: float) -> float:
        """计算杠杆因子分数（杠杆适中时分数高）。"""
        if leverage <= 0:
            return 0.0

        if leverage < 5:
            return leverage * 4.0
        elif leverage < 10:
            return 20.0 + (leverage - 5) * 8.0
        elif leverage <= 50:
            return 60.0 + (leverage - 10) * 1.0
        elif leverage <= 100:
            return 100.0 - (leverage - 50) * 1.2
        else:
            return max(0.0, 40.0 - (leverage - 100) * 0.4)

    def _calculate_liquidity_score(self, volume: int, open_interest: int) -> float:
        """计算流动性因子分数。"""
        # 成交量分数
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

        # 持仓量分数
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

        return volume_score * 0.6 + oi_score * 0.4

    def _calculate_time_value_score(self, time_value: float, option_price: float) -> float:
        """计算时间价值因子分数。"""
        if option_price <= 0:
            return 50.0

        time_value_ratio = time_value / option_price

        if time_value_ratio <= 0.2:
            return 100.0 - time_value_ratio * 100
        elif time_value_ratio <= 0.4:
            return 80.0 - (time_value_ratio - 0.2) * 100
        elif time_value_ratio <= 0.6:
            return 60.0 - (time_value_ratio - 0.4) * 100
        elif time_value_ratio <= 0.8:
            return 40.0 - (time_value_ratio - 0.6) * 100
        else:
            return max(0.0, 20.0 - (time_value_ratio - 0.8) * 100)

    def _calculate_moneyness_score(self, moneyness: float, is_call: bool) -> float:
        """计算价值度因子分数。"""
        if moneyness <= 0:
            return 0.0

        deviation = abs(moneyness - 1.0)

        if deviation <= 0.02:
            return 100.0
        elif deviation <= 0.05:
            return 90.0 - deviation * 200
        elif deviation <= 0.10:
            return 80.0 - deviation * 300
        elif deviation <= 0.20:
            return 50.0 - deviation * 200
        else:
            return max(10.0, 30.0 - deviation * 50)

    def _determine_signal(self, score: float) -> Signal:
        """根据评分确定交易信号。"""
        if score > 70:
            return Signal.BUY
        elif score < 30:
            return Signal.SELL
        else:
            return Signal.HOLD

    def _determine_signal_str(self, score: float) -> str:
        """根据评分确定交易信号字符串。"""
        if score > 70:
            return "BUY"
        elif score < 30:
            return "SELL"
        else:
            return "HOLD"