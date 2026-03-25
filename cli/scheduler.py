"""
WiseCoin 定时调度执行脚本 by playbonze
在交易日期（周一至周六凌晨）按配置的时间点自动执行 06wisecoin_oneclick.command
"""

import asyncio
import datetime
import subprocess
import sys
import os
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('WiseCoin-Scheduler')

# ============================================================================
# 配置
# ============================================================================

# 定时触发时间点配置（24小时制，格式：(时, 分)）
SCHEDULED_TIMES = [
    (20, 40), (21, 40), (22, 40), (23, 40), (0, 40), (1, 40),
    (8, 40), (9, 40), (10, 40), (12, 40), (13, 40), (14, 40), (15, 16)
]

# 要执行的脚本路径
TARGET_SCRIPT = "06wisecoin_oneclick.command"

# 检查间隔（秒）
CHECK_INTERVAL = 30

# 触发冷却时间（分钟）- 防止同一时间点重复触发
COOLDOWN_MINUTES = 5

# ============================================================================
# 工具函数
# ============================================================================

def is_trading_day():
    """
    判断当前是否为交易日期

    交易日期范围：
    - 周一至周五：全天都是交易日（包括夜盘）
    - 周六凌晨：00:00-02:30 算作交易日（周五夜盘延续）
    - 周六 02:30 之后至周一：非交易日

    Returns:
        bool: 是否为交易日期
    """
    now = datetime.datetime.now()
    weekday = now.weekday()  # 0=周一, 6=周日
    current_time = now.time()

    # 周一至周五：全天都是交易日
    if weekday in [0, 1, 2, 3, 4]:  # 周一至周五
        return True

    # 周六凌晨 00:00-02:30：算作交易日（周五夜盘延续）
    if weekday == 5:  # 周六
        if datetime.time(0, 0) <= current_time <= datetime.time(2, 30):
            return True
        else:
            return False

    # 周日：不是交易日
    if weekday == 6:  # 周日
        return False

    return False


def is_scheduled_time(current_time, tolerance_minutes=0):
    """
    检查当前时间是否为配置的触发时间点

    Args:
        current_time: 当前时间 (datetime.datetime)
        tolerance_minutes: 时间容差（分钟），默认为0（精确匹配）

    Returns:
        tuple: (是否为触发时间, 匹配的时间点字符串)
    """
    current_hour = current_time.hour
    current_minute = current_time.minute

    for trigger_hour, trigger_minute in SCHEDULED_TIMES:
        # 检查是否在触发时间点的容差范围内
        if current_hour == trigger_hour:
            minute_diff = abs(current_minute - trigger_minute)
            if minute_diff <= tolerance_minutes:
                return True, f"{trigger_hour:02d}:{trigger_minute:02d}"

    return False, None


def execute_script(script_path):
    """
    执行目标脚本

    Args:
        script_path: 脚本路径

    Returns:
        bool: 执行是否成功
    """
    logger.info(f"🚀 开始执行脚本: {script_path}")

    script_file = Path(script_path)
    if not script_file.exists():
        logger.error(f"❌ 脚本文件不存在: {script_path}")
        return False

    try:
        # 使用绝对路径执行
        abs_script_path = str(script_file.resolve())

        # 根据文件扩展名选择执行方式
        if abs_script_path.endswith('.command') or abs_script_path.endswith('.sh'):
            # bash 脚本，使用 /bin/bash 执行
            cmd = ['/bin/bash', abs_script_path]
        else:
            # Python 脚本，使用 python 执行
            cmd = [sys.executable, abs_script_path]

        # 执行脚本
        start_time = datetime.datetime.now()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,  # 禁止标准输入，防止阻塞
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # 记录是否出现"成功"标记（避免 .command 尾部 read 导致退出码非0）
        success_marker_seen = False

        stdout = process.stdout
        if stdout is None:
            logger.error("❌ 子进程 stdout 为空，无法读取输出")
            _ = process.wait()
            return False

        # 实时显示输出（只显示关键信息）
        for line in iter(stdout.readline, ''):
            line = line.strip()
            if line:
                # 判定成功标记（不依赖 emoji，避免字符变体导致匹配失败）
                if ('脚本执行成功' in line) or ('执行成功' in line and '耗时' in line):
                    success_marker_seen = True

                # 只显示包含特定标记的行
                if any(marker in line for marker in ['✅', '❌', '🎉', '📊', '💾', '🚀', '⏳', '🛑']):
                    logger.info(f"  │ {line}")

        _ = process.wait()
        return_code = process.returncode
        elapsed = (datetime.datetime.now() - start_time).total_seconds()

        # 返回码为0，或看到了成功标记，都按成功处理
        if return_code == 0 or success_marker_seen:
            if return_code != 0 and success_marker_seen:
                logger.warning(f"⚠️ 返回码为 {return_code}，但检测到成功标记，按成功处理")
            logger.info(f"✅ 脚本执行成功！耗时: {elapsed:.1f}秒")
            return True
        else:
            logger.error(f"❌ 脚本执行失败 (错误码: {return_code})")
            return False

    except Exception as e:
        logger.error(f"❌ 执行脚本异常: {e}")
        return False


# ============================================================================
# 主调度协程
# ============================================================================

async def scheduler_loop():
    """
    定时调度主循环

    逻辑：
    1. 每隔 CHECK_INTERVAL 秒检查一次
    2. 判断当前是否为交易日期
    3. 判断当前时间是否为配置的触发时间点
    4. 满足条件时执行 TARGET_SCRIPT
    5. 使用冷却时间防止重复触发
    """
    last_trigger_time = None

    logger.info("=" * 80)
    logger.info("⏰ WiseCoin 定时调度系统启动")
    logger.info("=" * 80)
    logger.info(f"📅 交易日期: 周一至周六凌晨（00:00-02:30）")
    logger.info(f"🎯 目标脚本: {TARGET_SCRIPT}")
    logger.info(f"🕐 检查间隔: {CHECK_INTERVAL} 秒")
    logger.info(f"❄️  冷却时间: {COOLDOWN_MINUTES} 分钟")
    logger.info(f"⏰ 触发时间点: {len(SCHEDULED_TIMES)} 个")
    logger.info(f"   {', '.join([f'{h:02d}:{m:02d}' for h, m in SCHEDULED_TIMES])}")
    logger.info("=" * 80)

    # 程序启动时立即检查一次
    startup_check = True

    while True:
        try:
            # 第一次循环不等待，后续循环等待
            if not startup_check:
                await asyncio.sleep(CHECK_INTERVAL)
            else:
                startup_check = False
                logger.info("🚀 程序启动，立即检查是否需要触发...")

            current_time = datetime.datetime.now()

            # 1. 检查是否为交易日期
            if not is_trading_day():
                # 不是交易日期，跳过本次检查
                continue

            # 2. 检查是否为触发时间点
            is_trigger_time, trigger_time_str = is_scheduled_time(current_time, tolerance_minutes=0)

            if not is_trigger_time:
                # 不是触发时间点，跳过本次检查
                continue

            # 3. 检查冷却时间
            can_trigger = True
            if last_trigger_time is not None:
                time_since_last_trigger = (current_time - last_trigger_time).total_seconds() / 60
                if time_since_last_trigger < COOLDOWN_MINUTES:
                    can_trigger = False
                    logger.debug(f"⏳ 冷却中，距上次触发 {time_since_last_trigger:.1f} 分钟 (< {COOLDOWN_MINUTES} 分钟)")

            # 4. 满足所有条件，执行脚本
            if can_trigger:
                logger.info("")
                logger.info("╔" + "═" * 78 + "╗")
                logger.info("║" + "🎯 触发定时任务".center(76) + "║")
                logger.info("╠" + "═" * 78 + "╣")
                logger.info(f"║  触发时间点: {trigger_time_str}".ljust(79) + "║")
                logger.info(f"║  当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}".ljust(79) + "║")
                if last_trigger_time:
                    time_since_last = (current_time - last_trigger_time).total_seconds() / 60
                    logger.info(f"║  距上次触发: {time_since_last:.1f} 分钟".ljust(79) + "║")
                else:
                    logger.info("║  距上次触发: 首次触发".ljust(79) + "║")
                logger.info("╚" + "═" * 78 + "╝")
                logger.info("")

                # 执行脚本
                success = execute_script(TARGET_SCRIPT)

                if success:
                    # 更新最后触发时间
                    last_trigger_time = current_time
                    logger.info(f"✅ 任务执行完成，下次触发时间不早于 {(current_time + datetime.timedelta(minutes=COOLDOWN_MINUTES)).strftime('%H:%M:%S')}")
                else:
                    logger.error("❌ 任务执行失败")

                logger.info("")

        except asyncio.CancelledError:
            logger.info("🛑 调度系统已停止")
            return
        except Exception as e:
            logger.error(f"❌ 调度异常: {e}")
            import traceback
            logger.error(traceback.format_exc())


# ============================================================================
# 主程序
# ============================================================================

async def main():
    """主程序入口"""
    logger.info('调度系统开始运行。')

    try:
        # 运行调度循环
        await scheduler_loop()
    except KeyboardInterrupt:
        logger.info('\n⏹️  收到中断信号，正在停止...')
    except Exception as e:
        logger.error(f'❌ 异常: {repr(e)}')
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info('调度系统已关闭。')


def run():
    """命令行入口"""
    asyncio.run(main())
    return 0


if __name__ == '__main__':
    exit(run())