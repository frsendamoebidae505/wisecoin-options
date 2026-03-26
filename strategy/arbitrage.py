# strategy/arbitrage.py
"""
套利机会识别模块。

识别期权套利机会：
1. 平价套利 (Put-Call Parity)
2. 垂直套利 (Vertical Spread)
3. 日历套利 (Calendar Spread)
4. 蝶式套利 (Butterfly Spread)
5. 盒式套利 (Box Spread)
6. 深度实值套利 (Deep ITM)
7. 时间价值低估 (Time Value Undervalued)
8. 转换/逆转套利 (Conversion/Reversal)

基于真实盘口数据进行检测。
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import os
import logging
from pathlib import Path

from core.models import OptionQuote, CallOrPut, ArbitrageOpportunity

logger = logging.getLogger(__name__)

# ============ 全局参数 ============
RISK_FREE_RATE = 0.02  # 无风险利率 2%
TRANSACTION_COST_RATE = 0.0003  # 交易成本 0.03%
MIN_PROFIT_THRESHOLD = 0.5  # 最小利润阈值 (%)
PARITY_THRESHOLD = 0.5  # 平价套利偏离阈值 (%)
INTRINSIC_TOLERANCE = 0.99  # 内在价值容差 (99%)
THEORETICAL_TOLERANCE = 0.95  # 理论价格容差 (95%)
IV_HV_BUFFER_THRESHOLD = 0.8  # IV低于min(HV)的缓冲阈值

# 流动性和实用性筛选
MIN_OPEN_INTEREST = 100  # 最小持仓量
MIN_VOLUME = 50  # 最小成交量
MAX_BID_ASK_SPREAD_PCT = 15  # 最大买卖价差百分比
MIN_DAYS_TO_EXPIRY = 3  # 最小剩余天数
MAX_DAYS_TO_EXPIRY = 100  # 最大剩余天数
MAX_UNDERVALUE_PCT = 100  # 最大低估比例

# 涨跌停判断容差
LIMIT_PRICE_TOLERANCE = 0.001  # 0.1%


@dataclass
class ArbitrageConfig:
    """套利检测配置。"""
    risk_free_rate: float = 0.02
    transaction_cost_rate: float = 0.0003
    min_profit_threshold: float = 0.5
    parity_threshold: float = 0.5
    intrinsic_tolerance: float = 0.99
    theoretical_tolerance: float = 0.95
    iv_hv_buffer_threshold: float = 0.8
    min_open_interest: int = 100
    min_volume: int = 50
    max_bid_ask_spread_pct: float = 15.0
    min_days_to_expiry: int = 3
    max_days_to_expiry: int = 100
    limit_price_tolerance: float = 0.001


@dataclass
class ArbitrageResult:
    """套利检测结果。"""
    opportunity_type: str
    underlying: str
    strike: float
    days_to_expiry: int
    expected_profit: float
    annualized_return: float
    exec_score: int
    is_executable: bool
    trade_instruction: str
    strategy_description: str
    risk_warning: str
    risk_level: str
    details: Dict[str, Any] = field(default_factory=dict)


class ArbitrageDetector:
    """
    期权套利机会综合检测器。

    检测8种低风险套利策略机会。

    Example:
        >>> detector = ArbitrageDetector()
        >>> detector.load_data(options_df, futures_df)
        >>> opportunities = detector.run_all_detections()
    """

    def __init__(self, config: Optional[ArbitrageConfig] = None):
        """
        初始化检测器。

        Args:
            config: 套利检测配置
        """
        self.config = config or ArbitrageConfig()

        # 数据存储
        self.options_df: Optional[pd.DataFrame] = None
        self.futures_df: Optional[pd.DataFrame] = None
        self.merged_options: Optional[pd.DataFrame] = None

        # 套利机会列表（8种策略）
        self.parity_opportunities: List[ArbitrageResult] = []
        self.vertical_opportunities: List[ArbitrageResult] = []
        self.calendar_opportunities: List[ArbitrageResult] = []
        self.butterfly_opportunities: List[ArbitrageResult] = []
        self.box_opportunities: List[ArbitrageResult] = []
        self.deep_itm_opportunities: List[ArbitrageResult] = []
        self.time_value_opportunities: List[ArbitrageResult] = []
        self.conversion_opportunities: List[ArbitrageResult] = []

    def load_data(
        self,
        options_df: pd.DataFrame,
        futures_df: Optional[pd.DataFrame] = None,
    ) -> bool:
        """
        加载数据。

        Args:
            options_df: 期权数据（需包含盘口价格、Greeks等）
            futures_df: 期货数据（可选，用于获取标的价格）

        Returns:
            是否加载成功
        """
        self.options_df = options_df.copy()
        self.futures_df = futures_df.copy() if futures_df is not None else None

        # 预处理数据
        self._preprocess_options()

        return True

    def _preprocess_options(self):
        """预处理期权数据。"""
        if self.options_df is None:
            return

        df = self.options_df.copy()

        # 标准化期权类型
        if '期权类型' in df.columns:
            df['期权类型'] = df['期权类型'].apply(self._normalize_option_type)

        # 计算实际买入/卖出价
        if 'ask_price1' in df.columns and 'bid_price1' in df.columns:
            df['实际买入价'] = df['ask_price1'].fillna(df.get('期权价', 0))
            df['实际卖出价'] = df['bid_price1'].fillna(df.get('期权价', 0))
        else:
            df['实际买入价'] = df.get('期权价', 0)
            df['实际卖出价'] = df.get('期权价', 0)

        # 计算买卖价差百分比
        price_col = df.get('期权价', df.get('last_price', 1))
        df['买卖价差%'] = (
            (df['实际买入价'] - df['实际卖出价']) /
            price_col.replace(0, np.nan) * 100
        ).fillna(100)

        # 计算内在价值（如果不存在）
        if '内在价值' not in df.columns:
            underlying_price = df.get('标的现价', 0)
            strike = df.get('行权价', 0)
            is_call = df['期权类型'].str.upper().str.contains('CALL|C')
            df['内在价值'] = np.where(
                is_call,
                np.maximum(0, underlying_price - strike),
                np.maximum(0, strike - underlying_price)
            )

        # 检查有效盘口
        df['有效盘口'] = (
            (df['实际买入价'] > 0) &
            (df['实际卖出价'] > 0) &
            (df['买卖价差%'] <= self.config.max_bid_ask_spread_pct)
        )

        self.merged_options = df
        logger.info(f"预处理完成: {len(df)} 条期权数据, 有效盘口: {df['有效盘口'].sum()} 条")

    def _normalize_option_type(self, opt_type) -> str:
        """标准化期权类型。"""
        if opt_type is None or pd.isna(opt_type):
            return 'UNKNOWN'
        opt_str = str(opt_type).strip().upper()
        if opt_str in ('CALL', 'C', '认购', '看涨'):
            return 'CALL'
        elif opt_str in ('PUT', 'P', '认沽', '看跌'):
            return 'PUT'
        return opt_str

    def _calculate_exec_score(self, row: pd.Series) -> int:
        """计算可执行性评分 (0-100)。"""
        exec_score = 100
        bid_ask_spread = row.get('买卖价差%', 10)
        exec_score -= min(30, bid_ask_spread * 3)
        exec_score -= max(0, 30 - row.get('open_interest', 0) / 10)
        exec_score -= max(0, 20 - row.get('volume', 0) / 5)
        return int(max(0, min(100, exec_score)))

    def _get_futures_price(
        self,
        underlying: str,
        delivery_month: Optional[str] = None
    ) -> Optional[float]:
        """获取标的期货价格。"""
        if self.futures_df is None:
            return None

        symbol = str(underlying).strip()

        # 尝试完全匹配
        matches = self.futures_df[self.futures_df['instrument_id'] == symbol]

        # 如果未找到，尝试后缀匹配
        if len(matches) == 0:
            short_symbol = symbol.split('.')[-1]
            matches = self.futures_df[
                self.futures_df['instrument_id'].str.endswith('.' + short_symbol, na=False)
            ]

        if len(matches) > 0:
            row = matches.iloc[0]
            bid = row.get('bid_price1', 0)
            ask = row.get('ask_price1', 0)
            if bid and ask and bid > 0 and ask > 0:
                return (bid + ask) / 2
            return row.get('last_price') or row.get('settlement')

        return None

    # ========== 1. 平价套利检测 ==========
    def detect_parity_arbitrage(self) -> List[ArbitrageResult]:
        """
        检测期权平价套利机会。

        平价关系: C - P = (F - K) * e^(-rT)
        当实际价差偏离理论价差时存在套利机会。
        """
        logger.info("检测平价套利机会...")
        self.parity_opportunities = []

        if self.merged_options is None:
            return []

        valid_options = self.merged_options[self.merged_options['有效盘口']].copy()
        calls = valid_options[valid_options['期权类型'] == 'CALL'].copy()
        puts = valid_options[valid_options['期权类型'] == 'PUT'].copy()

        for _, call_row in calls.iterrows():
            underlying = call_row.get('标的合约', call_row.get('underlying_symbol', ''))
            strike = call_row['行权价']
            days_to_expiry = call_row.get('剩余天数', call_row.get('expire_rest_days', 30))
            delivery_month = call_row.get('交割年月')

            # 找到匹配的看跌期权
            matching_puts = puts[
                (puts.get('标的合约', puts.get('underlying_symbol', '')) == underlying) &
                (puts['行权价'] == strike) &
                (puts.get('剩余天数', puts.get('expire_rest_days', 30)) == days_to_expiry)
            ]

            if len(matching_puts) == 0:
                continue

            put_row = matching_puts.iloc[0]

            # 获取期货价格
            futures_price = self._get_futures_price(underlying, delivery_month)
            if futures_price is None or futures_price <= 0:
                continue

            T = days_to_expiry / 365.0
            discount_factor = np.exp(-self.config.risk_free_rate * T)
            theoretical_spread = (futures_price - strike) * discount_factor

            call_buy = call_row['实际买入价']
            call_sell = call_row['实际卖出价']
            put_buy = put_row['实际买入价']
            put_sell = put_row['实际卖出价']

            multiplier = call_row.get('volume_multiple', call_row.get('合约乘数', 1))

            # 正向套利：卖出认购(Bid) + 买入认沽(Ask) + 做多期货
            actual_spread_forward = call_sell - put_buy
            deviation_forward = (actual_spread_forward - theoretical_spread) / futures_price * 100

            if deviation_forward > self.config.parity_threshold:
                profit = (actual_spread_forward - theoretical_spread) * multiplier
                capital = call_row.get('卖方保证金', 0) + put_row.get('买方期权费', 0)
                if capital <= 0:
                    capital = futures_price * multiplier * 0.15
                ret_pct = (profit / capital * 100) if capital > 0 else 0
                ann_ret = (ret_pct * 365 / days_to_expiry) if days_to_expiry > 0 else 0
                exec_score = int((self._calculate_exec_score(call_row) + self._calculate_exec_score(put_row)) / 2)

                result = ArbitrageResult(
                    opportunity_type='正向平价套利',
                    underlying=underlying,
                    strike=strike,
                    days_to_expiry=int(days_to_expiry),
                    expected_profit=round(profit, 2),
                    annualized_return=round(ann_ret, 2),
                    exec_score=exec_score,
                    is_executable=True,
                    trade_instruction=f"卖出{call_row.get('合约代码', '')}@{call_sell:.2f} + 买入{put_row.get('合约代码', '')}@{put_buy:.2f} + 做多期货@{futures_price:.2f}",
                    strategy_description='卖出认购+买入认沽+做多期货，锁定正向平价偏离',
                    risk_warning='欧式期权需持有到期',
                    risk_level='低' if deviation_forward > 2 and exec_score >= 60 else '中',
                    details={
                        'call_code': call_row.get('合约代码', ''),
                        'put_code': put_row.get('合约代码', ''),
                        'futures_price': round(futures_price, 2),
                        'theoretical_spread': round(theoretical_spread, 2),
                        'actual_spread': round(actual_spread_forward, 2),
                        'deviation_pct': round(deviation_forward, 2),
                        'capital': round(capital, 2),
                    }
                )
                self.parity_opportunities.append(result)

            # 反向套利：买入认购(Ask) + 卖出认沽(Bid) + 做空期货
            actual_spread_reverse = call_buy - put_sell
            deviation_reverse = (theoretical_spread - actual_spread_reverse) / futures_price * 100

            if deviation_reverse > self.config.parity_threshold:
                profit = (theoretical_spread - actual_spread_reverse) * multiplier
                capital = call_row.get('买方期权费', 0) + put_row.get('卖方保证金', 0)
                if capital <= 0:
                    capital = futures_price * multiplier * 0.15
                ret_pct = (profit / capital * 100) if capital > 0 else 0
                ann_ret = (ret_pct * 365 / days_to_expiry) if days_to_expiry > 0 else 0
                exec_score = int((self._calculate_exec_score(call_row) + self._calculate_exec_score(put_row)) / 2)

                result = ArbitrageResult(
                    opportunity_type='反向平价套利',
                    underlying=underlying,
                    strike=strike,
                    days_to_expiry=int(days_to_expiry),
                    expected_profit=round(profit, 2),
                    annualized_return=round(ann_ret, 2),
                    exec_score=exec_score,
                    is_executable=True,
                    trade_instruction=f"买入{call_row.get('合约代码', '')}@{call_buy:.2f} + 卖出{put_row.get('合约代码', '')}@{put_sell:.2f} + 做空期货@{futures_price:.2f}",
                    strategy_description='买入认购+卖出认沽+做空期货，锁定反向平价偏离',
                    risk_warning='欧式期权需持有到期',
                    risk_level='低' if deviation_reverse > 2 and exec_score >= 60 else '中',
                    details={
                        'call_code': call_row.get('合约代码', ''),
                        'put_code': put_row.get('合约代码', ''),
                        'futures_price': round(futures_price, 2),
                        'theoretical_spread': round(theoretical_spread, 2),
                        'actual_spread': round(actual_spread_reverse, 2),
                        'deviation_pct': round(deviation_reverse, 2),
                        'capital': round(capital, 2),
                    }
                )
                self.parity_opportunities.append(result)

        self.parity_opportunities.sort(key=lambda x: (-x.exec_score, -x.annualized_return))
        logger.info(f"发现 {len(self.parity_opportunities)} 个平价套利机会")
        return self.parity_opportunities

    # ========== 2. 垂直套利检测 ==========
    def detect_vertical_arbitrage(self) -> List[ArbitrageResult]:
        """
        检测垂直套利机会（价格单调性违反）。

        看涨期权：低行权价价格应 >= 高行权价价格
        看跌期权：高行权价价格应 >= 低行权价价格
        违反此单调性则存在套利机会。
        """
        logger.info("检测垂直套利机会...")
        self.vertical_opportunities = []

        if self.merged_options is None:
            return []

        valid_options = self.merged_options[self.merged_options['有效盘口']].copy()

        for (underlying, days), group in valid_options.groupby(['标的合约', '剩余天数']):
            # 看涨期权
            calls = group[group['期权类型'] == 'CALL'].sort_values('行权价')
            for i in range(len(calls) - 1):
                low_k = calls.iloc[i]
                high_k = calls.iloc[i + 1]
                k1, k2 = low_k['行权价'], high_k['行权价']
                c1_buy, c2_sell = low_k['实际买入价'], high_k['实际卖出价']

                if c1_buy < c2_sell:  # 价格倒挂
                    arbitrage = c2_sell - c1_buy
                    multiplier = low_k.get('volume_multiple', low_k.get('合约乘数', 1))
                    profit = arbitrage * multiplier
                    capital = low_k.get('买方期权费', 0) + high_k.get('卖方保证金', 0)
                    if capital <= 0:
                        capital = c1_buy * multiplier
                    ret_pct = (profit / capital * 100) if capital > 0 else 0
                    ann_ret = (ret_pct * 365 / days) if days > 0 else 0
                    exec_score = int((self._calculate_exec_score(low_k) + self._calculate_exec_score(high_k)) / 2)

                    result = ArbitrageResult(
                        opportunity_type='看涨期权垂直套利',
                        underlying=underlying,
                        strike=k1,
                        days_to_expiry=int(days),
                        expected_profit=round(profit, 2),
                        annualized_return=round(ann_ret, 2),
                        exec_score=exec_score,
                        is_executable=True,
                        trade_instruction=f"买入{low_k.get('合约代码', '')}@{c1_buy:.2f} + 卖出{high_k.get('合约代码', '')}@{c2_sell:.2f}",
                        strategy_description='买入低K + 卖出高K，锁定价差倒挂收益',
                        risk_warning='正常交易',
                        risk_level='低',
                        details={
                            'low_k_code': low_k.get('合约代码', ''),
                            'high_k_code': high_k.get('合约代码', ''),
                            'low_strike': k1,
                            'high_strike': k2,
                            'price_inversion': round(arbitrage, 2),
                            'capital': round(capital, 2),
                        }
                    )
                    self.vertical_opportunities.append(result)

            # 看跌期权
            puts = group[group['期权类型'] == 'PUT'].sort_values('行权价')
            for i in range(len(puts) - 1):
                low_k = puts.iloc[i]
                high_k = puts.iloc[i + 1]
                k1, k2 = low_k['行权价'], high_k['行权价']
                p1_sell, p2_buy = low_k['实际卖出价'], high_k['实际买入价']

                if p2_buy < p1_sell:  # 价格倒挂
                    arbitrage = p1_sell - p2_buy
                    multiplier = low_k.get('volume_multiple', low_k.get('合约乘数', 1))
                    profit = arbitrage * multiplier
                    capital = high_k.get('买方期权费', 0) + low_k.get('卖方保证金', 0)
                    if capital <= 0:
                        capital = p2_buy * multiplier
                    ret_pct = (profit / capital * 100) if capital > 0 else 0
                    ann_ret = (ret_pct * 365 / days) if days > 0 else 0
                    exec_score = int((self._calculate_exec_score(low_k) + self._calculate_exec_score(high_k)) / 2)

                    result = ArbitrageResult(
                        opportunity_type='看跌期权垂直套利',
                        underlying=underlying,
                        strike=k2,
                        days_to_expiry=int(days),
                        expected_profit=round(profit, 2),
                        annualized_return=round(ann_ret, 2),
                        exec_score=exec_score,
                        is_executable=True,
                        trade_instruction=f"买入{high_k.get('合约代码', '')}@{p2_buy:.2f} + 卖出{low_k.get('合约代码', '')}@{p1_sell:.2f}",
                        strategy_description='买入高K + 卖出低K，锁定价差倒挂收益',
                        risk_warning='正常交易',
                        risk_level='低',
                        details={
                            'low_k_code': low_k.get('合约代码', ''),
                            'high_k_code': high_k.get('合约代码', ''),
                            'low_strike': k1,
                            'high_strike': k2,
                            'price_inversion': round(arbitrage, 2),
                            'capital': round(capital, 2),
                        }
                    )
                    self.vertical_opportunities.append(result)

        self.vertical_opportunities.sort(key=lambda x: (-x.exec_score, -x.annualized_return))
        logger.info(f"发现 {len(self.vertical_opportunities)} 个垂直套利机会")
        return self.vertical_opportunities

    # ========== 3. 日历套利检测 ==========
    def detect_calendar_arbitrage(self) -> List[ArbitrageResult]:
        """
        检测日历套利机会（时间价值曲线倒挂）。

        同行权价的期权，远月价格应 >= 近月价格。
        当近月卖价 > 远月买价时存在套利机会。
        """
        logger.info("检测日历套利机会...")
        self.calendar_opportunities = []

        if self.merged_options is None:
            return []

        valid_options = self.merged_options[self.merged_options['有效盘口']].copy()

        for (underlying, strike, opt_type), group in valid_options.groupby(
            ['标的合约', '行权价', '期权类型']
        ):
            if len(group) < 2:
                continue

            group = group.sort_values('剩余天数')

            for i in range(len(group) - 1):
                near = group.iloc[i]
                far = group.iloc[i + 1]

                near_sell = near['实际卖出价']  # 卖出近月(Bid)
                far_buy = far['实际买入价']      # 买入远月(Ask)

                if near_sell > far_buy:  # 价格倒挂
                    arbitrage = near_sell - far_buy
                    multiplier = near.get('volume_multiple', near.get('合约乘数', 1))
                    profit = arbitrage * multiplier
                    capital = near.get('卖方保证金', 0) + far.get('买方期权费', 0)
                    if capital <= 0:
                        capital = far_buy * multiplier
                    ret_pct = (profit / capital * 100) if capital > 0 else 0
                    ann_ret = (ret_pct * 365 / near['剩余天数']) if near['剩余天数'] > 0 else 0
                    exec_score = int((self._calculate_exec_score(near) + self._calculate_exec_score(far)) / 2)

                    result = ArbitrageResult(
                        opportunity_type=f'{opt_type}日历套利',
                        underlying=underlying,
                        strike=strike,
                        days_to_expiry=int(near['剩余天数']),
                        expected_profit=round(profit, 2),
                        annualized_return=round(ann_ret, 2),
                        exec_score=exec_score,
                        is_executable=True,
                        trade_instruction=f"卖出{near.get('合约代码', '')}@{near_sell:.2f} + 买入{far.get('合约代码', '')}@{far_buy:.2f}",
                        strategy_description='卖出近月+买入远月，锁定时间价值倒挂',
                        risk_warning='需注意远月流动性',
                        risk_level='低',
                        details={
                            'near_code': near.get('合约代码', ''),
                            'far_code': far.get('合约代码', ''),
                            'near_days': int(near['剩余天数']),
                            'far_days': int(far['剩余天数']),
                            'price_inversion': round(arbitrage, 2),
                            'capital': round(capital, 2),
                        }
                    )
                    self.calendar_opportunities.append(result)

        self.calendar_opportunities.sort(key=lambda x: (-x.exec_score, -x.annualized_return))
        logger.info(f"发现 {len(self.calendar_opportunities)} 个日历套利机会")
        return self.calendar_opportunities

    # ========== 4. 蝶式套利检测 ==========
    def detect_butterfly_arbitrage(self) -> List[ArbitrageResult]:
        """
        检测蝶式套利机会（凸性违反）。

        蝶式组合: 买K1 + 卖2*K2 + 买K3
        当净成本为负（收到净权利金）时存在套利机会。
        """
        logger.info("检测蝶式套利机会...")
        self.butterfly_opportunities = []

        if self.merged_options is None:
            return []

        valid_options = self.merged_options[self.merged_options['有效盘口']].copy()

        for (underlying, days, opt_type), group in valid_options.groupby(
            ['标的合约', '剩余天数', '期权类型']
        ):
            if len(group) < 3:
                continue

            group = group.sort_values('行权价').reset_index(drop=True)

            for i in range(len(group) - 2):
                for j in range(i + 1, len(group) - 1):
                    for k in range(j + 1, len(group)):
                        low = group.iloc[i]
                        mid = group.iloc[j]
                        high = group.iloc[k]

                        k1, k2, k3 = low['行权价'], mid['行权价'], high['行权价']

                        # 检查是否近似等间距
                        interval1 = k2 - k1
                        interval2 = k3 - k2
                        if max(interval1, interval2) > 0 and abs(interval1 - interval2) / max(interval1, interval2) > 0.1:
                            continue

                        c1_buy = low['实际买入价']
                        c2_sell = mid['实际卖出价']
                        c3_buy = high['实际买入价']

                        net_cost = c1_buy + c3_buy - 2 * c2_sell

                        if net_cost < 0:  # 收到净权利金
                            arbitrage = -net_cost
                            multiplier = low.get('volume_multiple', low.get('合约乘数', 1))
                            profit = arbitrage * multiplier
                            capital = low.get('买方期权费', 0) + high.get('买方期权费', 0) + 2 * mid.get('卖方保证金', 0)
                            if capital <= 0:
                                capital = (c1_buy + c3_buy) * multiplier
                            ret_pct = (profit / capital * 100) if capital > 0 else 0
                            ann_ret = (ret_pct * 365 / days) if days > 0 else 0
                            exec_score = int((self._calculate_exec_score(low) + self._calculate_exec_score(mid) + self._calculate_exec_score(high)) / 3)

                            result = ArbitrageResult(
                                opportunity_type=f'{opt_type}蝶式套利',
                                underlying=underlying,
                                strike=k2,
                                days_to_expiry=int(days),
                                expected_profit=round(profit, 2),
                                annualized_return=round(ann_ret, 2),
                                exec_score=exec_score,
                                is_executable=True,
                                trade_instruction=f"买1手{low.get('合约代码', '')}@{c1_buy:.2f} + 卖2手{mid.get('合约代码', '')}@{c2_sell:.2f} + 买1手{high.get('合约代码', '')}@{c3_buy:.2f}",
                                strategy_description='买入K1/K3 + 卖出2倍K2，利用凸性违反锁定净收入',
                                risk_warning='正常交易',
                                risk_level='低',
                                details={
                                    'k1_code': low.get('合约代码', ''),
                                    'k2_code': mid.get('合约代码', ''),
                                    'k3_code': high.get('合约代码', ''),
                                    'k1_strike': k1,
                                    'k2_strike': k2,
                                    'k3_strike': k3,
                                    'net_income': round(arbitrage, 2),
                                    'capital': round(capital, 2),
                                }
                            )
                            self.butterfly_opportunities.append(result)

        self.butterfly_opportunities.sort(key=lambda x: (-x.exec_score, -x.annualized_return))
        logger.info(f"发现 {len(self.butterfly_opportunities)} 个蝶式套利机会")
        return self.butterfly_opportunities

    # ========== 5. 盒式套利检测 ==========
    def detect_box_arbitrage(self) -> List[ArbitrageResult]:
        """
        检测盒式套利机会 (Box Spread)。

        盒式组合 = 牛市价差 + 熊市价差
        理论价值 = (K2 - K1) * e^(-rT)
        当实际成本低于理论价值时存在套利机会。
        """
        logger.info("检测盒式套利机会...")
        self.box_opportunities = []

        if self.merged_options is None:
            return []

        valid_options = self.merged_options[self.merged_options['有效盘口']].copy()

        for (underlying, days), group in valid_options.groupby(['标的合约', '剩余天数']):
            calls = group[group['期权类型'] == 'CALL']
            puts = group[group['期权类型'] == 'PUT']

            strikes = set(calls['行权价'].unique()) & set(puts['行权价'].unique())
            strikes = sorted(list(strikes))

            if len(strikes) < 2:
                continue

            for i in range(len(strikes) - 1):
                k1, k2 = strikes[i], strikes[i + 1]

                c1 = calls[calls['行权价'] == k1]
                c2 = calls[calls['行权价'] == k2]
                p1 = puts[puts['行权价'] == k1]
                p2 = puts[puts['行权价'] == k2]

                if len(c1) == 0 or len(c2) == 0 or len(p1) == 0 or len(p2) == 0:
                    continue

                c1, c2, p1, p2 = c1.iloc[0], c2.iloc[0], p1.iloc[0], p2.iloc[0]

                T = days / 365.0
                theoretical_value = (k2 - k1) * np.exp(-self.config.risk_free_rate * T)

                box_cost = (c1['实际买入价'] - c2['实际卖出价'] + p2['实际买入价'] - p1['实际卖出价'])

                if box_cost > 0 and box_cost < theoretical_value * 0.98:
                    arbitrage = theoretical_value - box_cost
                    multiplier = c1.get('volume_multiple', c1.get('合约乘数', 1))
                    profit = arbitrage * multiplier
                    capital = box_cost * multiplier
                    ret_pct = (profit / capital * 100) if capital > 0 else 0
                    ann_ret = (ret_pct * 365 / days) if days > 0 else 0
                    exec_score = int((self._calculate_exec_score(c1) + self._calculate_exec_score(c2) + self._calculate_exec_score(p1) + self._calculate_exec_score(p2)) / 4)

                    result = ArbitrageResult(
                        opportunity_type='盒式套利',
                        underlying=underlying,
                        strike=k1,
                        days_to_expiry=int(days),
                        expected_profit=round(profit, 2),
                        annualized_return=round(ann_ret, 2),
                        exec_score=exec_score,
                        is_executable=True,
                        trade_instruction=f"买入{c1.get('合约代码', '')} + 卖出{c2.get('合约代码', '')} + 买入{p2.get('合约代码', '')} + 卖出{p1.get('合约代码', '')}",
                        strategy_description='牛市价差+熊市价差组合，到期锁定(K2-K1)无风险收益',
                        risk_warning='正常交易',
                        risk_level='低',
                        details={
                            'c1_code': c1.get('合约代码', ''),
                            'c2_code': c2.get('合约代码', ''),
                            'p1_code': p1.get('合约代码', ''),
                            'p2_code': p2.get('合约代码', ''),
                            'k1_strike': k1,
                            'k2_strike': k2,
                            'theoretical_value': round(theoretical_value, 2),
                            'actual_cost': round(box_cost, 2),
                            'capital': round(capital, 2),
                        }
                    )
                    self.box_opportunities.append(result)

        self.box_opportunities.sort(key=lambda x: (-x.exec_score, -x.annualized_return))
        logger.info(f"发现 {len(self.box_opportunities)} 个盒式套利机会")
        return self.box_opportunities

    # ========== 6. 深度实值套利检测 ==========
    def detect_deep_itm_arbitrage(self) -> List[ArbitrageResult]:
        """
        检测深度实值套利机会。

        当期权市场价格 < 内在价值 * 容差时，
        存在买入期权并立即行权的套利机会。
        """
        logger.info("检测深度实值套利机会...")
        self.deep_itm_opportunities = []

        if self.merged_options is None:
            return []

        df = self.merged_options.copy()
        price_col = '实际买入价'

        basic_filter = (
            (df['剩余天数'] >= self.config.min_days_to_expiry) &
            (df['剩余天数'] <= self.config.max_days_to_expiry) &
            (df['内在价值'] > 0) &
            (df[price_col] < df['内在价值'] * self.config.intrinsic_tolerance) &
            (df[price_col] > 0) &
            (df.get('open_interest', df.get('持仓量', 0)) >= self.config.min_open_interest) &
            (df.get('volume', df.get('成交量', 0)) >= self.config.min_volume) &
            (df['买卖价差%'] <= self.config.max_bid_ask_spread_pct)
        )
        df = df[basic_filter]

        for _, row in df.iterrows():
            intrinsic = row['内在价值']
            market_price = row[price_col]
            arb_spread = intrinsic - market_price
            arb_pct = (arb_spread / market_price * 100) if market_price > 0 else 0

            multiplier = row.get('volume_multiple', row.get('合约乘数', 1))
            net_profit = arb_spread * multiplier
            capital = row.get('买方期权费', market_price * multiplier)
            ret_pct = (net_profit / capital * 100) if capital > 0 else 0
            ann_ret = (ret_pct * 365 / row['剩余天数']) if row['剩余天数'] > 0 else 0

            opt_type = row['期权类型']
            exec_score = int(self._calculate_exec_score(row))

            result = ArbitrageResult(
                opportunity_type='深度实值套利',
                underlying=row.get('标的合约', ''),
                strike=row['行权价'],
                days_to_expiry=int(row['剩余天数']),
                expected_profit=round(net_profit, 2),
                annualized_return=round(ann_ret, 2),
                exec_score=exec_score,
                is_executable=True,
                trade_instruction=f"买入{row.get('合约代码', '')}@{market_price:.2f} + 行权获取内在价值",
                strategy_description='买入期权+对冲标的，锁定内在价值价差',
                risk_warning='需要持有到期或行权',
                risk_level='低' if arb_pct > 2 and exec_score >= 60 else '中',
                details={
                    'option_code': row.get('合约代码', ''),
                    'option_type': opt_type,
                    'underlying_price': round(row.get('标的现价', 0), 2),
                    'market_price': round(market_price, 2),
                    'intrinsic_value': round(intrinsic, 2),
                    'arb_spread': round(arb_spread, 2),
                    'arb_pct': round(arb_pct, 2),
                    'capital': round(capital, 2),
                }
            )
            self.deep_itm_opportunities.append(result)

        self.deep_itm_opportunities.sort(key=lambda x: (-x.exec_score, -x.details.get('arb_pct', 0)))
        logger.info(f"发现 {len(self.deep_itm_opportunities)} 个深度实值套利机会")
        return self.deep_itm_opportunities

    # ========== 7. 时间价值低估套利检测 ==========
    def detect_time_value_arbitrage(self) -> List[ArbitrageResult]:
        """
        检测时间价值低估套利机会。

        当市场价格 < BS理论价格，且IV < HV时，
        可能存在波动率低估的套利机会。
        """
        logger.info("检测时间价值低估套利机会...")
        self.time_value_opportunities = []

        if self.merged_options is None or '理论价格' not in self.merged_options.columns:
            return []

        df = self.merged_options.copy()
        price_col = '实际买入价'

        basic_filter = (
            (df['剩余天数'] >= self.config.min_days_to_expiry) &
            (df['剩余天数'] <= self.config.max_days_to_expiry) &
            (df[price_col] >= df['内在价值'] * self.config.intrinsic_tolerance) &
            (df[price_col] < df['理论价格'] * self.config.theoretical_tolerance) &
            (df['理论价格'] > 0) &
            (df[price_col] > 0) &
            (df.get('open_interest', df.get('持仓量', 0)) >= self.config.min_open_interest) &
            (df.get('volume', df.get('成交量', 0)) >= self.config.min_volume) &
            (df['买卖价差%'] <= self.config.max_bid_ask_spread_pct)
        )
        df = df[basic_filter]

        for _, row in df.iterrows():
            market_price = row[price_col]
            theoretical_price = row['理论价格']
            undervalue = theoretical_price - market_price
            undervalue_pct = (undervalue / market_price * 100) if market_price > 0 else 0

            if undervalue_pct > MAX_UNDERVALUE_PCT:
                continue

            multiplier = row.get('volume_multiple', row.get('合约乘数', 1))
            capital = row.get('买方期权费', market_price * multiplier)
            expected_profit = undervalue * multiplier
            ret_pct = (expected_profit / capital * 100) if capital > 0 else 0
            ann_ret = (ret_pct * 365 / row['剩余天数']) if row['剩余天数'] > 0 else 0

            # IV vs HV 分析
            hv20 = row.get('HV20', row.get('近期波动率', 0))
            hv60 = row.get('HV60', hv20)
            iv = row.get('隐含波动率', 0)
            ref_hv = min(hv20, hv60) if hv20 and hv60 else (hv20 or hv60 or 0)
            iv_hv_ratio = (iv / ref_hv) if ref_hv > 0 else 1.0

            # 必须留出适当空间
            if iv_hv_ratio >= self.config.iv_hv_buffer_threshold:
                continue

            opt_type = row['期权类型']
            exec_score = int(self._calculate_exec_score(row))

            result = ArbitrageResult(
                opportunity_type='时间价值低估',
                underlying=row.get('标的合约', ''),
                strike=row['行权价'],
                days_to_expiry=int(row['剩余天数']),
                expected_profit=round(expected_profit, 2),
                annualized_return=round(ann_ret, 2),
                exec_score=exec_score,
                is_executable=True,
                trade_instruction=f"买入{row.get('合约代码', '')}@{market_price:.2f}",
                strategy_description=f"IV低于HV，市场价低于理论价{undervalue_pct:.1f}%",
                risk_warning='波动率可能继续下跌',
                risk_level='低' if undervalue_pct > 10 and exec_score >= 60 else '中',
                details={
                    'option_code': row.get('合约代码', ''),
                    'option_type': opt_type,
                    'market_price': round(market_price, 2),
                    'theoretical_price': round(theoretical_price, 2),
                    'undervalue': round(undervalue, 2),
                    'undervalue_pct': round(undervalue_pct, 2),
                    'iv': round(iv, 2),
                    'hv20': round(hv20, 2),
                    'hv60': round(hv60, 2),
                    'iv_hv_ratio': round(iv_hv_ratio, 2),
                    'capital': round(capital, 2),
                }
            )
            self.time_value_opportunities.append(result)

        self.time_value_opportunities.sort(key=lambda x: (-x.exec_score, -x.details.get('undervalue_pct', 0)))
        logger.info(f"发现 {len(self.time_value_opportunities)} 个时间价值低估机会")
        return self.time_value_opportunities

    # ========== 8. 转换/逆转套利检测 ==========
    def detect_conversion_arbitrage(self) -> List[ArbitrageResult]:
        """
        检测转换/逆转套利机会。

        转换套利: 买入标的 + 买入看跌 + 卖出看涨
        逆转套利: 卖出标的 + 卖出看跌 + 买入看涨
        """
        logger.info("检测转换/逆转套利机会...")
        self.conversion_opportunities = []

        if self.merged_options is None:
            return []

        valid_options = self.merged_options[self.merged_options['有效盘口']].copy()
        calls = valid_options[valid_options['期权类型'] == 'CALL']
        puts = valid_options[valid_options['期权类型'] == 'PUT']

        for _, call_row in calls.iterrows():
            underlying = call_row.get('标的合约', '')
            strike = call_row['行权价']
            days = call_row['剩余天数']
            delivery_month = call_row.get('交割年月')

            matching_puts = puts[
                (puts.get('标的合约', '') == underlying) &
                (puts['行权价'] == strike) &
                (puts['剩余天数'] == days)
            ]

            if len(matching_puts) == 0:
                continue

            put_row = matching_puts.iloc[0]
            futures_price = self._get_futures_price(underlying, delivery_month)
            if futures_price is None or futures_price <= 0:
                continue

            T = days / 365.0
            discount = np.exp(-self.config.risk_free_rate * T)
            multiplier = call_row.get('volume_multiple', call_row.get('合约乘数', 1))

            # 转换套利
            conversion_cost = futures_price + put_row['实际买入价'] - call_row['实际卖出价']
            conversion_value = strike * discount
            conversion_profit = (conversion_value - conversion_cost) * multiplier

            if conversion_profit > 0:
                futures_margin = futures_price * multiplier * 0.15
                put_premium = put_row.get('买方期权费', put_row['实际买入价'] * multiplier)
                call_seller_margin = call_row.get('卖方保证金', call_row['实际卖出价'] * multiplier * 0.15)
                capital = futures_margin + put_premium + call_seller_margin
                ret_pct = (conversion_profit / capital * 100) if capital > 0 else 0
                ann_ret = (ret_pct * 365 / days) if days > 0 else 0
                exec_score = int((self._calculate_exec_score(call_row) + self._calculate_exec_score(put_row)) / 2)

                result = ArbitrageResult(
                    opportunity_type='转换套利',
                    underlying=underlying,
                    strike=strike,
                    days_to_expiry=int(days),
                    expected_profit=round(conversion_profit, 2),
                    annualized_return=round(ann_ret, 2),
                    exec_score=exec_score,
                    is_executable=True,
                    trade_instruction=f"买入期货@{futures_price:.2f} + 买入{put_row.get('合约代码', '')} + 卖出{call_row.get('合约代码', '')}",
                    strategy_description='买入标的+买入看跌+卖出看涨，锁定K价值',
                    risk_warning='欧式期权需持有到期',
                    risk_level='低',
                    details={
                        'call_code': call_row.get('合约代码', ''),
                        'put_code': put_row.get('合约代码', ''),
                        'futures_price': round(futures_price, 2),
                        'conversion_cost': round(conversion_cost, 2),
                        'conversion_value': round(conversion_value, 2),
                        'capital': round(capital, 2),
                    }
                )
                self.conversion_opportunities.append(result)

            # 逆转套利
            reversal_income = futures_price + put_row['实际卖出价'] - call_row['实际买入价']
            reversal_cost = strike * discount
            reversal_profit = (reversal_income - reversal_cost) * multiplier

            if reversal_profit > 0:
                futures_margin = futures_price * multiplier * 0.15
                call_premium = call_row.get('买方期权费', call_row['实际买入价'] * multiplier)
                put_seller_margin = put_row.get('卖方保证金', put_row['实际卖出价'] * multiplier * 0.15)
                capital = futures_margin + call_premium + put_seller_margin
                ret_pct = (reversal_profit / capital * 100) if capital > 0 else 0
                ann_ret = (ret_pct * 365 / days) if days > 0 else 0
                exec_score = int((self._calculate_exec_score(call_row) + self._calculate_exec_score(put_row)) / 2)

                result = ArbitrageResult(
                    opportunity_type='逆转套利',
                    underlying=underlying,
                    strike=strike,
                    days_to_expiry=int(days),
                    expected_profit=round(reversal_profit, 2),
                    annualized_return=round(ann_ret, 2),
                    exec_score=exec_score,
                    is_executable=True,
                    trade_instruction=f"卖出期货@{futures_price:.2f} + 卖出{put_row.get('合约代码', '')} + 买入{call_row.get('合约代码', '')}",
                    strategy_description='卖出标的+卖出看跌+买入看涨，锁定超额收益',
                    risk_warning='欧式期权需持有到期',
                    risk_level='低',
                    details={
                        'call_code': call_row.get('合约代码', ''),
                        'put_code': put_row.get('合约代码', ''),
                        'futures_price': round(futures_price, 2),
                        'reversal_income': round(reversal_income, 2),
                        'reversal_cost': round(reversal_cost, 2),
                        'capital': round(capital, 2),
                    }
                )
                self.conversion_opportunities.append(result)

        self.conversion_opportunities.sort(key=lambda x: (-x.exec_score, -x.annualized_return))
        logger.info(f"发现 {len(self.conversion_opportunities)} 个转换/逆转套利机会")
        return self.conversion_opportunities

    def run_all_detections(self) -> Dict[str, List[ArbitrageResult]]:
        """
        运行所有套利检测。

        Returns:
            各类套利机会的字典
        """
        logger.info("=" * 70)
        logger.info("开始全面套利机会扫描 (8种策略)...")
        logger.info("=" * 70)

        self.detect_parity_arbitrage()
        self.detect_vertical_arbitrage()
        self.detect_calendar_arbitrage()
        self.detect_butterfly_arbitrage()
        self.detect_box_arbitrage()
        self.detect_deep_itm_arbitrage()
        self.detect_time_value_arbitrage()
        self.detect_conversion_arbitrage()

        total = (
            len(self.parity_opportunities) +
            len(self.vertical_opportunities) +
            len(self.calendar_opportunities) +
            len(self.butterfly_opportunities) +
            len(self.box_opportunities) +
            len(self.deep_itm_opportunities) +
            len(self.time_value_opportunities) +
            len(self.conversion_opportunities)
        )

        logger.info("=" * 70)
        logger.info(f"套利扫描完成，共发现 {total} 个机会")
        logger.info(f"  - 平价套利: {len(self.parity_opportunities)} 个")
        logger.info(f"  - 垂直套利: {len(self.vertical_opportunities)} 个")
        logger.info(f"  - 日历套利: {len(self.calendar_opportunities)} 个")
        logger.info(f"  - 蝶式套利: {len(self.butterfly_opportunities)} 个")
        logger.info(f"  - 盒式套利: {len(self.box_opportunities)} 个")
        logger.info(f"  - 深度实值: {len(self.deep_itm_opportunities)} 个")
        logger.info(f"  - 时间价值低估: {len(self.time_value_opportunities)} 个")
        logger.info(f"  - 转换/逆转套利: {len(self.conversion_opportunities)} 个")
        logger.info("=" * 70)

        return {
            'parity': self.parity_opportunities,
            'vertical': self.vertical_opportunities,
            'calendar': self.calendar_opportunities,
            'butterfly': self.butterfly_opportunities,
            'box': self.box_opportunities,
            'deep_itm': self.deep_itm_opportunities,
            'time_value': self.time_value_opportunities,
            'conversion': self.conversion_opportunities,
        }

    def get_all_opportunities(self) -> List[ArbitrageResult]:
        """获取所有套利机会列表（按评分排序）。"""
        all_opps = (
            self.parity_opportunities +
            self.vertical_opportunities +
            self.calendar_opportunities +
            self.butterfly_opportunities +
            self.box_opportunities +
            self.deep_itm_opportunities +
            self.time_value_opportunities +
            self.conversion_opportunities
        )
        return sorted(all_opps, key=lambda x: (-x.exec_score, -x.annualized_return))

    def detect(
        self,
        options: List[OptionQuote],
        future_price: float,
        run_all: bool = True
    ) -> List[ArbitrageResult]:
        """
        便捷检测方法：加载期权数据并执行套利检测。

        Args:
            options: 期权列表
            future_price: 标的期货价格
            run_all: 是否运行所有检测（默认 True）

        Returns:
            套利机会列表
        """
        # 将期权列表转换为 DataFrame
        options_data = []
        for opt in options:
            cp_value = opt.call_or_put.value if hasattr(opt.call_or_put, 'value') else str(opt.call_or_put)
            # 计算剩余天数
            days_to_expiry = 30
            if hasattr(opt, 'expire_date') and opt.expire_date:
                from datetime import date
                if isinstance(opt.expire_date, date):
                    days_to_expiry = (opt.expire_date - date.today()).days
            options_data.append({
                'symbol': opt.symbol,
                'underlying': opt.underlying,
                'exchange_id': opt.exchange_id,
                'strike_price': opt.strike_price,
                '行权价': opt.strike_price,  # Chinese column name
                '期权类型': 'CALL' if cp_value.upper() in ('CALL', 'C') else 'PUT',
                'call_or_put': cp_value,
                'last_price': opt.last_price,
                '期权价': opt.last_price,  # Chinese column name
                'bid_price1': opt.bid_price,
                'ask_price1': opt.ask_price,
                'volume': opt.volume,
                'open_interest': opt.open_interest,
                'expire_date': opt.expire_date,
                '剩余天数': days_to_expiry,  # Chinese column name
                'iv': opt.iv or 0.2,
                '标的合约': opt.underlying,  # Chinese column name
            })

        options_df = pd.DataFrame(options_data)

        # 创建期货 DataFrame（简单结构）
        underlying_symbol = options[0].underlying if options else ''
        futures_df = pd.DataFrame({
            'instrument_id': [underlying_symbol],
            'underlying': [underlying_symbol],
            'last_price': [future_price],
            'bid_price1': [future_price - 1],
            'ask_price1': [future_price + 1],
        })

        # 加载数据
        self.load_data(options_df, futures_df)
        self._future_price = future_price

        if run_all:
            # 运行所有检测
            self.run_all_detections()
        else:
            # 仅运行转换套利检测（用于测试）
            self.detect_conversion_arbitrage()

        return self.get_all_opportunities()

    def _calculate_risk_level(self, opportunity_type: str, legs: List[Dict]) -> str:
        """
        计算风险等级。

        Args:
            opportunity_type: 套利类型
            legs: 交易腿

        Returns:
            风险等级 (LOW, MEDIUM, HIGH)
        """
        # 简单风险评级逻辑
        if opportunity_type in ('CONVERSION', 'REVERSAL'):
            return 'LOW'
        elif opportunity_type in ('PARITY', 'BOX'):
            return 'LOW'
        elif opportunity_type in ('VERTICAL', 'CALENDAR'):
            return 'MEDIUM'
        else:
            return 'HIGH'