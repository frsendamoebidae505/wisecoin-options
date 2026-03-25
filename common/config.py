# common/config.py
"""
WiseCoin 配置管理模块。

提供统一的配置管理，支持运行模式切换、账户配置、业务参数配置。

Example:
    >>> config = Config(run_mode=2)
    >>> print(config.RUN_MODES[config.run_mode])
    'TqKq 快期模拟'
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import os


@dataclass
class AccountConfig:
    """
    账户配置。

    Attributes:
        broker: 期货公司名称。
        account: 账户号。
        password: 密码（应从环境变量读取）。
    """
    broker: str
    account: str
    password: str


@dataclass
class TradingConfig:
    """
    交易配置。

    Attributes:
        max_position_per_symbol: 单品种最大持仓手数。
        max_margin_usage: 最大保证金占用比例。
        default_order_volume: 默认下单手数。
        daily_loss_limit: 日内亏损限制比例。
    """
    max_position_per_symbol: int = 10
    max_margin_usage: float = 0.8
    default_order_volume: int = 1
    daily_loss_limit: float = 0.05


@dataclass
class DataConfig:
    """
    数据配置。

    Attributes:
        quote_batch_size: 行情获取批次大小。
        save_interval: 数据保存间隔。
        api_rebuild_interval: API 重建间隔。
        kline_data_length: K 线数据长度。
        cache_ttl_seconds: 缓存过期时间（秒）。
    """
    quote_batch_size: int = 200
    save_interval: int = 3000
    api_rebuild_interval: int = 3000
    kline_data_length: int = 250
    cache_ttl_seconds: int = 60


@dataclass
class SchedulerConfig:
    """
    调度配置。

    Attributes:
        scheduled_times: 调度时间列表 (hour, minute)。
        check_interval: 检查间隔（秒）。
        cooldown_minutes: 冷却时间（分钟）。
    """
    scheduled_times: List[tuple] = field(default_factory=lambda: [
        (20, 40), (21, 40), (22, 40), (23, 40), (0, 40), (1, 40),
        (8, 40), (9, 40), (10, 40), (12, 40), (13, 40), (14, 40), (15, 16)
    ])
    check_interval: int = 30
    cooldown_minutes: int = 5


class Config:
    """
    全局配置管理器。

    管理所有配置项，支持从环境变量加载敏感信息。

    Attributes:
        run_mode: 运行模式。
        trading: 交易配置。
        data: 数据配置。
        scheduler: 调度配置。

    Example:
        >>> config = Config(run_mode=2)
        >>> account = config.get_account()
    """

    RUN_MODES = {
        1: 'TqSim 回测',
        2: 'TqKq 快期模拟',
        3: 'Simnow 模拟',
        4: '渤海期货实盘',
        5: '华安期货实盘',
        6: '金信期货实盘',
        7: '东吴期货实盘',
        8: '宏源期货实盘',
    }

    def __init__(self, run_mode: int = 2, config_path: Optional[str] = None):
        """
        初始化配置。

        Args:
            run_mode: 运行模式，默认 2（快期模拟）。
            config_path: 配置文件路径（可选）。
        """
        self.run_mode = run_mode
        self.trading = TradingConfig()
        self.data = DataConfig()
        self.scheduler = SchedulerConfig()
        self._accounts: Dict[int, AccountConfig] = {}

        if config_path:
            self._load_from_file(config_path)
        self._load_accounts()

    def _load_from_file(self, path: str):
        """
        从文件加载配置。

        Args:
            path: 配置文件路径。
        """
        # TODO: 实现 JSON/YAML 配置文件加载
        pass

    def _load_accounts(self):
        """从环境变量加载账户配置。"""
        for mode in self.RUN_MODES.keys():
            broker = os.getenv(f'TQ_BROKER_{mode}')
            account = os.getenv(f'TQ_ACCOUNT_{mode}')
            password = os.getenv(f'TQ_PASSWORD_{mode}')
            if broker and account and password:
                self._accounts[mode] = AccountConfig(
                    broker=broker,
                    account=account,
                    password=password,
                )

    def get_account(self) -> Optional[AccountConfig]:
        """
        获取当前运行模式的账户配置。

        Returns:
            账户配置，如果未配置则返回 None。
        """
        return self._accounts.get(self.run_mode)