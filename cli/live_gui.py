import sys
import time
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
                             QHeaderView, QComboBox, QPushButton, QGroupBox,
                             QGridLayout, QSplitter, QMessageBox, QTabWidget, QDialog, QFrame,
                             QStyledItemDelegate, QStyleOptionViewItem)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont
import datetime
import shutil
import glob
import subprocess
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import griddata
from scipy.stats import kurtosis, skew
import platform
import re
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as OpenpyxlImage
import io


def _truncate_text(text: str, max_chars: int = 50) -> str:
    """
    截断文本以避免 UI 过宽。

    Args:
        text: 原始文本
        max_chars: 最大字符数

    Returns:
        截断后的文本
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."

# 配置matplotlib中文显示
if platform.system() == 'Darwin':
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
elif platform.system() == 'Windows':
    plt.rcParams['font.sans-serif'] = ['SimHei']
else:
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class AlignmentDelegate(QStyledItemDelegate):
    """强制对齐代理"""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # 0: 指标 (Left), 1: 数值 (Right), 2: 说明 (Left)
        col = index.column()
        if col == 0: # 指标
            option.displayAlignment = Qt.AlignLeft | Qt.AlignVCenter
        elif col == 1: # 数值
            option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter
        elif col == 2: # 说明
            option.displayAlignment = Qt.AlignLeft | Qt.AlignVCenter
        else:
            # 兜底：尝试判断内容是不是数字
            try:
                # 获取列名不太方便，这里简单假设其他列都左对齐，除非是最后一列
                option.displayAlignment = Qt.AlignLeft | Qt.AlignVCenter
            except:
                pass



class ScriptRunner(QThread):
    """
    后台脚本执行线程
    按顺序执行数据流水线模块，并在每一步完成后通知 UI。
    调用 cli.oneclick 模块保证数据处理的一致性。
    """
    progress_signal = pyqtSignal(str)  # 状态消息
    finished_signal = pyqtSignal(bool, str)  # 成功/失败, 消息

    def __init__(self, project_root):
        super().__init__()
        self.project_root = project_root
        self.python_exe = sys.executable

    def run(self):
        """执行一键数据处理流程"""
        start_time = time.time()
        try:
            self.progress_signal.emit("启动一键数据处理...")

            # 调用 cli.oneclick 模块
            cmd = [self.python_exe, '-m', 'cli.oneclick']

            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # 实时读取输出
            current_step = ""
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                # 解析关键进度信息
                if '🚀' in line or '步骤' in line or '开始执行' in line:
                    current_step = line
                    self.progress_signal.emit(line)
                elif '✅' in line or '完成' in line:
                    self.progress_signal.emit(line)
                elif '❌' in line or '失败' in line:
                    self.progress_signal.emit(line)
                # 显示模块进度
                elif '│' in line:
                    self.progress_signal.emit(line)

            process.wait()

            if process.returncode != 0:
                raise Exception(f"数据处理失败 (返回码 {process.returncode})")

            elapsed = time.time() - start_time
            self.finished_signal.emit(True, f"数据刷新完成 (耗时 {elapsed:.1f}s)")

        except Exception as e:
            self.finished_signal.emit(False, str(e))


class MarketOverviewWindow(QDialog):
    """市场概览弹出窗口"""
    def __init__(self, project_root, parent=None):
        super().__init__(parent)
        self.project_root = project_root
        self.setWindowTitle("WiseCoin 市场概览")
        self.resize(1600, 900)
        # 窗口关闭时自动销毁
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.init_ui()
        self.load_data()

    def closeEvent(self, event):
        """窗口关闭处理：主动释放数据引用"""
        # 清理表格数据
        self.futures_table.clearContents()
        self.futures_table.setRowCount(0)
        self.options_table.clearContents()
        self.options_table.setRowCount(0)
        # 强制垃圾回收提示（Python会自动处理，但这里显式为None有助于切断引用）
        self.futures_table = None
        self.options_table = None
        super().closeEvent(event)

    def init_ui(self):
        # 极简布局，去除所有多余边框和背景色
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        self.setStyleSheet("background-color: white;")

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1) # 极细分割线
        splitter.setStyleSheet("QSplitter::handle { background-color: #e5e7eb; }")

        # 左侧：期货市场
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        
        lbl_futures = QLabel("期货市场")
        lbl_futures.setStyleSheet("font-size: 15px; font-weight: bold; color: #111827;")
        left_layout.addWidget(lbl_futures)
        
        self.futures_table = self.create_table()
        left_layout.addWidget(self.futures_table)
        
        # 右侧：期权市场
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        lbl_options = QLabel("期权市场")
        lbl_options.setStyleSheet("font-size: 15px; font-weight: bold; color: #111827;")
        right_layout.addWidget(lbl_options)
        
        self.options_table = self.create_table()
        right_layout.addWidget(self.options_table)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        layout.addWidget(splitter)

    def create_table(self):
        table = QTableWidget()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(True) # 保留网格线，专业报表风格
        table.setGridStyle(Qt.SolidLine)
        table.setFocusPolicy(Qt.NoFocus)
        table.setSelectionMode(QTableWidget.NoSelection) # 禁止选中，纯展示
        
        # 极简专业风格：白底黑字，淡灰边框
        # 注意：移除 QTableWidget::item 的 padding 设置，避免干扰对齐
        table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e5e7eb;
                gridline-color: #f3f4f6;
                font-size: 13px;
                background-color: white;
            }
            QTableWidget::item:alternate {
                background-color: #f9fafb;
            }
            QHeaderView::section {
                background-color: #f9fafb;
                color: #4b5563;
                padding: 6px 8px;
                font-weight: 600;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                border-right: 1px solid #f3f4f6;
            }
        """)
        
        # 使用自定义 Delegate 强制对齐
        table.setItemDelegate(AlignmentDelegate(table))
        
        return table

    def load_data(self):
        file_path = self.project_root / 'wisecoin-市场概览.xlsx'
        if not file_path.exists():
            return

        try:
            df_futures = None
            df_options = None
            with pd.ExcelFile(file_path) as xl:
                if '期货市场' in xl.sheet_names:
                    df_futures = pd.read_excel(xl, '期货市场')
                    # 仅当数值确实是数字时才尝试转换，否则保留原样（处理如“市场整体偏多”等文本内容）
                    # 移除了强制转numeric的代码，改为在 display 时判断
                    self.fill_table(self.futures_table, df_futures)
                
                if '期权市场' in xl.sheet_names:
                    df_options = pd.read_excel(xl, '期权市场')
                    # 同上，移除强制转换
                    self.fill_table(self.options_table, df_options)
        except Exception as e:
            print(f"加载市场概览数据失败: {e}")

    def fill_table(self, table, df):
        table.setRowCount(df.shape[0])
        table.setColumnCount(df.shape[1])
        headers = df.columns.astype(str).tolist()
        table.setHorizontalHeaderLabels(headers)
        table.setSortingEnabled(False)
        
        # 设置表头对齐方式 (强制)
        for col_idx, col_name in enumerate(headers):
            header_item = table.horizontalHeaderItem(col_idx)
            if header_item:
                # 0: 指标 (Left), 1: 数值 (Right), 2: 说明 (Left)
                if col_idx == 1: # 数值
                    header_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    header_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                val = df.iloc[i, j]
                display_val = ""
                if pd.notna(val):
                    # 智能判断：如果是数字（包括整数和浮点数），格式化；如果是字符串，保留原样
                    if isinstance(val, (int, float)):
                        # 如果是整数（如合约数），不显示小数位；如果是浮点数，保留2位
                        if isinstance(val, int) or val.is_integer():
                             display_val = f"{int(val):,}"
                        else:
                             display_val = f"{val:,.2f}"
                    else:
                        display_val = str(val)
                
                item = QTableWidgetItem(display_val)
                # 设置默认字体颜色 (深灰)
                item.setForeground(QBrush(QColor("#374151")))
                
                col_name = str(df.columns[j]).strip()
                
                # 双重保险：在 Item 上也设置对齐，配合 Delegate
                if j == 1: # 数值
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                
                if j == 0: # 指标
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                
                # 颜色区分逻辑
                val_str = str(val)
                # 1. 文本关键词匹配 (优先级最高)
                if any(k in val_str for k in ['多头', '看多', '上涨', '流入', '偏多', '做多']):
                    item.setForeground(QBrush(QColor("#dc2626"))) # Red 600
                elif any(k in val_str for k in ['空头', '看空', '下跌', '流出', '偏空', '做空']):
                    item.setForeground(QBrush(QColor("#16a34a"))) # Green 600
                
                # 2. 数值列根据指标名称染色
                elif col_name == "数值":
                    try:
                        # 获取当前行的指标名称
                        metric_col_idx = -1
                        for idx, name in enumerate(df.columns):
                            if name.strip() == "指标":
                                metric_col_idx = idx
                                break
                        
                        if metric_col_idx != -1:
                            metric_name = str(df.iloc[i, metric_col_idx])
                            
                            # Case A: 指标名隐含方向 (强制红/绿)
                            if any(k in metric_name for k in ['看多', '多头', '流入', '上涨', '偏多', '做多']):
                                    item.setForeground(QBrush(QColor("#dc2626")))
                            elif any(k in metric_name for k in ['看空', '空头', '流出', '下跌', '偏空', '做空']):
                                    item.setForeground(QBrush(QColor("#16a34a")))
                            
                            # Case B: 指标名隐含波动 (根据正负值红/绿)
                            elif any(k in metric_name for k in ['涨跌', '变动', '方向', '%', '比率', '评分', '沉淀', '资金', '信号']):
                                f_val = 0.0
                                if isinstance(val, (int, float)):
                                    f_val = float(val)
                                elif isinstance(val, str):
                                    clean_val = val.replace('%', '').replace(',', '')
                                    f_val = float(clean_val)

                                if f_val > 0: 
                                    item.setForeground(QBrush(QColor("#dc2626"))) # Red 600
                                elif f_val < 0: 
                                    item.setForeground(QBrush(QColor("#16a34a"))) # Green 600
                    except:
                        pass
                
                table.setItem(i, j, item)
        
        header = table.horizontalHeader()
        cols = [str(c) for c in df.columns.tolist()]
        
        # 自动调整列宽
        table.resizeColumnsToContents()
        
        # 优化特定列宽
        if "说明" in cols:
             header.setSectionResizeMode(cols.index("说明"), QHeaderView.Stretch)
        else:
             header.setSectionResizeMode(QHeaderView.Stretch)

class OptionTShapeWindow(QMainWindow):
    """期权T型报价窗口 - Live 实时版本（每3分钟自动刷新）"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WiseCoin 期权")
        self.setGeometry(50, 50, 1800, 1000)
        
        # 数据存储
        self.market_overview_df = None
        self.option_ref_df = None
        self.klines_data = {}  # 期货K线数据 {symbol: DataFrame}
        self.contract_list = []  # 合约列表（标的+交割月）
        self.current_underlying = None # 当前选中的标的
        self.current_expiry = None     # 当前选中的交割月
        self.product_names = {}  # 品种中文名称映射 {品种代码: 中文名}

        # 项目根目录 - 所有文件读写基于此路径
        self.project_root = Path(__file__).parent.parent.resolve()
        print(f"项目根目录: {self.project_root}")

        # 加载品种中文名称
        self._load_product_names()

        # 自动刷新配置（默认关闭）
        self.auto_refresh_enabled = False
        self.refresh_interval = 180000 * 3 * 3  # 27分钟
        self.countdown_seconds = 180 * 3 * 3
        self.is_refreshing = False # 防止重复刷新

        # 初始化UI
        self.init_ui()

        # 初始加载已有数据（不触发脚本）
        self.load_data()

        # 仅在启用自动刷新时启动定时器
        if self.auto_refresh_enabled:
            self.refresh_timer = QTimer(self)
            self.refresh_timer.timeout.connect(self.auto_refresh_check)
            self.refresh_timer.start(self.refresh_interval)

            self.countdown_timer = QTimer(self)
            self.countdown_timer.timeout.connect(self.update_countdown)
            self.countdown_timer.start(1000)  # 每秒更新
        else:
            self.refresh_timer = None
            self.countdown_timer = None

    def _load_product_names(self):
        """加载品种中文名称映射"""
        # 硬编码指数代码到中文名（中金所股指期权标的）
        # 标的格式如 SSE.000300, SSE.000016, SSE.00852 等
        index_names = {
            # 上交所指数（6位标准代码）
            '000300': '沪深300',
            '000016': '上证50',
            '000852': '中证1000',
            '000903': '中证100',
            '000001': '上证指数',
            # 上交所指数（5位代码，部分系统使用）
            '00300': '沪深300',
            '00016': '上证50',
            '00852': '中证1000',
            '00903': '中证100',
            '00001': '上证指数',
            # 深交所指数
            '399005': '中小板指',
            '399006': '创业板指',
            '399300': '沪深300',
            '399673': '创业板50',
        }
        for code, name in index_names.items():
            self.product_names[code] = name

        # 同时支持期货品种代码（商品期权和国债期权）
        future_names = {
            'TS': '2年期国债',
            'TF': '5年期国债',
            'T': '10年期国债',
            'TL': '30年期国债',
        }
        for code, name in future_names.items():
            self.product_names[code] = name

        try:
            params_file = self.project_root / 'wisecoin-symbol-params.json'
            if params_file.exists():
                with open(params_file, 'r', encoding='utf-8') as f:
                    params = json.load(f)

                # 遍历所有交易所，提取品种名称
                for exchange, products in params.items():
                    if exchange.startswith('_'):  # 跳过说明字段
                        continue
                    if isinstance(products, dict):
                        for product_code, info in products.items():
                            if product_code.startswith('_'):  # 跳过交易所说明
                                continue
                            if isinstance(info, dict) and 'name' in info:
                                # 存储大写的品种代码 -> 中文名称
                                self.product_names[product_code.upper()] = info['name']

                print(f"已加载 {len(self.product_names)} 个品种名称")
        except Exception as e:
            print(f"加载品种名称失败: {e}")

    def is_trading_time(self):
        """判断当前是否为交易时间"""
        now = datetime.datetime.now()
        weekday = now.weekday() # 0-6 (Mon-Sun)
        t = now.time()
        
        # 定义交易时段
        # 日盘: 09:00 - 15:00 (宽容一点到 15:15)
        day_start = datetime.time(9, 0)
        day_end = datetime.time(15, 15)
        
        # 夜盘: 21:00 - 02:30 (次日)
        night_start = datetime.time(21, 0)
        night_end_next_day = datetime.time(2, 30)
        
        # 判断逻辑
        is_trading = False
        
        # 周一至周五: 日盘 + 夜盘
        if 0 <= weekday <= 4:
            if day_start <= t <= day_end:
                 is_trading = True
            elif t >= night_start:
                 is_trading = True
            elif t <= night_end_next_day: # 凌晨属于前一交易日的夜盘
                 is_trading = True
                 
        # 周六: 只有凌晨 (周五夜盘延续)
        elif weekday == 5:
            if t <= night_end_next_day:
                is_trading = True
                
        return is_trading

    def auto_refresh_check(self):
        """自动刷新检查 (只在交易时间触发)"""
        # 重置倒计时
        self.countdown_seconds = 180
        
        if self.is_refreshing:
            return

        if self.is_trading_time():
            self.start_script_runner(is_auto=True)
        else:
            self.status_label.setText("状态：非交易时间，暂停自动刷新")
            self.status_label.setStyleSheet("color: gray;")

    def start_script_runner(self, is_auto=False):
        """启动脚本执行线程"""
        if self.is_refreshing:
            QMessageBox.warning(self, "提示", "数据刷新正在进行中...")
            return

        # 清理旧数据 (关键：删除支持断点续传的文件，强制重新获取)
        try:
            files_to_clean = [
                "wisecoin-期权行情.csv",   # 优先清理CSV格式
                "wisecoin-期权行情.xlsx",  # 兼容旧格式
                "wisecoin-期货行情.xlsx",
                "wisecoin-期货K线.csv",    # 清理CSV格式
                "wisecoin-期货K线.xlsx",   # 兼容旧格式
            ]
            for clean_file in files_to_clean:
                clean_path = self.project_root / clean_file
                if clean_path.exists():
                    clean_path.unlink()
                    print(f"🧹 已清理旧文件以便重新获取: {clean_file}")
        except Exception as e:
            print(f"❌ 清理旧文件失败: {e}")

        # 启动线程
        self.is_refreshing = True
        self.refresh_button.setEnabled(False)
        self.market_overview_button.setEnabled(False)
        
        prefix = "[自动] " if is_auto else "[手工] "
        
        self.runner = ScriptRunner(self.project_root)
        self.runner.progress_signal.connect(
            lambda msg: self.status_label.setText(f"状态：{prefix}{_truncate_text(msg)}")
        )
        self.runner.finished_signal.connect(self.on_script_finished)
        self.runner.start()

    def on_script_finished(self, success, msg):
        """脚本执行完成回调"""
        self.is_refreshing = False
        self.refresh_button.setEnabled(True)
        self.market_overview_button.setEnabled(True)
        
        if success:
            self.status_label.setText(f"状态：{msg}")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            # 重新加载数据到 UI
            self.load_data()
        else:
            self.status_label.setText(f"状态：刷新失败 - {msg}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.warning(self, "刷新失败", msg)

    def update_countdown(self):
        """更新倒计时显示"""
        if self.countdown_seconds > 0:
            self.countdown_seconds -= 1
        
        mins = self.countdown_seconds // 60
        secs = self.countdown_seconds % 60
        
        status_text = f"下次刷新: {mins}:{secs:02d}"
        if not self.is_trading_time():
            status_text += " (非交易时间)"
            
        self.countdown_label.setText(status_text)
    
    def init_ui(self):
        """初始化UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # ========== 顶部控制区 ==========
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("期权合约:"))
        
        # 上一个按钮
        self.prev_button = QPushButton("◀ 上一个")
        self.prev_button.setFixedWidth(80)
        self.prev_button.clicked.connect(self.on_prev_contract)
        controls_layout.addWidget(self.prev_button)
        
        self.contract_combo = QComboBox()
        self.contract_combo.setMinimumWidth(250)
        self.contract_combo.currentTextChanged.connect(self.on_contract_changed)
        controls_layout.addWidget(self.contract_combo)
        
        # 下一个按钮
        self.next_button = QPushButton("下一个 ▶")
        self.next_button.setFixedWidth(80)
        self.next_button.clicked.connect(self.on_next_contract)
        controls_layout.addWidget(self.next_button)
        
        controls_layout.addSpacing(20)
        
        self.refresh_button = QPushButton("🔄 刷新数据")
        self.refresh_button.clicked.connect(lambda: self.start_script_runner(is_auto=False))
        controls_layout.addWidget(self.refresh_button)
        
        
        self.market_overview_button = QPushButton("📊 市场概览")
        self.market_overview_button.clicked.connect(self.show_market_overview)
        controls_layout.addWidget(self.market_overview_button)
        
        controls_layout.addStretch()

        # 倒计时标签（默认隐藏）
        self.countdown_label = QLabel("下次刷新: 27:00")
        self.countdown_label.setStyleSheet("color: #666; font-size: 10pt; margin-right: 10px;")
        self.countdown_label.setVisible(self.auto_refresh_enabled)  # 根据配置显示/隐藏
        controls_layout.addWidget(self.countdown_label)
        
        self.status_label = QLabel("状态：未加载")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        self.status_label.setMaximumWidth(400)  # 限制最大宽度，避免撑大UI
        controls_layout.addWidget(self.status_label)
        
        main_layout.addLayout(controls_layout)
        
        # ========== 上方统计信息区（紧凑布局）==========
        stats_layout = QHBoxLayout()
        
        # 1. 标的信息（精简版）
        self.underlying_stats_group = QGroupBox("标的信息")
        self.underlying_stats_grid = QGridLayout(self.underlying_stats_group)
        self.underlying_stats_grid.setHorizontalSpacing(10)
        self.underlying_stats_grid.setVerticalSpacing(3)
        self.underlying_stat_labels = {}
        
        # 字段映射：GUI标签 -> Excel列名（兼容新旧格式）
        # 货权联动表的列名可能与GUI预期不一致，需要映射
        self.underlying_field_map = {
            "标的合约": "标的合约",
            "期货现价": "期货现价",
            "杠杆涨跌%": "杠杆涨跌%",
            "期货沉淀(亿)": "期货沉淀(亿)",  # 直接使用期货沉淀列
            "期货状态": "期货趋势",          # 映射到期货趋势
            "期货方向": "期货流向",          # 映射到期货流向
        }

        underlying_fields = [
            ("标的合约", "标的合约"),
            ("期货现价", "期货现价"),
            ("杠杆涨跌%", "杠杆涨跌%"),
            ("期货沉淀(亿)", "期货沉淀(亿)"),
            ("期货状态", "期货状态"),
            ("期货方向", "期货方向"),
        ]

        # 一行3个指标
        for idx, (label_text, key) in enumerate(underlying_fields):
            row = idx // 3
            col = (idx % 3) * 2

            label = QLabel(f"{label_text}:")
            label.setStyleSheet("font-size: 10pt;")
            value_label = QLabel("-")
            value_label.setStyleSheet("font-size: 11pt; color: #0066cc;")

            self.underlying_stats_grid.addWidget(label, row, col)
            self.underlying_stats_grid.addWidget(value_label, row, col + 1)
            self.underlying_stat_labels[key] = value_label
        
        stats_layout.addWidget(self.underlying_stats_group)
        
        # 2. 期权信息（精简版）
        self.option_stats_group = QGroupBox("期权信息")
        self.option_stats_grid = QGridLayout(self.option_stats_group)
        self.option_stats_grid.setHorizontalSpacing(10)
        self.option_stats_grid.setVerticalSpacing(3)
        self.option_stat_labels = {}
        
        # 字段映射：期权统计
        self.option_field_map = {
            "期权结构": "期权结构",
            "期权PCR": "期权PCR",
            "期权沉淀(亿)": "期权沉淀(亿)",  # 直接使用期权沉淀列
            "最大痛点": "最大痛点",
            "痛点距离%": "痛点距离%",
            "联动状态": "联动状态",
        }

        option_fields = [
            ("期权结构", "期权结构"),
            ("期权PCR", "期权PCR"),
            ("期权沉淀(亿)", "期权沉淀(亿)"),
            ("最大痛点", "最大痛点"),
            ("痛点距离%", "痛点距离%"),
            ("联动状态", "联动状态"),
        ]

        # 一行3个指标
        for idx, (label_text, key) in enumerate(option_fields):
            row = idx // 3
            col = (idx % 3) * 2

            label = QLabel(f"{label_text}:")
            label.setStyleSheet("font-size: 10pt;")
            value_label = QLabel("-")
            value_label.setStyleSheet("font-size: 11pt; color: #cc6600;")

            self.option_stats_grid.addWidget(label, row, col)
            self.option_stats_grid.addWidget(value_label, row, col + 1)
            self.option_stat_labels[key] = value_label
        
        stats_layout.addWidget(self.option_stats_group)
        stats_layout.setStretch(0, 1)
        stats_layout.setStretch(1, 1) # 调整比例
        
        main_layout.addLayout(stats_layout)
        
        # ========== 3. 联动分析（核心分析 + 波动率曲面信息）==========
        linkage_group = QGroupBox("联动分析")
        linkage_layout = QGridLayout(linkage_group)
        linkage_layout.setHorizontalSpacing(8)
        linkage_layout.setVerticalSpacing(4)
        self.linkage_labels = {}
        
        # 一行6个指标，按逻辑分组
        # 第一行：波动结构
        # 第二行：IV分布
        # 第三行：资金与策略
        linkage_fields = [
            # 第一行（波动结构）
            ("期限结构", "期限结构", 0, 0, "#0066cc"),
            ("倾斜方向", "倾斜方向", 0, 2, "#006666"),
            ("IV/RV比率", "IV/RV比率", 0, 4, "#cc6600"),
            ("期限结构差", "期限结构差", 0, 6, "#0066cc"),
            ("IV倾斜度", "IV倾斜度", 0, 8, "#006666"),
            ("峰度", "峰度", 0, 10, "#cc6600"),

            # 第二行（IV分布）
            ("短期IV", "短期IV", 1, 0, "#0066cc"),
            ("长期IV", "长期IV", 1, 2, "#006666"),
            ("虚值认沽IV", "虚值认沽IV均值", 1, 4, "#cc6600"),
            ("虚值认购IV", "虚值认购IV均值", 1, 6, "#0066cc"),
            ("偏度", "偏度", 1, 8, "#006666"),
            ("合约数量", "合约数量", 1, 10, "#666600"),

            # 第三行（资金与策略）
            ("沉淀合计", "沉淀资金合计(亿)", 2, 0, "#666600"),
            ("市场解读", "市场解读", 2, 2, "#FF0000"),
            ("波曲策略", "推荐策略", 2, 4, "#FF0000"),
            ("适合策略", "适合策略", 2, 6, "#FF0000"),
            ("不适合策略", "不适合策略", 2, 8, "#008800"),
        ]

        for label_text, key, row, col, color in linkage_fields:
            label = QLabel(f"{label_text}:")
            label.setStyleSheet("font-size: 10pt;")
            value_label = QLabel("-")
            value_label.setStyleSheet(f"font-size: 11pt; color: {color}; font-weight: bold;")
            value_label.setWordWrap(True)

            linkage_layout.addWidget(label, row, col)
            linkage_layout.addWidget(value_label, row, col + 1)
            self.linkage_labels[key] = value_label

        # 设置列宽比例
        for i in range(12):
            linkage_layout.setColumnStretch(i, 1)
        
        main_layout.addWidget(linkage_group)
        
        # ========== 中间：期权T型报价表（全字段对称显示）==========
        t_group = QGroupBox("T型报价")
        t_layout = QVBoxLayout(t_group)
        t_layout.setContentsMargins(1, 1, 1, 1)
        t_layout.setSpacing(0)
        
        self.option_t_table = QTableWidget()
        
        # 定义所有显示字段（期权参考的全字段）
        # 排除行权价(中心列), 标的合约/交割年月(表头选择), 交易所/期权类型等
        self.all_ref_cols = [
            '合约代码', '期权价', '涨跌幅%', '成交量', '成交金额', 
            '持仓量', '昨持仓量', '合约乘数', '最小跳动', '沉淀资金(万)', 
            '成交资金(万)', '理论价格', '近期波动率', '隐含波动率', 'Delta', 
            'Gamma', 'Theta', 'Vega', 'Rho', '虚实幅度%', '虚实档位', '内在价值', '溢价率%', 
            '时间价值', '时间占比%', '买方期权费', '买方杠杆', '标的期货保证金', '卖方保证金', 
            '收益%', '收益年化%', '杠杆收益%', '杠杆年化%', '期货保证金率%', '期货杠杆'
        ]
        
        # 左右对称显示这些字段
        put_headers = [f"P-{f}" for f in self.all_ref_cols]
        call_headers = [f"C-{f}" for f in self.all_ref_cols]
        headers = put_headers + ['行权价'] + call_headers
        
        self.option_t_table.setColumnCount(len(headers))
        self.option_t_table.setHorizontalHeaderLabels(headers)
        
        self.option_t_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #999999;
                gridline-color: #cccccc;
                font-size: 10pt;
                background-color: white;
            }
            QTableWidget::item {
                padding: 1px 2px;
                border-right: 1px solid #e0e0e0;
            }
            QHeaderView::section {
                background-color: #4a4a4a;
                color: white;
                padding: 2px 3px;
                border: 1px solid #666666;
                font-weight: bold;
                font-size: 9pt;
            }
            QTableWidget::item:selected {
                background-color: #b3d9ff;
            }
            
            /* 垂直滚动条 - 金黄色风格 */
            QScrollBar:vertical {
                border: none;
                background: #f5f5f5;
                width: 14px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFD700, stop:1 #FFB900);
                min-height: 30px;
                border-radius: 7px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #FFA500;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            /* 水平滚动条 - 金黄色风格 */
            QScrollBar:horizontal {
                border: none;
                background: #f5f5f5;
                height: 14px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFD700, stop:1 #FFB900);
                min-width: 30px;
                border-radius: 7px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #FFA500;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        
        # 设置列宽
        header = self.option_t_table.horizontalHeader()
        for i in range(len(headers)):
            if i == len(self.all_ref_cols):  # 行权价列
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                self.option_t_table.setColumnWidth(i, 90)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.option_t_table.verticalHeader().setVisible(False)
        self.option_t_table.verticalHeader().setDefaultSectionSize(22)  # 设置紧凑行高
        self.option_t_table.setAlternatingRowColors(True)
        self.option_t_table.setSortingEnabled(False)
        self.option_t_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.option_t_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        t_layout.addWidget(self.option_t_table)
        main_layout.addWidget(t_group, stretch=3)
        
        # ========== 下方：图表区（K线 + 波动率曲面 + 微笑曲线）==========
        charts_splitter = QSplitter(Qt.Horizontal)
        
        # 标的K线图（左边1/3）
        kline_group = QGroupBox("标的K线")
        kline_layout = QVBoxLayout(kline_group)
        kline_layout.setContentsMargins(2, 2, 2, 2)
        self.kline_fig = Figure(figsize=(5, 4), dpi=90)
        self.kline_canvas = FigureCanvas(self.kline_fig)
        kline_layout.addWidget(self.kline_canvas)
        
        # 波动率曲面（中间1/3）
        surface_group = QGroupBox("波动率曲面")
        surface_layout = QVBoxLayout(surface_group)
        surface_layout.setContentsMargins(2, 2, 2, 2)
        self.surface_fig = Figure(figsize=(5, 4), dpi=90)
        self.surface_canvas = FigureCanvas(self.surface_fig)
        surface_layout.addWidget(self.surface_canvas)
        
        # 微笑曲线（右边1/3）
        smile_group = QGroupBox("微笑曲线")
        smile_layout = QVBoxLayout(smile_group)
        smile_layout.setContentsMargins(2, 2, 2, 2)
        self.smile_fig = Figure(figsize=(5, 4), dpi=90)
        self.smile_canvas = FigureCanvas(self.smile_fig)
        smile_layout.addWidget(self.smile_canvas)
        
        charts_splitter.addWidget(kline_group)
        charts_splitter.addWidget(surface_group)
        charts_splitter.addWidget(smile_group)
        charts_splitter.setStretchFactor(0, 1)  # K线 1/3
        charts_splitter.setStretchFactor(1, 1)  # 波动率曲面 1/3
        charts_splitter.setStretchFactor(2, 1)  # 微笑曲线 1/3
        
        main_layout.addWidget(charts_splitter, stretch=2)
    
    def load_data(self):
        """加载Excel数据"""
        try:
            self.status_label.setText("状态：加载中...")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            QApplication.processEvents()

            # 读取市场概览
            market_file = self.project_root / 'wisecoin-市场概览.xlsx'
            if not market_file.exists():
                raise FileNotFoundError(f"未找到文件: {market_file}")

            with pd.ExcelFile(market_file) as xl:
                self.market_overview_df = pd.read_excel(xl, sheet_name='货权联动')

            # 读取期权参考
            option_file = self.project_root / 'wisecoin-期权参考.xlsx'
            if not option_file.exists():
                raise FileNotFoundError(f"未找到文件: {option_file}")
            self.option_ref_df = pd.read_excel(option_file, sheet_name='期权参考')

            # 读取波动率曲面数据 (尝试读取，若不存在则忽略)
            self.vol_surface_df = None
            try:
                # 检查是否存在 '波动率曲面' sheet
                xl = pd.ExcelFile(option_file)
                if '波动率曲面' in xl.sheet_names:
                    self.vol_surface_df = pd.read_excel(option_file, sheet_name='波动率曲面')
            except Exception as e:
                print(f"读取波动率曲面失败 (可能未生成): {e}")

            # 读取期货K线数据（支持CSV和XLSX格式）
            klines_file_csv = self.project_root / 'wisecoin-期货K线.csv'
            klines_file_xlsx = self.project_root / 'wisecoin-期货K线.xlsx'

            self.klines_data = {}

            # 优先读取CSV格式
            klines_file = None
            if klines_file_csv.exists():
                klines_file = klines_file_csv
            elif klines_file_xlsx.exists():
                klines_file = klines_file_xlsx

            if klines_file:
                try:
                    if str(klines_file).endswith('.csv'):
                        # CSV格式：直接读取，按symbol分组
                        df_all = pd.read_csv(klines_file)
                        if not df_all.empty and 'symbol' in df_all.columns:
                            for symbol, group_df in df_all.groupby('symbol'):
                                # 过滤 datetime_str 为空的数据
                                if 'datetime_str' in group_df.columns:
                                    group_df = group_df[group_df['datetime_str'].notna() & (group_df['datetime_str'] != '')]
                                if not group_df.empty:
                                    self.klines_data[symbol] = group_df
                            print(f"已加载 {len(self.klines_data)} 个合约的K线数据 (CSV格式)")
                    else:
                        # XLSX格式：读取多个sheet
                        klines_xl = pd.ExcelFile(klines_file)
                        for sheet_name in klines_xl.sheet_names:
                            if sheet_name == 'Summary':
                                continue
                            df = pd.read_excel(klines_xl, sheet_name=sheet_name)
                            # 过滤 datetime_str 为空的数据
                            if 'datetime_str' in df.columns:
                                df = df[df['datetime_str'].notna() & (df['datetime_str'] != '')]
                            if not df.empty:
                                # 恢复原始合约代码 (sheet名用_替换了.)
                                symbol = sheet_name.replace('_', '.', 1)
                                self.klines_data[symbol] = df
                        print(f"已加载 {len(self.klines_data)} 个合约的K线数据 (XLSX格式)")
                except Exception as e:
                    print(f"读取期货K线数据失败: {e}")
            
            # 计算涨跌幅
            if '昨收' in self.option_ref_df.columns and '期权价' in self.option_ref_df.columns:
                self.option_ref_df['涨跌幅%'] = (
                    (self.option_ref_df['期权价'] - self.option_ref_df['昨收']) / 
                    self.option_ref_df['昨收'] * 100
                ).round(2)
            
            # 构建合约列表
            self.build_contract_list()
            
            # 更新视图
            if self.contract_combo.count() > 0:
                self.on_contract_changed(self.contract_combo.currentText())
            
            self.status_label.setText("状态：数据已加载")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            
        except Exception as e:
            error_msg = f"加载数据失败: {str(e)}"
            self.status_label.setText(f"状态：{error_msg}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.critical(self, "错误", error_msg)
    
    def build_contract_list(self):
        """构建合约列表，按期权沉淀资金排序"""
        if self.market_overview_df is None or self.option_ref_df is None:
            return

        if '标的合约' not in self.option_ref_df.columns or '交割年月' not in self.option_ref_df.columns:
            return

        contracts_df = self.option_ref_df[['标的合约', '交割年月']].drop_duplicates()

        # 计算期权沉淀资金（从期权参考表汇总）
        option_deposit_col = None
        if '沉淀资金(万)' in self.option_ref_df.columns:
            option_deposit_col = '沉淀资金(万)'
        elif '沉淀资金(亿)' in self.option_ref_df.columns:
            option_deposit_col = '沉淀资金(亿)'

        if option_deposit_col:
            # 按标的合约汇总期权沉淀资金
            option_capital = self.option_ref_df.groupby('标的合约')[option_deposit_col].sum().reset_index()
            # 如果是万元，转换为亿元
            if option_deposit_col == '沉淀资金(万)':
                option_capital['期权沉淀(亿)'] = option_capital[option_deposit_col] / 10000
            else:
                option_capital['期权沉淀(亿)'] = option_capital[option_deposit_col]
            contracts_df = contracts_df.merge(option_capital[['标的合约', '期权沉淀(亿)']], on='标的合约', how='left')
            contracts_df = contracts_df.sort_values('期权沉淀(亿)', ascending=False, na_position='last')
        else:
            contracts_df = contracts_df.sort_values(['标的合约', '交割年月'])

        self.contract_list = []
        for _, row in contracts_df.iterrows():
            underlying = str(row['标的合约'])
            expiry = str(row['交割年月'])
            deposit = row.get('期权沉淀(亿)', None)

            # 提取品种代码并获取中文名称
            product_code = self._extract_product_code(underlying)
            product_name = self.product_names.get(product_code, '')

            # 构建显示文本：品种代码【中文名】交割月 (沉淀:xx亿)
            display_parts = []
            if product_name:
                display_parts.append(f"{product_code}【{product_name}】")
            else:
                display_parts.append(underlying)
            display_parts.append(expiry)

            display_text = ' '.join(display_parts)
            if pd.notna(deposit):
                display_text += f" (沉淀:{deposit:.2f}亿)"

            self.contract_list.append({
                'display': display_text,
                'underlying': underlying,
                'expiry': expiry
            })

        self.contract_combo.blockSignals(True)
        self.contract_combo.clear()
        self.contract_combo.addItems([c['display'] for c in self.contract_list])

        # 尝试通过持久化标识(标的+交割月)还原选择
        if self.current_underlying and self.current_expiry:
            target_idx = -1
            for idx, c in enumerate(self.contract_list):
                if c['underlying'] == self.current_underlying and c['expiry'] == self.current_expiry:
                    target_idx = idx
                    break
            if target_idx >= 0:
                self.contract_combo.setCurrentIndex(target_idx)
            elif self.contract_list:
                self.contract_combo.setCurrentIndex(0)
        elif self.contract_list:
            self.contract_combo.setCurrentIndex(0)
        self.contract_combo.blockSignals(False)

        # 更新导航按钮状态
        self._update_nav_buttons()
    
    def on_contract_changed(self, contract_text):
        """合约变化时"""
        if not contract_text or not self.contract_list:
            return
        
        contract_info = None
        for c in self.contract_list:
            if c['display'] == contract_text:
                contract_info = c
                break
        
        if contract_info:
            self.current_underlying = contract_info['underlying']
            self.current_expiry = contract_info['expiry']
            self.update_option_t_view(contract_info['underlying'], contract_info['expiry'])
        
        # 更新导航按钮状态
        self._update_nav_buttons()

    def show_market_overview(self):
        """显示市场概览窗口"""
        # 每次创建新实例，弹窗时加载数据
        dialog = MarketOverviewWindow(self.project_root, self)
        dialog.exec_()
    
    def on_prev_contract(self):
        """切换到上一个合约"""
        current_idx = self.contract_combo.currentIndex()
        if current_idx > 0:
            self.contract_combo.setCurrentIndex(current_idx - 1)
    
    def on_next_contract(self):
        """切换到下一个合约"""
        current_idx = self.contract_combo.currentIndex()
        if current_idx < self.contract_combo.count() - 1:
            self.contract_combo.setCurrentIndex(current_idx + 1)
    
    def _update_nav_buttons(self):
        """更新导航按钮状态"""
        current_idx = self.contract_combo.currentIndex()
        total = self.contract_combo.count()
        
        self.prev_button.setEnabled(current_idx > 0)
        self.next_button.setEnabled(current_idx < total - 1)
        
        # 更新按钮提示
        if current_idx > 0:
            self.prev_button.setToolTip(self.contract_combo.itemText(current_idx - 1))
        if current_idx < total - 1:
            self.next_button.setToolTip(self.contract_combo.itemText(current_idx + 1))
    
    
    def update_option_t_view(self, underlying, expiry):
        """更新期权T型视图"""
        if self.market_overview_df is None or self.option_ref_df is None:
            return
        
        self.update_stats(underlying)
        self.update_t_shape_table(underlying, expiry)
        self.update_vol_charts(underlying, expiry)
    
    def update_stats(self, underlying):
        """更新统计信息 (货权联动 + 波动率曲面数据匹配)"""
        if self.market_overview_df is None:
            return

        if '标的合约' not in self.market_overview_df.columns:
            return

        # 1. 匹配 市场概览/货权联动 数据 (按标的合约精确匹配)
        row_match = self.market_overview_df[
            self.market_overview_df['标的合约'].astype(str) == str(underlying)
        ]
        market_row = row_match.iloc[0] if not row_match.empty else None

        # 2. 匹配 波动率曲面 分析数据 (按品种代码匹配)
        vol_row = None
        product_code = self._extract_product_code(underlying)

        if self.vol_surface_df is not None and product_code:
            # 宽容匹配：去空格、转大写
            if '品种代码' in self.vol_surface_df.columns:
                vol_match = self.vol_surface_df[
                    self.vol_surface_df['品种代码'].astype(str).str.strip().str.upper() == product_code
                ]
                if not vol_match.empty:
                    vol_row = vol_match.iloc[0]

        # 3. 如果Excel中没有波动率曲面汇总数据，则根据当前数据实时计算 (确保信息不为空)
        if vol_row is None and self.option_ref_df is not None and product_code:
            try:
                vol_row = self._calculate_vol_surface_metrics(product_code)
            except Exception as e:
                print(f"实时计算波动率指标失败: {e}")

        # 4. 更新 UI 标签
        # A. 标的统计信息 - 使用字段映射
        for key, label in self.underlying_stat_labels.items():
            val = '-'
            if market_row is not None:
                # 使用字段映射获取实际列名
                actual_key = self.underlying_field_map.get(key, key)
                if actual_key in market_row.index:
                    val = market_row[actual_key]

            # 格式化: 期货沉淀(亿) 保留2位小数
            if key == '期货沉淀(亿)' and pd.notna(val) and val != '-':
                try: val = f"{float(val):.2f}"
                except: pass

            label.setText(str(val) if pd.notna(val) else '-')

        # B. 期权整体统计信息 - 使用字段映射
        for key, label in self.option_stat_labels.items():
            val = '-'
            if market_row is not None:
                # 使用字段映射获取实际列名
                actual_key = self.option_field_map.get(key, key)
                if actual_key in market_row.index:
                    val = market_row[actual_key]

            # 格式化: 期权PCR, 期权沉淀(亿) 保留2位小数
            if key in ['期权PCR', '期权沉淀(亿)'] and pd.notna(val) and val != '-':
                try: val = f"{float(val):.2f}"
                except: pass

            label.setText(str(val) if pd.notna(val) else '-')

        # C. 货权联动分析 (含波动率曲面汇总字段)
        # 定义联动字段的映射（部分字段需要从不同来源获取）
        linkage_field_map = {
            "适合策略": "策略建议",    # 从策略建议获取
            "沉淀资金合计(亿)": "沉淀资金(亿)",
        }

        for key, label in self.linkage_labels.items():
            val = '-'
            # 先检查字段映射
            actual_key = linkage_field_map.get(key, key)

            # 逻辑：优先从 market_row 获取，若无则从 vol_row 获取
            if market_row is not None and actual_key in market_row.index:
                val = market_row[actual_key]

            if (val == '-' or pd.isna(val)) and vol_row is not None and key in vol_row:
                val = vol_row[key]

            # 格式化数值 (希腊字母、百分比等)
            if pd.notna(val) and val != '-':
                if key in ['IV倾斜度', '期限结构差', '峰度', '偏度', 'IV/RV比率', '沉淀资金合计(亿)']:
                    try: val = f"{float(val):.2f}"
                    except: pass
                elif ('IV' in key or '%' in key) and isinstance(val, (int, float)):
                    if val < 1.0 and val > 0: # 可能是小数格式
                        val = f"{val*100:.2f}%"
                    else:
                        val = f"{val:.2f}%"

            label.setText(str(val) if pd.notna(val) else '-')
    
    def _calculate_vol_surface_metrics(self, product_code):
        """实时计算波动率曲面指标（当Excel中没有时）"""
        # 筛选该品种的所有期权
        mask = self.option_ref_df['标的合约'].apply(self._extract_product_code) == product_code
        prod_df = self.option_ref_df[mask].copy()

        if len(prod_df) < 10:
            return None

        result = {}

        # 合约数量和资金
        result['合约数量'] = len(prod_df)
        result['沉淀资金合计(亿)'] = round(prod_df['沉淀资金(万)'].sum() / 10000, 2) if '沉淀资金(万)' in prod_df.columns else 0

        # IV 统计
        iv_values = prod_df['隐含波动率'].dropna()
        hv_values = prod_df['近期波动率'].dropna()

        avg_iv = iv_values.mean() if len(iv_values) > 0 else 0
        avg_hv = hv_values.mean() if len(hv_values) > 0 else 0
        result['IV/RV比率'] = round(avg_iv / avg_hv, 2) if avg_hv > 0 else '-'

        # 峰度和偏度
        result['峰度'] = round(kurtosis(iv_values, fisher=True), 2) if len(iv_values) >= 4 else 0
        result['偏度'] = round(skew(iv_values), 2) if len(iv_values) >= 4 else 0

        # IV Skew (虚值认沽 vs 虚值认购)
        prod_df['期权类型'] = prod_df['期权类型'].apply(self._normalize_option_type)
        otm_puts = prod_df[(prod_df['期权类型'] == 'PUT') & (prod_df['虚实幅度%'] < -5)]
        otm_calls = prod_df[(prod_df['期权类型'] == 'CALL') & (prod_df['虚实幅度%'] < -5)]

        put_iv_mean = otm_puts['隐含波动率'].mean() if len(otm_puts) > 0 else 0
        call_iv_mean = otm_calls['隐含波动率'].mean() if len(otm_calls) > 0 else 0
        iv_skew = put_iv_mean - call_iv_mean

        result['虚值认沽IV均值'] = round(put_iv_mean, 2)
        result['虚值认购IV均值'] = round(call_iv_mean, 2)
        result['IV倾斜度'] = round(iv_skew, 2)
        result['倾斜方向'] = '看跌倾斜' if iv_skew > 2 else ('看涨倾斜' if iv_skew < -2 else '平坦')

        # 期限结构 (短期 vs 长期)
        short_term = prod_df[prod_df['剩余天数'] <= 30]['隐含波动率'].mean()
        long_term = prod_df[prod_df['剩余天数'] > 60]['隐含波动率'].mean()
        term_diff = short_term - long_term if not pd.isna(short_term) and not pd.isna(long_term) else 0

        result['短期IV'] = round(short_term, 2) if not pd.isna(short_term) else 0
        result['长期IV'] = round(long_term, 2) if not pd.isna(long_term) else 0
        result['期限结构差'] = round(term_diff, 2)
        result['期限结构'] = '倒挂' if term_diff > 3 else ('升水' if term_diff < -3 else '平坦')

        # 市场情绪分类
        iv_rv_ratio = result['IV/RV比率'] if isinstance(result['IV/RV比率'], (int, float)) else 1
        result['市场情绪'] = self._classify_market_sentiment(iv_skew, term_diff, result['峰度'], iv_rv_ratio)

        # 市场解读
        result['市场解读'] = self._get_market_interpretation(result['市场情绪'], iv_skew, term_diff, avg_iv)

        # 推荐策略
        result['推荐策略'] = self._suggest_strategies(result['市场情绪'], iv_rv_ratio, iv_skew, term_diff)

        # 适合策略
        result['适合策略'] = result['推荐策略']

        # 不适合策略
        result['不适合策略'] = self._get_unsuitable_strategies(result['市场情绪'], iv_rv_ratio)

        return result
    
    def _classify_market_sentiment(self, iv_skew, term_structure, iv_kurtosis, iv_rv_ratio):
        """根据波动率特征分类市场情绪"""
        if iv_skew > 3 and term_structure > 3:
            return '恐慌下跌'
        elif iv_skew < -3 and term_structure < -3:
            return '狂热上涨'
        elif abs(iv_skew) <= 3 and abs(term_structure) <= 3:
            if iv_kurtosis < -0.5:
                return '窄幅震荡(瘦尾)'
            else:
                return '窄幅震荡'
        elif iv_skew > 0:
            return '震荡筑底'
        elif iv_skew < 0:
            return '震荡冲高'
        return '中性'
    
    def _suggest_strategies(self, sentiment, iv_rv_ratio, iv_skew, term_diff):
        """根据市场情绪推荐策略"""
        strategies = []
        iv_undervalued = iv_rv_ratio < 0.8 if isinstance(iv_rv_ratio, (int, float)) else False
        iv_overvalued = iv_rv_ratio > 1.2 if isinstance(iv_rv_ratio, (int, float)) else False
        
        if '恐慌' in sentiment:
            strategies.append('认沽多头价差')
            if iv_undervalued:
                strategies.append('买入虚值认沽')
        elif '狂热' in sentiment:
            strategies.append('认购多头价差')
            if iv_undervalued:
                strategies.append('买入虚值认购')
        elif '窄幅' in sentiment:
            if iv_overvalued:
                strategies.append('铁鹰式')
                strategies.append('宽跨式空头')
            else:
                strategies.append('日历价差')
        elif '筑底' in sentiment:
            strategies.append('牛市认沽价差')
        elif '冲高' in sentiment:
            strategies.append('保护性认沽')
        else:
            strategies.append('观望')
        
        return ', '.join(strategies[:3])

    def _get_market_interpretation(self, sentiment, iv_skew, term_diff, avg_iv):
        """生成市场解读文本"""
        if '恐慌' in sentiment:
            return f"市场恐慌情绪浓厚，IV偏斜{iv_skew:.1f}，短期波动率高企，注意风险"
        elif '狂热' in sentiment:
            return f"市场情绪狂热，看涨倾斜明显，可能面临回调风险"
        elif '窄幅' in sentiment:
            return f"市场预期平稳，波动率{avg_iv:.1f}%处于正常区间，适合卖方策略"
        elif '筑底' in sentiment:
            return f"市场震荡筑底，认沽IV偏高，可能接近底部区域"
        elif '冲高' in sentiment:
            return f"市场震荡冲高，认购IV偏高，注意追高风险"
        else:
            return f"市场中性震荡，波动率结构正常"

    def _get_unsuitable_strategies(self, sentiment, iv_rv_ratio):
        """获取不适合的策略"""
        unsuitable = []
        iv_overvalued = iv_rv_ratio > 1.2 if isinstance(iv_rv_ratio, (int, float)) else False

        if '恐慌' in sentiment:
            unsuitable.append('裸卖认沽')
            if iv_overvalued:
                unsuitable.append('买入期权')
        elif '狂热' in sentiment:
            unsuitable.append('裸卖认购')
            if iv_overvalued:
                unsuitable.append('买入期权')
        elif '窄幅' in sentiment:
            unsuitable.append('买入跨式')
            unsuitable.append('买入宽跨式')
        else:
            unsuitable.append('高杠杆策略')

        return ', '.join(unsuitable[:2])

    def update_t_shape_table(self, underlying, expiry):
        """更新T型表格（全字段对称显示，智能多色染色）"""
        self.option_t_table.setRowCount(0)
        
        if self.option_ref_df is None:
            return
        
        df = self.option_ref_df[
            (self.option_ref_df['标的合约'].astype(str) == str(underlying)) &
            (self.option_ref_df['交割年月'].astype(str) == str(expiry))
        ].copy()
        
        if df.empty:
            return
        
        if '行权价' not in df.columns or '期权类型' not in df.columns:
            return
        
        df['期权类型'] = df['期权类型'].apply(self._normalize_option_type)
        df = df[df['期权类型'].isin(['CALL', 'PUT'])]
        
        strikes = sorted(df['行权价'].dropna().unique().tolist(), reverse=True)
        
        if not strikes:
            return
        
        atm_price = df['标的现价'].iloc[0] if '标的现价' in df.columns and not df.empty else None
        
        self.option_t_table.setRowCount(len(strikes))
        
        for row_idx, strike in enumerate(strikes):
            call_rows = df[(df['行权价'] == strike) & (df['期权类型'] == 'CALL')]
            put_rows = df[(df['行权价'] == strike) & (df['期权类型'] == 'PUT')]
            
            call = call_rows.sort_values('成交金额', ascending=False).iloc[0] if not call_rows.empty else None
            put = put_rows.sort_values('成交金额', ascending=False).iloc[0] if not put_rows.empty else None
            
            is_atm = False
            if atm_price is not None:
                is_atm = abs(strike - atm_price) / atm_price < 0.02
            
            col_idx = 0
            
            # 看跌 Wing (P-...)
            for field in self.all_ref_cols:
                value = self._get_field_value(put, field)
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                
                # 智能染色
                if put is not None:
                    fg_color, bg_color = self._get_cell_color(field, put, is_atm, 'PUT')
                    if fg_color:
                        item.setForeground(QBrush(fg_color))
                    if bg_color:
                        item.setBackground(QBrush(bg_color))
                
                self.option_t_table.setItem(row_idx, col_idx, item)
                col_idx += 1
            
            # 行权价 (Center)
            strike_item = QTableWidgetItem(f"{strike}")
            strike_item.setTextAlignment(Qt.AlignCenter)
            strike_item.setFont(self._get_bold_font())
            if is_atm:
                strike_item.setBackground(QBrush(QColor("#ffff99")))
                strike_item.setForeground(QBrush(QColor("#cc0000")))
            else:
                strike_item.setBackground(QBrush(QColor("#f0f0f0")))
            self.option_t_table.setItem(row_idx, col_idx, strike_item)
            col_idx += 1
            
            # 看涨 Wing (C-...)
            for field in self.all_ref_cols:
                value = self._get_field_value(call, field)
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                
                # 智能染色
                if call is not None:
                    fg_color, bg_color = self._get_cell_color(field, call, is_atm, 'CALL')
                    if fg_color:
                        item.setForeground(QBrush(fg_color))
                    if bg_color:
                        item.setBackground(QBrush(bg_color))
                
                self.option_t_table.setItem(row_idx, col_idx, item)
                col_idx += 1
    
    def _get_cell_color(self, field, row, is_atm, option_type):
        """根据字段类型和值返回前景色和背景色"""
        fg_color = None
        bg_color = None
        
        # ATM 行高亮
        if is_atm:
            bg_color = QColor("#fffacd") if option_type == 'PUT' else QColor("#fff0f5")
        
        try:
            value = row[field] if field in row.index else None
            if pd.isna(value):
                return fg_color, bg_color
            
            # Delta: 渐变色 (绝对值越大颜色越深)
            if field == 'Delta':
                abs_delta = abs(float(value))
                if abs_delta > 0.7:
                    fg_color = QColor("#8B0000")  # 深红 (深度实值)
                elif abs_delta > 0.5:
                    fg_color = QColor("#cc0000")  # 红色
                elif abs_delta > 0.3:
                    fg_color = QColor("#ff6600")  # 橙色
                elif abs_delta < 0.15:
                    fg_color = QColor("#0066cc")  # 蓝色 (深度虚值)
                else:
                    fg_color = QColor("#333333")  # 灰色 (中性)
            
            # 隐含波动率/近期波动率: 高IV警示
            elif field in ['隐含波动率', '近期波动率']:
                v = float(value)
                if v > 50:
                    bg_color = QColor("#ffcccc")  # 浅红 (极高波动)
                    fg_color = QColor("#8B0000")
                elif v > 35:
                    bg_color = QColor("#ffe6cc")  # 浅橙
                    fg_color = QColor("#cc6600")
                elif v < 15:
                    bg_color = QColor("#e6f3ff")  # 浅蓝 (低波动)
                    fg_color = QColor("#0066cc")
            
            # 虚实幅度%: ITM红/OTM蓝 渐变
            elif field == '虚实幅度%':
                v = float(value)
                if v > 10:
                    bg_color = QColor("#ffcccc")  # 深度实值
                    fg_color = QColor("#8B0000")
                elif v > 5:
                    bg_color = QColor("#ffe6e6")
                    fg_color = QColor("#cc0000")
                elif v > 0:
                    fg_color = QColor("#ff6600")
                elif v < -10:
                    bg_color = QColor("#cce6ff")  # 深度虚值
                    fg_color = QColor("#003366")
                elif v < -5:
                    bg_color = QColor("#e6f3ff")
                    fg_color = QColor("#0066cc")
                elif v < 0:
                    fg_color = QColor("#3399ff")
            
            # 溢价率%: 低=绿(便宜), 高=红(贵)
            elif field == '溢价率%':
                v = float(value)
                if v < 2:
                    bg_color = QColor("#ccffcc")  # 绿 (便宜)
                    fg_color = QColor("#006600")
                elif v > 10:
                    bg_color = QColor("#ffcccc")  # 红 (贵)
                    fg_color = QColor("#cc0000")
                elif v > 5:
                    fg_color = QColor("#ff6600")
            
            # 涨跌幅%: 涨红/跌绿
            elif field == '涨跌幅%':
                v = float(value)
                if v > 5:
                    fg_color = QColor("#cc0000")
                    bg_color = QColor("#ffe6e6")
                elif v > 0:
                    fg_color = QColor("#cc0000")
                elif v < -5:
                    fg_color = QColor("#008800")
                    bg_color = QColor("#e6ffe6")
                elif v < 0:
                    fg_color = QColor("#008800")
            
            # 成交量/持仓量: 活跃度高亮
            elif field in ['成交量', '持仓量']:
                v = float(value)
                if v > 10000:
                    bg_color = QColor("#fff3cd")  # 黄色 (高活跃)
                    fg_color = QColor("#856404")
                elif v > 5000:
                    fg_color = QColor("#996600")
            
            # Theta: 负值越大颜色越深
            elif field == 'Theta':
                v = float(value)
                if v < -0.01:
                    fg_color = QColor("#8B0000")  # 深红 (时间损耗大)
                elif v < -0.005:
                    fg_color = QColor("#cc0000")
                elif v < 0:
                    fg_color = QColor("#ff6600")
            
            # Vega: 高敏感度高亮
            elif field == 'Vega':
                v = float(value)
                if v > 0.05:
                    fg_color = QColor("#6600cc")  # 紫色 (高波动敏感)
                elif v > 0.02:
                    fg_color = QColor("#9933ff")
            
            # Gamma: 高Gamma高亮
            elif field == 'Gamma':
                v = float(value)
                if v > 0.001:
                    fg_color = QColor("#cc6600")  # 橙色 (高Gamma)
            
            # 收益%/年化收益%: 收益高低
            elif field in ['收益%', '收益年化%', '杠杆收益%', '杠杆年化%']:
                v = float(value)
                if v > 50:
                    fg_color = QColor("#006600")
                    bg_color = QColor("#ccffcc")
                elif v > 20:
                    fg_color = QColor("#008800")
                elif v < 0:
                    fg_color = QColor("#cc0000")
            
            # 时间价值/时间占比%
            elif field == '时间占比%':
                v = float(value)
                if v > 80:
                    fg_color = QColor("#cc6600")  # 高时间价值占比
                elif v < 20:
                    fg_color = QColor("#0066cc")  # 低时间价值占比
            
            # 买方杠杆
            elif field == '买方杠杆':
                v = float(value)
                if v > 50:
                    fg_color = QColor("#cc0000")
                    bg_color = QColor("#fff0f0")
                elif v > 20:
                    fg_color = QColor("#ff6600")
                elif v > 10:
                    fg_color = QColor("#996600")
            
            # 资金类字段: 大资金高亮
            elif '资金' in field:
                v = float(value)
                if v > 1000:
                    bg_color = QColor("#e6f3ff")
                    fg_color = QColor("#003366")
                elif v > 500:
                    fg_color = QColor("#0066cc")
                    
        except (ValueError, TypeError):
            pass
        
        return fg_color, bg_color
    
    def update_vol_charts(self, underlying, expiry):
        """更新波动率图表和K线图"""
        if self.option_ref_df is None:
            return
        
        # 1. 提取品种代码 (e.g. SHFE.au2602 -> AU)
        product_code = self._extract_product_code(underlying)
        
        # 2. 筛选该品种的所有期权数据 (用于波动率曲面)
        # 需匹配所有属于该品种的标的合约
        if product_code:
            # 临时添加品种代码列进行筛选 (或直接apply)
            # 为了性能，建议在 load_data 时预处理，这里直接apply
            mask = self.option_ref_df['标的合约'].apply(self._extract_product_code) == product_code
            df_product = self.option_ref_df[mask].copy()
            surface_title = f"{product_code}"
        else:
            # 回退：仅使用当前标的
            df_product = self.option_ref_df[
                self.option_ref_df['标的合约'].astype(str) == str(underlying)
            ].copy()
            surface_title = f"{underlying} 波动率曲面"
        
        # 3. 筛选当前标的和到期日的数据 (用于微笑曲线)
        df_smile = self.option_ref_df[
            (self.option_ref_df['标的合约'].astype(str) == str(underlying)) &
            (self.option_ref_df['交割年月'].astype(str) == str(expiry))
        ].copy()
        
        # 4. 绘制K线图
        self.plot_kline_chart(underlying)
        
        # 5. 绘制波动率图表
        self.plot_vol_surface(df_product, surface_title)
        self.plot_vol_smile(df_smile, expiry)

    def _extract_product_code(self, symbol):
        """
        从合约代码提取品种代码 (e.g. SHFE.au2602 -> AU, SSE.000852 -> 000852)
        逻辑与 04/05 脚本保持一致，确保跨表匹配成功
        """
        try:
            s = str(symbol).strip()
            if '.' in s:
                parts = s.split('.')
                code_part = parts[1]
            else:
                code_part = s
            
            # 优先匹配开头的纯字母部分 (如 au2602 -> AU)
            match_letter = re.match(r'^([a-zA-Z]+)', code_part)
            if match_letter:
                return match_letter.group(1).upper()
            
            # 如果开头是数字，则匹配数字部分 (如 000852 -> 000852)
            match_number = re.match(r'^(\d+)', code_part)
            if match_number:
                return match_number.group(1)
                
            return code_part.upper()
        except:
            return ''
    
    def plot_kline_chart(self, underlying):
        """绘制标的K线图（简明清晰大方风格）"""
        self.kline_fig.clear()
        
        # 获取K线数据
        kline_df = self.klines_data.get(underlying)
        
        if kline_df is None or kline_df.empty:
            ax = self.kline_fig.add_subplot(111)
            ax.text(0.5, 0.5, f'无K线数据\n{underlying}', 
                    transform=ax.transAxes, ha='center', va='center',
                    fontsize=10, color='gray')
            ax.axis('off')
            self.kline_canvas.draw()
            return
        
        # 准备数据
        df = kline_df.copy()
        
        # 确保有必要的列
        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            ax = self.kline_fig.add_subplot(111)
            ax.text(0.5, 0.5, 'K线数据缺少OHLC字段', 
                    transform=ax.transAxes, ha='center', va='center')
            ax.axis('off')
            self.kline_canvas.draw()
            return
        
        # 转换数据类型
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 过滤无效数据
        df = df.dropna(subset=required_cols)
        
        if df.empty:
            ax = self.kline_fig.add_subplot(111)
            ax.text(0.5, 0.5, 'K线数据无效', 
                    transform=ax.transAxes, ha='center', va='center')
            ax.axis('off')
            self.kline_canvas.draw()
            return
        
        # 取最近两年（约500根日K线）显示
        df = df.tail(500).reset_index(drop=True)
        
        try:
            ax = self.kline_fig.add_subplot(111)
            
            # 计算涨跌
            up = df['close'] >= df['open']
            down = df['close'] < df['open']
            
            # 颜色设置（中国市场风格：红涨绿跌）
            up_color = '#CC0000'      # 红色-上涨
            down_color = '#009900'    # 绿色-下跌
            
            # K线宽度
            width = 0.6
            width2 = 0.08
            
            # 绘制上涨K线
            ax.bar(df.index[up], df['close'][up] - df['open'][up], width, 
                   bottom=df['open'][up], color=up_color, edgecolor=up_color, linewidth=0.5)
            ax.bar(df.index[up], df['high'][up] - df['close'][up], width2, 
                   bottom=df['close'][up], color=up_color, linewidth=0)
            ax.bar(df.index[up], df['open'][up] - df['low'][up], width2, 
                   bottom=df['low'][up], color=up_color, linewidth=0)
            
            # 绘制下跌K线
            ax.bar(df.index[down], df['close'][down] - df['open'][down], width, 
                   bottom=df['open'][down], color=down_color, edgecolor=down_color, linewidth=0.5)
            ax.bar(df.index[down], df['high'][down] - df['open'][down], width2, 
                   bottom=df['open'][down], color=down_color, linewidth=0)
            ax.bar(df.index[down], df['close'][down] - df['low'][down], width2, 
                   bottom=df['low'][down], color=down_color, linewidth=0)
            
            # 添加MA5和MA20均线
            if len(df) >= 5:
                ma5 = df['close'].rolling(window=5).mean()
                ax.plot(df.index, ma5, color='#FF9900', linewidth=1, label='MA5', alpha=0.8)
            if len(df) >= 20:
                ma20 = df['close'].rolling(window=20).mean()
                ax.plot(df.index, ma20, color='#0066CC', linewidth=1, label='MA20', alpha=0.8)
            
            # 设置标题和标签
            contract_name = underlying.split('.')[-1] if '.' in underlying else underlying
            ax.set_title(f'{contract_name} 日K线', fontsize=10, fontweight='bold')
            
            # 简化X轴刻度
            if 'datetime_str' in df.columns:
                # 只显示首尾和中间几个日期
                tick_positions = [0, len(df)//4, len(df)//2, 3*len(df)//4, len(df)-1]
                tick_positions = [p for p in tick_positions if p < len(df)]
                tick_labels = [str(df['datetime_str'].iloc[p])[:10] if pd.notna(df['datetime_str'].iloc[p]) else '' 
                              for p in tick_positions]
                ax.set_xticks(tick_positions)
                ax.set_xticklabels(tick_labels, fontsize=7, rotation=15)
            else:
                ax.set_xticks([])
            
            # 设置Y轴格式
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
            ax.tick_params(axis='y', labelsize=8)
            
            # 网格线
            ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
            ax.set_axisbelow(True)
            
            # 图例
            if len(df) >= 5:
                ax.legend(loc='upper left', fontsize=7, framealpha=0.8)
            
            # 边框美化
            for spine in ['top', 'right']:
                ax.spines[spine].set_visible(False)
            ax.spines['left'].set_color('#888888')
            ax.spines['bottom'].set_color('#888888')
            
            # 显示最新价格
            last_close = df['close'].iloc[-1]
            ax.axhline(y=last_close, color='#666666', linestyle=':', linewidth=0.8, alpha=0.6)
            ax.text(len(df)-1, last_close, f' {last_close:,.1f}', 
                    fontsize=7, va='center', ha='left', color='#333333')
            
        except Exception as e:
            ax = self.kline_fig.add_subplot(111)
            ax.text(0.5, 0.5, f'绘图错误:\n{str(e)[:30]}', 
                    transform=ax.transAxes, ha='center', va='center', fontsize=9)
            ax.axis('off')
        
        self.kline_fig.tight_layout()
        self.kline_canvas.draw()
    
    def plot_vol_surface(self, df, underlying):
        """绘制波动率曲面 - X轴:到期年月, Y轴:行权价, Z轴:隐含波动率"""
        self.surface_fig.clear()
        # 设置背景色为白色
        self.surface_fig.patch.set_facecolor('white')

        if df is None or df.empty:
            ax = self.surface_fig.add_subplot(111)
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, '无数据', transform=ax.transAxes, ha='center', va='center')
            ax.axis('off')
            self.surface_canvas.draw()
            return

        # 过滤有效数据 (IV > 0.5 以排除极端接近0的异常点)
        plot_df = df[(df['隐含波动率'] > 0.5) & (df['行权价'] > 0)].copy()

        # 需要有交割年月字段
        if '交割年月' not in plot_df.columns:
            ax = self.surface_fig.add_subplot(111)
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, '缺少交割年月字段', transform=ax.transAxes, ha='center', va='center')
            ax.axis('off')
            self.surface_canvas.draw()
            return

        # 合成 Call/Put IV (取平均): 对同一交割年月和行权价的IV取均值
        if not plot_df.empty:
            plot_df = plot_df.groupby(['交割年月', '行权价'], as_index=False).agg({
                '隐含波动率': 'mean',
                '剩余天数': 'first'
            })

        if len(plot_df) < 6:
            ax = self.surface_fig.add_subplot(111)
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, f'数据不足 ({len(plot_df)}点)', transform=ax.transAxes, ha='center', va='center')
            ax.axis('off')
            self.surface_canvas.draw()
            return

        try:
            from matplotlib import cm
            ax = self.surface_fig.add_subplot(111, projection='3d')
            ax.set_facecolor('white')

            # 获取所有唯一的到期年月并排序
            expiries = sorted(plot_df['交割年月'].unique(), reverse=True)  # 倒序：最近月在前
            expiry_to_num = {exp: i for i, exp in enumerate(expiries)}

            # X轴：到期年月（转为数值索引）
            # Y轴：行权价
            # Z轴：隐含波动率
            plot_df['到期序号'] = plot_df['交割年月'].map(expiry_to_num)
            x = plot_df['到期序号'].values
            y = plot_df['行权价'].values
            z = plot_df['隐含波动率'].values

            # 创建更密集的网格
            xi = np.linspace(x.min(), x.max(), 100)
            yi = np.linspace(y.min(), y.max(), 100)
            xi_grid, yi_grid = np.meshgrid(xi, yi)

            # 插值
            try:
                zi_grid = griddata((x, y), z, (xi_grid, yi_grid), method='linear', rescale=True)

                if len(x) > 10:
                    try:
                        zi_cubic = griddata((x, y), z, (xi_grid, yi_grid), method='cubic', rescale=True)
                        if not np.isnan(zi_cubic).all():
                            mask_nan = np.isnan(zi_cubic)
                            zi_grid = np.where(mask_nan, zi_grid, zi_cubic)
                    except:
                        pass
            except:
                zi_grid = griddata((x, y), z, (xi_grid, yi_grid), method='nearest', rescale=True)

            # 填充NaN值
            if np.any(np.isnan(zi_grid)):
                zi_nearest = griddata((x, y), z, (xi_grid, yi_grid), method='nearest', rescale=True)
                zi_grid = np.where(np.isnan(zi_grid), zi_nearest, zi_grid)

            # 确保IV非负
            zi_grid = np.maximum(zi_grid, 0)

            # 绘制曲面
            surf = ax.plot_surface(xi_grid, yi_grid, zi_grid, cmap=cm.RdYlBu_r,
                                   rcount=100, ccount=100,
                                   linewidth=0.1, antialiased=True, alpha=0.9,
                                   edgecolor=(0.5, 0.5, 0.5, 0.2))

            # 绘制实际数据点
            cmap = cm.RdYlBu_r
            norm = plt.Normalize(vmin=z.min(), vmax=z.max())
            colors = cmap(norm(z))

            ax.scatter(x, y, z, c=colors, s=8, alpha=0.7, depthshade=True)

            # 设置X轴刻度为实际的到期年月
            ax.set_xticks(list(expiry_to_num.values()))
            ax.set_xticklabels([str(exp) for exp in expiries], fontsize=7, rotation=30)

            # 设置坐标轴标签
            ax.set_xlabel('到期年月', fontsize=9, labelpad=8, fontweight='bold', color='#333333')
            ax.set_ylabel('行权价', fontsize=9, labelpad=8, fontweight='bold', color='#333333')

            # 设置刻度样式
            ax.tick_params(axis='x', pad=2, colors='#555555', labelsize=7)
            ax.tick_params(axis='y', pad=2, colors='#555555', labelsize=8)
            ax.tick_params(axis='z', pad=5, colors='#555555', labelsize=8)

            # 设置网格颜色
            ax.xaxis._axinfo["grid"]['color'] = (0.8, 0.8, 0.8, 0.5)
            ax.yaxis._axinfo["grid"]['color'] = (0.8, 0.8, 0.8, 0.5)
            ax.zaxis._axinfo["grid"]['color'] = (0.8, 0.8, 0.8, 0.5)

            # 优化视角
            ax.view_init(elev=25, azim=-45)

            # 添加颜色条
            cbar = self.surface_fig.colorbar(surf, shrink=0.55, aspect=12, pad=0.1)
            cbar.set_label('IV (%)', fontsize=8)

            # 调整边距
            self.surface_fig.subplots_adjust(left=0.0, right=0.90, top=0.95, bottom=0.05)

        except Exception as e:
            ax = self.surface_fig.add_subplot(111)
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, f'绘图错误: {str(e)[:50]}', transform=ax.transAxes, ha='center', va='center')
            ax.axis('off')

        self.surface_canvas.draw()
    
    def plot_vol_smile(self, df, expiry):
        """绘制微笑曲线 - X轴:行权价, Y轴:IV"""
        self.smile_fig.clear()

        if df is None or df.empty:
            ax = self.smile_fig.add_subplot(111)
            ax.text(0.5, 0.5, '无数据', transform=ax.transAxes, ha='center', va='center')
            ax.axis('off')
            self.smile_canvas.draw()
            return

        temp = df.copy()
        temp['期权类型'] = temp['期权类型'].apply(self._normalize_option_type)
        temp = temp[(temp['隐含波动率'] > 0) & (temp['行权价'] > 0)]

        if temp.empty:
            ax = self.smile_fig.add_subplot(111)
            ax.text(0.5, 0.5, '无有效波动率数据', transform=ax.transAxes, ha='center', va='center')
            ax.axis('off')
            self.smile_canvas.draw()
            return

        # 获取标的现价用于ATM标记
        und_price = temp['标的现价'].iloc[0] if '标的现价' in temp.columns and pd.notna(temp['标的现价'].iloc[0]) else None

        # X轴：行权价
        x_col = '行权价'
        x_label = '行权价'

        calls = temp[temp['期权类型'] == 'CALL'].sort_values(x_col)
        puts = temp[temp['期权类型'] == 'PUT'].sort_values(x_col)

        ax = self.smile_fig.add_subplot(111)

        # 绘制看涨和看跌曲线
        if not calls.empty:
            ax.plot(calls[x_col], calls['隐含波动率'], label='看涨 (Call)',
                    color='#cc0000', marker='o', markersize=3, linewidth=2, alpha=0.85)
        if not puts.empty:
            ax.plot(puts[x_col], puts['隐含波动率'], label='看跌 (Put)',
                    color='#008800', marker='s', markersize=3, linewidth=2, alpha=0.85)

        # 添加ATM垂直线
        if und_price and und_price > 0:
            ax.axvline(x=und_price, color='blue', linestyle='--', linewidth=1.5, alpha=0.7, label=f'ATM ({und_price:.2f})')

        ax.set_xlabel(x_label, fontsize=10)
        ax.set_ylabel('IV (%)', fontsize=10)
        ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')

        self.smile_fig.tight_layout()
        self.smile_canvas.draw()
    
    def _normalize_option_type(self, opt_type):
        if pd.isna(opt_type): return ''
        ot = str(opt_type).upper()
        if 'CALL' in ot or ot == 'C': return 'CALL'
        if 'PUT' in ot or ot == 'P': return 'PUT'
        return ''
    
    def _get_field_value(self, row, field):
        if row is None or field not in row.index: return '-'
        value = row[field]
        if pd.isna(value): return '-'
        if isinstance(value, (int, float)):
            if field == 'Gamma': return f"{value:.6f}"
            if field in ['Delta', 'Theta', 'Vega', 'Rho']: return f"{value:.4f}"
            if field in ['隐含波动率', '近期波动率', '虚实幅度%', '涨跌幅%', '收益%', '溢价率%']: return f"{value:.2f}"
            if field in ['期权价', '理论价格', '内在价值', '时间价值', '标的现价', '昨收', '昨结', '今结']: return f"{value:.1f}"
            if '资金' in field or '成交' in field or '持仓' in field or '合约乘数' in field:
                try: return f"{int(value):,}"
                except: return f"{value}"
            return f"{value:.2f}"
        return str(value)
    
    def _get_bold_font(self):
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        return font
    
    def _safe_get_value(self, row, field, default='-'):
        """安全地从Series或dict中获取值，处理NaN和None"""
        try:
            if isinstance(row, pd.Series):
                if field in row.index:
                    val = row[field]
                    if pd.notna(val):
                        return val
            elif isinstance(row, dict):
                if field in row:
                    val = row[field]
                    if val is not None and (not isinstance(val, float) or not pd.isna(val)):
                        return val
        except:
            pass
        return default
    
    def _calculate_display_width(self, text):
        """计算字符串的显示宽度（中文字符算2个宽度，英文算1个）"""
        if text is None:
            return 0
        text_str = str(text)
        width = 0
        for char in text_str:
            # 判断是否为中文字符（包括中文标点）
            if '\u4e00' <= char <= '\u9fff' or '\u3000' <= char <= '\u303f':
                width += 2
            else:
                width += 1
        return width
    
    


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = OptionTShapeWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
