# WiseCoin 期权分析系统

> 架构重构版本 | 更新时间: 2026-03-26

基于 Python 的期货期权量化分析平台，支持期权品种筛选、行情获取、波动率分析、策略生成等功能。

---

## 一、快速开始

### 智能启动（推荐）

```bash
cd /Users/playbonze/pb-quant/26WiseCoin/wisecoin-options-free
python3 run.py
```

智能模式会自动：
1. 检测必需的 xlsx 文件是否存在
2. 如缺失则运行 `oneclick` 生成数据
3. 检测并清理旧的 GUI 进程
4. 启动实时监控 GUI

### 其他启动方式

```bash
python3 run.py --force      # 强制重新生成数据后启动GUI
python3 run.py --no-gui     # 只生成数据，不启动GUI
python3 run.py --scheduler  # 启动定时调度
python3 run.py --live       # 仅启动实时监控GUI
```

### 一键执行

```bash
python3 -m cli.oneclick
```

一键执行依次运行：
1. 数据备份
2. 期权行情获取（含标的期货行情）
3. OpenCTP数据获取
4. 期权综合分析
5. 期货联动分析
6. 实时监控配置生成
7. 期货K线获取

---

## 二、模块命令速查表

### 数据层 (data/)

| 命令 | 说明 | 输出文件 |
|------|------|----------|
| `python3 -m data.backup` | 数据备份 | `backups/YYYYMMDD_HHMM/` |
| `python3 -m data.backup list` | 列出所有备份 | - |
| `python3 -m data.backup clean` | 清理旧备份（保留10个） | - |
| `python3 -m data.option_quotes` | 期权+期货行情获取 | `wisecoin-期权行情.xlsx` 等 |
| `python3 -m data.openctp` | OpenCTP数据获取 | `wisecoin-openctp数据.xlsx` |
| `python3 -m data.klines` | 期货K线获取 | `wisecoin-期货K线.xlsx` |
| `python3 -m data.live_symbol` | 实时监控配置 | `wisecoin-symbol-live.json` |

### 核心层 (core/)

核心层模块被CLI层调用，不直接作为命令行工具使用：

| 模块 | 类 | 说明 |
|------|-----|------|
| `core.analyzer` | `OptionAnalyzer`, `OptionScorer`, `PCRAnalyzer`, `MaxPainCalculator` | 期权多因子分析 |
| `core.iv_calculator` | `IVCalculator` | 隐含波动率与Greeks计算 |
| `core.futures_analyzer` | `FuturesAnalyzer` | 期货分析、货权联动 |

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

| 文件名 | 说明 | 工作表 |
|--------|------|--------|
| `wisecoin-期权行情.xlsx` | 期权实时行情 | 按品种分类的Sheet |
| `wisecoin-期货行情.xlsx` | 标的期货行情 | 按品种分类的Sheet |
| `wisecoin-期权品种.xlsx` | 期权品种汇总 | Summary + 各品种Sheet |
| `wisecoin-期货K线.xlsx` | 期货日K线数据 | Summary + 各合约Sheet (250根K线) |
| `wisecoin-openctp数据.xlsx` | OpenCTP补充数据 | 多Sheet |
| `wisecoin-symbol-live.json` | 实时监控标的配置 | 标的合约列表 (JSON数组)，用于过滤期权数据 |

> **提示**: 当存在 `wisecoin-symbol-live.json` 时，`data.option_quotes` 模块会自动读取该配置，只获取配置中指定的标的合约的期权数据，大幅降低数据获取开销。

### 3.2 分析文件

| 文件名 | 说明 | 工作表 |
|--------|------|--------|
| `wisecoin-期权排行.xlsx` | 期权排行分析 | 期权排行、方向型期权、波动率型期权、期权PCR、期权痛点、期权资金 |
| `wisecoin-期权参考.xlsx` | 期权参考(含IV/Greeks) | 期权参考 (52列全字段) |
| `wisecoin-货权联动.xlsx` | 货权联动分析 | 期货市场、货权联动、期货品种、期货板块、期货排行、期货涨跌、期货看多、期货看空、期货资金 |
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
│   ├── config.py          # 配置管理
│   ├── logger.py          # 日志系统
│   └── exceptions.py      # 异常定义
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
│   ├── analyzer.py        # 期权分析器
│   ├── iv_calculator.py   # IV与Greeks计算
│   └── futures_analyzer.py # 期货分析器
│
├── strategy/               # 策略层
│   ├── evaluator.py       # 策略评估
│   ├── signals.py         # 信号生成
│   └── arbitrage.py       # 套利检测
│
├── trade/                  # 交易层
│   ├── executor.py        # 订单执行
│   ├── position.py        # 持仓管理
│   └── position_mock.py   # 模拟持仓
│
├── cli/                    # CLI层
│   ├── oneclick.py        # 一键执行
│   ├── scheduler.py       # 定时调度
│   ├── option_analyzer.py # 期权分析CLI
│   ├── futures_analyzer.py # 期货分析CLI
│   └── live_gui.py        # 实时监控GUI
│
├── run.py                  # 智能启动入口
├── run.command             # macOS双击启动脚本
└── backups/                # 备份目录（最多10个）
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
            "broker": "渤海期货",
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

# 实盘账户配置（运行模式3-8需要）
export TQ_BROKER_4="broker_name"
export TQ_ACCOUNT_4="account_number"
export TQ_PASSWORD_4="account_password"
```

### 运行模式
| 模式 | 说明 |
|------|------|
| 1 | TqSim 回测 |
| 2 | TqKq 快期模拟（默认） |
| 3 | Simnow 模拟 |
| 4-8 | 各期货公司实盘 |

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
pip install tqsdk  # 行情获取
pip install PyQt5 matplotlib  # GUI和图表
```

---

## 八、迁移对应表

原始脚本与新模块对应关系：

### 数据层

| 原始脚本 | 新模块 | 说明 |
|----------|--------|------|
| `00wisecoin_options_backup.py` | `data.backup` | 数据备份 |
| `00wisecoin_options_backup_clean.py` | `data.backup clean` | 备份清理 |
| `01wisecoin-options-ranking.py` | `data.option_quotes` | 期权合约获取 |
| `02wisecoin-openctp-api.py` | `data.openctp` | OpenCTP数据 |
| `09wisecoin-futures-klines.py` | `data.klines` | K线获取 |
| `13wisecoin_options_live_symbol.py` | `data.live_symbol` | 实时监控配置 |
| `14wisecoin_options_client_data.py` | `data.option_quotes` | 期权数据 |
| `14wisecoin_options_client_data_klines.py` | `data.klines` | K线获取CLI |

### 核心层

| 原始脚本 | 新模块 | 说明 |
|----------|--------|------|
| `03wisecoin-options-analyze.py` | `core.analyzer` + `cli.option_analyzer` | 期权分析 |
| `04wisecoin-options-iv.py` | `core.iv_calculator` + `cli.option_analyzer` | IV计算(已整合) |
| `05wisecoin-futures-analyze.py` | `core.futures_analyzer` + `cli.futures_analyzer` | 期货分析 |

### CLI层

| 原始脚本 | 新模块 | 说明 |
|----------|--------|------|
| `06wisecoin_oneclick.py` | `cli.oneclick` | 一键执行 |
| `07wisecoin_run.py` | `cli.scheduler` | 定时调度 |
| `18wisecoin_options_client_live.py` | `cli.live_gui` | 实时监控GUI |

### 代码量对比

| 指标 | 原始文件 | 新模块 | 变化 |
|------|----------|--------|------|
| 总行数 | 34,286 | 14,701 | -57.1% |
| 文件数 | 28 | 按层级组织 | 结构化 |

---

## 九、常见问题

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

## 十、更新日志

### 2026-03-26
- 完成架构重构，代码量从 34,286 行减少到 14,701 行 (-57%)
- 新增 `run.py` 智能启动入口
- 新增 `run.command` macOS启动脚本（自动清理旧进程）
- 新增 `data/live_symbol.py` 实时监控配置模块
- 新增 `config.json` 账号配置文件（支持 TqAuth 和实盘账户）
- 新增 `cli/futures_analyzer.py` 期货品种、期货板块分页
- 优化 `common/config.py` 支持从配置文件加载账号
- 优化 `data/tqsdk_client.py` 移除硬编码账号，从 Config 读取
- 优化 `data/openctp.py` 自动创建 symbol-params.json，路径统一到项目根目录
- 优化 `data/option_quotes.py` 支持 wisecoin-symbol-live.json 过滤标的，降低数据获取开销
- 优化 `cli/live_gui.py` 刷新数据按钮调用 oneclick 模块，保证数据处理一致性
- 优化 `cli/live_gui.py` 路径处理，移除冗余备份逻辑
- 优化 `data/backup.py` 自动清理，最多保留10个备份
- 修复 `data/backup.py` 递归复制问题
- 修复 `data/live_symbol.py` 日志导入错误，兼容多种列名
- 测试状态: 310 passed, 7 failed, 3 errors

---

## 十一、联系方式

如有问题，请提交 Issue 到项目仓库。