# trade/position.py
"""
持仓管理模块。

提供持仓查询、目标管理、止盈止损功能。
分离 TqSDK 相关代码和纯逻辑。

包含:
- TargetConfig: 持仓目标配置
- TargetHit: 目标触发事件
- OptionPricer: 期权定价器 (Black-Scholes)
- PriceSimulator: 价格路径模拟器
- RiskMetrics: 风险度量指标
- PositionAnalyzer: 持仓分析器
- BasePositionManager: 持仓管理器基类
- PositionManager: 持仓管理器
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date
import re
import numpy as np
import pandas as pd

from core.models import Position


# ============================================================
# 目标管理配置
# ============================================================

@dataclass
class TargetConfig:
    """持仓目标配置"""
    symbol: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class TargetHit:
    """目标触发事件"""
    symbol: str
    position: Position
    target: TargetConfig
    hit_type: str  # STOP_LOSS, TAKE_PROFIT, TARGET
    current_price: float
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# ============================================================
# 品种配置
# ============================================================

# 夜盘品种代码集合
NIGHT_TRADING_VARIETIES = {
    # SHFE (上期所)
    'au', 'ag', 'cu', 'al', 'zn', 'pb', 'ni', 'sn', 'ss', 'ru', 'sp', 'rb', 'hc', 'bu', 'fu',
    # DCE (大商所)
    'm', 'y', 'a', 'b', 'p', 'c', 'cs', 'j', 'jm', 'i', 'l', 'v', 'pp', 'pg', 'eb', 'eg',
    # CZCE (郑商所)
    'CF', 'SR', 'TA', 'MA', 'FG', 'RM', 'OI', 'ZC', 'SA', 'PF', 'PK',
    # INE (能源中心)
    'sc', 'nr', 'lu', 'bc'
}

# 卖方保证金范围
MIN_MARGIN = 10000
MAX_MARGIN = 80000


def get_variety_code(symbol: str) -> Optional[str]:
    """
    从合约代码提取品种代码。

    Args:
        symbol: 合约代码，如 'DCE.lh2605-P-14000'

    Returns:
        品种代码，如 'lh'
    """
    try:
        if isinstance(symbol, str) and '.' in symbol:
            part = symbol.split('.', 1)[1]
            match = re.match(r'^[A-Za-z]+', part)
            if match:
                return match.group(0)
    except Exception:
        pass
    return None


def normalize_contract_code(code: Any) -> str:
    """
    标准化合约代码。

    Args:
        code: 原始合约代码

    Returns:
        标准化后的合约代码
    """
    if pd.isna(code):
        return ''
    s = str(code).strip()
    s = re.sub(r'\s+', '', s)
    s = re.sub(r'^[A-Z]+\.', '', s)  # 移除交易所前缀
    s = s.replace('-', '')  # 移除连字符
    return s.upper()


def is_index_underlying(underlying: Any) -> bool:
    """判断标的是否为指数"""
    if underlying is None or pd.isna(underlying):
        return False
    text = str(underlying)
    return text.startswith('SSE.') or text.startswith('SZSE.') or text.startswith('CFFEX.')


# ============================================================
# 期权定价器 (Black-Scholes)
# ============================================================

class OptionPricer:
    """
    高性能期权定价器。

    基于 Black-Scholes 模型，支持向量化批量计算。
    用于计算期权价格和 Greeks。
    """

    @staticmethod
    def norm_cdf(x: np.ndarray) -> np.ndarray:
        """标准正态分布累积分布函数 (向量化)"""
        from scipy import stats
        return stats.norm.cdf(x)

    @staticmethod
    def norm_pdf(x: np.ndarray) -> np.ndarray:
        """标准正态分布概率密度函数 (向量化)"""
        from scipy import stats
        return stats.norm.pdf(x)

    @classmethod
    def d1(cls, S: np.ndarray, K: np.ndarray, r: float, sigma: np.ndarray, T: np.ndarray) -> np.ndarray:
        """计算 Black-Scholes d1 参数 (向量化)"""
        with np.errstate(divide='ignore', invalid='ignore'):
            sqrt_T = np.sqrt(T)
            result = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
            result = np.where((sigma <= 0) | (T <= 0) | (S <= 0) | (K <= 0), np.nan, result)
            return result

    @classmethod
    def d2(cls, S: np.ndarray, K: np.ndarray, r: float, sigma: np.ndarray, T: np.ndarray) -> np.ndarray:
        """计算 Black-Scholes d2 参数 (向量化)"""
        return cls.d1(S, K, r, sigma, T) - sigma * np.sqrt(T)

    @classmethod
    def bs_price(cls, S: Any, K: Any, r: float, sigma: Any, T: Any, option_type: str) -> Any:
        """
        计算 Black-Scholes 期权价格 (向量化)。

        Args:
            S: 标的价格
            K: 行权价
            r: 无风险利率
            sigma: 波动率
            T: 剩余时间(年)
            option_type: 期权类型 'CALL' 或 'PUT'

        Returns:
            期权价格
        """
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)

        T = np.maximum(T, 1e-6)

        d_1 = cls.d1(S, K, r, sigma, T)
        d_2 = d_1 - sigma * np.sqrt(T)

        discount = np.exp(-r * T)

        is_call = option_type.upper() == 'CALL'
        if is_call:
            price = S * cls.norm_cdf(d_1) - K * discount * cls.norm_cdf(d_2)
        else:
            price = K * discount * cls.norm_cdf(-d_2) - S * cls.norm_cdf(-d_1)

        price = np.where((sigma <= 0) | (T <= 0) | (S <= 0) | (K <= 0), np.nan, price)
        price = np.maximum(price, 0.0)

        if price.shape == ():
            return float(price)
        return price

    @classmethod
    def delta(cls, S: Any, K: Any, r: float, sigma: Any, T: Any, option_type: str) -> Any:
        """计算 Delta"""
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)
        T = np.maximum(T, 1e-6)

        d_1 = cls.d1(S, K, r, sigma, T)

        is_call = option_type.upper() == 'CALL'
        if is_call:
            return cls.norm_cdf(d_1)
        else:
            return cls.norm_cdf(d_1) - 1

    @classmethod
    def gamma(cls, S: Any, K: Any, r: float, sigma: Any, T: Any) -> Any:
        """计算 Gamma"""
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)
        T = np.maximum(T, 1e-6)

        d_1 = cls.d1(S, K, r, sigma, T)
        with np.errstate(divide='ignore', invalid='ignore'):
            gamma = cls.norm_pdf(d_1) / (S * sigma * np.sqrt(T))
            gamma = np.where((sigma <= 0) | (S <= 0), np.nan, gamma)
        return gamma

    @classmethod
    def theta(cls, S: Any, K: Any, r: float, sigma: Any, T: Any, option_type: str) -> Any:
        """计算 Theta (返回值为负数)"""
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)
        T = np.maximum(T, 1e-6)

        d_1 = cls.d1(S, K, r, sigma, T)
        d_2 = d_1 - sigma * np.sqrt(T)

        sqrt_T = np.sqrt(T)
        discount = np.exp(-r * T)

        term1 = -S * cls.norm_pdf(d_1) * sigma / (2 * sqrt_T)

        is_call = option_type.upper() == 'CALL'
        if is_call:
            term2 = -r * K * discount * cls.norm_cdf(d_2)
        else:
            term2 = r * K * discount * cls.norm_cdf(-d_2)

        theta = term1 + term2
        theta = np.where((sigma <= 0) | (S <= 0) | (K <= 0), np.nan, theta)
        return theta

    @classmethod
    def vega(cls, S: Any, K: Any, r: float, sigma: Any, T: Any) -> Any:
        """计算 Vega (波动率变化 1% 时期权价格变化)"""
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)
        T = np.maximum(T, 1e-6)

        d_1 = cls.d1(S, K, r, sigma, T)
        vega = S * np.sqrt(T) * cls.norm_pdf(d_1)
        vega = np.where((sigma <= 0) | (S <= 0), np.nan, vega)
        return vega / 100.0

    @classmethod
    def rho(cls, S: Any, K: Any, r: float, sigma: Any, T: Any, option_type: str) -> Any:
        """计算 Rho"""
        S = np.asarray(S, dtype=np.float64)
        K = np.asarray(K, dtype=np.float64)
        sigma = np.asarray(sigma, dtype=np.float64)
        T = np.asarray(T, dtype=np.float64)
        T = np.maximum(T, 1e-6)

        d_1 = cls.d1(S, K, r, sigma, T)
        d_2 = d_1 - sigma * np.sqrt(T)

        discount = np.exp(-r * T)

        is_call = option_type.upper() == 'CALL'
        if is_call:
            rho = K * T * discount * cls.norm_cdf(d_2)
        else:
            rho = -K * T * discount * cls.norm_cdf(-d_2)

        rho = np.where((sigma <= 0) | (S <= 0) | (K <= 0), np.nan, rho)
        return rho / 100.0


# ============================================================
# 价格路径模拟器
# ============================================================

class PriceSimulator:
    """价格路径模拟器 - 几何布朗运动（GBM）"""

    @staticmethod
    def simulate_gbm(S0: float, mu: float, sigma: float, T: float,
                     n_paths: int = 1000, n_steps: int = 30) -> Tuple[np.ndarray, np.ndarray]:
        """
        使用几何布朗运动模拟价格路径。

        Args:
            S0: 初始价格
            mu: 漂移率（年化）
            sigma: 波动率（年化）
            T: 时间长度（年）
            n_paths: 路径数量
            n_steps: 时间步数

        Returns:
            (price_paths, time_points) 价格路径矩阵和时间点数组
        """
        dt = T / n_steps
        time_points = np.linspace(0, T, n_steps + 1)

        dW = np.random.normal(0, np.sqrt(dt), (n_paths, n_steps))

        price_paths = np.zeros((n_paths, n_steps + 1))
        price_paths[:, 0] = S0

        for i in range(1, n_steps + 1):
            price_paths[:, i] = price_paths[:, i-1] * np.exp(
                (mu - 0.5 * sigma**2) * dt + sigma * dW[:, i-1]
            )

        return price_paths, time_points

    @staticmethod
    def calculate_terminal_pnl(price_paths: np.ndarray, positions: List[Dict],
                                r: float = 0.015) -> np.ndarray:
        """
        计算各路径在到期时的盈亏。

        Args:
            price_paths: (n_paths, n_steps+1) 价格路径
            positions: 持仓列表
            r: 无风险利率

        Returns:
            各路径的到期盈亏
        """
        n_paths = price_paths.shape[0]
        terminal_prices = price_paths[:, -1]
        terminal_pnl = np.zeros(n_paths)

        valid_positions = 0

        for pos in positions:
            if pos.get('is_option'):
                strike = pos.get('strike', 0)
                opt_type = pos.get('option_type', 'CALL')
                qty = pos.get('net_pos', 0)
                mult = pos.get('multiplier', 10)
                avg_open_price = pos.get('avg_open_price', 0)

                if avg_open_price <= 0:
                    avg_open_price = pos.get('option_price', 0) or 0

                if strike <= 0 or avg_open_price <= 0 or mult <= 0 or qty == 0:
                    continue

                try:
                    if opt_type == 'CALL':
                        intrinsic = np.maximum(terminal_prices - strike, 0)
                    else:
                        intrinsic = np.maximum(strike - terminal_prices, 0)

                    if qty > 0:
                        pos_pnl = (intrinsic - avg_open_price) * qty * mult
                    else:
                        pos_pnl = (avg_open_price - intrinsic) * abs(qty) * mult

                    terminal_pnl += pos_pnl
                    valid_positions += 1
                except Exception:
                    continue
            else:
                qty = pos.get('net_pos', 0)
                mult = pos.get('multiplier', 10)
                entry_price = pos.get('avg_open_price', 0) or pos.get('price', 0)

                if entry_price <= 0 or mult <= 0 or qty == 0:
                    continue

                try:
                    pos_pnl = (terminal_prices - entry_price) * qty * mult
                    terminal_pnl += pos_pnl
                    valid_positions += 1
                except Exception:
                    continue

        if valid_positions == 0:
            return np.full(n_paths, np.nan)

        return terminal_pnl


# ============================================================
# 风险度量指标
# ============================================================

class RiskMetrics:
    """专业风险度量指标"""

    @staticmethod
    def calculate_var(pnl_array: np.ndarray, confidence: float = 0.95) -> float:
        """
        计算VaR (Value at Risk)

        Args:
            pnl_array: 盈亏数组
            confidence: 置信水平

        Returns:
            VaR值（负数表示损失）
        """
        if len(pnl_array) == 0:
            return 0
        return np.percentile(pnl_array, (1 - confidence) * 100)

    @staticmethod
    def calculate_cvar(pnl_array: np.ndarray, confidence: float = 0.95) -> float:
        """
        计算CVaR (Conditional VaR / Expected Shortfall)

        Args:
            pnl_array: 盈亏数组
            confidence: 置信水平

        Returns:
            CVaR值（尾部平均损失）
        """
        if len(pnl_array) == 0:
            return 0
        var = RiskMetrics.calculate_var(pnl_array, confidence)
        tail_losses = pnl_array[pnl_array <= var]
        if len(tail_losses) == 0:
            return var
        return float(tail_losses.mean())

    @staticmethod
    def calculate_sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.015) -> float:
        """计算Sharpe比率"""
        if len(returns) == 0 or returns.std() == 0:
            return 0
        excess_return = returns.mean() - risk_free_rate / 252
        return float(excess_return / returns.std() * np.sqrt(252))

    @staticmethod
    def calculate_sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.015) -> float:
        """计算Sortino比率（只考虑下行风险）"""
        if len(returns) == 0:
            return 0

        excess_return = returns.mean() - risk_free_rate / 252
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0

        downside_std = downside_returns.std()
        return float(excess_return / downside_std * np.sqrt(252))

    @staticmethod
    def calculate_max_drawdown(pnl_series: np.ndarray) -> float:
        """计算最大回撤"""
        if len(pnl_series) == 0:
            return 0

        cumulative = np.maximum.accumulate(pnl_series)
        drawdown = pnl_series - cumulative
        return abs(float(drawdown.min())) if len(drawdown) > 0 else 0


# ============================================================
# 持仓分析器
# ============================================================

class PositionAnalyzer:
    """
    持仓分析器。

    分析持仓组合，计算Greeks、识别策略、评估风险。
    """

    def __init__(self, risk_free_rate: float = 0.015):
        self.risk_free_rate = risk_free_rate

    def analyze_position(self, position: Dict[str, Any],
                         underlying_price: float,
                         time_to_expiry: float,
                         iv: float) -> Dict[str, Any]:
        """
        分析单个持仓。

        Args:
            position: 持仓信息字典
            underlying_price: 标的价格
            time_to_expiry: 剩余时间(年)
            iv: 隐含波动率

        Returns:
            分析结果字典
        """
        result = {
            'symbol': position.get('symbol', ''),
            'greeks': {},
            'pnl_analysis': {},
        }

        is_option = position.get('is_option', False)

        if is_option:
            strike = position.get('strike', 0)
            opt_type = position.get('option_type', 'CALL')
            qty = position.get('net_pos', 0)

            if strike > 0 and iv > 0:
                # 计算Greeks
                delta = OptionPricer.delta(underlying_price, strike, self.risk_free_rate,
                                          iv, time_to_expiry, opt_type)
                gamma = OptionPricer.gamma(underlying_price, strike, self.risk_free_rate,
                                          iv, time_to_expiry)
                theta = OptionPricer.theta(underlying_price, strike, self.risk_free_rate,
                                          iv, time_to_expiry, opt_type)
                vega = OptionPricer.vega(underlying_price, strike, self.risk_free_rate,
                                        iv, time_to_expiry)

                result['greeks'] = {
                    'delta': delta * qty if not np.isnan(delta) else 0,
                    'gamma': gamma * abs(qty) if not np.isnan(gamma) else 0,
                    'theta': theta * qty if not np.isnan(theta) else 0,
                    'vega': vega * abs(qty) if not np.isnan(vega) else 0,
                }

        return result

    def analyze_portfolio(self, positions: List[Dict[str, Any]],
                          underlying_price: float,
                          time_to_expiry: float,
                          iv: float) -> Dict[str, Any]:
        """
        分析持仓组合。

        Args:
            positions: 持仓列表
            underlying_price: 标的价格
            time_to_expiry: 剩余时间(年)
            iv: 隐含波动率

        Returns:
            组合分析结果
        """
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        strategies = []

        for pos in positions:
            analysis = self.analyze_position(pos, underlying_price, time_to_expiry, iv)
            greeks = analysis.get('greeks', {})
            total_delta += greeks.get('delta', 0)
            total_gamma += greeks.get('gamma', 0)
            total_theta += greeks.get('theta', 0)
            total_vega += greeks.get('vega', 0)

        # 识别策略类型
        strategies = self._identify_strategies(positions)

        return {
            'greeks': {
                'Delta': total_delta,
                'Gamma': total_gamma,
                'Theta': total_theta,
                'Vega': total_vega,
            },
            'strategies': strategies,
            'position_count': len(positions),
        }

    def _identify_strategies(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """识别持仓策略"""
        strategies = []

        # 按期权类型分组
        calls = [p for p in positions if p.get('is_option') and p.get('option_type') == 'CALL']
        puts = [p for p in positions if p.get('is_option') and p.get('option_type') == 'PUT']

        # 简单策略识别
        for pos in positions:
            if pos.get('is_option'):
                qty = pos.get('net_pos', 0)
                opt_type = pos.get('option_type', 'CALL')

                if qty > 0:
                    strategies.append({
                        'type': f'long_{opt_type.lower()}',
                        'name': f'买入{opt_type}',
                        'description': f'买入{pos.get("symbol", "")}',
                    })
                elif qty < 0:
                    strategies.append({
                        'type': f'short_{opt_type.lower()}',
                        'name': f'卖出{opt_type}',
                        'description': f'卖出{pos.get("symbol", "")}',
                    })

        return strategies

    def calculate_payoff(self, positions: List[Dict[str, Any]],
                         price_range: np.ndarray) -> np.ndarray:
        """
        计算到期损益曲线。

        Args:
            positions: 持仓列表
            price_range: 价格范围数组

        Returns:
            各价格点的到期损益
        """
        payoff = np.zeros_like(price_range)

        for pos in positions:
            if pos.get('is_option'):
                strike = pos.get('strike', 0)
                opt_type = pos.get('option_type', 'CALL')
                qty = pos.get('net_pos', 0)
                mult = pos.get('multiplier', 10)
                avg_price = pos.get('avg_open_price', 0)

                if strike <= 0 or mult <= 0 or qty == 0:
                    continue

                if opt_type == 'CALL':
                    intrinsic = np.maximum(price_range - strike, 0)
                else:
                    intrinsic = np.maximum(strike - price_range, 0)

                if qty > 0:
                    pos_payoff = (intrinsic - avg_price) * qty * mult
                else:
                    pos_payoff = (avg_price - intrinsic) * abs(qty) * mult

                payoff += pos_payoff
            else:
                # 期货持仓
                qty = pos.get('net_pos', 0)
                mult = pos.get('multiplier', 10)
                entry = pos.get('avg_open_price', 0)

                if mult <= 0 or qty == 0:
                    continue

                pos_payoff = (price_range - entry) * qty * mult
                payoff += pos_payoff

        return payoff


# ============================================================
# 持仓管理器基类
# ============================================================

class BasePositionManager(ABC):
    """持仓管理器基类"""

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """获取当前持仓"""
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定合约持仓"""
        pass

    @abstractmethod
    def set_target(self, symbol: str, target_price: float = None,
                   stop_loss: float = None, take_profit: float = None) -> bool:
        """设置持仓目标"""
        pass

    @abstractmethod
    def check_targets(self) -> List[TargetHit]:
        """检查是否有持仓触及目标"""
        pass


# ============================================================
# 持仓管理器
# ============================================================

class PositionManager(BasePositionManager):
    """
    持仓管理器。

    管理持仓目标和止盈止损配置。
    注意：此版本不依赖 TqSDK，仅管理配置。
    实际持仓数据需要从外部注入。

    Attributes:
        positions: 当前持仓字典（外部注入）
        targets: 目标配置字典
    """

    def __init__(self):
        self._positions: Dict[str, Position] = {}
        self._targets: Dict[str, TargetConfig] = {}
        self._analyzer = PositionAnalyzer()

    def update_positions(self, positions: List[Position]):
        """更新持仓数据（外部调用）"""
        self._positions = {p.symbol: p for p in positions if p.volume > 0}

    def get_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self._positions.values())

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定合约持仓"""
        return self._positions.get(symbol)

    def set_target(self, symbol: str, target_price: float = None,
                   stop_loss: float = None, take_profit: float = None) -> bool:
        """设置持仓目标"""
        self._targets[symbol] = TargetConfig(
            symbol=symbol,
            target_price=target_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        return True

    def get_target(self, symbol: str) -> Optional[TargetConfig]:
        """获取目标配置"""
        return self._targets.get(symbol)

    def remove_target(self, symbol: str) -> bool:
        """移除目标配置"""
        if symbol in self._targets:
            del self._targets[symbol]
            return True
        return False

    def check_targets(self) -> List[TargetHit]:
        """检查持仓目标"""
        hits = []
        for symbol, target in self._targets.items():
            position = self._positions.get(symbol)
            if not position:
                continue

            current_price = position.current_price

            # 检查止损
            if target.stop_loss and current_price <= target.stop_loss:
                hits.append(TargetHit(
                    symbol=symbol,
                    position=position,
                    target=target,
                    hit_type='STOP_LOSS',
                    current_price=current_price,
                ))
            # 检查止盈
            elif target.take_profit and current_price >= target.take_profit:
                hits.append(TargetHit(
                    symbol=symbol,
                    position=position,
                    target=target,
                    hit_type='TAKE_PROFIT',
                    current_price=current_price,
                ))
            # 检查目标价
            elif target.target_price and current_price >= target.target_price:
                hits.append(TargetHit(
                    symbol=symbol,
                    position=position,
                    target=target,
                    hit_type='TARGET',
                    current_price=current_price,
                ))

        return hits

    def get_total_margin(self) -> float:
        """获取总保证金占用"""
        return sum(p.margin for p in self._positions.values())

    def get_total_unrealized_pnl(self) -> float:
        """获取总未实现盈亏"""
        return sum(p.unrealized_pnl for p in self._positions.values())

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
        for p in self._positions.values():
            positions.append({
                'symbol': p.symbol,
                'net_pos': p.volume if p.direction == 'LONG' else -p.volume,
                'avg_open_price': p.avg_price,
                'is_option': '-' in p.symbol,  # 简单判断是否为期权
                'multiplier': 10,  # 默认合约乘数
            })

        return self._analyzer.analyze_portfolio(
            positions,
            underlying_price or 0,
            time_to_expiry or 0.1,
            iv or 0.2
        )

    def load_positions_from_excel(self, file_path: str) -> bool:
        """
        从Excel文件加载持仓。

        Args:
            file_path: Excel文件路径

        Returns:
            是否加载成功
        """
        try:
            df = pd.read_excel(file_path)
            positions = []

            for _, row in df.iterrows():
                symbol = self._get_symbol_from_row(row)
                if not symbol:
                    continue

                pos_long = self._get_value(row, ['pos_long', '多头持仓', 'volume_long'], 0)
                pos_short = self._get_value(row, ['pos_short', '空头持仓', 'volume_short'], 0)

                if pos_long > 0 or pos_short > 0:
                    position = Position(
                        symbol=symbol,
                        exchange_id=self._get_value(row, ['exchange_id', '交易所'], ''),
                        direction='LONG' if pos_long > 0 else 'SHORT',
                        volume=int(max(pos_long, pos_short)),
                        avg_price=self._get_value(row, ['open_price_long', 'open_price_short', '开仓均价'], 0),
                        current_price=self._get_value(row, ['last_price', '最新价', 'current_price'], 0),
                        unrealized_pnl=self._get_value(row, ['float_profit', '浮动盈亏', 'unrealized_pnl'], 0),
                        margin=self._get_value(row, ['margin', '保证金'], 0),
                    )
                    positions.append(position)

            self.update_positions(positions)
            return True
        except Exception as e:
            print(f"加载持仓文件失败: {e}")
            return False

    def _get_symbol_from_row(self, row: pd.Series) -> Optional[str]:
        """从行数据获取合约代码"""
        candidates = ['symbol', 'instrument_id', '合约代码', '合约']
        for col in candidates:
            if col in row and pd.notna(row[col]):
                return str(row[col])
        return None

    def _get_value(self, row: pd.Series, columns: List[str], default: Any = None) -> Any:
        """从行数据获取指定列的值"""
        for col in columns:
            if col in row and pd.notna(row[col]):
                return row[col]
        return default

    def export_positions_to_excel(self, file_path: str) -> bool:
        """
        导出持仓到Excel文件。

        Args:
            file_path: Excel文件路径

        Returns:
            是否导出成功
        """
        try:
            positions = self.get_positions()
            if not positions:
                return False

            data = []
            for p in positions:
                data.append({
                    'symbol': p.symbol,
                    'exchange_id': p.exchange_id,
                    'direction': p.direction,
                    'volume': p.volume,
                    'avg_price': p.avg_price,
                    'current_price': p.current_price,
                    'unrealized_pnl': p.unrealized_pnl,
                    'margin': p.margin,
                })

            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            return True
        except Exception as e:
            print(f"导出持仓文件失败: {e}")
            return False