# 02wisecoin-openctp-api.py - 开发文档

## 文件概述

OpenCTP 数据获取与保证金比率检查工具，用于从 OpenCTP API 获取期货和期权合约信息，并自动更新品种参数配置。

## 作者

playbonze

## 功能描述

1. 从 OpenCTP 公开 API 获取期货和期权合约信息
2. 检查并比较保证金比率
3. 自动更新 `wisecoin-symbol-params.json` 配置文件

## 配置参数

```python
OUTPUT_FILE = "wisecoin-openctp数据.xlsx"
SYMBOL_PARAMS_FILE = "wisecoin-symbol-params.json"
MARKET_FILE_OPT = "wisecoin-期货行情.xlsx"
MARKET_FILE_NO_OPT = "wisecoin-期货行情-无期权.xlsx"
```

## 交易所映射

```python
EXCHANGE_NAMES = {
    "CFFEX": "中国金融期货交易所",
    "CZCE": "郑州商品交易所",
    "DCE": "大连商品交易所",
    "GFEX": "广州期货交易所",
    "INE": "上海国际能源交易中心",
    "SHFE": "上海期货交易所"
}
```

## 核心函数

### `check_margin_ratios(auto_update=False)`

检查并比较保证金比率，支持自动更新配置文件。

**流程：**
1. 加载市场数据（期货行情文件）
2. 识别每个品种的主力合约（成交量+持仓量最大）
3. 从 OpenCTP 数据获取主力合约的保证金比率
4. 与 JSON 配置文件中的比率比较
5. 检测新品种并自动添加

**参数：**
- `auto_update`: 是否自动更新配置文件

**主力合约识别逻辑：**
```python
df_market['activity'] = df_market['volume'] + df_market['open_interest']
main_contracts = df_market.sort_values('activity', ascending=False).drop_duplicates('product_code')
```

**更新内容：**
- `margin_ratio`: 保证金比率
- `volume_multiple`: 合约乘数
- `name`: 品种名称

### `fetch_openctp_data(url, description)`

从 OpenCTP API 获取数据。

**API 端点：**
- 期货合约信息：`http://dict.openctp.cn/instruments?types=futures&areas=China`
- 期权合约信息：`http://dict.openctp.cn/instruments?types=option&areas=China`

**返回：**
- pandas DataFrame 格式的合约信息

### `main()`

主函数，执行完整的数据获取和检查流程。

**命令行参数：**
```bash
python 02wisecoin-openctp-api.py [--auto-update]
```

**流程：**
1. 获取期货合约信息
2. 获取期权合约信息
3. 保存到 Excel
4. 检查保证金比率（自动更新模式）

## 数据处理细节

### 科学计数法处理

保存 JSON 时自动转换科学计数法为小数格式：
```python
# 6.5e-05 -> 0.000065
sci_pattern = re.compile(r'\b-?\d+(\.\d+)?[eE][+-]?\d+\b')
json_str = sci_pattern.sub(replace_sci, json_str)
```

### 品种代码大小写规则

- CFFEX（金融期货）和 CZCE（郑商所）：使用大写
- 其他交易所：使用小写

## 输出文件

| Sheet名称 | 说明 |
|-----------|------|
| 期货合约信息 | 所有期货合约详细信息 |
| 期权合约信息 | 所有期权合约详细信息 |

## 依赖模块

- `requests`: HTTP 请求
- `pandas`: 数据处理
- `json`: JSON 文件处理
- `argparse`: 命令行参数解析
- `shutil`: 文件拷贝

## 使用方式

```bash
# 仅获取数据
python 02wisecoin-openctp-api.py

# 获取数据并自动更新配置
python 02wisecoin-openctp-api.py --auto-update
```

## 输出示例

```
🚀 Starting OpenCTP data fetch...
Fetching Futures Contract Info from http://dict.openctp.cn/instruments?types=futures&areas=China...
✅ Successfully fetched 500 records for Futures Contract Info
Fetching Options Contract Info from http://dict.openctp.cn/instruments?types=option&areas=China...
✅ Successfully fetched 5000 records for Options Contract Info
Saving data to wisecoin-openctp数据.xlsx...
✅ Saved '期货合约信息' sheet
✅ Saved '期权合约信息' sheet
✨ DONE! Total time: 3.45s. File: wisecoin-openctp数据.xlsx
🔍 Checking margin ratios...
✅ All margin ratios and names match, and no new products found.
```

## 注意事项

- 需要网络连接访问 OpenCTP API
- 使用 `--auto-update` 会修改 `wisecoin-symbol-params.json`
- 更新后会自动拷贝一份到上级目录