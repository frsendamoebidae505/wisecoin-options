# cli/oneclick.py
"""
一键分析模块。

编排完整的数据获取 -> 分析 -> 评分流程。
"""
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

from core.models import OptionQuote, FutureQuote, AnalyzedOption, Signal
from core.analyzer import OptionAnalyzer
from core.iv_calculator import IVCalculator
from strategy.evaluator import StrategyEvaluator
from strategy.signals import SignalGenerator
from common.logger import StructuredLogger


@dataclass
class AnalysisResult:
    """分析结果"""
    timestamp: datetime
    total_options: int
    analyzed_options: List[AnalyzedOption]
    top_signals: List[dict]
    summary: dict

    @property
    def buy_count(self) -> int:
        return sum(1 for a in self.analyzed_options if a.signal == Signal.BUY)

    @property
    def sell_count(self) -> int:
        return sum(1 for a in self.analyzed_options if a.signal == Signal.SELL)


class OneClickAnalyzer:
    """
    一键分析器。

    编排完整分析流程：数据准备 -> 基础分析 -> IV计算 -> 评分 -> 信号生成

    Example:
        >>> analyzer = OneClickAnalyzer()
        >>> result = analyzer.run(options, futures_prices)
    """

    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger("oneclick")
        self.option_analyzer = OptionAnalyzer()
        self.iv_calculator = IVCalculator()
        self.evaluator = StrategyEvaluator()
        self.signal_generator = SignalGenerator()

    def run(
        self,
        options: List[OptionQuote],
        futures_prices: Dict[str, float],
        iv_reference: Optional[float] = None,
    ) -> AnalysisResult:
        """
        执行一键分析。

        Args:
            options: 期权行情列表
            futures_prices: 标的期货价格映射
            iv_reference: IV 参考值（可选）

        Returns:
            分析结果
        """
        self.logger.info("开始一键分析", total_options=len(options))

        timestamp = datetime.now()

        # 1. 基础分析
        analyzed = self.option_analyzer.analyze(options, futures_prices)
        self.logger.info("基础分析完成", analyzed_count=len(analyzed))

        # 2. IV 计算
        for item in analyzed:
            future_price = futures_prices.get(item.option.underlying, 0)
            if future_price > 0:
                try:
                    iv = self.iv_calculator.calculate_iv(item.option, future_price)
                    item.iv = iv
                except ValueError:
                    # Skip IV calculation if option price is invalid
                    pass

        # 3. 评分
        evaluated = self.evaluator.evaluate(analyzed, iv_reference)
        self.logger.info("评分完成", evaluated_count=len(evaluated))

        # 4. 生成信号
        signals = self.signal_generator.generate(evaluated)

        # 5. 构建结果
        top_signals = [
            {
                'symbol': s.symbol,
                'direction': s.direction,
                'volume': s.volume,
                'price': s.price,
                'score': s.score,
                'reasons': s.reasons[:3],  # 只保留前3个原因
            }
            for s in signals[:10]  # 只保留前10个信号
        ]

        summary = {
            'total_options': len(options),
            'analyzed_count': len(analyzed),
            'avg_score': sum(a.score for a in evaluated) / len(evaluated) if evaluated else 0,
            'max_score': max((a.score for a in evaluated), default=0),
            'signal_count': len(signals),
        }

        result = AnalysisResult(
            timestamp=timestamp,
            total_options=len(options),
            analyzed_options=evaluated,
            top_signals=top_signals,
            summary=summary,
        )

        self.logger.info(
            "一键分析完成",
            total=len(evaluated),
            buy=result.buy_count,
            sell=result.sell_count,
        )

        return result

    def run_quick(
        self,
        options: List[OptionQuote],
        futures_prices: Dict[str, float],
        top_n: int = 5,
    ) -> List[AnalyzedOption]:
        """
        快速分析，只返回前N个评分最高的期权。

        Args:
            options: 期权行情列表
            futures_prices: 标的期货价格映射
            top_n: 返回数量

        Returns:
            前N个分析结果
        """
        result = self.run(options, futures_prices)
        return result.analyzed_options[:top_n]


def main():
    """命令行入口。"""
    from datetime import date
    from core.models import CallOrPut

    print("=" * 60)
    print("WiseCoin 期权分析系统 - 一键分析")
    print("=" * 60)

    # 创建示例数据
    options = [
        OptionQuote(
            symbol="SHFE.au2406C480",
            underlying="SHFE.au2406",
            exchange_id="SHFE",
            strike_price=480.0,
            call_or_put=CallOrPut.CALL,
            last_price=15.0,
            bid_price=14.8,
            ask_price=15.2,
            volume=100,
            open_interest=500,
            expire_date=date(2024, 6, 15),
        ),
        OptionQuote(
            symbol="SHFE.au2406P480",
            underlying="SHFE.au2406",
            exchange_id="SHFE",
            strike_price=480.0,
            call_or_put=CallOrPut.PUT,
            last_price=10.0,
            bid_price=9.8,
            ask_price=10.2,
            volume=200,
            open_interest=800,
            expire_date=date(2024, 6, 15),
        ),
    ]

    futures_prices = {"SHFE.au2406": 485.0}

    # 运行分析
    analyzer = OneClickAnalyzer()
    result = analyzer.run(options, futures_prices)

    # 打印结果
    print(f"\n分析时间: {result.timestamp}")
    print(f"分析期权数: {result.total_options}")
    print(f"买入信号: {result.buy_count}")
    print(f"卖出信号: {result.sell_count}")
    print(f"\n评分摘要:")
    print(f"  平均分: {result.summary['avg_score']:.2f}")
    print(f"  最高分: {result.summary['max_score']:.2f}")

    if result.top_signals:
        print(f"\nTop 信号:")
        for i, sig in enumerate(result.top_signals, 1):
            print(f"  {i}. {sig['symbol']} - {sig['direction']} "
                  f"@{sig['price']:.2f} 评分:{sig['score']:.1f}")

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())