"""
TaskScheduler 单元测试。
"""
import pytest
from datetime import datetime, time
from unittest.mock import Mock, patch
import threading
import time as time_module

from cli.scheduler import (
    TaskStatus,
    ScheduledTime,
    TaskResult,
    TaskScheduler,
)


class TestScheduledTime:
    """ScheduledTime 测试类"""

    def test_create_scheduled_time(self):
        """测试创建调度时间"""
        st = ScheduledTime(hour=9, minute=30)
        assert st.hour == 9
        assert st.minute == 30

    def test_to_time(self):
        """测试转换为 time 对象"""
        st = ScheduledTime(hour=14, minute=45)
        t = st.to_time()
        assert isinstance(t, time)
        assert t.hour == 14
        assert t.minute == 45

    def test_is_now_true(self):
        """测试 is_now 返回 True"""
        st = ScheduledTime(hour=10, minute=30)
        current = datetime(2024, 1, 15, 10, 30, 0)
        assert st.is_now(current) is True

    def test_is_now_false_different_hour(self):
        """测试 is_now 返回 False (小时不同)"""
        st = ScheduledTime(hour=10, minute=30)
        current = datetime(2024, 1, 15, 11, 30, 0)
        assert st.is_now(current) is False

    def test_is_now_false_different_minute(self):
        """测试 is_now 返回 False (分钟不同)"""
        st = ScheduledTime(hour=10, minute=30)
        current = datetime(2024, 1, 15, 10, 31, 0)
        assert st.is_now(current) is False

    def test_str_format(self):
        """测试字符串格式化"""
        st1 = ScheduledTime(hour=9, minute=5)
        assert str(st1) == "09:05"

        st2 = ScheduledTime(hour=14, minute=30)
        assert str(st2) == "14:30"

    def test_equality(self):
        """测试相等比较"""
        st1 = ScheduledTime(hour=9, minute=30)
        st2 = ScheduledTime(hour=9, minute=30)
        st3 = ScheduledTime(hour=9, minute=31)

        assert st1 == st2
        assert st1 != st3


class TestTaskResult:
    """TaskResult 测试类"""

    def test_create_task_result(self):
        """测试创建任务结果"""
        st = ScheduledTime(hour=9, minute=30)
        started = datetime(2024, 1, 15, 9, 30, 0)
        finished = datetime(2024, 1, 15, 9, 30, 5)

        result = TaskResult(
            scheduled_time=st,
            started_at=started,
            finished_at=finished,
            success=True,
            message="任务执行成功",
        )

        assert result.scheduled_time == st
        assert result.started_at == started
        assert result.finished_at == finished
        assert result.success is True
        assert result.message == "任务执行成功"
        assert result.error is None

    def test_task_result_with_error(self):
        """测试带错误的任务结果"""
        st = ScheduledTime(hour=9, minute=30)
        result = TaskResult(
            scheduled_time=st,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            success=False,
            message="任务执行失败",
            error="Connection refused",
        )

        assert result.success is False
        assert result.error == "Connection refused"


class TestTaskScheduler:
    """TaskScheduler 测试类"""

    def test_create_scheduler(self):
        """测试创建调度器"""
        scheduler = TaskScheduler()
        assert scheduler.status == TaskStatus.IDLE
        assert scheduler.check_interval == 30
        assert len(scheduler.get_scheduled_times()) == 0

    def test_create_scheduler_with_custom_interval(self):
        """测试使用自定义检查间隔创建调度器"""
        scheduler = TaskScheduler(check_interval=60)
        assert scheduler.check_interval == 60

    def test_add_time(self):
        """测试添加调度时间"""
        scheduler = TaskScheduler()
        scheduler.add_time(9, 30)

        times = scheduler.get_scheduled_times()
        assert len(times) == 1
        assert times[0].hour == 9
        assert times[0].minute == 30

    def test_add_time_duplicate(self):
        """测试添加重复的调度时间"""
        scheduler = TaskScheduler()
        scheduler.add_time(9, 30)
        scheduler.add_time(9, 30)  # 重复添加

        times = scheduler.get_scheduled_times()
        assert len(times) == 1

    def test_add_times(self):
        """测试批量添加调度时间"""
        scheduler = TaskScheduler()
        scheduler.add_times([(9, 30), (10, 0), (14, 30)])

        times = scheduler.get_scheduled_times()
        assert len(times) == 3

    def test_add_times_sorted(self):
        """测试添加时间后自动排序"""
        scheduler = TaskScheduler()
        scheduler.add_times([(14, 30), (9, 30), (10, 0)])

        times = scheduler.get_scheduled_times()
        assert times[0].hour == 9
        assert times[1].hour == 10
        assert times[2].hour == 14

    def test_remove_time(self):
        """测试移除调度时间"""
        scheduler = TaskScheduler()
        scheduler.add_time(9, 30)

        result = scheduler.remove_time(9, 30)
        assert result is True
        assert len(scheduler.get_scheduled_times()) == 0

    def test_remove_time_not_found(self):
        """测试移除不存在的调度时间"""
        scheduler = TaskScheduler()
        result = scheduler.remove_time(9, 30)
        assert result is False

    def test_get_scheduled_times_returns_copy(self):
        """测试获取调度时间返回副本"""
        scheduler = TaskScheduler()
        scheduler.add_time(9, 30)

        times1 = scheduler.get_scheduled_times()
        times2 = scheduler.get_scheduled_times()

        assert times1 is not times2
        assert times1 == times2

    def test_get_next_execution_with_times(self):
        """测试获取下一个执行时间"""
        scheduler = TaskScheduler()
        scheduler.add_times([(9, 0), (12, 0), (18, 0)])

        # Mock 当前时间
        with patch('cli.scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            next_time = scheduler.get_next_execution()
            assert next_time.hour == 12

    def test_get_next_execution_no_times(self):
        """测试没有调度时间时获取下一个执行时间"""
        scheduler = TaskScheduler()
        next_time = scheduler.get_next_execution()
        assert next_time is None

    def test_get_next_execution_end_of_day(self):
        """测试一天结束时获取下一个执行时间"""
        scheduler = TaskScheduler()
        scheduler.add_times([(9, 0), (12, 0), (18, 0)])

        # 当前时间是 20:00，应返回明天的第一个
        with patch('cli.scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 20, 0, 0)
            next_time = scheduler.get_next_execution()
            assert next_time.hour == 9

    def test_status_transitions_idle_to_running(self):
        """测试状态转换: IDLE -> RUNNING"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()

        scheduler.start(mock_task)
        assert scheduler.status == TaskStatus.RUNNING

        scheduler.stop()
        assert scheduler.status == TaskStatus.STOPPED

    def test_status_transitions_running_to_paused(self):
        """测试状态转换: RUNNING -> PAUSED"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()

        scheduler.start(mock_task)
        assert scheduler.status == TaskStatus.RUNNING

        scheduler.pause()
        assert scheduler.status == TaskStatus.PAUSED

        scheduler.stop()

    def test_status_transitions_paused_to_running(self):
        """测试状态转换: PAUSED -> RUNNING"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()

        scheduler.start(mock_task)
        scheduler.pause()
        assert scheduler.status == TaskStatus.PAUSED

        scheduler.resume()
        assert scheduler.status == TaskStatus.RUNNING

        scheduler.stop()

    def test_start_when_already_running(self):
        """测试调度器已在运行时再次启动"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()

        scheduler.start(mock_task)
        first_thread = scheduler._thread

        # 再次启动不应创建新线程
        scheduler.start(mock_task)
        assert scheduler._thread is first_thread

        scheduler.stop()

    def test_stop_when_not_running(self):
        """测试停止未运行的调度器"""
        scheduler = TaskScheduler()
        # 不应抛出异常
        scheduler.stop()
        assert scheduler.status == TaskStatus.IDLE

    def test_pause_when_not_running(self):
        """测试暂停未运行的调度器"""
        scheduler = TaskScheduler()
        scheduler.pause()
        # IDLE 状态不应变为 PAUSED
        assert scheduler.status == TaskStatus.IDLE

    def test_resume_when_not_paused(self):
        """测试恢复非暂停状态的调度器"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()

        scheduler.start(mock_task)
        # RUNNING 状态不应改变
        scheduler.resume()
        assert scheduler.status == TaskStatus.RUNNING

        scheduler.stop()

    def test_task_execution(self):
        """测试任务执行"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()

        scheduler.add_time(9, 30)
        scheduler.start(mock_task)

        # 模拟触发任务执行
        scheduler._execute_task(ScheduledTime(9, 30))

        mock_task.assert_called_once()

        results = scheduler.get_results()
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].scheduled_time.hour == 9

        scheduler.stop()

    def test_task_execution_with_error(self):
        """测试任务执行失败"""
        scheduler = TaskScheduler(check_interval=0.1)

        def failing_task():
            raise ValueError("测试错误")

        scheduler.add_time(9, 30)
        scheduler.start(failing_task)

        scheduler._execute_task(ScheduledTime(9, 30))

        results = scheduler.get_results()
        assert len(results) == 1
        assert results[0].success is False
        assert "测试错误" in results[0].error

        scheduler.stop()

    def test_get_results_limit(self):
        """测试获取执行结果限制"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()
        scheduler.start(mock_task)

        # 执行多次任务
        for i in range(15):
            scheduler._execute_task(ScheduledTime(9, 30))

        # 默认限制 10 条
        results = scheduler.get_results()
        assert len(results) == 10

        # 自定义限制
        results = scheduler.get_results(limit=5)
        assert len(results) == 5

        scheduler.stop()

    def test_default_times_constant(self):
        """测试默认时间常量"""
        assert len(TaskScheduler.DEFAULT_TIMES) == 13
        assert (9, 40) in TaskScheduler.DEFAULT_TIMES

    def test_scheduler_with_default_times(self):
        """测试使用默认时间初始化调度器"""
        scheduler = TaskScheduler()
        scheduler.add_times(TaskScheduler.DEFAULT_TIMES)

        times = scheduler.get_scheduled_times()
        assert len(times) == 13

    def test_scheduler_thread_daemon(self):
        """测试调度器线程是守护线程"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()

        scheduler.start(mock_task)

        assert scheduler._thread is not None
        assert scheduler._thread.daemon is True

        scheduler.stop()

    def test_scheduler_stop_waits_for_thread(self):
        """测试停止调度器等待线程结束"""
        scheduler = TaskScheduler(check_interval=0.1)
        mock_task = Mock()

        scheduler.start(mock_task)
        thread = scheduler._thread

        scheduler.stop()

        # 线程应该已结束
        assert not thread.is_alive()
        assert scheduler.status == TaskStatus.STOPPED