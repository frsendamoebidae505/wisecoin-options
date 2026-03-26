# 41wisecoin_options_position.py - 开发文档

## 文件概述

期权持仓获取系统，获取账户持仓信息并导出为 Excel。

## 作者

playbonze

## 功能描述

1. 连接交易账户
2. 获取所有持仓信息
3. 导出到 Excel 文件

## 核心函数

### `export_positions(api)`

异步函数，获取并导出持仓。

**流程：**
1. 等待数据同步
2. 调用 `api.get_position()` 获取所有持仓
3. 转换为 DataFrame
4. 导出到 Excel

**输出文件：** `wisecoin-持仓.xlsx`

## 运行模式配置

| RUN_MODE | 说明 | 账户类型 |
|----------|------|----------|
| 1 | 回测模式 | TqSim |
| 2 | 快期模拟 | TqKq |
| 4 | 渤海期货 | 实盘 |
| 6 | 金信期货 | 实盘 |
| 9 | 宏源期货 | 实盘 |

### `get_api()`

根据 RUN_MODE 初始化 TqApi。

```python
def get_api():
    if RUN_MODE == 9:
        return TqApi(TqAccount('H宏源期货', '账户', '密码'), ...)
    # ...
```

## 使用方式

```bash
python 41wisecoin_options_position.py
```

## 输出示例

```
正在获取账户持仓信息...
正在导出 5 条持仓记录到 wisecoin-持仓.xlsx...
✅ 导出完成。
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`: 数据处理
- `asyncio`: 异步编程

## 注意事项

- 需要配置正确的账户信息
- 持仓数据包含多空头信息