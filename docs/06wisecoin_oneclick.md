# 06wisecoin_oneclick.py - 开发文档

## 文件概述

WiseCoin 期权分析一键执行脚本，依次调用期权相关脚本，完成数据获取、分析和计算的完整流程。

## 作者

playbonze

## 功能描述

提供一键式的期权分析流程自动化执行：

1. 备份数据
2. 获取期权合约排名与行情
3. 获取 OpenCTP 数据
4. 执行期权分析与策略筛选
5. 计算隐含波动率
6. 分析期货标的行情
7. 生成期货开仓方向配置
8. 获取标的期货K线数据

## 脚本执行序列

```python
SCRIPTS_TO_RUN = [
    {'name': '备份', 'path': '00wisecoin_options_backup.py'},
    {'name': '期权合约排名与行情获取', 'path': '01wisecoin-options-ranking.py'},
    {'name': 'OpenCTP行情数据获取', 'path': '02wisecoin-openctp-api.py'},
    {'name': '期权分析与策略筛选', 'path': '03wisecoin-options-analyze.py'},
    {'name': '期权隐含波动率计算', 'path': '04wisecoin-options-iv.py'},
    {'name': '期货标的行情分析', 'path': '05wisecoin-futures-analyze.py'},
    {'name': '期货开仓方向', 'path': '08wisecoin_symbol_lsn.py'},
    {'name': '标的期货K线', 'path': '09wisecoin-futures-klines.py'},
]
```

## 核心类

### `OptionsOneClickExecutor`

一键执行引擎类。

**方法：**

#### `execute_task(index, task) -> bool`

执行单个任务。

**参数：**
- `index`: 任务序号
- `task`: 任务配置字典

**返回：**
- 执行是否成功

#### `_execute_normal(cmd, task, task_start) -> bool`

执行普通任务（等待进程正常退出）。

**特性：**
- 实时显示包含特定表情符号的输出行
- 过滤非关键输出

**监控的表情符号：**
```python
['✅', '❌', '🎉', '📊', '💾', '🚀', '📈', '📉', '🎯']
```

#### `_execute_with_output_monitoring(cmd, task, completion_signal, task_start) -> bool`

执行需要监控实时输出的任务。

**特性：**
- 监控输出中是否出现完成标志
- 检测到完成标志后终止进程
- 优雅终止（terminate）+ 强制终止（kill）机制

**完成信号检测：**
```python
if completion_signal in line:
    completion_detected = True
    # 终止进程...
```

#### `run()`

运行全部流程。

#### `print_summary()`

打印执行总结。

## 任务配置结构

```python
{
    'name': '任务名称',
    'path': '脚本路径',
    'type': 'python/command',
    'description': '任务描述',
    'completion_signal': '完成标志文本'  # 可选
}
```

## 完成信号监控

某些长时间运行的任务需要监控输出判断完成：

| 脚本 | 完成信号 |
|------|----------|
| 01wisecoin-options-ranking.py | 非标的期货行情保存完成 |
| 03wisecoin-options-analyze.py | 期权参考数据生成完成 |
| 09wisecoin-futures-klines.py | 所有标的期货K线数据获取完成 |

## 使用方式

```bash
# 方式一：直接运行 Python
python 06wisecoin_oneclick.py

# 方式二：通过 .command 文件运行
./06wisecoin_oneclick.command
```

## 输出示例

```
================================================================================
                     WiseCoin 期权分析一键执行流程启动
================================================================================

🚀 [1/8] 执行任务: 备份
   路径: 00wisecoin_options_backup.py
   描述: 备份数据
   ✅ 执行成功！耗时: 2.3秒

🚀 [2/8] 执行任务: 期权合约排名与行情获取
   ...

================================================================================
                              一键执行总结
================================================================================
总耗时: 180.5秒
  [1] ✅ 备份                       (2.3s)
  [2] ✅ 期权合约排名与行情获取      (45.2s)
  ...
================================================================================
```

## 依赖模块

- `subprocess`: 子进程管理
- `sys`: 系统相关
- `logging`: 日志记录
- `pathlib`: 路径处理

## 注意事项

- 即使某个任务失败也会继续执行后续任务
- 日志只显示关键输出，避免刷屏
- 使用绝对路径避免工作目录问题