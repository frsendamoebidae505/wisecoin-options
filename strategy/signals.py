# strategy/signals.py
"""
交易信号生成模块。

基于分析结果生成具体的交易信号。
支持品种情绪信号、策略信号、持仓信号等多种信号类型。
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import date
import pandas as pd
import numpy as np

from core.models import (
    AnalyzedOption,
    Signal,
    StrategySignal,
    OptionQuote,
    CallOrPut,
)


@dataclass
class SymbolSignal:
    """品种信号。"""
    symbol: str
    direction: str  # LONG / SHORT / NONE
    sentiment: str  # 偏多 / 偏空 / 中性
    capital: float  # 沉淀资金(亿)
    confidence: float  # 置信度
    reasons: List[str] = field(default_factory=list)


@dataclass
class StrategyLeg:
    """策略腿。"""
    action: str  # 买入 / 卖出
    symbol: str
    option_type: str  # CALL / PUT / FUTURE
    strike: Optional[float] = None
    quantity: int = 1
    price: Optional[float] = None
    premium: Optional[float] = None


@dataclass
class DetailedStrategySignal:
    """详细策略信号。"""
    strategy_type: str
    strategy_name: str
    underlying: str
    expiry: str
    legs: List[StrategyLeg]
    score: float
    expected_profit: Optional[float] = None
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven: Optional[float] = None
    risk_level: str = "MEDIUM"
    reasons: List[str] = field(default_factory=list)


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
                    price=analyzed.option.ask_price,
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
                    price=analyzed.option.bid_price,
                    score=analyzed.score,
                    strategy_type="评分卖出",
                    reasons=[f"评分过低: {analyzed.score:.1f}"],
                )
                signals.append(signal)

        return signals

    def generate_symbol_signals(
        self,
        market_overview_df: pd.DataFrame,
        min_capital: float = 0.5,
    ) -> List[SymbolSignal]:
        """
        根据市场概览生成品种信号。

        Args:
            market_overview_df: 市场概览数据
            min_capital: 最小沉淀资金阈值(亿)

        Returns:
            品种信号列表
        """
        signals = []

        if market_overview_df is None or market_overview_df.empty:
            return signals

        # 筛选沉淀资金 > 阈值的品种
        df = market_overview_df.copy()
        capital_col = None
        for c in ['沉淀资金(亿)', '期货沉淀(亿)', '资金合计(万)']:
            if c in df.columns:
                capital_col = c
                break

        if capital_col is None:
            return signals

        df['capital_numeric'] = pd.to_numeric(df[capital_col], errors='coerce')
        df = df[df['capital_numeric'] > min_capital]

        # 情绪映射
        sentiment_map = {
            '偏多': 'LONG',
            '偏空': 'SHORT',
            '中性': 'NONE',
            '看多': 'LONG',
            '看空': 'SHORT',
        }

        symbol_col = None
        for c in ['品种代码', '标的合约', 'symbol']:
            if c in df.columns:
                symbol_col = c
                break

        sentiment_col = None
        for c in ['品种情绪', '期货方向', '市场情绪']:
            if c in df.columns:
                sentiment_col = c
                break

        if symbol_col is None:
            return signals

        for _, row in df.iterrows():
            symbol = row.get(symbol_col, '')
            sentiment = row.get(sentiment_col, '中性') if sentiment_col else '中性'
            direction = sentiment_map.get(sentiment, 'NONE')
            capital = float(row.get('capital_numeric', 0) or 0)

            # 计算置信度
            confidence = self._calculate_sentiment_confidence(row)

            reasons = []
            if direction == 'LONG':
                reasons.append(f"市场情绪偏多 ({sentiment})")
            elif direction == 'SHORT':
                reasons.append(f"市场情绪偏空 ({sentiment})")
            else:
                reasons.append(f"市场情绪中性 ({sentiment})")

            if capital > 5:
                reasons.append(f"资金规模较大 ({capital:.2f}亿)")

            signal = SymbolSignal(
                symbol=symbol,
                direction=direction,
                sentiment=sentiment,
                capital=capital,
                confidence=confidence,
                reasons=reasons,
            )
            signals.append(signal)

        return signals

    def generate_strategy_signals(
        self,
        options_df: pd.DataFrame,
        market_state: Dict[str, Any],
        strategy_recommendations: List[Dict[str, Any]],
    ) -> List[DetailedStrategySignal]:
        """
        根据策略推荐生成详细信号。

        Args:
            options_df: 期权数据
            market_state: 市场状态
            strategy_recommendations: 策略推荐列表

        Returns:
            详细策略信号列表
        """
        signals = []

        for rec in strategy_recommendations:
            strategy_type = rec.get('strategy_type', '')
            strategy_name = rec.get('strategy_name', '')

            # 根据策略类型构建腿
            legs = self._build_strategy_legs(
                strategy_name,
                options_df,
                market_state
            )

            if not legs:
                continue

            signal = DetailedStrategySignal(
                strategy_type=strategy_type,
                strategy_name=strategy_name,
                underlying=market_state.get('underlying', ''),
                expiry=str(market_state.get('expiry', '')),
                legs=legs,
                score=rec.get('score', 0),
                expected_profit=rec.get('expected_profit'),
                max_profit=rec.get('max_profit'),
                max_loss=rec.get('max_loss'),
                breakeven=rec.get('breakeven'),
                risk_level=rec.get('risk_level', 'MEDIUM'),
                reasons=rec.get('reasons', []),
            )
            signals.append(signal)

        return signals

    def generate_directional_signals(
        self,
        options_df: pd.DataFrame,
        market_state: Dict[str, Any],
        direction: str = "LONG",
    ) -> List[DetailedStrategySignal]:
        """
        生成方向性策略信号。

        Args:
            options_df: 期权数据
            market_state: 市场状态
            direction: 方向 (LONG / SHORT)

        Returns:
            方向性策略信号列表
        """
        signals = []

        if options_df is None or options_df.empty:
            return signals

        underlying_price = market_state.get('underlying_price', 0)
        if underlying_price <= 0:
            return signals

        # 筛选流动性好的期权
        liquid = options_df[
            (options_df.get('成交量', options_df.get('volume', 0)) >= 50) &
            (options_df.get('持仓量', options_df.get('open_interest', 0)) >= 100) &
            (options_df.get('剩余天数', 30) >= 7) &
            (options_df.get('剩余天数', 30) <= 90)
        ].copy()

        if liquid.empty:
            return signals

        if direction == "LONG":
            # 买入看涨
            opt_type_col = None
            for c in ['期权类型', 'option_type', 'call_or_put']:
                if c in liquid.columns:
                    opt_type_col = c
                    break

            if opt_type_col:
                calls = liquid[liquid[opt_type_col].astype(str).str.upper().str.contains('CALL|C|认购')].copy()
                if not calls.empty:
                    calls['strike_diff'] = abs(calls['行权价'] - underlying_price)
                    calls = calls[
                        (calls['行权价'] >= underlying_price * 0.98) &
                        (calls['行权价'] <= underlying_price * 1.05)
                    ].sort_values('strike_diff')

                    if not calls.empty:
                        best_call = calls.iloc[0]
                        signal = self._build_long_option_signal(
                            best_call, "LONG", market_state
                        )
                        if signal:
                            signals.append(signal)

        elif direction == "SHORT":
            # 买入看跌
            opt_type_col = None
            for c in ['期权类型', 'option_type', 'call_or_put']:
                if c in liquid.columns:
                    opt_type_col = c
                    break

            if opt_type_col:
                puts = liquid[liquid[opt_type_col].astype(str).str.upper().str.contains('PUT|P|认沽')].copy()
                if not puts.empty:
                    puts['strike_diff'] = abs(puts['行权价'] - underlying_price)
                    puts = puts[
                        (puts['行权价'] >= underlying_price * 0.95) &
                        (puts['行权价'] <= underlying_price * 1.02)
                    ].sort_values('strike_diff')

                    if not puts.empty:
                        best_put = puts.iloc[0]
                        signal = self._build_long_option_signal(
                            best_put, "SHORT", market_state
                        )
                        if signal:
                            signals.append(signal)

        return signals

    def _calculate_volume(
        self,
        analyzed: AnalyzedOption,
        current_volume: int,
    ) -> int:
        """计算建议开仓数量。"""
        remaining = self.max_position_per_symbol - current_volume
        if remaining <= 0:
            return 0

        if analyzed.score >= 90:
            return min(remaining, 5)
        elif analyzed.score >= 80:
            return min(remaining, 3)
        elif analyzed.score >= 70:
            return min(remaining, 2)
        return 1

    def _calculate_sentiment_confidence(self, row: pd.Series) -> float:
        """计算情绪置信度。"""
        confidence = 0.5

        # 根据资金规模调整
        capital = float(row.get('capital_numeric', 0) or 0)
        if capital > 10:
            confidence += 0.2
        elif capital > 5:
            confidence += 0.1

        # 根据PCR调整
        pcr = float(row.get('期权PCR', 1.0) or 1.0)
        if pcr > 1.2:  # Put偏向
            confidence += 0.1 if '偏多' in str(row.get('品种情绪', '')) else 0
        elif pcr < 0.8:  # Call偏向
            confidence += 0.1 if '偏空' in str(row.get('品种情绪', '')) else 0

        return min(1.0, confidence)

    def _build_strategy_legs(
        self,
        strategy_name: str,
        options_df: pd.DataFrame,
        market_state: Dict[str, Any],
    ) -> List[StrategyLeg]:
        """构建策略腿。"""
        legs = []

        if options_df is None or options_df.empty:
            return legs

        underlying_price = market_state.get('underlying_price', 0)

        # 根据策略类型构建腿
        if strategy_name == "买入看涨期权":
            call = self._find_best_call(options_df, underlying_price)
            if call is not None:
                legs.append(StrategyLeg(
                    action="买入",
                    symbol=call.get('合约代码', ''),
                    option_type="CALL",
                    strike=call.get('行权价'),
                    quantity=1,
                    price=call.get('ask_price1', call.get('期权价')),
                ))

        elif strategy_name == "买入看跌期权":
            put = self._find_best_put(options_df, underlying_price)
            if put is not None:
                legs.append(StrategyLeg(
                    action="买入",
                    symbol=put.get('合约代码', ''),
                    option_type="PUT",
                    strike=put.get('行权价'),
                    quantity=1,
                    price=put.get('ask_price1', put.get('期权价')),
                ))

        elif strategy_name in ["铁鹰式价差", "Iron Condor"]:
            legs = self._build_iron_condor_legs(options_df, underlying_price)

        elif "日历" in strategy_name or "Calendar" in strategy_name:
            legs = self._build_calendar_legs(options_df, underlying_price)

        return legs

    def _find_best_call(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
    ) -> Optional[pd.Series]:
        """找到最佳看涨期权。"""
        opt_type_col = None
        for c in ['期权类型', 'option_type']:
            if c in options_df.columns:
                opt_type_col = c
                break

        if opt_type_col is None:
            return None

        calls = options_df[
            options_df[opt_type_col].astype(str).str.upper().str.contains('CALL|C|认购')
        ].copy()

        if calls.empty:
            return None

        calls['strike_diff'] = abs(calls['行权价'] - underlying_price)
        calls = calls[
            (calls['行权价'] >= underlying_price * 0.98) &
            (calls['行权价'] <= underlying_price * 1.05)
        ].sort_values('strike_diff')

        if calls.empty:
            return None

        return calls.iloc[0]

    def _find_best_put(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
    ) -> Optional[pd.Series]:
        """找到最佳看跌期权。"""
        opt_type_col = None
        for c in ['期权类型', 'option_type']:
            if c in options_df.columns:
                opt_type_col = c
                break

        if opt_type_col is None:
            return None

        puts = options_df[
            options_df[opt_type_col].astype(str).str.upper().str.contains('PUT|P|认沽')
        ].copy()

        if puts.empty:
            return None

        puts['strike_diff'] = abs(puts['行权价'] - underlying_price)
        puts = puts[
            (puts['行权价'] >= underlying_price * 0.95) &
            (puts['行权价'] <= underlying_price * 1.02)
        ].sort_values('strike_diff')

        if puts.empty:
            return None

        return puts.iloc[0]

    def _build_iron_condor_legs(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
    ) -> List[StrategyLeg]:
        """构建铁鹰式腿。"""
        legs = []

        opt_type_col = None
        for c in ['期权类型', 'option_type']:
            if c in options_df.columns:
                opt_type_col = c
                break

        if opt_type_col is None:
            return legs

        calls = options_df[
            options_df[opt_type_col].astype(str).str.upper().str.contains('CALL|C|认购')
        ].sort_values('行权价')

        puts = options_df[
            options_df[opt_type_col].astype(str).str.upper().str.contains('PUT|P|认沽')
        ].sort_values('行权价', ascending=False)

        if len(calls) < 2 or len(puts) < 2:
            return legs

        # 卖出价外看涨
        otm_calls = calls[calls['行权价'] > underlying_price * 1.02]
        if len(otm_calls) >= 2:
            sell_call = otm_calls.iloc[0]
            buy_call = otm_calls.iloc[1]
            legs.append(StrategyLeg(
                action="卖出",
                symbol=sell_call.get('合约代码', ''),
                option_type="CALL",
                strike=sell_call.get('行权价'),
                price=sell_call.get('bid_price1', sell_call.get('期权价')),
            ))
            legs.append(StrategyLeg(
                action="买入",
                symbol=buy_call.get('合约代码', ''),
                option_type="CALL",
                strike=buy_call.get('行权价'),
                price=buy_call.get('ask_price1', buy_call.get('期权价')),
            ))

        # 卖出价外看跌
        otm_puts = puts[puts['行权价'] < underlying_price * 0.98]
        if len(otm_puts) >= 2:
            sell_put = otm_puts.iloc[0]
            buy_put = otm_puts.iloc[1]
            legs.append(StrategyLeg(
                action="卖出",
                symbol=sell_put.get('合约代码', ''),
                option_type="PUT",
                strike=sell_put.get('行权价'),
                price=sell_put.get('bid_price1', sell_put.get('期权价')),
            ))
            legs.append(StrategyLeg(
                action="买入",
                symbol=buy_put.get('合约代码', ''),
                option_type="PUT",
                strike=buy_put.get('行权价'),
                price=buy_put.get('ask_price1', buy_put.get('期权价')),
            ))

        return legs

    def _build_calendar_legs(
        self,
        options_df: pd.DataFrame,
        underlying_price: float,
    ) -> List[StrategyLeg]:
        """构建日历价差腿。"""
        legs = []

        # 按到期日分组
        if '剩余天数' not in options_df.columns:
            return legs

        near = options_df[options_df['剩余天数'] <= 45]
        far = options_df[options_df['剩余天数'] > 45]

        if near.empty or far.empty:
            return legs

        # 找ATM期权
        near['strike_diff'] = abs(near['行权价'] - underlying_price)
        far['strike_diff'] = abs(far['行权价'] - underlying_price)

        near_atm = near.sort_values('strike_diff').iloc[0]
        far_atm = far.sort_values('strike_diff').iloc[0]

        legs.append(StrategyLeg(
            action="卖出",
            symbol=near_atm.get('合约代码', ''),
            option_type=near_atm.get('期权类型', 'CALL'),
            strike=near_atm.get('行权价'),
            price=near_atm.get('bid_price1', near_atm.get('期权价')),
        ))
        legs.append(StrategyLeg(
            action="买入",
            symbol=far_atm.get('合约代码', ''),
            option_type=far_atm.get('期权类型', 'CALL'),
            strike=far_atm.get('行权价'),
            price=far_atm.get('ask_price1', far_atm.get('期权价')),
        ))

        return legs

    def _build_long_option_signal(
        self,
        option_row: pd.Series,
        direction: str,
        market_state: Dict[str, Any],
    ) -> Optional[DetailedStrategySignal]:
        """构建买入期权信号。"""
        strategy_name = "买入看涨期权" if direction == "LONG" else "买入看跌期权"
        option_type = "CALL" if direction == "LONG" else "PUT"

        price = option_row.get('ask_price1', option_row.get('期权价', 0))
        strike = option_row.get('行权价', 0)
        multiplier = option_row.get('合约乘数', option_row.get('volume_multiple', 1))

        leg = StrategyLeg(
            action="买入",
            symbol=option_row.get('合约代码', ''),
            option_type=option_type,
            strike=strike,
            quantity=1,
            price=price,
            premium=-price * multiplier if price else None,
        )

        # 计算盈亏平衡
        if direction == "LONG":
            breakeven = strike + (price or 0)
            max_loss = (price or 0) * multiplier
        else:
            breakeven = strike - (price or 0)
            max_loss = (price or 0) * multiplier

        reasons = [
            f"方向: {direction}",
            f"行权价: {strike}",
            f"剩余天数: {option_row.get('剩余天数', 'N/A')}",
        ]

        iv = option_row.get('隐含波动率', option_row.get('iv'))
        if iv:
            reasons.append(f"IV: {iv:.2f}%")

        return DetailedStrategySignal(
            strategy_type="directional",
            strategy_name=strategy_name,
            underlying=market_state.get('underlying', ''),
            expiry=str(market_state.get('expiry', '')),
            legs=[leg],
            score=75.0,
            max_loss=max_loss,
            breakeven=breakeven,
            risk_level="MEDIUM",
            reasons=reasons,
        )


def generate_symbol_lsn_from_excel(
    input_file: str,
    output_file: str,
    sheet_name: str = "期货品种",
    min_capital: float = 0.5,
) -> int:
    """
    从Excel文件生成品种-方向映射。

    读取'wisecoin-市场概览.xlsx'，根据'沉淀资金(亿)'和'品种情绪'
    生成品种方向映射JSON文件。

    Args:
        input_file: 输入Excel文件路径
        output_file: 输出JSON文件路径
        sheet_name: 工作表名称
        min_capital: 最小沉淀资金阈值(亿)

    Returns:
        生成的品种数量
    """
    import json
    import os

    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return 0

    try:
        df = pd.read_excel(input_file, sheet_name=sheet_name)

        # 筛选沉淀资金 > 阈值
        df['沉淀资金(亿)'] = pd.to_numeric(df['沉淀资金(亿)'], errors='coerce')
        filtered_df = df[df['沉淀资金(亿)'] > min_capital].copy()

        if filtered_df.empty:
            print(f"No symbols found with '沉淀资金(亿)' > {min_capital}.")
            return 0

        # 情绪映射
        sentiment_map = {
            '偏多': 'LONG',
            '偏空': 'SHORT',
            '中性': 'NONE'
        }

        results = []
        for _, row in filtered_df.iterrows():
            symbol = row.get('品种代码', row.get('symbol', ''))
            sentiment = row.get('品种情绪', '中性')
            direction = sentiment_map.get(sentiment, 'NONE')

            results.append({
                '品种代码': symbol,
                '开仓方向': direction,
                '品种情绪': sentiment,
                '沉淀资金(亿)': row.get('沉淀资金(亿)', 0),
            })

        # 写入JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)

        print(f"Successfully generated {output_file} with {len(results)} symbols.")
        return len(results)

    except Exception as e:
        print(f"An error occurred: {e}")
        return 0