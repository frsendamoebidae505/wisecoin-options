"""
WiseCoin 策略层。

提供策略评估、套利检测、信号生成等功能。

模块:
- evaluator: 多因子策略评估器
- arbitrage: 8种套利策略检测
- signals: 交易信号生成器
"""

from strategy.evaluator import (
    StrategyEvaluator,
    ScoringFactors,
    MarketState,
    VolatilityFeatures,
    StrategyRecommendation,
)

from strategy.arbitrage import (
    ArbitrageDetector,
    ArbitrageConfig,
    ArbitrageResult,
)

from strategy.signals import (
    SignalGenerator,
    SymbolSignal,
    StrategyLeg,
    DetailedStrategySignal,
    generate_symbol_lsn_from_excel,
)

__all__ = [
    # Evaluator
    'StrategyEvaluator',
    'ScoringFactors',
    'MarketState',
    'VolatilityFeatures',
    'StrategyRecommendation',

    # Arbitrage
    'ArbitrageDetector',
    'ArbitrageConfig',
    'ArbitrageResult',

    # Signals
    'SignalGenerator',
    'SymbolSignal',
    'StrategyLeg',
    'DetailedStrategySignal',
    'generate_symbol_lsn_from_excel',
]