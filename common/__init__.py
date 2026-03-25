"""
WiseCoin 公共模块。

提供配置、日志、异常、Excel 读写、错误处理、指标监控等基础功能。
"""

from common.config import (
    Config,
    AccountConfig,
    TradingConfig,
    DataConfig,
    SchedulerConfig,
)
from common.exceptions import (
    WiseCoinError,
    DataFetchError,
    APIConnectionError,
    OrderExecutionError,
    RiskCheckError,
    ConfigurationError,
    ValidationError,
)
from common.logger import StructuredLogger
from common.excel_io import ExcelWriter, ExcelReader
from common.error_handler import ErrorHandler
from common.metrics import Metrics

__all__ = [
    # Config
    'Config',
    'AccountConfig',
    'TradingConfig',
    'DataConfig',
    'SchedulerConfig',
    # Exceptions
    'WiseCoinError',
    'DataFetchError',
    'APIConnectionError',
    'OrderExecutionError',
    'RiskCheckError',
    'ConfigurationError',
    'ValidationError',
    # Logger
    'StructuredLogger',
    # Excel
    'ExcelWriter',
    'ExcelReader',
    # Error Handler
    'ErrorHandler',
    # Metrics
    'Metrics',
]
