# 16wisecoin_options_client_iv.py - 开发文档

## 文件概述

期权隐含波动率计算模块（实时监控版本）。

## 作者

playbonze

## 功能描述

1. 读取期权行情和参考数据
2. 计算各期权的隐含波动率
3. 生成波动率微笑曲线数据

## 核心配置

```python
TEMP_DIR = "wisecoin_options_client_live_temp"
```

## 隐含波动率计算

使用 TqSDK 的期权定价函数：
```python
from tqsdk.ta import OPTION_IMPV, OPTION_GREEKS
```

## 使用方式

```bash
python 16wisecoin_options_client_iv.py
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理

## 注意事项

- 需要先运行期权分析脚本
- IV 计算需要有效的期权价格数据