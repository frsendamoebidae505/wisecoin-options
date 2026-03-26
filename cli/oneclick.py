#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WiseCoin 期权分析一键执行脚本 (Options Analysis One-Click)
--------------------------------------------------
功能：
依次调用期权相关脚本，完成期权数据获取、分析和隐含波动率计算的完整流程。
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
logger = logging.getLogger('WiseCoin-Options-OneClick')

# ============================================================================
# 配置脚本序列
# ============================================================================

SCRIPTS_TO_RUN = [
    {
        'name': '备份',
        'path': '00wisecoin_options_backup.py',
        'type': 'python',
        'description': '备份数据'
    },
    {
        'name': '期权合约排名与行情获取',
        'path': '01wisecoin-options-ranking.py',
        'type': 'python',
        'description': '获取期权合约列表、详细信息、行情数据，并按产品分类导出',
        'completion_signal': '非标的期货行情保存完成'  # 完成标志（监控实时输出）
    },
    {
        'name': 'OpenCTP行情数据获取',
        'path': '02wisecoin-openctp-api.py',
        'type': 'python',
        'description': '通过OpenCTP接口获取期权行情数据'
    },
    {
        'name': '期权分析与策略筛选',
        'path': '03wisecoin-options-analyze.py',
        'type': 'python',
        'description': '执行期权深度分析、策略筛选和多因子评分',
        'completion_signal': '期权参考数据生成完成'  # 完成标志（监控实时输出）
    },
    {
        'name': '期权隐含波动率计算',
        'path': '04wisecoin-options-iv.py',
        'type': 'python',
        'description': '计算期权隐含波动率并生成波动率微笑曲线'
    },
    {
        'name': '期货标的行情分析',
        'path': '05wisecoin-futures-analyze.py',
        'type': 'python',
        'description': '分析期权标的期货合约的行情数据'
    },
    {
        'name': '标的期货K线',
        'path': '09wisecoin-futures-klines.py',
        'type': 'python',
        'description': '标的期货K线',
        'completion_signal': '所有标的期货K线数据获取完成'  # 完成标志（监控实时输出）
    }
]

# ============================================================================
# 执行引擎
# ============================================================================

class OptionsOneClickExecutor:
    """期权分析一键执行引擎"""

    def __init__(self):
        self.results = []
        self.start_time = None

    def execute_task(self, index: int, task: dict) -> bool:
        """执行单个任务"""
        logger.info(f"\n🚀 [{index}/{len(SCRIPTS_TO_RUN)}] 执行任务: {task['name']}")
        logger.info(f"   路径: {task['path']}")
        logger.info(f"   描述: {task['description']}")

        script_path = Path(task['path'])
        if not script_path.exists():
            logger.error(f"   ❌ 错误: 文件不存在: {task['path']}")
            return False

        # 使用绝对路径以避免 cwd 切换导致的路径寻找失败
        abs_script_path = str(script_path.resolve())

        task_start = time.time()
        try:
            if task['type'] == 'python':
                cmd = [sys.executable, abs_script_path]
            elif task['type'] == 'command':
                # 对于 .command 文件，使用 bash 执行
                cmd = ['bash', abs_script_path]
            else:
                logger.error(f"   ❌ 未知的任务类型: {task['type']}")
                return False

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
            cwd=task.get('cwd', os.getcwd()),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # 实时显示输出（可选：根据需要过滤）
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                # 只显示包含特定表情符号的行，或者是关键结果
                if any(emoji in line for emoji in ['✅', '❌', '🎉', '📊', '💾', '🚀', '📈', '📉', '🎯']):
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
            cwd=task.get('cwd', os.getcwd()),
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
                    # 显示包含特定表情符号的行，或者是关键结果
                    if any(emoji in line for emoji in ['✅', '❌', '🎉', '📊', '💾', '🚀', '📈', '📉', '🎯']):
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

        for i, task in enumerate(SCRIPTS_TO_RUN, 1):
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

        for i, res in enumerate(self.results, 1):
            task = res['task']
            status = res['status']
            icon = "✅" if status == 'SUCCESS' else "❌"
            time_str = f"({res['time']:.1f}s)" if 'time' in res else ""
            logger.info(f"  [{i}] {icon} {task['name']:25} {time_str}")

        logger.info("=" * 80)


def main():
    """命令行入口"""
    executor = OptionsOneClickExecutor()
    executor.run()
    return 0


if __name__ == "__main__":
    exit(main())