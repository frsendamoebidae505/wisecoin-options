"""
WiseCoin CLI 层。

提供一键分析、定时调度、实时监控等功能。
"""

from cli.oneclick import OneClickAnalyzer, AnalysisResult
from cli.scheduler import (
    TaskScheduler,
    TaskStatus,
    ScheduledTime,
    TaskResult,
)
from cli.live import (
    LiveMonitor,
    MonitorStatus,
    MonitorEvent,
)

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