# WiseCoin 期权分析系统 - 开发文档索引

## 项目概述

WiseCoin 期权分析系统是一个基于 Python 的期货期权量化分析平台，使用 TqSDK 进行行情数据获取和交易操作。系统支持期权品种筛选、行情获取、波动率分析、策略生成等功能。

## 文件分类

| 编号前缀 | 功能分类 |
|---------|---------|
| 00 | 备份与清理工具 |
| 01-05 | 数据获取与分析脚本 |
| 06-07 | 一键执行与调度系统 |
| 08-09 | 辅助工具与K线数据 |
| 10-19 | 客户端数据获取与分析 |
| 31-33 | 持仓交易处理 |
| 41-42 | 持仓信息获取 |
| 51-52 | 模拟持仓生成 |

## 核心依赖

- **TqSDK**: 天勤量化SDK，用于行情获取和交易
- **pandas/numpy**: 数据处理
- **openpyxl**: Excel文件操作
- **asyncio**: 异步编程支持

## 文档列表

### 备份与清理工具 (00系列)
| 文档 | 源文件 | 说明 |
|------|--------|------|
| [00wisecoin_options_backup.md](./00wisecoin_options_backup.md) | 00wisecoin_options_backup.py | 期权数据备份工具 |
| [00wisecoin_options_backup_clean.md](./00wisecoin_options_backup_clean.md) | 00wisecoin_options_backup_clean.py | 备份目录清理工具 |

### 数据获取与分析 (01-05系列)
| 文档 | 源文件 | 说明 |
|------|--------|------|
| [01wisecoin-options-ranking.md](./01wisecoin-options-ranking.md) | 01wisecoin-options-ranking.py | 期权排名与行情获取 |
| [02wisecoin-openctp-api.md](./02wisecoin-openctp-api.md) | 02wisecoin-openctp-api.py | OpenCTP数据获取 |
| [03wisecoin-options-analyze.md](./03wisecoin-options-analyze.md) | 03wisecoin-options-analyze.py | 期权分析模块 |
| [04wisecoin-options-iv.md](./04wisecoin-options-iv.md) | 04wisecoin-options-iv.py | 隐含波动率计算 |
| [05wisecoin-futures-analyze.md](./05wisecoin-futures-analyze.md) | 05wisecoin-futures-analyze.py | 期货分析模块 |

### 一键执行与调度 (06-07系列)
| 文档 | 源文件 | 说明 |
|------|--------|------|
| [06wisecoin_oneclick.md](./06wisecoin_oneclick.md) | 06wisecoin_oneclick.py | 一键执行脚本 |
| [06wisecoin_oneclick_command.md](./06wisecoin_oneclick_command.md) | 06wisecoin_oneclick.command | macOS执行脚本 |
| [07wisecoin_run.md](./07wisecoin_run.md) | 07wisecoin_run.py | 定时调度系统 |

### 辅助工具 (08-09系列)
| 文档 | 源文件 | 说明 |
|------|--------|------|
| [08wisecoin_symbol_lsn.md](./08wisecoin_symbol_lsn.md) | 08wisecoin_symbol_lsn.py | 开仓方向生成 |
| [09wisecoin-futures-klines.md](./09wisecoin-futures-klines.md) | 09wisecoin-futures-klines.py | 期货K线获取 |

### 客户端数据获取 (10-19系列)
| 文档 | 源文件 | 说明 |
|------|--------|------|
| [10wisecoin_options_client.md](./10wisecoin_options_client.md) | 10wisecoin_options_client.py | 期权品种获取 |
| [10wisecoin_options_client_eat.md](./10wisecoin_options_client_eat.md) | 相关吃单脚本 | 盘口吃单交易 |
| [13wisecoin_options_live_symbol.md](./13wisecoin_options_live_symbol.md) | 13wisecoin_options_live_symbol.py | 监控配置生成 |
| [14wisecoin_options_client_data.md](./14wisecoin_options_client_data.md) | 14wisecoin_options_client_data.py | 客户端数据获取 |
| [14wisecoin_options_client_data_klines.md](./14wisecoin_options_client_data_klines.md) | 14wisecoin_options_client_data_klines.py | 客户端K线获取 |
| [15wisecoin_options_client_analyze_options.md](./15wisecoin_options_client_analyze_options.md) | 15wisecoin_options_client_analyze_options.py | 客户端期权分析 |
| [16wisecoin_options_client_iv.md](./16wisecoin_options_client_iv.md) | 16wisecoin_options_client_iv.py | 客户端IV计算 |
| [17wisecoin_options_client_analyze_futures.md](./17wisecoin_options_client_analyze_futures.md) | 17wisecoin_options_client_analyze_futures.py | 客户端期货分析 |
| [18wisecoin_options_client_live.md](./18wisecoin_options_client_live.md) | 18wisecoin_options_client_live.py | 实时监控一键执行 |
| [19wisecoin_options_client_arbitrage.md](./19wisecoin_options_client_arbitrage.md) | 19wisecoin_options_client_arbitrage.py | 期权套利分析 |
| [19wisecoin_options_client_strategy.md](./19wisecoin_options_client_strategy.md) | 19wisecoin_options_client_strategy.py | 期权策略生成 |

### 持仓交易处理 (31-33系列)
| 文档 | 源文件 | 说明 |
|------|--------|------|
| [31wisecoin_options_position_deal_taget.md](./31wisecoin_options_position_deal_taget.md) | 31wisecoin_options_position_deal_taget.py | 持仓目标处理 |
| [32wisecoin_options_position_deal_1sell.md](./32wisecoin_options_position_deal_1sell.md) | 32wisecoin_options_position_deal_1sell.py | 卖出处理 |
| [33wisecoin_options_position_deal_2buy.md](./33wisecoin_options_position_deal_2buy.md) | 33wisecoin_options_position_deal_2buy.py | 买入处理 |

### 持仓信息获取 (41-42系列)
| 文档 | 源文件 | 说明 |
|------|--------|------|
| [41wisecoin_options_position.md](./41wisecoin_options_position.md) | 41wisecoin_options_position.py | 持仓获取系统 |
| [42wisecoin_options_position_client.md](./42wisecoin_options_position_client.md) | 42wisecoin_options_position_client.py | 持仓客户端处理 |

### 模拟持仓生成 (51-52系列)
| 文档 | 源文件 | 说明 |
|------|--------|------|
| [51wisecoin_options_position_mock.md](./51wisecoin_options_position_mock.md) | 51wisecoin_options_position_mock.py | 模拟持仓生成器 |
| [52wisecoin_options_position_client_mock.md](./52wisecoin_options_position_client_mock.md) | 52wisecoin_options_position_client_mock.py | 模拟持仓客户端 |

## 数据流图

```
┌─────────────────────────────────────────────────────────────┐
│                      一键执行流程                            │
│                  (06wisecoin_oneclick.py)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. 备份数据 (00wisecoin_options_backup.py)                 │
│  2. 获取期权合约 (01wisecoin-options-ranking.py)            │
│  3. 获取OpenCTP数据 (02wisecoin-openctp-api.py)             │
│  4. 期权分析 (03wisecoin-options-analyze.py)                │
│  5. 计算IV (04wisecoin-options-iv.py)                       │
│  6. 期货分析 (05wisecoin-futures-analyze.py)                │
│  7. 生成开仓方向 (08wisecoin_symbol_lsn.py)                 │
│  8. 获取K线 (09wisecoin-futures-klines.py)                  │
└─────────────────────────────────────────────────────────────┘
```

## 输出文件说明

| 文件名 | 生成脚本 | 说明 |
|--------|----------|------|
| wisecoin-期权品种.xlsx | 01/10/14 | 期权合约列表 |
| wisecoin-期权行情.xlsx | 01/14 | 期权实时行情 |
| wisecoin-期货行情.xlsx | 01/14 | 标的期货行情 |
| wisecoin-期权参考.xlsx | 03/15 | 期权分析结果 |
| wisecoin-期货K线.xlsx | 09/14 | 期货K线数据 |
| wisecoin-持仓.xlsx | 41 | 账户持仓 |
| wisecoin-期权策略.xlsx | 19 | 交易策略 |
| wisecoin-期权套利.xlsx | 19 | 套利机会 |
| wisecoin-symbol-params.json | 02 | 品种参数配置 |
| wisecoin-symbol-lsn.json | 08 | 开仓方向配置 |
| wisecoin-symbol-live.json | 13 | 监控标的配置 |

## 快速开始

1. **一键执行完整流程**
   ```bash
   python 06wisecoin_oneclick.py
   # 或双击 06wisecoin_oneclick.command
   ```

2. **定时自动执行**
   ```bash
   python 07wisecoin_run.py
   ```

3. **实时监控版本**
   ```bash
   python 18wisecoin_options_client_live.py
   ```

## 注意事项

- 所有脚本使用统一的 `UnifiedLogger` 日志系统
- 运行模式 (RUN_MODE) 控制是模拟还是实盘
- 大部分脚本支持异步操作提高效率
- 关键数据支持断点续传