"""
WiseCoin CLI 层。

提供一键分析、定时调度、实时监控等功能。
"""

__all__ = [
    # One-click analysis
    'OptionsOneClickExecutor',
    # Scheduler
    'SCHEDULED_TIMES',
    'is_trading_day',
    'execute_script',
]


def __getattr__(name):
    """延迟导入以避免模块执行时的警告。"""
    if name == 'OptionsOneClickExecutor':
        from cli.oneclick import OptionsOneClickExecutor
        return OptionsOneClickExecutor
    elif name in ('SCHEDULED_TIMES', 'is_trading_day', 'execute_script'):
        from cli.scheduler import SCHEDULED_TIMES, is_trading_day, execute_script
        return locals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")