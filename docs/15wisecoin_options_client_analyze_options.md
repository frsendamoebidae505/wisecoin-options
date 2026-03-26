# 15wisecoin_options_client_analyze_options.py - 开发文档

## 文件概述

期权分析模块（实时监控版本），对期权数据进行深度分析和策略筛选。

## 作者

playbonze

## 功能描述

1. 读取临时目录中的期权行情数据
2. 执行期权多因子评分
3. 筛选符合条件的期权合约
4. 生成期权参考数据

## 核心配置

```python
TEMP_DIR = "wisecoin_options_client_live_temp"
```

## 输入文件

| 文件名 | 说明 |
|--------|------|
| wisecoin-期权行情.xlsx | 期权实时行情 |
| wisecoin-期货行情.xlsx | 标的期货行情 |

## 输出文件

| 文件名 | 说明 |
|--------|------|
| wisecoin-期权参考.xlsx | 期权参考数据（含评分和筛选结果） |

## 运行模式

RUN_MODE = 2（TqKq 快期模拟）

## 使用方式

```bash
python 15wisecoin_options_client_analyze_options.py
```

## 注意事项

- 需要先运行 `14wisecoin_options_client_data.py` 获取行情数据
- 输出完成标志：`期权参考数据生成完成`

## 详细文档

由于分析逻辑复杂，建议直接阅读源码了解具体分析算法。