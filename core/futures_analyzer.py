# core/futures_analyzer.py
"""
WiseCoin 期货分析器模块。

提供期货技术分析、趋势判断、资金流向分析等核心计算功能。
不包含数据获取逻辑（TqSDK 相关部分应在 data/ 层）。

主要功能：
1. 趋势状态分类 - 基于价格和持仓变化判断趋势
2. 资金流向分析 - 计算沉淀资金、成交资金、杠杆涨跌
3. 货权联动分析 - 期货期权共振/背离检测
4. 联动强度模型 - 综合评分系统
"""
from dataclasses import dataclass, field
from typing import Tuple, Dict, List, Optional
from enum import Enum
import pandas as pd
import numpy as np


class TrendDirection(str, Enum):
    """趋势方向枚举。"""
    BULLISH = "多"
    BEARISH = "空"
    NEUTRAL = "震荡"


class FlowSignal(int, Enum):
    """资金流向信号枚举。"""
    STRONG_BULLISH = 2    # 增仓上涨
    WEAK_BULLISH = 1      # 减仓上涨
    NEUTRAL = 0           # 持平
    WEAK_BEARISH = -1     # 减仓下跌
    STRONG_BEARISH = -2   # 增仓下跌


class ResonanceLevel(str, Enum):
    """共振等级枚举。"""
    STRONG = "强共振"
    MEDIUM = "共振"
    NEUTRAL = "中性"
    WEAK = "弱相关"
    DIVERGENCE = "背离"


@dataclass
class FuturesAnalysisResult:
    """
    期货分析结果。

    Attributes:
        symbol: 合约代码
        product_code: 品种代码
        last_price: 现价
        pre_close: 昨收
        price_change_pct: 涨跌幅%
        leverage_change_pct: 杠杆涨跌%
        leverage: 杠杆倍数
        margin_ratio: 保证金率
        open_interest: 持仓量
        volume: 成交量
        oi_change: 持仓变化
        oi_change_pct: 持仓变化%
        settled_capital: 沉淀资金(亿)
        traded_capital: 成交资金(亿)
        turnover_rate: 换手率%
        flow_direction: 资金流向
        flow_signal: 流向信号
        trend_state: 趋势状态
        trend_direction: 趋势方向
        trend_strength: 趋势强度
    """
    symbol: str
    product_code: str
    last_price: float
    pre_close: float
    price_change_pct: float
    leverage_change_pct: float
    leverage: float
    margin_ratio: float
    open_interest: int
    volume: int
    oi_change: int
    oi_change_pct: float
    settled_capital: float  # 沉淀资金(亿)
    traded_capital: float   # 成交资金(亿)
    turnover_rate: float    # 换手率%
    flow_direction: str
    flow_signal: int
    trend_state: str
    trend_direction: str
    trend_strength: int


@dataclass
class LinkageAnalysisResult:
    """
    货权联动分析结果。

    Attributes:
        symbol: 标的合约
        futures_price: 期货现价
        leverage_change_pct: 杠杆涨跌%
        futures_state: 期货状态
        futures_direction: 期货方向
        futures_flow: 期货流向
        futures_capital: 期货沉淀(亿)
        option_structure: 期权结构
        option_sentiment: 期权情绪
        option_pcr: 期权PCR
        option_capital: 期权沉淀(亿)
        linkage_state: 联动状态
        market_interpretation: 市场解读
        resonance_score: 共振评分
        linkage_total_score: 联动总分
        price_score: 价格评分
        capital_score: 资金评分
        sentiment_score: 情绪评分
        resonance_grade: 共振等级
        resonance_label: 共振标签
        max_pain: 最大痛点
        max_pain_distance: 痛点距离%
        suitable_strategy: 适合策略
        unsuitable_strategy: 不适合策略
    """
    symbol: str
    futures_price: float
    leverage_change_pct: float
    futures_state: str
    futures_direction: str
    futures_flow: str
    futures_capital: float
    option_structure: str
    option_sentiment: str
    option_pcr: float
    option_capital: float
    linkage_state: str
    market_interpretation: str
    resonance_score: int
    linkage_total_score: float
    price_score: float
    capital_score: float
    sentiment_score: float
    resonance_grade: str
    resonance_label: str
    max_pain: float
    max_pain_distance: float
    suitable_strategy: str
    unsuitable_strategy: str


class FuturesAnalyzer:
    """
    期货分析器。

    提供期货技术分析、趋势判断、资金流向分析等核心计算功能。

    Example:
        >>> analyzer = FuturesAnalyzer()
        >>> result = analyzer.analyze_contract(
        ...     symbol="SHFE.ag2602",
        ...     last_price=5000.0,
        ...     pre_close=4900.0,
        ...     open_interest=100000,
        ...     pre_open_interest=95000,
        ...     volume=50000,
        ...     multiplier=10,
        ...     margin_ratio=0.12
        ... )
    """

    # 阈值常量
    PRICE_CHANGE_THRESHOLD = 0.5   # 价格变化阈值 ±0.5%
    OI_CHANGE_THRESHOLD = 1.0      # 持仓变化阈值 ±1%

    def analyze_contract(
        self,
        symbol: str,
        product_code: str,
        last_price: float,
        pre_close: float,
        open_interest: int,
        pre_open_interest: int,
        volume: int,
        multiplier: int,
        margin_ratio: float
    ) -> FuturesAnalysisResult:
        """
        分析单个期货合约。

        Args:
            symbol: 合约代码
            product_code: 品种代码
            last_price: 现价
            pre_close: 昨收价
            open_interest: 持仓量
            pre_open_interest: 昨日持仓量
            volume: 成交量
            multiplier: 合约乘数
            margin_ratio: 保证金率

        Returns:
            期货分析结果
        """
        # 杠杆倍数
        leverage = 1.0 / margin_ratio if margin_ratio > 0 else 10.0

        # 价格变化
        price_change_pct = ((last_price - pre_close) / pre_close) * 100 if pre_close > 0 else 0
        leverage_change_pct = price_change_pct * leverage

        # 持仓变化
        oi_change = open_interest - pre_open_interest if pre_open_interest > 0 else 0
        oi_change_pct = (oi_change / pre_open_interest * 100) if pre_open_interest > 0 else 0

        # 换手率
        turnover_rate = (volume / open_interest * 100) if open_interest > 0 else 0

        # 沉淀资金（保证金口径，亿元）
        settled_capital = (open_interest * last_price * multiplier * margin_ratio) / 1e8

        # 成交资金（保证金口径，亿元）
        traded_capital = (volume * last_price * multiplier * margin_ratio) / 1e8

        # 资金流向判断
        flow_direction, flow_signal = self._determine_flow_direction(
            oi_change, price_change_pct
        )

        # 趋势状态分类
        trend_state, trend_direction, trend_strength = self.classify_trend_state(
            price_change_pct, oi_change_pct
        )

        return FuturesAnalysisResult(
            symbol=symbol,
            product_code=product_code,
            last_price=round(last_price, 2),
            pre_close=round(pre_close, 2),
            price_change_pct=round(price_change_pct, 2),
            leverage_change_pct=round(leverage_change_pct, 2),
            leverage=round(leverage, 1),
            margin_ratio=round(margin_ratio, 4),
            open_interest=int(open_interest),
            volume=int(volume),
            oi_change=int(oi_change),
            oi_change_pct=round(oi_change_pct, 2),
            settled_capital=round(settled_capital, 4),
            traded_capital=round(traded_capital, 4),
            turnover_rate=round(turnover_rate, 2),
            flow_direction=flow_direction,
            flow_signal=flow_signal,
            trend_state=trend_state,
            trend_direction=trend_direction,
            trend_strength=trend_strength
        )

    def _determine_flow_direction(
        self,
        oi_change: int,
        price_change_pct: float
    ) -> Tuple[str, int]:
        """
        判断资金流向。

        Args:
            oi_change: 持仓变化
            price_change_pct: 价格变化百分比

        Returns:
            (流向描述, 信号值)
        """
        if oi_change > 0 and price_change_pct > 0:
            return ('增仓上涨', 2)   # 强多
        elif oi_change > 0 and price_change_pct < 0:
            return ('增仓下跌', -2)  # 强空
        elif oi_change < 0 and price_change_pct > 0:
            return ('减仓上涨', 1)   # 弱多
        elif oi_change < 0 and price_change_pct < 0:
            return ('减仓下跌', -1)  # 弱空
        else:
            return ('持平', 0)

    def classify_trend_state(
        self,
        price_change_pct: float,
        oi_change_pct: float
    ) -> Tuple[str, str, int]:
        """
        期货趋势状态机分类。

        【状态分类】:
        1. 趋势强化: 价格↑ + 持仓↑ (多头主动建仓)
        2. 趋势衰减: 价格↑ + 持仓↓ (空头止损离场)
        3. 空头强化: 价格↓ + 持仓↑ (空头主动建仓)
        4. 空头衰减: 价格↓ + 持仓↓ (多头止损离场)

        Args:
            price_change_pct: 价格变化百分比
            oi_change_pct: 持仓变化百分比

        Returns:
            (状态名称, 趋势方向, 趋势强度0-3)
        """
        # 价格方向
        if price_change_pct > self.PRICE_CHANGE_THRESHOLD:
            price_dir = 'up'
        elif price_change_pct < -self.PRICE_CHANGE_THRESHOLD:
            price_dir = 'down'
        else:
            price_dir = 'flat'

        # 持仓方向
        if oi_change_pct > self.OI_CHANGE_THRESHOLD:
            oi_dir = 'up'
        elif oi_change_pct < -self.OI_CHANGE_THRESHOLD:
            oi_dir = 'down'
        else:
            oi_dir = 'flat'

        # 状态分类
        if price_dir == 'up' and oi_dir == 'up':
            # 多头强化: 多头主动进场
            strength = min(3, int((abs(price_change_pct) + abs(oi_change_pct)) / 2))
            return ('多头强化', '多', strength)

        elif price_dir == 'up' and oi_dir == 'down':
            # 多头衰减: 空头平仓推升价格
            strength = min(2, int(abs(price_change_pct) / 1.5))
            return ('多头衰减', '多', strength)

        elif price_dir == 'down' and oi_dir == 'up':
            # 空头强化: 空头主动进场
            strength = min(3, int((abs(price_change_pct) + abs(oi_change_pct)) / 2))
            return ('空头强化', '空', strength)

        elif price_dir == 'down' and oi_dir == 'down':
            # 空头衰减: 多头平仓压低价格
            strength = min(2, int(abs(price_change_pct) / 1.5))
            return ('空头衰减', '空', strength)

        elif price_dir == 'flat':
            if oi_dir == 'up':
                return ('震荡蓄势', '震荡', 1)
            elif oi_dir == 'down':
                return ('震荡减仓', '震荡', 1)
            else:
                return ('盘整', '震荡', 0)

        else:
            # 持仓持平但价格有变化
            if price_dir == 'up':
                return ('弱多', '多', 1)
            else:
                return ('弱空', '空', 1)

    def classify_option_fund_structure(
        self,
        pcr: float,
        call_oi_change: int,
        put_oi_change: int
    ) -> Tuple[str, int]:
        """
        期权资金结构分类。

        【分类标准】:
        - 看多: PCR < 0.7 或 CALL单边增仓明显
        - 看空: PCR > 1.3 或 PUT单边增仓明显
        - 波动率: PCR接近1且双向增仓

        Args:
            pcr: PCR比率
            call_oi_change: CALL持仓变化
            put_oi_change: PUT持仓变化

        Returns:
            (结构类型, 方向一致性分数 -3到3)
        """
        # PCR判断
        if pcr < 0.5:
            pcr_score = 3
        elif pcr < 0.7:
            pcr_score = 2
        elif pcr < 0.9:
            pcr_score = 1
        elif pcr <= 1.1:
            pcr_score = 0
        elif pcr <= 1.3:
            pcr_score = -1
        elif pcr <= 1.5:
            pcr_score = -2
        else:
            pcr_score = -3

        # 增仓方向判断
        both_increasing = call_oi_change > 0 and put_oi_change > 0

        if both_increasing and 0.8 <= pcr <= 1.2:
            return ('波动率', 0)
        elif pcr_score >= 2:
            return ('看多', pcr_score)
        elif pcr_score <= -2:
            return ('看空', pcr_score)
        elif pcr_score > 0:
            return ('偏多', pcr_score)
        elif pcr_score < 0:
            return ('偏空', pcr_score)
        else:
            return ('中性', 0)

    def calculate_resonance_score(
        self,
        futures_trend_strength: int,
        futures_direction: str,
        option_structure: str,
        option_score: int,
        volatility_match: bool = True
    ) -> Tuple[int, str, str]:
        """
        期货-期权共振评分系统。

        【评分维度】:
        1. 期货趋势强度 (0-3分)
        2. 期权方向一致性 (0-3分)
        3. 波动率配合度 (0-2分)

        【输出】:
        - 总分 0-8 分
        - 7-8: 强共振 - 重点跟踪
        - 5-6: 共振
        - 3-4: 中性
        - 1-2: 弱相关
        - 0或负: 明显背离 - 风险提示

        Args:
            futures_trend_strength: 期货趋势强度
            futures_direction: 期货方向 ('多'/'空'/'震荡')
            option_structure: 期权结构
            option_score: 期权方向分数
            volatility_match: 波动率是否匹配

        Returns:
            (总分, 等级符号, 标签)
        """
        # 1. 期货趋势强度 (0-3)
        trend_score = min(3, max(0, futures_trend_strength))

        # 2. 方向一致性 (0-3)
        direction_match = 0
        if futures_direction == '多':
            if option_structure in ['看多', '偏多']:
                direction_match = abs(option_score)
            elif option_structure in ['看空', '偏空']:
                direction_match = -abs(option_score)  # 背离
        elif futures_direction == '空':
            if option_structure in ['看空', '偏空']:
                direction_match = abs(option_score)
            elif option_structure in ['看多', '偏多']:
                direction_match = -abs(option_score)  # 背离
        elif futures_direction == '震荡':
            if option_structure == '波动率':
                direction_match = 2  # 震荡 + 波动率交易 = 匹配

        # 3. 波动率配合度 (0-2)
        vol_score = 2 if volatility_match else 0

        # 总分
        total_score = trend_score + direction_match + vol_score

        # 等级和标签
        if total_score >= 7:
            return (total_score, '****', '强共振')
        elif total_score >= 5:
            return (total_score, '***', '共振')
        elif total_score >= 3:
            return (total_score, '**', '中性')
        elif total_score >= 1:
            return (total_score, '*', '弱相关')
        else:
            return (total_score, '*', '背离')

    def calculate_linkage_strength(
        self,
        futures_row: Dict,
        opt_data: Dict,
        pcr: float
    ) -> Dict[str, float]:
        """
        联动强度模型 (Linkage Strength Model)。

        综合价格、资金、情绪三个维度计算联动强度总分 (0-100)。

        【模型权重】:
        1. 价格强度 (30%): 杠杆涨跌幅强度 + 趋势状态得分
        2. 资金强度 (40%): 期货资金流向强度 + 期权资金流向一致性
        3. 情绪强度 (30%): PCR偏离度 + 情绪得分

        Args:
            futures_row: 期货分析数据字典
            opt_data: 期权数据字典
            pcr: PCR比率

        Returns:
            包含联动总分和各维度评分的字典
        """
        # ============ 1. 价格强度 (30分) ============
        # 杠杆涨跌幅得分 (0-20分)
        leverage_change = abs(futures_row.get('杠杆涨跌%', 0) or 0)
        price_score_raw = min(20, leverage_change * 2)

        # 趋势状态得分 (0-10分)
        trend_strength = futures_row.get('趋势强度', 0) or 0
        trend_score = min(10, trend_strength * 3)

        price_total = min(30, price_score_raw + trend_score)

        # ============ 2. 资金强度 (40分) ============
        # 期货资金强度 (0-20分)
        fut_signal = abs(futures_row.get('流向信号', 0) or 0)
        fut_fund = abs(futures_row.get('沉淀资金(亿)', 0) or 0)
        # 资金规模加成: 每10亿加1分，上限5分
        fund_bonus = min(5, fut_fund / 10)
        # 信号强度: 2分=15分, 1分=10分
        signal_score = 15 if fut_signal >= 2 else (10 if fut_signal >= 1 else 0)

        futures_fund_score = min(20, signal_score + fund_bonus)

        # 期权资金一致性 (0-20分)
        opt_fund_direction = 0
        call_oi_chg = opt_data.get('CALL持仓变化', 0)
        put_oi_chg = opt_data.get('PUT持仓变化', 0)
        futures_dir = futures_row.get('趋势方向', '震荡')

        if call_oi_chg > put_oi_chg:
            opt_fund_direction = 1  # 偏多
        elif put_oi_chg > call_oi_chg:
            opt_fund_direction = -1  # 偏空

        # 判断方向是否一致
        consistency_score = 0
        if futures_dir == '多' and opt_fund_direction == 1:
            consistency_score = 20
        elif futures_dir == '空' and opt_fund_direction == -1:
            consistency_score = 20
        elif futures_dir == '震荡' and call_oi_chg > 0 and put_oi_chg > 0:
            consistency_score = 15  # 震荡市双向增仓视为资金活跃匹配

        capital_total = min(40, futures_fund_score + consistency_score)

        # ============ 3. 情绪强度 (30分) ============
        # PCR偏离度得分 (0-15分)
        # 偏离中枢1.0越远，情绪越强烈
        pcr_deviation = abs(pcr - 1.0)
        pcr_score = min(15, pcr_deviation * 30)

        # 情绪倾向一致性 (0-15分)
        sentiment_score = 0
        opt_sentiment = opt_data.get('情绪倾向', 0)  # -100 to 100

        if futures_dir == '多':
            if opt_sentiment > 0:
                sentiment_score = min(15, opt_sentiment / 100 * 15)
            elif pcr < 0.7:  # 极度看多
                sentiment_score = 15

        elif futures_dir == '空':
            if opt_sentiment < 0:
                sentiment_score = min(15, abs(opt_sentiment) / 100 * 15)
            elif pcr > 1.3:  # 极度看空
                sentiment_score = 15

        sentiment_total = min(30, pcr_score + sentiment_score)

        # ============ 总分汇总 ============
        total_score = price_total + capital_total + sentiment_total

        return {
            '联动总分': round(total_score, 1),
            '价格评分': round(price_total, 1),
            '资金评分': round(capital_total, 1),
            '情绪评分': round(sentiment_total, 1)
        }

    def determine_linkage_state(
        self,
        futures_state: str,
        futures_dir: str,
        option_structure: str,
        pcr: float,
        vol_sentiment: str = ''
    ) -> Tuple[str, str]:
        """
        四层联动判断框架。

        【第一层】期货趋势（方向）: 多 / 空 / 震荡
        【第二层】期权资金结构（预期）: 看多 / 看空 / 波动率
        【第三层】期权波动率情绪: 狂热 / 恐慌 / 筑底 / 冲高
        【第四层】一致性或背离

        Args:
            futures_state: 期货趋势状态
            futures_dir: 期货方向
            option_structure: 期权结构
            pcr: PCR比率
            vol_sentiment: 波动率情绪

        Returns:
            (联动状态标签, 市场解读)
        """
        # 基础解读逻辑
        base_state = ''
        base_interpretation = ''

        # 1. 期货多头情形
        if futures_dir == '多':
            if option_structure in ['看多', '偏多']:
                base_state, base_interpretation = ('趋势确认', '期货上涨+CALL主导，趋势延续概率高')
                # 叠加情绪
                if '狂热' in vol_sentiment:
                    return ('加速赶顶', f"{base_interpretation} | 波动率狂热，小心过热回落")
            elif option_structure in ['看空', '偏空']:
                base_state, base_interpretation = ('顶部警惕', '期货上涨+PUT增仓，注意对冲或反转信号')
                if '恐慌' in vol_sentiment:
                    return ('极度背离', f"{base_interpretation} | 波动率恐慌，反转风险极大")

        # 2. 期货空头情形
        elif futures_dir == '空':
            if option_structure in ['看空', '偏空']:
                base_state, base_interpretation = ('空头确认', '期货下跌+PUT主导，空头趋势延续')
                if '恐慌' in vol_sentiment:
                    return ('加速赶底', f"{base_interpretation} | 波动率恐慌，小心超跌反弹")
            elif option_structure in ['看多', '偏多']:
                base_state, base_interpretation = ('抄底信号', '期货下跌+CALL增仓，可能有抄底资金或错配')
                if '狂热' in vol_sentiment:
                    return ('极度背离', f"{base_interpretation} | 波动率狂热，可能是期权诱多")

        # 3. 期货震荡情形
        elif futures_dir == '震荡':
            if option_structure == '波动率':
                base_state, base_interpretation = ('波动率机会', '期货震荡+双向期权放量，适合波动率策略')
            elif option_structure in ['看多', '偏多']:
                base_state, base_interpretation = ('蓄势待涨', '期货震荡+期权看多，关注突破方向')
            elif option_structure in ['看空', '偏空']:
                base_state, base_interpretation = ('蓄势待跌', '期货震荡+期权看空，关注破位风险')
            else:
                base_state, base_interpretation = ('观望', '期货和期权均无明确方向')

            # 叠加情绪
            if '筑底' in vol_sentiment:
                return ('震荡筑底', f"{base_interpretation} | 波动率显示筑底特征")
            elif '冲高' in vol_sentiment:
                return ('震荡冲高', f"{base_interpretation} | 波动率显示冲高特征")

        # 如果已有定义则返回
        if base_state:
            # 如果有特殊情绪叠加
            if '恐慌' in vol_sentiment and '确认' in base_state:
                return ('恐慌加速', f"{base_interpretation} | 市场陷入恐慌")
            if '狂热' in vol_sentiment and '确认' in base_state:
                return ('狂热过热', f"{base_interpretation} | 市场情绪狂热")

            return (base_state, base_interpretation)

        return ('信号不明', '需要进一步观察')

    def suggest_strategy(
        self,
        linkage_state: str,
        futures_state: str,
        option_structure: str,
        resonance_label: str
    ) -> Tuple[str, str]:
        """
        策略导向建议。

        基于联动状态和共振评分，给出具体的策略建议。

        Args:
            linkage_state: 联动状态
            futures_state: 期货趋势状态
            option_structure: 期权结构
            resonance_label: 共振标签

        Returns:
            (适合策略, 不适合策略)
        """
        suitable = []
        unsuitable = []

        if linkage_state == '趋势确认':
            suitable = ['趋势跟随', '买入CALL', '卖出PUT']
            unsuitable = ['裸卖CALL', '逆势做空']

        elif linkage_state == '空头确认':
            suitable = ['趋势跟随', '买入PUT', '卖出CALL']
            unsuitable = ['裸卖PUT', '逆势做多']

        elif linkage_state == '顶部警惕':
            suitable = ['保护性PUT', '领口策略', '减仓观望']
            unsuitable = ['单边追价', '裸卖PUT', '激进加仓']

        elif linkage_state == '抄底信号':
            suitable = ['分批建仓', '卖出PUT', '牛市价差']
            unsuitable = ['单边追空', '裸卖CALL']

        elif linkage_state == '波动率机会':
            suitable = ['买跨式', '买宽跨式', '比率价差']
            unsuitable = ['裸卖跨式', '单边方向策略']

        elif linkage_state == '蓄势待涨':
            suitable = ['轻仓试多', '牛市价差', '卖出PUT']
            unsuitable = ['重仓做空', '裸卖CALL']

        elif linkage_state == '蓄势待跌':
            suitable = ['轻仓试空', '熊市价差', '卖出CALL']
            unsuitable = ['重仓做多', '裸卖PUT']

        elif resonance_label == '背离':
            suitable = ['观望', '对冲', '减仓']
            unsuitable = ['单边追价', '裸卖期权', '加杠杆']

        else:
            suitable = ['观望', '小仓位试探']
            unsuitable = ['重仓单边']

        return ' / '.join(suitable), ' / '.join(unsuitable)

    def analyze_linkage(
        self,
        futures_result: FuturesAnalysisResult,
        option_data: Dict,
        vol_sentiment: str = ''
    ) -> LinkageAnalysisResult:
        """
        执行货权联动分析。

        Args:
            futures_result: 期货分析结果
            option_data: 期权数据字典，包含PCR、最大痛点等
            vol_sentiment: 波动率情绪

        Returns:
            联动分析结果
        """
        pcr = option_data.get('PCR(持仓)', 1.0)
        max_pain = option_data.get('最大痛点', 0)
        max_pain_distance = option_data.get('痛点距离%', 0)
        option_sentiment_score = option_data.get('情绪倾向', 0)
        option_capital = option_data.get('沉淀资金(亿)', 0)
        call_oi_change = option_data.get('CALL持仓变化', 0)
        put_oi_change = option_data.get('PUT持仓变化', 0)

        # 期权资金结构分类
        option_structure, option_dir_score = self.classify_option_fund_structure(
            pcr, call_oi_change, put_oi_change
        )

        # 联动状态判断
        linkage_state, market_interpretation = self.determine_linkage_state(
            futures_result.trend_state,
            futures_result.trend_direction,
            option_structure,
            pcr,
            vol_sentiment
        )

        # 共振评分
        resonance_score, resonance_grade, resonance_label = self.calculate_resonance_score(
            futures_result.trend_strength,
            futures_result.trend_direction,
            option_structure,
            option_dir_score,
            volatility_match=(option_structure == '波动率' and futures_result.trend_direction == '震荡')
        )

        # 联动强度模型评分
        futures_row = {
            '杠杆涨跌%': futures_result.leverage_change_pct,
            '趋势强度': futures_result.trend_strength,
            '趋势方向': futures_result.trend_direction,
            '流向信号': futures_result.flow_signal,
            '沉淀资金(亿)': futures_result.settled_capital
        }
        strength_scores = self.calculate_linkage_strength(futures_row, option_data, pcr)

        # 策略建议
        suitable_strategy, unsuitable_strategy = self.suggest_strategy(
            linkage_state,
            futures_result.trend_state,
            option_structure,
            resonance_label
        )

        return LinkageAnalysisResult(
            symbol=futures_result.symbol,
            futures_price=futures_result.last_price,
            leverage_change_pct=futures_result.leverage_change_pct,
            futures_state=futures_result.trend_state,
            futures_direction=futures_result.trend_direction,
            futures_flow=futures_result.flow_direction,
            futures_capital=futures_result.settled_capital,
            option_structure=option_structure,
            option_sentiment=vol_sentiment if vol_sentiment else str(option_sentiment_score),
            option_pcr=round(pcr, 4),
            option_capital=round(option_capital, 4),
            linkage_state=linkage_state,
            market_interpretation=market_interpretation,
            resonance_score=resonance_score,
            linkage_total_score=strength_scores['联动总分'],
            price_score=strength_scores['价格评分'],
            capital_score=strength_scores['资金评分'],
            sentiment_score=strength_scores['情绪评分'],
            resonance_grade=resonance_grade,
            resonance_label=resonance_label,
            max_pain=round(max_pain, 2),
            max_pain_distance=round(max_pain_distance, 2),
            suitable_strategy=suitable_strategy,
            unsuitable_strategy=unsuitable_strategy
        )


def generate_market_summary(
    futures_df: pd.DataFrame,
    correlation_analysis: Optional[List[Dict]] = None
) -> pd.DataFrame:
    """
    生成期货市场概览。

    Args:
        futures_df: 期货分析结果DataFrame
        correlation_analysis: 联动分析结果列表（可选）

    Returns:
        市场概览DataFrame
    """
    summary_data = []

    # 整体统计
    total_contracts = len(futures_df)
    total_chendian = futures_df['沉淀资金(亿)'].sum() if '沉淀资金(亿)' in futures_df.columns else 0
    total_chengjiao = futures_df['成交资金(亿)'].sum() if '成交资金(亿)' in futures_df.columns else 0

    # 涨跌统计
    up_count = len(futures_df[futures_df['杠杆涨跌%'] > 0]) if '杠杆涨跌%' in futures_df.columns else 0
    down_count = len(futures_df[futures_df['杠杆涨跌%'] < 0]) if '杠杆涨跌%' in futures_df.columns else 0
    flat_count = total_contracts - up_count - down_count

    avg_leverage_change = futures_df['杠杆涨跌%'].mean() if '杠杆涨跌%' in futures_df.columns else 0
    max_leverage_up = futures_df['杠杆涨跌%'].max() if '杠杆涨跌%' in futures_df.columns else 0
    max_leverage_down = futures_df['杠杆涨跌%'].min() if '杠杆涨跌%' in futures_df.columns else 0

    # 资金流向统计
    bullish_count = len(futures_df[futures_df['流向信号'] > 0]) if '流向信号' in futures_df.columns else 0
    bearish_count = len(futures_df[futures_df['流向信号'] < 0]) if '流向信号' in futures_df.columns else 0
    neutral_count = len(futures_df[futures_df['流向信号'] == 0]) if '流向信号' in futures_df.columns else 0

    summary_data = [
        {'指标': '期货合约总数', '数值': total_contracts, '说明': '分析的期货合约数量'},
        {'指标': '期货沉淀资金(亿)', '数值': round(total_chendian, 2), '说明': '持仓量 x 价格 x 乘数 x 保证金率'},
        {'指标': '期货成交资金(亿)', '数值': round(total_chengjiao, 2), '说明': '成交量 x 价格 x 乘数 x 保证金率'},
        {'指标': '上涨品种数', '数值': up_count, '说明': '杠杆涨跌>0的品种'},
        {'指标': '下跌品种数', '数值': down_count, '说明': '杠杆涨跌<0的品种'},
        {'指标': '平盘品种数', '数值': flat_count, '说明': '杠杆涨跌=0的品种'},
        {'指标': '平均杠杆涨跌%', '数值': round(avg_leverage_change, 2), '说明': '所有品种杠杆涨跌均值'},
        {'指标': '最大杠杆涨幅%', '数值': round(max_leverage_up, 2), '说明': '单日最大杠杆收益'},
        {'指标': '最大杠杆跌幅%', '数值': round(max_leverage_down, 2), '说明': '单日最大杠杆亏损'},
        {'指标': '做多信号品种', '数值': bullish_count, '说明': '增仓上涨或减仓下跌'},
        {'指标': '做空信号品种', '数值': bearish_count, '说明': '增仓下跌或减仓上涨'},
        {'指标': '中性品种', '数值': neutral_count, '说明': '无明显方向'},
    ]

    # 市场情绪判断
    if bullish_count > bearish_count * 1.5:
        market_sentiment = '市场整体偏多'
    elif bearish_count > bullish_count * 1.5:
        market_sentiment = '市场整体偏空'
    else:
        market_sentiment = '市场情绪中性'

    summary_data.append({'指标': '期货市场情绪', '数值': market_sentiment,
                         '说明': f'多头{bullish_count}个 vs 空头{bearish_count}个'})

    # 货权联动统计
    if correlation_analysis:
        corr_df = pd.DataFrame(correlation_analysis)

        # 新增共振评分统计
        strong_resonance = len(corr_df[corr_df['共振评分'] >= 7]) if '共振评分' in corr_df.columns else 0
        medium_resonance = len(corr_df[(corr_df['共振评分'] >= 5) & (corr_df['共振评分'] < 7)]) if '共振评分' in corr_df.columns else 0
        warning_count = len(corr_df[corr_df['共振标签'] == '背离']) if '共振标签' in corr_df.columns else 0

        summary_data.append({'指标': '货权联动品种', '数值': len(correlation_analysis),
                             '说明': '同时有期货和期权数据的品种'})
        summary_data.append({'指标': '强共振', '数值': strong_resonance,
                             '说明': '共振评分>=7，重点跟踪'})
        summary_data.append({'指标': '共振', '数值': medium_resonance,
                             '说明': '共振评分5-6，值得关注'})
        summary_data.append({'指标': '背离警示', '数值': warning_count,
                             '说明': '期货期权明显背离，风险提示'})

        # 趋势状态分布
        if '期货状态' in corr_df.columns:
            trend_strengthen = len(corr_df[corr_df['期货状态'] == '多头强化'])
            trend_weaken = len(corr_df[corr_df['期货状态'] == '多头衰减'])
            short_strengthen = len(corr_df[corr_df['期货状态'] == '空头强化'])
            short_weaken = len(corr_df[corr_df['期货状态'] == '空头衰减'])
            summary_data.append({'指标': '多头强化品种', '数值': trend_strengthen,
                                 '说明': '价涨+持仓涨，多头主动建仓'})
            summary_data.append({'指标': '多头衰减品种', '数值': trend_weaken,
                                 '说明': '价涨+持仓跌，空头止损'})
            summary_data.append({'指标': '空头强化品种', '数值': short_strengthen,
                                 '说明': '价跌+持仓涨，空头主动建仓'})
            summary_data.append({'指标': '空头衰减品种', '数值': short_weaken,
                                 '说明': '价跌+持仓跌，多头止损'})

    # 资金Top5
    if '沉淀资金(亿)' in futures_df.columns:
        top5_capital = futures_df.nlargest(5, '沉淀资金(亿)')['合约'].tolist()
        summary_data.append({'指标': '资金TOP5', '数值': ', '.join(top5_capital),
                             '说明': '沉淀资金最大的5个品种'})

    # 涨幅Top5
    if '杠杆涨跌%' in futures_df.columns:
        top5_up = futures_df.nlargest(5, '杠杆涨跌%')['合约'].tolist()
        summary_data.append({'指标': '涨幅TOP5', '数值': ', '.join(top5_up),
                             '说明': '杠杆涨幅最大的5个品种'})

    # 跌幅Top5
    if '杠杆涨跌%' in futures_df.columns:
        top5_down = futures_df.nsmallest(5, '杠杆涨跌%')['合约'].tolist()
        summary_data.append({'指标': '跌幅TOP5', '数值': ', '.join(top5_down),
                             '说明': '杠杆跌幅最大的5个品种'})

    return pd.DataFrame(summary_data)


def generate_product_analysis(
    futures_df_analysis: pd.DataFrame,
    corr_df: Optional[pd.DataFrame] = None,
    futures_df_raw: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    按期货品种（product_id）维度生成汇总分析。

    【分析内容】:
    1. 所有品种资金排名（按沉淀资金、成交资金降序）
    2. 品种合约数量统计
    3. 品种平均杠杆涨跌
    4. 品种多空情绪
    5. 品种货权联动情况（如有期权）

    Args:
        futures_df_analysis: 期货分析结果DataFrame
        corr_df: 联动分析结果DataFrame（可选）
        futures_df_raw: 原始期货数据DataFrame（可选，用于提取product_id）

    Returns:
        品种分析DataFrame
    """
    product_data = []

    # 确保有product_id列
    if 'product_id' not in futures_df_analysis.columns and futures_df_raw is not None:
        if 'product_id' in futures_df_raw.columns:
            # 建立合约到 product_id 的映射
            product_map = {}
            for _, row in futures_df_raw.iterrows():
                symbol = row.get('instrument_id') or row.get('symbol', '')
                product_id = row.get('product_id', '')
                if symbol and product_id:
                    product_map[symbol] = product_id
            futures_df_analysis['product_id'] = futures_df_analysis['合约'].map(product_map)

    if 'product_id' not in futures_df_analysis.columns:
        return pd.DataFrame()

    grouped = futures_df_analysis.groupby('product_id')

    for product_id, group in grouped:
        if pd.isna(product_id) or product_id == '':
            continue

        # 品种汇总统计
        product_summary = {
            '品种代码': product_id,
            '合约数量': len(group),
            '沉淀资金(亿)': round(group['沉淀资金(亿)'].sum(), 4) if '沉淀资金(亿)' in group.columns else 0,
            '成交资金(亿)': round(group['成交资金(亿)'].sum(), 4) if '成交资金(亿)' in group.columns else 0,
            '平均杠杆涨跌%': round(group['杠杆涨跌%'].mean(), 2) if '杠杆涨跌%' in group.columns else 0,
            '最大杠杆涨跌%': round(group['杠杆涨跌%'].max(), 2) if '杠杆涨跌%' in group.columns else 0,
            '最小杠杆涨跌%': round(group['杠杆涨跌%'].min(), 2) if '杠杆涨跌%' in group.columns else 0,
            '总持仓量': int(group['持仓量'].sum()) if '持仓量' in group.columns else 0,
            '总成交量': int(group['成交量'].sum()) if '成交量' in group.columns else 0,
            '看多合约数': len(group[group['流向信号'] > 0]) if '流向信号' in group.columns else 0,
            '看空合约数': len(group[group['流向信号'] < 0]) if '流向信号' in group.columns else 0,
            '中性合约数': len(group[group['流向信号'] == 0]) if '流向信号' in group.columns else 0,
        }

        # 多空情绪判断
        if product_summary['合约数量'] > 0:
            bullish_ratio = product_summary['看多合约数'] / product_summary['合约数量']
            if bullish_ratio >= 0.6:
                product_summary['品种情绪'] = '偏多'
            elif bullish_ratio <= 0.4:
                product_summary['品种情绪'] = '偏空'
            else:
                product_summary['品种情绪'] = '中性'
        else:
            product_summary['品种情绪'] = '中性'

        # 检查是否有期权联动数据
        if corr_df is not None and '标的合约' in corr_df.columns:
            product_corr = corr_df[corr_df['标的合约'].str.contains(product_id, na=False, case=False)]
            if not product_corr.empty:
                product_summary['有期权联动'] = '是'
                product_summary['期权PCR均值'] = round(product_corr['期权PCR'].mean(), 4) if '期权PCR' in product_corr.columns else 0
                product_summary['期权痛点均值'] = round(product_corr['最大痛点'].mean(), 2) if '最大痛点' in product_corr.columns else 0
                product_summary['共振评分均值'] = round(product_corr['共振评分'].mean(), 2) if '共振评分' in product_corr.columns else 0
            else:
                product_summary['有期权联动'] = '否'

        product_data.append(product_summary)

    # 创建品种汇总表
    if product_data:
        product_df = pd.DataFrame(product_data)
        product_df = product_df.sort_values(
            by=['沉淀资金(亿)', '成交资金(亿)'],
            ascending=False
        ).reset_index(drop=True)
        product_df.insert(0, '排名', range(1, len(product_df) + 1))
        return product_df

    return pd.DataFrame()


def extract_category_name(categories_field) -> str:
    """
    从 categories 字段提取板块名称。

    Args:
        categories_field: 可能是字符串、列表或None

    Returns:
        板块名称，如 '农副'、'软商'、'能化' 等
    """
    import ast

    if pd.isna(categories_field):
        return '未分类'

    try:
        # 如果是字符串，尝试解析为JSON
        if isinstance(categories_field, str):
            categories_field = ast.literal_eval(categories_field)

        # 如果是列表，取第一个元素
        if isinstance(categories_field, list) and len(categories_field) > 0:
            cat = categories_field[0]
            if isinstance(cat, dict) and 'name' in cat:
                return cat['name']

        # 如果是字典
        if isinstance(categories_field, dict) and 'name' in categories_field:
            return categories_field['name']

    except Exception:
        pass

    return '未分类'


def generate_sector_analysis(
    futures_df_analysis: pd.DataFrame,
    corr_df: Optional[pd.DataFrame] = None,
    futures_df_raw: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    按期货板块维度生成汇总分析。

    【板块分类】:
    - 从 categories 字段自动提取板块分类
    - 如：农副、软商、能化、黑色、有色、贵金属等

    【分析内容】:
    1. 板块资金汇总及占比
    2. 板块品种数量统计
    3. 板块平均涨跌
    4. 板块多空情绪
    5. 板块内品种排行

    Args:
        futures_df_analysis: 期货分析结果DataFrame
        corr_df: 联动分析结果DataFrame（可选）
        futures_df_raw: 原始期货数据DataFrame（可选，用于提取categories）

    Returns:
        板块分析DataFrame
    """
    sector_data = []

    # 从原始期货数据中提取 categories
    if futures_df_raw is None or 'categories' not in futures_df_raw.columns:
        return pd.DataFrame()

    # 建立合约到板块的映射
    sector_map = {}

    for _, row in futures_df_raw.iterrows():
        symbol = row.get('instrument_id') or row.get('symbol', '')
        categories = row.get('categories')

        if symbol:
            sector_name = extract_category_name(categories)
            sector_map[symbol] = sector_name

    # 添加板块列
    futures_df_analysis['板块'] = futures_df_analysis['合约'].map(sector_map)

    # 按板块分组统计
    grouped = futures_df_analysis.groupby('板块')

    total_capital = futures_df_analysis['沉淀资金(亿)'].sum() if '沉淀资金(亿)' in futures_df_analysis.columns else 0

    for sector_name, group in grouped:
        if pd.isna(sector_name) or sector_name == '未分类':
            continue

        sector_capital = group['沉淀资金(亿)'].sum() if '沉淀资金(亿)' in group.columns else 0

        # 板块汇总统计
        sector_summary = {
            '板块名称': sector_name,
            '品种数量': group['品种代码'].nunique() if '品种代码' in group.columns else 0,
            '合约数量': len(group),
            '沉淀资金(亿)': round(sector_capital, 4),
            '成交资金(亿)': round(group['成交资金(亿)'].sum(), 4) if '成交资金(亿)' in group.columns else 0,
            '资金占比%': round(sector_capital / total_capital * 100, 2) if total_capital > 0 else 0,
            '平均杠杆涨跌%': round(group['杠杆涨跌%'].mean(), 2) if '杠杆涨跌%' in group.columns else 0,
            '最大杠杆涨跌%': round(group['杠杆涨跌%'].max(), 2) if '杠杆涨跌%' in group.columns else 0,
            '最小杠杆涨跌%': round(group['杠杆涨跌%'].min(), 2) if '杠杆涨跌%' in group.columns else 0,
            '总持仓量': int(group['持仓量'].sum()) if '持仓量' in group.columns else 0,
            '总成交量': int(group['成交量'].sum()) if '成交量' in group.columns else 0,
            '看多合约数': len(group[group['流向信号'] > 0]) if '流向信号' in group.columns else 0,
            '看空合约数': len(group[group['流向信号'] < 0]) if '流向信号' in group.columns else 0,
            '中性合约数': len(group[group['流向信号'] == 0]) if '流向信号' in group.columns else 0,
        }

        # 板块情绪判断
        if sector_summary['合约数量'] > 0:
            bullish_ratio = sector_summary['看多合约数'] / sector_summary['合约数量']
            if bullish_ratio >= 0.6:
                sector_summary['板块情绪'] = '偏多'
            elif bullish_ratio <= 0.4:
                sector_summary['板块情绪'] = '偏空'
            else:
                sector_summary['板块情绪'] = '中性'
        else:
            sector_summary['板块情绪'] = '中性'

        # 板块内品种排行（按沉淀资金）
        if '品种代码' in group.columns and '沉淀资金(亿)' in group.columns:
            product_ranking = group.groupby('品种代码').agg({
                '沉淀资金(亿)': 'sum',
                '成交资金(亿)': 'sum',
                '杠杆涨跌%': 'mean',
                '持仓量': 'sum',
                '成交量': 'sum',
                '流向信号': lambda x: (x > 0).sum() - (x < 0).sum()
            }).reset_index()

            product_ranking.columns = ['品种代码', '沉淀资金(亿)', '成交资金(亿)',
                                        '平均杠杆涨跌%', '总持仓量', '总成交量', '多空信号']
            product_ranking = product_ranking.sort_values('沉淀资金(亿)', ascending=False)

            # TOP3品种
            top3_products = product_ranking.head(3)['品种代码'].tolist()
            sector_summary['品种TOP3'] = ' | '.join(top3_products)

            # 所有品种
            all_products = product_ranking['品种代码'].tolist()
            sector_summary['品种'] = ' / '.join(all_products)

        sector_data.append(sector_summary)

    # 创建板块汇总表
    if sector_data:
        sector_df = pd.DataFrame(sector_data)
        sector_df = sector_df.sort_values('沉淀资金(亿)', ascending=False).reset_index(drop=True)
        sector_df.insert(0, '排名', range(1, len(sector_df) + 1))
        return sector_df

    return pd.DataFrame()