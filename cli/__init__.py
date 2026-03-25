"""
WiseCoin CLI 层。

提供一键分析、定时调度、实时监控等功能。
"""

__all__ = [
    # One-click analysis
    'OneClickAnalyzer',
    'AnalysisResult',
    # Scheduler
    'TaskScheduler',
    'TaskStatus',
    'ScheduledTime',
    'TaskResult',
    # Live monitor
    'LiveMonitor',
    'MonitorStatus',
    'MonitorEvent',
]


def __getattr__(name):
    """延迟导入以避免模块执行时的警告。"""
    if name in ('OneClickAnalyzer', 'AnalysisResult'):
        from cli.oneclick import OneClickAnalyzer, AnalysisResult
        return locals().get(name)
    elif name in ('TaskScheduler', 'TaskStatus', 'ScheduledTime', 'TaskResult'):
        from cli.scheduler import TaskScheduler, TaskStatus, ScheduledTime, TaskResult
        return locals().get(name)
    elif name in ('LiveMonitor', 'MonitorStatus', 'MonitorEvent'):
        from cli.live import LiveMonitor, MonitorStatus, MonitorEvent
        return locals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")