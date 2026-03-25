"""
定时任务调度模块。

管理定时执行分析任务的调度器。
"""
from typing import List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
import threading
import time as time_module

from common.logger import StructuredLogger


class TaskStatus(str, Enum):
    """任务状态"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


@dataclass
class ScheduledTime:
    """调度时间"""
    hour: int
    minute: int

    def to_time(self) -> time:
        return time(self.hour, self.minute)

    def is_now(self, current_time: datetime) -> bool:
        """检查是否到达调度时间"""
        return (
            current_time.hour == self.hour and
            current_time.minute == self.minute
        )

    def __str__(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


@dataclass
class TaskResult:
    """任务执行结果"""
    scheduled_time: ScheduledTime
    started_at: datetime
    finished_at: Optional[datetime]
    success: bool
    message: str = ""
    error: Optional[str] = None


class TaskScheduler:
    """
    任务调度器。

    在指定时间点执行分析任务。

    Example:
        >>> scheduler = TaskScheduler()
        >>> scheduler.add_time(9, 40)  # 09:40 执行
        >>> scheduler.start(task_func)
    """

    DEFAULT_TIMES = [
        (20, 40), (21, 40), (22, 40), (23, 40), (0, 40), (1, 40),
        (8, 40), (9, 40), (10, 40), (12, 40), (13, 40), (14, 40), (15, 16)
    ]

    def __init__(
        self,
        check_interval: int = 30,
        logger: Optional[StructuredLogger] = None,
    ):
        """
        初始化调度器。

        Args:
            check_interval: 检查间隔（秒）
            logger: 日志器
        """
        self.check_interval = check_interval
        self.logger = logger or StructuredLogger("scheduler")

        self._scheduled_times: List[ScheduledTime] = []
        self._status = TaskStatus.IDLE
        self._task_func: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_execution: Optional[datetime] = None
        self._results: List[TaskResult] = []

    def add_time(self, hour: int, minute: int):
        """添加调度时间"""
        st = ScheduledTime(hour, minute)
        if st not in self._scheduled_times:
            self._scheduled_times.append(st)
            self._scheduled_times.sort(key=lambda t: (t.hour, t.minute))

    def add_times(self, times: List[tuple]):
        """批量添加调度时间"""
        for h, m in times:
            self.add_time(h, m)

    def remove_time(self, hour: int, minute: int) -> bool:
        """移除调度时间"""
        st = ScheduledTime(hour, minute)
        if st in self._scheduled_times:
            self._scheduled_times.remove(st)
            return True
        return False

    def get_scheduled_times(self) -> List[ScheduledTime]:
        """获取所有调度时间"""
        return self._scheduled_times.copy()

    def get_next_execution(self) -> Optional[ScheduledTime]:
        """获取下一个执行时间"""
        if not self._scheduled_times:
            return None

        now = datetime.now()
        current_time = time(now.hour, now.minute)

        # 找下一个今天的执行时间
        for st in self._scheduled_times:
            if st.to_time() > current_time:
                return st

        # 如果今天没有了，返回明天的第一个
        return self._scheduled_times[0]

    def start(self, task_func: Callable):
        """
        启动调度器。

        Args:
            task_func: 要执行的任务函数
        """
        if self._status == TaskStatus.RUNNING:
            self.logger.warning("调度器已在运行")
            return

        self._task_func = task_func
        self._status = TaskStatus.RUNNING
        self._stop_event.clear()

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self.logger.info("调度器已启动", times=len(self._scheduled_times))

    def stop(self):
        """停止调度器"""
        if self._status != TaskStatus.RUNNING:
            return

        self._status = TaskStatus.STOPPED
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5)

        self.logger.info("调度器已停止")

    def pause(self):
        """暂停调度器"""
        if self._status == TaskStatus.RUNNING:
            self._status = TaskStatus.PAUSED
            self.logger.info("调度器已暂停")

    def resume(self):
        """恢复调度器"""
        if self._status == TaskStatus.PAUSED:
            self._status = TaskStatus.RUNNING
            self.logger.info("调度器已恢复")

    def _run_loop(self):
        """调度循环"""
        executed_today = set()  # 今天已执行的时间点

        while not self._stop_event.is_set():
            if self._status == TaskStatus.RUNNING:
                now = datetime.now()
                today = now.date()

                # 重置每日执行记录
                if executed_today and now.hour == 0 and now.minute == 0:
                    executed_today.clear()

                # 检查是否到达调度时间
                for st in self._scheduled_times:
                    key = (today, str(st))
                    if st.is_now(now) and key not in executed_today:
                        self._execute_task(st)
                        executed_today.add(key)
                        self._last_execution = now

            time_module.sleep(self.check_interval)

    def _execute_task(self, scheduled_time: ScheduledTime):
        """执行任务"""
        started_at = datetime.now()
        self.logger.info(f"执行调度任务", scheduled_time=str(scheduled_time))

        result = TaskResult(
            scheduled_time=scheduled_time,
            started_at=started_at,
            finished_at=None,
            success=False,
        )

        try:
            if self._task_func:
                self._task_func()
            result.success = True
            result.message = "任务执行成功"
        except Exception as e:
            result.error = str(e)
            result.message = f"任务执行失败: {e}"
            self.logger.error(f"任务执行失败", error=str(e))
        finally:
            result.finished_at = datetime.now()
            self._results.append(result)

    def get_results(self, limit: int = 10) -> List[TaskResult]:
        """获取执行结果"""
        return self._results[-limit:]

    @property
    def status(self) -> TaskStatus:
        return self._status