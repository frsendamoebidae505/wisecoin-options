#!/usr/bin/env python3
"""
WiseCoin 期权分析系统入口。

Usage:
    python3 run.py              # 运行一键分析示例
    python3 run.py --scheduler  # 启动定时调度
    python3 run.py --live       # 启动实时监控
"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_oneclick():
    """运行一键分析示例。"""
    from datetime import date
    from cli.oneclick import OneClickAnalyzer
    from core.models import OptionQuote, CallOrPut

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
    return result


def run_scheduler():
    """启动定时调度器。"""
    from cli.scheduler import TaskScheduler

    print("启动定时调度器...")

    scheduler = TaskScheduler()
    scheduler.add_times(TaskScheduler.DEFAULT_TIMES)

    def task():
        print(f"[{__import__('datetime').datetime.now()}] 执行定时任务...")

    scheduler.start(task)

    try:
        while True:
            __import__('time').sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("调度器已停止")


def run_live():
    """启动实时监控。"""
    from cli.live import LiveMonitor

    print("启动实时监控...")

    monitor = LiveMonitor()
    monitor.start()

    try:
        while True:
            __import__('time').sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("监控器已停止")


if __name__ == "__main__":
    if "--scheduler" in sys.argv:
        run_scheduler()
    elif "--live" in sys.argv:
        run_live()
    else:
        run_oneclick()