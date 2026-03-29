# WiseCoin 期权分析系统

> 更新时间: 2026-03-29

基于 Python 的期权分析工具，支持期权品种筛选、行情获取、波动率分析等功能。

---

## 一、快速开始

### 快速启动

```bash
cd /Users/playbonze/pb-quant/26WiseCoin/wisecoin-options-free
python3 run.py
```

该模式会自动：
1. 检测必需的数据文件是否存在（支持 CSV/XLSX 格式）
2. 如缺失则运行 `oneclick` 生成数据
3. 启动实时监控 GUI

### 其他启动方式

```bash
python3 run.py --force      # 强制重新生成数据后启动GUI
python3 run.py --no-gui     # 只生成数据，不启动GUI
```

### macOS 双击启动

双击 `run.command` 文件即可启动系统（自动清理旧进程）。

### 一键执行

```bash
python3 -m cli.oneclick
```

一键执行依次运行：
1. 数据备份
2. OpenCTP数据获取
3. 期权行情获取
4. 期权综合分析
5. 期货联动分析
6. 期货K线获取

---

## 二、模块命令速查表

### 数据层 (data/)

| 命令 | 说明 | 输出文件 |
|------|------|----------|
| `python3 -m data.backup` | 数据备份 | `backups/YYYYMMDD_HHMM/` |
| `python3 -m data.backup list` | 列出所有备份 | - |
| `python3 -m data.backup clean` | 清理旧备份（保留10个） | - |
| `python3 -m data.openctp` | OpenCTP数据获取 | `wisecoin-openctp数据.xlsx` |
| `python3 -m data.option_quotes` | 期权+期货行情获取 | `wisecoin-期权行情.csv` 等 |
| `python3 -m data.klines` | 期货K线获取 | `wisecoin-期货K线.csv` (250根K线) |
| `python3 -m data.live_symbol` | 实时监控配置 | `wisecoin-symbol-live.json` |

### 核心层 (core/)

核心层模块被CLI层调用，不直接作为命令行工具使用：

| 模块 | 主要类/函数 | 说明 |
|------|-------------|------|
| `core.models` | `OptionQuote`, `FutureQuote`, `AnalyzedOption`, `StrategySignal` | 数据模型定义 |
| `core.analyzer` | `OptionAnalyzer` | 期权多因子分析 |
| `core.iv_calculator` | `IVCalculator` | 隐含波动率与Greeks计算 |
| `core.futures_analyzer` | `FuturesAnalyzer`, `generate_market_summary`, `generate_product_analysis` | 期货分析、货权联动 |

### CLI层 (cli/)

| 命令 | 说明 | 输出文件 |
|------|------|----------|
| `python3 -m cli.oneclick` | 一键执行全部流程 | 见上方说明 |
| `python3 -m cli.option_analyzer` | 期权综合分析 | `wisecoin-期权排行.xlsx`<br>`wisecoin-期权参考.xlsx` |
| `python3 -m cli.futures_analyzer` | 期货联动分析 | `wisecoin-货权联动.xlsx`<br>`wisecoin-市场概览.xlsx` |
| `python3 -m cli.live_gui` | 实时监控GUI | 图形界面 |

---

## 三、输出文件说明

### 3.1 数据文件

| 文件名 | 格式 | 说明 |
|--------|------|------|
| `wisecoin-期权行情.csv` | CSV | 期权实时行情（优先格式） |
| `wisecoin-期权行情.xlsx` | XLSX | 期权实时行情（兼容格式） |
| `wisecoin-期货行情.xlsx` | XLSX | 标的期货行情 |
| `wisecoin-期权品种.xlsx` | XLSX | 期权品种汇总 |
| `wisecoin-期货K线.csv` | CSV | 期货日K线数据（250根，优先格式） |
| `wisecoin-期货K线.xlsx` | XLSX | 期货日K线数据（兼容格式） |
| `wisecoin-openctp数据.xlsx` | XLSX | OpenCTP补充数据 |
| `wisecoin-symbol-live.json` | JSON | 实时监控标的配置 |

> **提示**: 当存在 `wisecoin-symbol-live.json` 时，`data.option_quotes` 模块会自动读取该配置，只获取配置中指定的标的合约的期权数据，大幅降低数据获取开销。

### 3.2 分析文件

| 文件名 | 说明 | 主要工作表 |
|--------|------|------------|
| `wisecoin-期权排行.xlsx` | 期权排行分析 | 期权排行、方向型期权、波动率型期权、期权PCR、期权痛点、期权资金 |
| `wisecoin-期权参考.xlsx` | 期权参考(含IV/Greeks) | 期权参考 (52列全字段) |
| `wisecoin-货权联动.xlsx` | 货权联动分析 | 期货市场、货权联动、期货品种、期货板块、期货排行等9个工作表 |
| `wisecoin-市场概览.xlsx` | 市场概览汇总 | 期货市场、期权市场、货权联动、期货品种、期货板块等16个工作表 |

### 3.3 期权参考.xlsx 字段说明 (52列)

| 分类 | 字段 |
|------|------|
| 基本信息 | 交易所、合约代码、合约名称、期权类型、标的合约、标的品种名称、标的现价 |
| 价格信息 | 行权价、期权价、昨收、今结、昨结、虚实幅度%、虚实档位 |
| 成交持仓 | 成交量、成交金额、持仓量、昨持仓量、合约乘数、最小跳动 |
| 资金数据 | 沉淀资金(万)、沉淀资金变化(万)、成交资金(万)、资金合计(万) |
| 保证金 | 标的期货保证金、卖方保证金、期货保证金率%、期货杠杆 |
| 时间价值 | 内在价值、溢价率%、时间价值、时间占比%、剩余天数、到期日、交割年月 |
| 收益指标 | 收益%、收益年化%、杠杆收益%、杠杆年化%、买方期权费、买方杠杆 |
| 波动率 | 近期波动率、HV20、HV60、隐含波动率 |
| Greeks | Delta、Gamma、Theta、Vega、Rho |
| 理论价格 | 理论价格 (BS模型) |

---

## 四、架构说明

```
wisecoin-options-free/
├── common/                 # 公共模块
│   ├── config.py          # 配置管理（支持TqAuth、实盘账户）
│   ├── logger.py          # 日志系统
│   ├── exceptions.py      # 异常定义
│   ├── metrics.py         # 性能指标
│   ├── excel_io.py        # Excel读写工具
│   └── error_handler.py   # 错误处理
│
├── data/                   # 数据层
│   ├── __init__.py        # 延迟导入
│   ├── backup.py          # 数据备份（最多保留10个）
│   ├── cache.py           # 数据缓存
│   ├── openctp.py         # OpenCTP数据获取
│   ├── option_quotes.py   # 期权行情获取
│   ├── klines.py          # K线数据获取
│   ├── live_symbol.py     # 实时监控配置生成
│   └── tqsdk_client.py    # TqSDK客户端封装
│
├── core/                   # 核心层
│   ├── models.py          # 数据模型定义
│   ├── analyzer.py        # 期权分析器
│   ├── iv_calculator.py   # IV与Greeks计算
│   └── futures_analyzer.py # 期货分析器
│
├── cli/                    # CLI层
│   ├── oneclick.py        # 一键执行
│   ├── scheduler.py       # 定时调度
│   ├── option_analyzer.py # 期权分析CLI
│   ├── futures_analyzer.py # 期货分析CLI
│   └── live_gui.py        # 实时监控GUI
│
├── tests/                  # 测试目录
│   └── test_*.py          # 单元测试文件
│
├── backups/                # 备份目录（最多10个）
│
├── run.py                  # 智能启动入口
├── run.command             # macOS双击启动脚本
├── config.json             # 账号配置文件
└── config.example.json     # 配置示例文件
```

---

## 五、配置说明

### 配置文件

项目根目录下的 `config.json` 用于存储账号配置：

```bash
# 复制示例配置文件
cp config.example.json config.json

# 编辑配置文件，填入真实账号信息
vim config.json
```

### 配置文件结构

```json
{
    "tq_auth": {
        "user": "天勤账号",
        "password": "天勤密码"
    },
    "accounts": {
        "3": {
            "broker": "simnow",
            "account": "Simnow账号",
            "password": "Simnow密码"
        },
        "4": {
            "broker": "期货公司名称",
            "account": "实盘账号",
            "password": "实盘密码"
        }
    }
}
```

### 环境变量覆盖

环境变量优先级高于配置文件：

```bash
# TqAuth 认证
export TQ_AUTH_USER="your_username"
export TQ_AUTH_PASSWORD="your_password"

# 实盘账户配置
export TQ_BROKER_4="broker_name"
export TQ_ACCOUNT_4="account_number"
export TQ_PASSWORD_4="account_password"
```

### 运行模式

| 模式 | 说明 |
|------|------|
| 1 | TqSim 回测 |
| 2 | TqKq 快期模拟（默认） |
---

## 六、依赖说明

### 必需依赖
- Python 3.8+
- pandas
- openpyxl
- numpy
- scipy

### 可选依赖
- **tqsdk**: 期权行情获取（需要天勤账号）
- **PyQt5**: 实时监控GUI
- **matplotlib**: 图表绑制

### 安装依赖

```bash
pip install pandas openpyxl numpy scipy
pip install tqsdk           # 行情获取
pip install PyQt5 matplotlib  # GUI和图表
```

---

## 七、常见问题

### Q1: 运行 `python3 -m data.xxx` 报错 "No module named 'data'"
**A:** 确保在项目根目录下运行命令：
```bash
cd /Users/playbonze/pb-quant/26WiseCoin/wisecoin-options-free
python3 -m data.backup
```

### Q2: TqSDK 报错 "TqSDK 未安装"
**A:** 安装 TqSDK：
```bash
pip install tqsdk
```

### Q3: GUI显示某些字段为空
**A:** 确保 `wisecoin-市场概览.xlsx` 和 `wisecoin-期权参考.xlsx` 文件存在。重新运行：
```bash
python3 -m cli.option_analyzer
python3 -m cli.futures_analyzer
```

### Q4: 备份目录产生过多备份
**A:** 新版本已优化，每次创建备份后自动清理，最多保留10个。

---

## 八、更新日志

### 2026-03-29
- 优化 README.md 文档，修正目录结构描述
- 数据文件支持 CSV 格式（优先使用）

### 2026-03-26
- 完成架构重构，代码量从 34,286 行减少到 14,701 行 (-57%)
- 新增 `run.py` 智能启动入口
- 新增 `run.command` macOS启动脚本（自动清理旧进程）
- 新增 `data/live_symbol.py` 实时监控配置模块
- 新增 `config.json` 账号配置文件（支持 TqAuth 和实盘账户）
- 新增 `cli/futures_analyzer.py` 期货品种、期货板块分页
- 优化 `common/config.py` 支持从配置文件加载账号
- 优化 `data/tqsdk_client.py` 移除硬编码账号，从 Config 读取
- 优化 `data/openctp.py` 自动创建 symbol-params.json
- 优化 `data/option_quotes.py` 支持 wisecoin-symbol-live.json 过滤标的
- 优化 `cli/live_gui.py` 刷新数据按钮调用 oneclick 模块
- 优化 `data/backup.py` 自动清理，最多保留10个备份

---

## 九、联系方式

如有问题，请提交 Issue 到项目仓库。