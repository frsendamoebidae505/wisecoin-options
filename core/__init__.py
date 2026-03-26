"""
WiseCoin 业务层。

提供数据模型、分析器、计算器等核心功能。
"""

from core.models import (
    CallOrPut,
    Signal,
    OptionQuote,
    FutureQuote,
    Position,
    AnalyzedOption,
    StrategySignal,
    ArbitrageOpportunity,
)
from core.analyzer import OptionAnalyzer
from core.iv_calculator import IVCalculator
from core.futures_analyzer import (
    FuturesAnalyzer,
    TrendDirection,
    FlowSignal,
    ResonanceLevel,
    FuturesAnalysisResult,
    LinkageAnalysisResult,
    generate_market_summary,
    generate_product_analysis,
    generate_sector_analysis,
    extract_category_name,
)

__all__ = [
    # Enums
    'CallOrPut',
    'Signal',
    'TrendDirection',
    'FlowSignal',
    'ResonanceLevel',
    # Models
    'OptionQuote',
    'FutureQuote',
    'Position',
    'AnalyzedOption',
    'StrategySignal',
    'ArbitrageOpportunity',
    'FuturesAnalysisResult',
    'LinkageAnalysisResult',
    # Analyzers
    'OptionAnalyzer',
    'IVCalculator',
    'FuturesAnalyzer',
    # Helper functions
    'generate_market_summary',
    'generate_product_analysis',
    'generate_sector_analysis',
    'extract_category_name',
]