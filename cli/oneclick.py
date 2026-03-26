#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WiseCoin 期权分析一键执行脚本 (Options Analysis One-Click)
--------------------------------------------------
功能：
依次调用新架构模块，完成期权数据获取、分析和隐含波动率计算的完整流程。

Usage:
    python3 -m cli.oneclick
"""

import subprocess
import sys
import os
import time
from datetime import datetime
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('WiseCoin-OneClick')

# ============================================================================
# 配置模块序列（使用新架构）
# ============================================================================

MODULES_TO_RUN = [
    {
        'name': '数据备份',
        'module': 'data.backup',
        'description': '备份当前数据到 backups/ 目录',
    },
    {
        'name': '期权行情获取',
        'module': 'data.option_quotes',
        'description': '获取期权合约列表、行情数据并导出Excel',
        'completion_signal': '期权行情数据获取完成',  # 完成标志
    },
    {
        'name': 'OpenCTP数据获取',
        'module': 'data.openctp',
        'description': '通过OpenCTP接口获取期权行情数据',
    },
    {
        'name': '期权综合分析',
        'module': 'cli.option_analyzer',
        'description': '期权深度分析、IV计算、Greeks计算，生成期权排行和期权参考',
        'completion_signal': '期权参考数据生成完成',
    },
    {
        'name': '期货联动分析',
        'module': 'cli.futures_analyzer',
        'description': '期货期权联动分析，生成货权联动和市场概览',
    },
    {
        'name': '期货K线获取',
        'module': 'data.klines',
        'description': '获取标的期货K线数据',
        'completion_signal': '期货K线保存完成',
    },
]

# ============================================================================
# 执行引擎
# ============================================================================

class OneClickExecutor:
    """一键执行引擎"""

    def __init__(self):
        self.results = []
        self.start_time = None
        self.project_root = Path(__file__).parent.parent

    def execute_task(self, index: int, task: dict) -> bool:
        """执行单个任务"""
        logger.info(f"\n🚀 [{index}/{len(MODULES_TO_RUN)}] 执行任务: {task['name']}")
        logger.info(f"   模块: {task['module']}")
        logger.info(f"   描述: {task['description']}")

        task_start = time.time()
        try:
            # 使用 python -m 方式调用模块
            cmd = [sys.executable, '-m', task['module']]

            # 检查是否需要监控实时输出完成标志
            completion_signal = task.get('completion_signal')

            if completion_signal:
                # 需要监控实时输出的任务
                return self._execute_with_output_monitoring(cmd, task, completion_signal, task_start)
            else:
                # 普通任务，等待正常退出
                return self._execute_normal(cmd, task, task_start)

        except Exception as e:
            logger.error(f"   ❌ 执行异常: {e}")
            self.results.append({'task': task, 'status': 'ERROR', 'error': str(e)})
            return False

    def _execute_normal(self, cmd: list, task: dict, task_start: float) -> bool:
        """执行普通任务（等待进程正常退出）"""
        # 执行子进程
        process = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # 实时显示输出
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                # 只显示包含特定表情符号的行，或者是关键结果
                if any(emoji in line for emoji in ['✅', '❌', '🎉', '📊', '💾', '🚀', '📈', '📉', '🎯', 'INFO', '完成']):
                    logger.info(f"   │ {line}")

        process.wait()
        return_code = process.returncode
        elapsed = time.time() - task_start

        if return_code == 0:
            logger.info(f"   ✅ 执行成功！耗时: {elapsed:.1f}秒")
            self.results.append({'task': task, 'status': 'SUCCESS', 'time': elapsed})
            return True
        else:
            logger.error(f"   ❌ 执行失败 (错误码: {return_code})")
            self.results.append({'task': task, 'status': 'FAILED', 'time': elapsed, 'code': return_code})
            return False

    def _execute_with_output_monitoring(self, cmd: list, task: dict, completion_signal: str,
                                        task_start: float) -> bool:
        """执行需要监控实时输出的任务"""
        logger.info(f"   ⏳ 监控模式: 等待输出出现 '{completion_signal}'")

        # 启动子进程
        process = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        completion_detected = False

        # 实时读取并监控输出
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break

                line = line.strip()
                if line:
                    # 显示包含特定表情符号的行
                    if any(emoji in line for emoji in ['✅', '❌', '🎉', '📊', '💾', '🚀', '📈', '📉', '🎯', 'INFO', '完成']):
                        logger.info(f"   │ {line}")

                    # 检测完成标志
                    if completion_signal in line:
                        completion_detected = True
                        logger.info(f"   ✅ 检测到完成标志: '{completion_signal}'")
                        break
        except Exception as e:
            logger.error(f"   ❌ 读取输出异常: {e}")

        # 如果检测到完成标志，终止进程
        if completion_detected:
            logger.info(f"   🛑 正在终止进程 (PID: {process.pid})...")
            try:
                # 优雅终止
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 强制终止
                    logger.warning(f"   ⚠️ 优雅终止超时，强制结束进程")
                    process.kill()
                    process.wait()

                elapsed = time.time() - task_start
                logger.info(f"   ✅ 任务完成！耗时: {elapsed:.1f}秒")
                self.results.append({'task': task, 'status': 'SUCCESS', 'time': elapsed, 'terminated': True})
                return True
            except Exception as e:
                logger.error(f"   ❌ 终止进程失败: {e}")
                elapsed = time.time() - task_start
                self.results.append({'task': task, 'status': 'ERROR', 'time': elapsed, 'error': str(e)})
                return False
        else:
            # 进程自然退出
            process.wait()
            return_code = process.returncode
            elapsed = time.time() - task_start

            if return_code == 0:
                logger.info(f"   ✅ 执行成功！耗时: {elapsed:.1f}秒")
                self.results.append({'task': task, 'status': 'SUCCESS', 'time': elapsed})
                return True
            else:
                logger.error(f"   ❌ 执行失败 (错误码: {return_code})")
                self.results.append({'task': task, 'status': 'FAILED', 'time': elapsed, 'code': return_code})
                return False

    def run(self):
        """运行全部流程"""
        self.start_time = time.time()
        logger.info("=" * 80)
        logger.info("WiseCoin 期权分析一键执行流程启动".center(80))
        logger.info("=" * 80)

        for i, task in enumerate(MODULES_TO_RUN, 1):
            # 执行任务，即使失败也继续下一步
            self.execute_task(i, task)

        self.print_summary()

    def print_summary(self):
        """打印总结"""
        total_time = time.time() - self.start_time
        logger.info("\n" + "=" * 80)
        logger.info("一键执行总结".center(80))
        logger.info("=" * 80)
        logger.info(f"总耗时: {total_time:.1f}秒")

        success_count = 0
        fail_count = 0

        for i, res in enumerate(self.results, 1):
            task = res['task']
            status = res['status']
            icon = "✅" if status == 'SUCCESS' else "❌"
            time_str = f"({res['time']:.1f}s)" if 'time' in res else ""
            logger.info(f"  [{i}] {icon} {task['name']:25} {time_str}")

            if status == 'SUCCESS':
                success_count += 1
            else:
                fail_count += 1

        logger.info("-" * 80)
        logger.info(f"成功: {success_count} 个, 失败: {fail_count} 个")
        logger.info("=" * 80)


def main():
    """命令行入口"""
    executor = OneClickExecutor()
    executor.run()
    return 0


if __name__ == "__main__":
    exit(main())