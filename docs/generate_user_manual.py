#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WiseCoin Options 用户手册 PDF 生成器

基于 README.md 内容生成美观的用户手册。

用法：python3 generate_user_manual.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import fitz
except ImportError:
    print("❌ 请先安装 PyMuPDF: pip install PyMuPDF")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.resolve()

# 品牌配色
PRIMARY = (0.15, 0.25, 0.40)      # 深蓝
ACCENT = (0.95, 0.35, 0.15)       # 橙红
SECONDARY = (0.45, 0.55, 0.65)    # 灰蓝
TEXT_DARK = (0.15, 0.15, 0.15)
TEXT_GRAY = (0.5, 0.5, 0.5)
WHITE = (1.0, 1.0, 1.0)
LIGHT_BG = (0.97, 0.98, 0.99)

# A4
PW = 595.28
PH = 841.89
M = 55
CW = PW - 2 * M

FONT_HELV = fitz.Font("helv")
FONT_HELV_B = fitz.Font("hebo")
FONT_CJK = fitz.Font("china-s")
FONT_COUR = fitz.Font("cour")


def text(page, x, y, txt, size=11, color=TEXT_DARK, font=None):
    """绘制文本 - y 是基线位置"""
    if font is None:
        font = FONT_CJK if any(ord(c) > 127 for c in txt) else FONT_HELV
    tw = fitz.TextWriter(page.rect)
    tw.append((x, y), txt, font=font, fontsize=size)
    tw.write_text(page, color=color)


def text_center(page, cx, cy, txt, size=11, color=TEXT_DARK, font=None):
    """绘制居中文本 - cx, cy 是区域中心点"""
    if font is None:
        font = FONT_CJK if any(ord(c) > 127 for c in txt) else FONT_HELV
    x = cx - font.text_length(txt, fontsize=size) / 2
    y = cy + size * 0.3
    tw = fitz.TextWriter(page.rect)
    tw.append((x, y), txt, font=font, fontsize=size)
    tw.write_text(page, color=color)


def text_in_box(page, box_top, box_height, x, txt, size=11, color=TEXT_DARK, font=None, x_offset=8):
    """绘制文本在矩形框内垂直居中"""
    if font is None:
        font = FONT_CJK if any(ord(c) > 127 for c in txt) else FONT_HELV
    cy = box_top + box_height / 2
    y = cy + size * 0.3
    tw = fitz.TextWriter(page.rect)
    tw.append((x + x_offset, y), txt, font=font, fontsize=size)
    tw.write_text(page, color=color)


def rect(page, r, color=None, fill=None, width=0.5):
    page.draw_rect(r, color=color, fill=fill, width=width)


def line(page, x1, y1, x2, y2, color=SECONDARY, width=0.5):
    page.draw_line((x1, y1), (x2, y2), color=color, width=width)


class Manual:
    def __init__(self):
        self.doc = fitz.open()
        self.page = None
        self.y = M
        self.pn = 0

    def np(self):
        self.page = self.doc.new_page(width=PW, height=PH)
        self.y = M
        self.pn += 1

    def br(self, need=50):
        if self.y + need > PH - M - 40:
            self.ft()
            self.np()
            self.hd()
            return True
        return False

    def hd(self):
        line(self.page, M, 42, PW - M, 42, SECONDARY, 1)
        text(self.page, M, 35, "WiseCoin Options", 9, SECONDARY, FONT_HELV_B)

    def ft(self):
        line(self.page, M, PH - 42, PW - M, PH - 42, SECONDARY, 1)
        text_center(self.page, PW / 2, PH - 35, f"— {self.pn} —", 9, SECONDARY)

    def cover(self):
        self.np()
        rect(self.page, fitz.Rect(0, 0, PW, PH), fill=PRIMARY, color=PRIMARY)
        line(self.page, 0, PH * 0.35, PW, PH * 0.35, (0.25, 0.35, 0.5), 3)
        line(self.page, 0, PH * 0.65, PW, PH * 0.65, (0.25, 0.35, 0.5), 3)
        text_center(self.page, PW / 2, PH * 0.42, "WiseCoin Options", 52, WHITE, FONT_HELV_B)
        text_center(self.page, PW / 2, PH * 0.50, "用户手册", 28, (0.85, 0.88, 0.92))
        text_center(self.page, PW / 2, PH * 0.58, f"v2.0  ·  {datetime.now().strftime('%Y年%m月')}", 14, (0.6, 0.65, 0.72))
        text_center(self.page, PW / 2, PH - 75, "基于 Python 的期权分析工具", 13, (0.5, 0.55, 0.62))

    def sec(self, title):
        self.br(60)
        bar_h = 32
        rect(self.page, fitz.Rect(M - 5, self.y, PW - M + 5, self.y + bar_h), fill=LIGHT_BG, color=None)
        rect(self.page, fitz.Rect(M - 5, self.y, M, self.y + bar_h), fill=ACCENT, color=ACCENT)
        text_in_box(self.page, self.y, bar_h, M + 12, title, 18, PRIMARY, FONT_HELV_B)
        self.y += bar_h + 12

    def subsec(self, title):
        self.br(40)
        text(self.page, M, self.y + 4, title, 14, PRIMARY, FONT_HELV_B)
        self.y += 20

    def para(self, txt):
        font = FONT_CJK if any(ord(c) > 127 for c in txt) else FONT_HELV
        lines, ln = [], ""
        for c in txt:
            if font.text_length(ln + c, fontsize=11) > CW - 10:
                lines.append(ln)
                ln = c
            else:
                ln += c
        if ln:
            lines.append(ln)
        for l in lines:
            self.br(18)
            text(self.page, M, self.y + 4, l, 11, TEXT_DARK)
            self.y += 16
        self.y += 6

    def bullets(self, items):
        for item in items:
            self.br(20)
            text_y = self.y + 4
            dot_top = text_y - 5
            rect(self.page, fitz.Rect(M + 4, dot_top, M + 10, dot_top + 6), fill=ACCENT, color=ACCENT)
            font = FONT_CJK if any(ord(c) > 127 for c in item) else FONT_HELV
            lines, ln = [], ""
            for c in item:
                if font.text_length(ln + c, fontsize=11) > CW - 35:
                    lines.append(ln)
                    ln = c
                else:
                    ln += c
            if ln:
                lines.append(ln)
            for l in lines:
                text(self.page, M + 22, text_y, l, 11, TEXT_DARK)
                text_y += 16
            self.y = text_y + 4

    def code(self, txt):
        self.br(50)
        lines = txt.strip().split('\n')
        pad = 10
        lh = 13
        h = len(lines) * lh + pad * 2
        rect(self.page, fitz.Rect(M - 5, self.y, PW - M + 5, self.y + h), fill=(0.12, 0.15, 0.2), color=(0.2, 0.25, 0.3))
        rect(self.page, fitz.Rect(M - 5, self.y, M, self.y + h), fill=ACCENT, color=ACCENT)
        ty = self.y + pad + 3
        for l in lines:
            text(self.page, M + 10, ty, l, 9, (0.85, 0.88, 0.9), FONT_COUR)
            ty += lh
        self.y += h + 12

    def tbl(self, heads, rows, widths=None):
        if widths is None:
            widths = [CW / len(heads)] * len(heads)
        rh, hh = 20, 24
        self.br(hh + len(rows) * rh + 20)
        rect(self.page, fitz.Rect(M, self.y, M + sum(widths), self.y + hh), fill=PRIMARY, color=PRIMARY)
        x = M
        for i, h in enumerate(heads):
            text_in_box(self.page, self.y, hh, x, h, 10, WHITE, FONT_HELV_B)
            x += widths[i]
        self.y += hh
        for ri, row in enumerate(rows):
            self.br(rh)
            fill = LIGHT_BG if ri % 2 == 0 else WHITE
            rect(self.page, fitz.Rect(M, self.y, M + sum(widths), self.y + rh), fill=fill, color=(0.88, 0.9, 0.92))
            x = M
            for i, c in enumerate(row):
                text_in_box(self.page, self.y, rh, x, str(c), 9, TEXT_DARK)
                x += widths[i]
            self.y += rh
        self.y += 12

    def tip(self, txt, warn=False):
        self.br(35)
        box_h = 24
        bg = (1.0, 0.96, 0.92) if warn else (0.92, 0.96, 0.94)
        bd = (0.9, 0.5, 0.3) if warn else (0.3, 0.55, 0.4)
        rect(self.page, fitz.Rect(M - 5, self.y, PW - M + 5, self.y + box_h), fill=bg, color=bd)
        rect(self.page, fitz.Rect(M - 5, self.y, M, self.y + box_h), fill=bd, color=bd)
        icon = "⚠" if warn else "💡"
        text_in_box(self.page, self.y, box_h, M + 12, f"{icon}  {txt}", 10, TEXT_DARK, x_offset=0)
        self.y += box_h + 10

    def save(self, path):
        if self.page:
            self.ft()
        self.doc.save(path)
        self.doc.close()
        print(f"✅ 已生成: {path}")


def generate():
    m = Manual()
    out = PROJECT_ROOT / "WiseCoin_Options_用户手册.pdf"

    # 封面
    m.cover()

    # 一、快速开始
    m.np()
    m.hd()
    m.sec("一、快速开始")
    m.para("智能启动（推荐）：")
    m.code("python3 run.py")
    m.para("自动检测数据文件，缺失则生成数据，然后启动 GUI。其他方式：")
    m.code("python3 run.py --force      # 强制重新生成\npython3 run.py --no-gui     # 只生成数据")
    m.para("一键执行流程：")
    m.bullets(["数据备份 → OpenCTP数据获取 → 期权行情获取", "期权综合分析 → 期货联动分析 → 期货K线获取"])
    m.tip("首次运行约3-10分钟，后续1-2分钟")

    # 二、模块命令
    m.sec("二、模块命令速查表")
    m.para("数据层 (data/)：")
    m.tbl(["命令", "说明", "输出"], [
        ["python3 -m data.backup", "数据备份", "backups/"],
        ["python3 -m data.openctp", "OpenCTP数据", "wisecoin-openctp数据.xlsx"],
        ["python3 -m data.option_quotes", "期权行情", "wisecoin-期权行情.csv"],
        ["python3 -m data.klines", "期货K线", "wisecoin-期货K线.csv"],
    ], [180, 160, 190])
    m.para("CLI层 (cli/)：")
    m.tbl(["命令", "说明", "输出"], [
        ["python3 -m cli.oneclick", "一键执行", "全部文件"],
        ["python3 -m cli.option_analyzer", "期权分析", "wisecoin-期权排行.xlsx"],
        ["python3 -m cli.futures_analyzer", "期货联动", "wisecoin-货权联动.xlsx"],
        ["python3 -m cli.live_gui", "监控GUI", "图形界面"],
    ], [180, 160, 190])

    # 三、输出文件说明
    m.np()
    m.hd()
    m.sec("三、输出文件说明")
    m.tbl(["文件名", "内容"], [
        ["wisecoin-期权行情.csv", "全市场期权+期货实时行情"],
        ["wisecoin-期权排行.xlsx", "评分排名、PCR、最大痛点（7个Sheet）"],
        ["wisecoin-期权参考.xlsx", "52列全字段参考表（含IV/Greeks）"],
        ["wisecoin-货权联动.xlsx", "期权与期货联动分析"],
        ["wisecoin-市场概览.xlsx", "16个Sheet市场全景报告"],
        ["wisecoin-期货K线.csv", "期货日K线历史数据（250根）"],
    ], [200, 350])
    m.para("期权排行包含：期权排行、期权PCR、期权痛点、期权资金、方向型期权、波动率型期权、期权市场。")

    # 四、架构说明
    m.sec("四、架构说明")
    m.code("wisecoin-options-free/\n├── common/    # 公共模块\n├── data/      # 数据层\n├── core/      # 业务层\n├── cli/       # 入口层\n├── tests/     # 单元测试\n└── backups/   # 数据备份")

    # 五、核心层业务逻辑详解
    m.np()
    m.hd()
    m.sec("五、核心层业务逻辑详解")

    m.subsec("5.1 数据模型 (core/models.py)")
    m.para("定义期权、期货、持仓等核心数据结构：")
    m.tbl(["模型", "说明"], [
        ["OptionQuote", "期权行情（代码、行权价、类型、价格、持仓等）"],
        ["FutureQuote", "期货行情（代码、价格、持仓、成交量等）"],
        ["AnalyzedOption", "分析后期权（含评分、信号、分析原因）"],
        ["StrategySignal", "策略信号（方向、数量、评分、策略类型）"],
    ], [150, 400])

    m.subsec("5.2 期权分析器 (core/analyzer.py)")
    m.para("期权多因子分析核心模块，主要功能：")
    m.bullets(["虚实度计算：虚实幅度%、虚实档位分类（深度实值/中度实值/平值/虚值）",
               "价值分解：内在价值、时间价值、时间价值占比、溢价率",
               "保证金计算：卖方保证金、标的期货保证金、杠杆收益",
               "评分系统：杠杆评分(0-30)、时间价值评分(0-20)、流动性评分(0-30)、实值评分(0-20)"])
    m.para("核心类说明：")
    m.tbl(["类名", "功能"], [
        ["OptionAnalyzer", "期权基础指标计算（杠杆、时间价值、价值度）"],
        ["OptionScorer", "多因子评分系统（满分100分）"],
        ["PCRAnalyzer", "P/C Ratio 分析（情绪解读：极度看多~极度看空）"],
        ["MaxPainCalculator", "最大痛点计算（使买方损失最大的价格）"],
        ["OptionTradingClassifier", "交易类型分类（方向型vs波动率型）"],
    ], [170, 380])

    m.subsec("5.3 IV计算器 (core/iv_calculator.py)")
    m.para("基于 Black-Scholes 模型的隐含波动率与 Greeks 计算：")
    m.bullets(["隐含波动率：Newton-Raphson迭代法 + 二分法备用",
               "期权定价：BS模型理论价格计算",
               "Greeks计算：Delta、Gamma、Theta、Vega、Rho",
               "波动率微笑：同一标的不同行权价的IV分布"])
    m.tbl(["参数", "说明"], [
        ["Delta", "价格敏感度：CALL=N(d1), PUT=N(d1)-1"],
        ["Gamma", "Delta变化率：N'(d1)/(Sσ√T)"],
        ["Theta", "时间衰减：每日时间价值损耗"],
        ["Vega", "波动率敏感度：S√T·N'(d1)"],
        ["Rho", "利率敏感度：利率变化对价格影响"],
    ], [100, 450])

    # 六、期货分析器详解
    m.np()
    m.hd()
    m.sec("六、期货分析器详解 (core/futures_analyzer.py)")

    m.subsec("6.1 资金流向分析")
    m.para("基于价格和持仓变化的四象限判断：")
    m.tbl(["状态", "价格", "持仓", "解读"], [
        ["增仓上涨", "↑", "↑", "多头主动建仓（强多）"],
        ["减仓上涨", "↑", "↓", "空头止损离场（弱多）"],
        ["增仓下跌", "↓", "↑", "空头主动建仓（强空）"],
        ["减仓下跌", "↓", "↓", "多头止损离场（弱空）"],
    ], [100, 80, 80, 290])

    m.subsec("6.2 货权联动分析")
    m.para("期货与期权共振/背离检测系统，四层判断框架：")
    m.bullets(["第一层：期货趋势方向（多/空/震荡）",
               "第二层：期权资金结构（看多/看空/波动率）",
               "第三层：期权波动率情绪（狂热/恐慌/筑底/冲高）",
               "第四层：一致性或背离判定"])
    m.para("联动状态输出：")
    m.tbl(["状态", "含义"], [
        ["趋势确认", "期货上涨+CALL主导，趋势延续概率高"],
        ["空头确认", "期货下跌+PUT主导，空头趋势延续"],
        ["顶部警惕", "期货上涨+PUT增仓，注意反转信号"],
        ["抄底信号", "期货下跌+CALL增仓，可能有抄底资金"],
        ["波动率机会", "期货震荡+双向期权放量，适合波动率策略"],
    ], [130, 420])

    m.subsec("6.3 共振评分系统")
    m.para("联动强度模型（总分0-100）：")
    m.tbl(["维度", "权重", "评分内容"], [
        ["价格强度", "30%", "杠杆涨跌幅强度 + 趋势状态得分"],
        ["资金强度", "40%", "期货资金流向 + 期权资金一致性"],
        ["情绪强度", "30%", "PCR偏离度 + 情绪倾向一致性"],
    ], [130, 80, 340])
    m.para("共振等级：强共振(≥7分)、共振(5-6)、中性(3-4)、弱相关(1-2)、背离(0)")

    # 七、Excel文件详细说明
    m.np()
    m.hd()
    m.sec("七、Excel文件详细说明")

    m.subsec("7.1 期权排行.xlsx（7个Sheet）")
    m.tbl(["Sheet名", "内容"], [
        ["期权排行", "所有期权综合评分排名（评分、杠杆、虚实度）"],
        ["方向型期权", "筛选出的方向型交易机会"],
        ["波动率型期权", "筛选出的波动率交易机会"],
        ["期权PCR", "各标的P/C Ratio统计（持仓PCR、成交PCR、资金PCR）"],
        ["期权痛点", "各标的最大痛点价格及距离"],
        ["期权资金", "各标的沉淀资金、成交资金统计"],
        ["期权市场", "期权市场整体概览"],
    ], [130, 420])

    m.subsec("7.2 期权参考.xlsx（52列全字段）")
    m.tbl(["分类", "主要字段"], [
        ["基本信息", "交易所、合约代码、合约名称、期权类型、标的合约"],
        ["价格信息", "行权价、期权价、昨收、今结、虚实幅度%、虚实档位"],
        ["成交持仓", "成交量、成交金额、持仓量、昨持仓量、合约乘数"],
        ["资金数据", "沉淀资金(万)、沉淀资金变化、成交资金(万)、资金合计"],
        ["保证金", "标的期货保证金、卖方保证金、期货保证金率%、期货杠杆"],
        ["时间价值", "内在价值、溢价率%、时间价值、时间占比%、剩余天数"],
        ["收益指标", "收益%、收益年化%、杠杆收益%、杠杆年化%、买方杠杆"],
        ["波动率", "近期波动率、HV20、HV60、隐含波动率"],
        ["Greeks", "Delta、Gamma、Theta、Vega、Rho"],
        ["理论价格", "BS模型理论价格"],
    ], [120, 430])

    m.subsec("7.3 货权联动.xlsx（9个Sheet）")
    m.tbl(["Sheet名", "内容"], [
        ["期货市场", "期货市场整体统计（涨跌、资金流向、情绪）"],
        ["货权联动", "期货期权联动分析核心结果"],
        ["期货品种", "按品种维度汇总分析"],
        ["期货板块", "按板块维度汇总分析（农副、能化、黑色等）"],
        ["期货排行", "期货合约按资金/涨跌排名"],
        ["多头强化", "筛选出的多头强化品种"],
        ["空头强化", "筛选出的空头强化品种"],
        ["背离警示", "期货期权背离品种（风险提示）"],
        ["策略建议", "各品种适合/不适合的策略建议"],
    ], [130, 420])

    m.subsec("7.4 市场概览.xlsx（16个Sheet）")
    m.para("综合市场全景报告，包含期货市场概览、期权市场概览、货权联动汇总、品种分析、板块分析等完整市场视角。")

    # 八、配置说明
    m.np()
    m.hd()
    m.sec("八、配置说明")
    m.para("复制 config.example.json 为 config.json：")
    m.code('{\n  "tq_auth": {\n    "user": "天勤账号",\n    "password": "天勤密码"\n  }\n}')
    m.para("运行模式：")
    m.tbl(["模式", "说明"], [
        ["1", "TqSim 回测"],
        ["2", "TqKq 快期模拟（默认）"],
        ["3", "Simnow 模拟"],
        ["4-8", "期货公司实盘"],
    ], [80, 450])
    m.para("环境变量覆盖：")
    m.code('export TQ_AUTH_USER="用户名"\nexport TQ_AUTH_PASSWORD="密码"')

    # 九、依赖说明
    m.sec("九、依赖说明")
    m.para("必需：Python 3.8+、pandas、openpyxl、numpy、scipy")
    m.para("可选：")
    m.bullets(["tqsdk - 期权行情获取（需要天勤账号）", "PyQt5 - 实时监控GUI", "matplotlib - 图表绑制"])
    m.code("pip install pandas openpyxl numpy scipy\npip install tqsdk PyQt5 matplotlib")

    # 十、常见问题
    m.np()
    m.hd()
    m.sec("十、常见问题")
    m.para("Q1：ModuleNotFoundError: No module named 'tqsdk'")
    m.tip("先激活虚拟环境：source .venv/bin/activate && pip install tqsdk")
    m.para("Q2：天勤账号验证失败")
    m.tip("检查 config.json 账号密码", True)
    m.para("Q3：数据拉取很慢")
    m.tip("首次需5-10分钟，后续会快")
    m.para("Q4：GUI 启动报错")
    m.code("pkill -f cli.live_gui")
    m.para("Q5：Excel 打开报错「文件已损坏」")
    m.tip("从 backups/ 恢复，或运行 python3 run.py --force", True)

    m.save(str(out))
    return str(out)


if __name__ == "__main__":
    print("📖 生成用户手册...")
    p = generate()
    print(f"📄 文件: {p}")
    print(f"📊 大小: {os.path.getsize(p)/1024/1024:.2f} MB")