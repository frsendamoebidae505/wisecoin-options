"""
模拟持仓管理模块。

用于策略回测和模拟交易，不依赖真实账户。

包含:
- MockPosition: 模拟持仓
- TradeRecord: 交易记录
- MockPositionGenerator: 模拟持仓生成器
- MockPositionManager: 模拟持仓管理器
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import os
import re
import numpy as np
import pandas as pd

from trade.position import (
    BasePositionManager, TargetConfig, TargetHit,
    PositionAnalyzer, OptionPricer, RiskMetrics,
    normalize_contract_code, is_index_underlying
)
from core.models import Position


# ============================================================
# 模拟持仓数据结构
# ============================================================

@dataclass
class MockPosition:
    """模拟持仓"""
    symbol: str
    exchange_id: str
    direction: str  # LONG / SHORT
    volume: int
    avg_price: float
    margin: float
    open_time: datetime = None
    current_price: float = 0.0

    def __post_init__(self):
        if self.open_time is None:
            self.open_time = datetime.now()

    def unrealized_pnl(self) -> float:
        """计算未实现盈亏"""
        if self.direction == "LONG":
            return (self.current_price - self.avg_price) * self.volume
        else:
            return (self.avg_price - self.current_price) * self.volume

    def to_position(self) -> Position:
        """转换为 Position 模型"""
        return Position(
            symbol=self.symbol,
            exchange_id=self.exchange_id,
            direction=self.direction,
            volume=self.volume,
            avg_price=self.avg_price,
            current_price=self.current_price,
            unrealized_pnl=self.unrealized_pnl(),
            margin=self.margin,
        )


@dataclass
class TradeRecord:
    """交易记录"""
    action: str  # OPEN / CLOSE
    symbol: str
    direction: str
    volume: int
    price: float
    timestamp: datetime
    pnl: float = 0.0


# ============================================================
# 模拟持仓生成器
# ============================================================

class MockPositionGenerator:
    """
    模拟持仓生成器。

    从策略文件和套利文件生成模拟持仓。
    移植自 51wisecoin_options_position_mock.py
    """

    # 默认配置
    TEMP_DIR = "wisecoin_options_client_live_temp"
    TEMPLATE_FILE = "wisecoin-持仓.xlsx"
    OUTPUT_EXCEL_FILE = "wisecoin-模拟持仓.xlsx"
    STRATEGY_FILE = "wisecoin-期权策略.xlsx"
    ARBITRAGE_FILE = "wisecoin-期权套利.xlsx"
    EXCLUDED_ARBITRAGE_SHEETS = {"套利汇总", "策略指南", "时间价值低估", "转换逆转套利"}

    def __init__(self, base_dir: str = None):
        """
        初始化生成器。

        Args:
            base_dir: 基础目录路径
        """
        self.base_dir = base_dir or os.getcwd()
        self.temp_dir = os.path.join(self.base_dir, self.TEMP_DIR)

    def resolve_input_path(self, filename: str, prefer_temp: bool = True) -> Optional[str]:
        """
        解析输入文件路径。

        Args:
            filename: 文件名
            prefer_temp: 是否优先使用临时目录

        Returns:
            文件路径，不存在则返回 None
        """
        candidates = []
        if prefer_temp:
            candidates.append(os.path.join(self.temp_dir, filename))
        candidates.append(os.path.join(self.base_dir, filename))

        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def load_template(self) -> Tuple[Optional[pd.DataFrame], Optional[List], Optional[Dict]]:
        """
        加载持仓模板文件。

        Returns:
            (template_df, template_cols, defaults)
        """
        template_path = self.resolve_input_path(self.TEMPLATE_FILE, prefer_temp=False)
        if not template_path:
            print(f"模板文件不存在: {self.TEMPLATE_FILE}")
            return None, None, None

        try:
            template_df = pd.read_excel(template_path)
            if template_df.empty:
                print(f"模板文件为空: {template_path}")
                return None, None, None

            template_cols = list(template_df.columns)
            first_row = template_df.iloc[0].to_dict()
            return template_df, template_cols, first_row
        except Exception as e:
            print(f"读取模板文件失败: {template_path}，错误: {e}")
            return None, None, None

    @staticmethod
    def sanitize_sheet_name(name: Any) -> str:
        """清理工作表名称"""
        if name is None:
            return ""
        text = str(name)
        for ch in ['\\', '/', '*', '[', ']', ':', '?']:
            text = text.replace(ch, '_')
        return text[:31]

    @staticmethod
    def normalize_expiry(value: Any) -> Optional[str]:
        """标准化到期月份"""
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        if text.endswith('.0'):
            text = text[:-2]
        digits = re.findall(r'\d{4,6}', text)
        if not digits:
            return None
        return digits[0]

    @staticmethod
    def extract_expiry_from_symbol(symbol: Any) -> Optional[str]:
        """从合约代码提取到期月份"""
        if symbol is None or pd.isna(symbol):
            return None
        text = str(symbol)
        match = re.search(r'\.(?:[A-Za-z]+)?(\d{4})', text)
        if match:
            return match.group(1)
        match = re.search(r'(\d{4})', text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def extract_expiry_from_legs(legs: List[Dict]) -> Optional[str]:
        """从腿列表提取到期月份"""
        for leg in legs:
            expiry = MockPositionGenerator.extract_expiry_from_symbol(leg.get('symbol'))
            if expiry:
                return expiry
        return None

    @staticmethod
    def to_number(value: Any, default: float = np.nan) -> float:
        """转换为数字"""
        try:
            value = float(value)
            if np.isnan(value):
                return default
            return value
        except Exception:
            return default

    @staticmethod
    def is_missing(value: Any) -> bool:
        """判断值是否缺失"""
        try:
            return bool(pd.isna(value))
        except Exception:
            return value is None

    @staticmethod
    def parse_legs_from_text(text: Any) -> List[Dict[str, Any]]:
        """
        从文本解析交易腿。

        支持格式:
        - 买入DCE.lh2605-P-14000*2@100
        - 卖出SHFE.au2506-C-600*1
        - 买入CZCE.CF505P15000*1@500

        Args:
            text: 文本内容

        Returns:
            腿列表
        """
        if text is None or (isinstance(text, float) and np.isnan(text)):
            return []

        raw = str(text)
        if '|' in raw:
            raw = raw.split('|')[0]

        parts = [p.strip() for p in raw.replace(';', ';').split(';') if p.strip()]
        legs = []

        for part in parts:
            action = None
            if part.startswith('买入'):
                action = 'buy'
                part = part.replace('买入', '', 1)
            elif part.startswith('卖出'):
                action = 'sell'
                part = part.replace('卖出', '', 1)

            if not action:
                continue

            symbol = None
            qty = None
            price = None

            if '*' in part:
                sym_part, rest = part.split('*', 1)
                symbol = sym_part.strip()
                if '@' in rest:
                    qty_part, price_part = rest.split('@', 1)
                    qty = MockPositionGenerator.to_number(qty_part.strip())
                    price = MockPositionGenerator.to_number(price_part.strip())
                else:
                    qty = MockPositionGenerator.to_number(rest.strip())
            else:
                if '@' in part:
                    sym_part, price_part = part.split('@', 1)
                    symbol = sym_part.strip()
                    price = MockPositionGenerator.to_number(price_part.strip())

            if symbol and qty:
                legs.append({
                    'action': action,
                    'symbol': symbol,
                    'qty': int(qty),
                    'price': price
                })

        return legs

    @staticmethod
    def build_position_row_from_leg(leg: Dict[str, Any], template_cols: List[str],
                                     defaults: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """
        从交易腿构建持仓行。

        Args:
            leg: 交易腿字典
            template_cols: 模板列名列表
            defaults: 默认值字典

        Returns:
            持仓行字典
        """
        record: Dict[str, Any] = {col: np.nan for col in template_cols}

        symbol = leg.get('symbol')
        if MockPositionGenerator.is_missing(symbol):
            return None

        if '.' in str(symbol):
            exchange_id, instrument_id = str(symbol).split('.', 1)
        else:
            exchange_id = np.nan
            instrument_id = str(symbol)

        qty = int(leg.get('qty', 0))
        if qty == 0:
            return None

        last_price = MockPositionGenerator.to_number(leg.get('price'))

        if 'exchange_id' in record:
            record['exchange_id'] = str(exchange_id) if not MockPositionGenerator.is_missing(exchange_id) else np.nan
        if 'instrument_id' in record:
            record['instrument_id'] = str(instrument_id)
        if 'symbol' in record:
            record['symbol'] = str(symbol)
        if 'last_price' in record:
            record['last_price'] = last_price
        if 'user_id' in record and defaults is not None and 'user_id' in defaults:
            record['user_id'] = defaults.get('user_id', np.nan)

        action = leg.get('action')
        pos_long = qty if action == 'buy' else 0
        pos_short = qty if action == 'sell' else 0

        if 'pos_long' in record:
            record['pos_long'] = pos_long
        if 'pos_short' in record:
            record['pos_short'] = pos_short
        if 'pos' in record:
            record['pos'] = pos_long - pos_short
        if 'volume_long' in record:
            record['volume_long'] = pos_long
        if 'volume_long_today' in record:
            record['volume_long_today'] = pos_long
        if 'volume_short' in record:
            record['volume_short'] = pos_short
        if 'volume_short_today' in record:
            record['volume_short_today'] = pos_short

        # 填充默认值
        zero_cols = ['pos_long_his', 'pos_long_today', 'pos_short_his', 'pos_short_today',
                     'volume_long_his', 'volume_long_frozen_today', 'volume_long_frozen_his',
                     'volume_long_frozen', 'volume_short_today', 'volume_short_his', 'volume_short',
                     'volume_short_frozen_today', 'volume_short_frozen_his', 'volume_short_frozen',
                     'volume_short_yd', 'volume_long_yd']

        for col in zero_cols:
            if col in record and MockPositionGenerator.is_missing(record[col]):
                record[col] = 0

        for col in ['open_price_long', 'position_price_long']:
            if col in record and pos_long:
                record[col] = last_price

        for col in ['open_price_short', 'position_price_short']:
            if col in record and pos_short:
                record[col] = last_price

        for col in ['open_cost_long', 'position_cost_long']:
            if col in record and pos_long:
                record[col] = last_price * pos_long if not MockPositionGenerator.is_missing(last_price) else np.nan

        for col in ['open_cost_short', 'position_cost_short']:
            if col in record and pos_short:
                record[col] = last_price * pos_short if not MockPositionGenerator.is_missing(last_price) else np.nan

        pnl_cols = ['float_profit_long', 'position_profit_long', 'float_profit', 'position_profit',
                    'margin_long', 'margin', 'market_value_long', 'market_value',
                    'float_profit_short', 'position_profit_short', 'margin_short', 'market_value_short']

        for col in pnl_cols:
            if col in record and MockPositionGenerator.is_missing(record[col]):
                record[col] = 0

        return record

    def load_strategy_positions(self, template_cols: List[str],
                                defaults: Optional[Dict]) -> Dict[str, List[Dict]]:
        """
        加载策略持仓。

        Args:
            template_cols: 模板列名列表
            defaults: 默认值字典

        Returns:
            {sheet_name: [position_records]}
        """
        path = self.resolve_input_path(self.STRATEGY_FILE)
        if not path:
            print(f"策略文件不存在: {self.STRATEGY_FILE}")
            return {}

        try:
            df = pd.read_excel(path, sheet_name='策略明细')
        except Exception as e:
            print(f"读取策略明细失败: {path}，错误: {e}")
            return {}

        buckets: Dict[str, List[Dict]] = {}

        for _, row in df.iterrows():
            underlying = row.get('标的合约', '')
            strategy = row.get('策略类型', '')
            expiry = self.normalize_expiry(row.get('到期月份', ''))

            if is_index_underlying(underlying) and expiry:
                sheet_name = self.sanitize_sheet_name(f"{underlying}_{expiry}_{strategy}")
            else:
                sheet_name = self.sanitize_sheet_name(f"{underlying}_{strategy}")

            legs = self.parse_legs_from_text(row.get('操作要点', ''))

            for leg in legs:
                record = self.build_position_row_from_leg(leg, template_cols, defaults)
                if record is None:
                    continue
                buckets.setdefault(sheet_name, []).append(record)

        return buckets

    def load_arbitrage_positions(self, template_cols: List[str],
                                  defaults: Optional[Dict]) -> Dict[str, List[Dict]]:
        """
        加载套利持仓。

        Args:
            template_cols: 模板列名列表
            defaults: 默认值字典

        Returns:
            {sheet_name: [position_records]}
        """
        path = self.resolve_input_path(self.ARBITRAGE_FILE)
        if not path:
            print(f"套利文件不存在: {self.ARBITRAGE_FILE}")
            return {}

        buckets: Dict[str, List[Dict]] = {}

        try:
            xls = pd.ExcelFile(path)
            for sheet_name in xls.sheet_names:
                if sheet_name in self.EXCLUDED_ARBITRAGE_SHEETS:
                    continue

                df = pd.read_excel(xls, sheet_name=sheet_name)
                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    underlying = row.get('标的合约', '')
                    strategy = row.get('套利类型', sheet_name)
                    text = row.get('交易指令', '') or row.get('操作建议', '')

                    legs = self.parse_legs_from_text(text)
                    expiry = self.extract_expiry_from_legs(legs)

                    if is_index_underlying(underlying) and expiry:
                        out_sheet = self.sanitize_sheet_name(f"{underlying}_{expiry}_{strategy}")
                    else:
                        out_sheet = self.sanitize_sheet_name(f"{underlying}_{strategy}")

                    for leg in legs:
                        record = self.build_position_row_from_leg(leg, template_cols, defaults)
                        if record is None:
                            continue
                        buckets.setdefault(out_sheet, []).append(record)

            return buckets
        except Exception as e:
            print(f"读取套利文件失败: {path}，错误: {e}")
            return {}

    @staticmethod
    def merge_records(records: List[Dict]) -> List[Dict]:
        """
        合并相同合约的持仓记录。

        Args:
            records: 持仓记录列表

        Returns:
            合并后的记录列表
        """
        merged: Dict[str, Dict] = {}

        for record in records:
            symbol = record.get('symbol')
            if MockPositionGenerator.is_missing(symbol):
                continue

            key = str(symbol)
            if key not in merged:
                merged[key] = record
                continue

            target = merged[key]
            for col in ['pos_long', 'pos_short', 'pos', 'volume_long', 'volume_long_today',
                        'volume_short', 'volume_short_today']:
                if col in target and col in record:
                    target[col] = int(
                        MockPositionGenerator.to_number(target.get(col), 0) +
                        MockPositionGenerator.to_number(record.get(col), 0)
                    )

            if 'last_price' in target and MockPositionGenerator.is_missing(target.get('last_price')):
                target['last_price'] = record.get('last_price')

        return list(merged.values())

    def build_mock_positions(self) -> bool:
        """
        构建模拟持仓文件。

        Returns:
            是否成功
        """
        template_df, template_cols, defaults = self.load_template()
        if template_cols is None or template_df is None:
            return False

        buckets: Dict[str, List[Dict]] = {}

        # 加载策略持仓
        for name, bucket in self.load_strategy_positions(template_cols, defaults).items():
            buckets.setdefault(name, []).extend(bucket)

        # 加载套利持仓
        for name, bucket in self.load_arbitrage_positions(template_cols, defaults).items():
            buckets.setdefault(name, []).extend(bucket)

        if not buckets:
            print("未生成任何有效持仓记录。")
            return False

        try:
            output_path = os.path.join(self.base_dir, self.OUTPUT_EXCEL_FILE)
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                total_rows = 0
                for sheet_name, records in buckets.items():
                    merged_records = self.merge_records(records)
                    if not merged_records:
                        continue

                    result_df = pd.DataFrame(merged_records)
                    result_df = result_df.reindex(columns=[str(c) for c in template_cols])

                    # 处理数据类型
                    for col in template_cols:
                        if col in template_df.columns:
                            dtype = template_df[col].dtype
                            try:
                                if dtype.kind in ['i', 'u']:
                                    result_df[col] = pd.to_numeric(result_df[col], errors='coerce')
                                    result_df[col] = result_df[col].fillna(0).astype('int64')
                                elif dtype.kind == 'f':
                                    result_df[col] = pd.to_numeric(result_df[col], errors='coerce')
                            except Exception:
                                continue

                    result_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    total_rows += len(result_df)

            print(f"模拟持仓导出完成: {self.OUTPUT_EXCEL_FILE}，分页数 {len(buckets)}，记录数 {total_rows}")
            return True
        except Exception as e:
            print(f"写入模拟持仓文件失败: {e}")
            return False


# ============================================================
# 模拟持仓管理器
# ============================================================

class MockPositionManager(BasePositionManager):
    """
    模拟持仓管理器。

    用于策略回测，管理虚拟账户资金和持仓。

    Attributes:
        initial_capital: 初始资金
        current_capital: 当前可用资金
        positions: 模拟持仓字典
        trade_history: 交易记录列表
    """

    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, MockPosition] = {}
        self.trade_history: List[TradeRecord] = []
        self._margin_rate = 0.1  # 保证金率 10%
        self._analyzer = PositionAnalyzer()

    def get_positions(self) -> List[Position]:
        """获取所有模拟持仓"""
        return [p.to_position() for p in self.positions.values() if p.volume > 0]

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定合约持仓"""
        mock_pos = self.positions.get(symbol)
        if mock_pos and mock_pos.volume > 0:
            return mock_pos.to_position()
        return None

    def open_position(
        self,
        symbol: str,
        exchange_id: str,
        direction: str,
        volume: int,
        price: float,
        timestamp: datetime = None,
    ) -> bool:
        """
        开仓。

        Args:
            symbol: 合约代码
            exchange_id: 交易所代码
            direction: 方向 (LONG/SHORT)
            volume: 数量
            price: 开仓价格
            timestamp: 时间戳

        Returns:
            是否成功开仓
        """
        margin = self._calculate_margin(price, volume)
        if margin > self.current_capital:
            return False

        self.current_capital -= margin

        if symbol in self.positions:
            # 加仓
            existing = self.positions[symbol]
            total_volume = existing.volume + volume
            total_cost = existing.avg_price * existing.volume + price * volume
            existing.avg_price = total_cost / total_volume
            existing.volume = total_volume
            existing.margin += margin
        else:
            self.positions[symbol] = MockPosition(
                symbol=symbol,
                exchange_id=exchange_id,
                direction=direction,
                volume=volume,
                avg_price=price,
                margin=margin,
                open_time=timestamp or datetime.now(),
                current_price=price,
            )

        self.trade_history.append(TradeRecord(
            action='OPEN',
            symbol=symbol,
            direction=direction,
            volume=volume,
            price=price,
            timestamp=timestamp or datetime.now(),
        ))

        return True

    def close_position(
        self,
        symbol: str,
        volume: int,
        price: float,
        timestamp: datetime = None,
    ) -> Optional[float]:
        """
        平仓。

        Args:
            symbol: 合约代码
            volume: 平仓数量
            price: 平仓价格
            timestamp: 时间戳

        Returns:
            平仓盈亏，失败返回 None
        """
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        if volume > pos.volume:
            volume = pos.volume

        # 计算盈亏
        if pos.direction == "LONG":
            pnl = (price - pos.avg_price) * volume
        else:
            pnl = (pos.avg_price - price) * volume

        # 释放保证金
        margin_released = pos.margin * volume / pos.volume
        self.current_capital += margin_released + pnl

        # 更新持仓
        pos.volume -= volume
        pos.margin -= margin_released

        if pos.volume <= 0:
            del self.positions[symbol]

        self.trade_history.append(TradeRecord(
            action='CLOSE',
            symbol=symbol,
            direction=pos.direction,
            volume=volume,
            price=price,
            timestamp=timestamp or datetime.now(),
            pnl=pnl,
        ))

        return pnl

    def update_prices(self, prices: Dict[str, float]):
        """更新持仓价格"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price

    def _calculate_margin(self, price: float, volume: int) -> float:
        """计算保证金"""
        return price * volume * self._margin_rate

    def set_target(self, symbol: str, target_price: float = None,
                   stop_loss: float = None, take_profit: float = None) -> bool:
        """模拟环境不支持目标设置"""
        return False

    def check_targets(self) -> List[TargetHit]:
        """模拟环境不支持目标检查"""
        return []

    def get_total_pnl(self) -> float:
        """获取累计盈亏"""
        return sum(t.pnl for t in self.trade_history if t.action == 'CLOSE')

    def get_statistics(self) -> dict:
        """获取交易统计"""
        closed_trades = [t for t in self.trade_history if t.action == 'CLOSE']
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl < 0]

        return {
            'total_trades': len(closed_trades),
            'win_count': len(wins),
            'loss_count': len(losses),
            'win_rate': len(wins) / len(closed_trades) if closed_trades else 0,
            'total_pnl': self.get_total_pnl(),
            'current_capital': self.current_capital,
            'return_rate': (self.current_capital - self.initial_capital) / self.initial_capital,
        }

    def analyze_portfolio(self, underlying_price: float = None,
                          time_to_expiry: float = None,
                          iv: float = None) -> Dict[str, Any]:
        """
        分析当前持仓组合。

        Args:
            underlying_price: 标的价格
            time_to_expiry: 剩余时间
            iv: 隐含波动率

        Returns:
            分析结果
        """
        positions = []
        for symbol, p in self.positions.items():
            if p.volume <= 0:
                continue
            positions.append({
                'symbol': p.symbol,
                'net_pos': p.volume if p.direction == 'LONG' else -p.volume,
                'avg_open_price': p.avg_price,
                'is_option': '-' in p.symbol,
                'multiplier': 10,
            })

        return self._analyzer.analyze_portfolio(
            positions,
            underlying_price or 0,
            time_to_expiry or 0.1,
            iv or 0.2
        )

    def calculate_payoff(self, price_range: np.ndarray) -> np.ndarray:
        """
        计算到期损益曲线。

        Args:
            price_range: 价格范围数组

        Returns:
            各价格点的到期损益
        """
        positions = []
        for symbol, p in self.positions.items():
            if p.volume <= 0:
                continue
            positions.append({
                'symbol': p.symbol,
                'net_pos': p.volume if p.direction == 'LONG' else -p.volume,
                'avg_open_price': p.avg_price,
                'is_option': '-' in p.symbol,
                'multiplier': 10,
            })

        return self._analyzer.calculate_payoff(positions, price_range)

    def simulate_pnl_distribution(self, underlying_price: float,
                                   sigma: float,
                                   time_to_expiry: float,
                                   n_paths: int = 1000) -> Dict[str, Any]:
        """
        模拟损益分布。

        Args:
            underlying_price: 标的当前价格
            sigma: 波动率
            time_to_expiry: 剩余时间(年)
            n_paths: 模拟路径数

        Returns:
            损益分布统计
        """
        from trade.position import PriceSimulator

        positions = []
        for symbol, p in self.positions.items():
            if p.volume <= 0:
                continue
            positions.append({
                'symbol': p.symbol,
                'net_pos': p.volume if p.direction == 'LONG' else -p.volume,
                'avg_open_price': p.avg_price,
                'is_option': '-' in p.symbol,
                'multiplier': 10,
                'strike': self._extract_strike(symbol),
                'option_type': self._extract_option_type(symbol),
            })

        if not positions:
            return {'error': 'No valid positions'}

        # 模拟价格路径
        price_paths, _ = PriceSimulator.simulate_gbm(
            underlying_price, 0, sigma, time_to_expiry, n_paths, 30
        )

        # 计算到期损益
        terminal_pnl = PriceSimulator.calculate_terminal_pnl(price_paths, positions)

        # 计算风险指标
        var_95 = RiskMetrics.calculate_var(terminal_pnl, 0.95)
        cvar_95 = RiskMetrics.calculate_cvar(terminal_pnl, 0.95)

        return {
            'mean_pnl': float(np.nanmean(terminal_pnl)),
            'std_pnl': float(np.nanstd(terminal_pnl)),
            'var_95': var_95,
            'cvar_95': cvar_95,
            'prob_profit': float(np.mean(terminal_pnl > 0)),
            'pnl_distribution': terminal_pnl,
        }

    def _extract_strike(self, symbol: str) -> float:
        """从合约代码提取行权价"""
        if not symbol or '-' not in symbol:
            return 0
        parts = symbol.split('-')
        if len(parts) >= 3:
            try:
                return float(parts[-1])
            except ValueError:
                pass
        return 0

    def _extract_option_type(self, symbol: str) -> str:
        """从合约代码提取期权类型"""
        if not symbol:
            return 'CALL'
        if '-C-' in symbol.upper():
            return 'CALL'
        elif '-P-' in symbol.upper():
            return 'PUT'
        return 'CALL'

    def load_mock_positions_from_excel(self, file_path: str) -> bool:
        """
        从Excel文件加载模拟持仓。

        Args:
            file_path: Excel文件路径

        Returns:
            是否加载成功
        """
        try:
            # 支持多sheet
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)

                for _, row in df.iterrows():
                    symbol = self._get_value(row, ['symbol', 'instrument_id', '合约代码'])
                    if not symbol:
                        continue

                    pos_long = int(self._get_value(row, ['pos_long', 'volume_long'], 0))
                    pos_short = int(self._get_value(row, ['pos_short', 'volume_short'], 0))

                    if pos_long > 0 or pos_short > 0:
                        direction = 'LONG' if pos_long > 0 else 'SHORT'
                        volume = max(pos_long, pos_short)
                        price = self._get_value(row, ['last_price', 'current_price', 'avg_price'], 0)
                        exchange_id = self._get_value(row, ['exchange_id', '交易所'], '')

                        self.positions[symbol] = MockPosition(
                            symbol=symbol,
                            exchange_id=exchange_id,
                            direction=direction,
                            volume=volume,
                            avg_price=price,
                            margin=price * volume * self._margin_rate,
                            current_price=price,
                        )

            return True
        except Exception as e:
            print(f"加载模拟持仓文件失败: {e}")
            return False

    def _get_value(self, row: pd.Series, columns: List[str], default: Any = None) -> Any:
        """从行数据获取指定列的值"""
        for col in columns:
            if col in row and pd.notna(row[col]):
                return row[col]
        return default