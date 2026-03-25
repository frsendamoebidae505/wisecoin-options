# tests/test_config.py
"""配置模块测试"""
import os
import pytest
from common.config import (
    Config,
    AccountConfig,
    TradingConfig,
    DataConfig,
    SchedulerConfig,
)


class TestTradingConfig:
    """交易配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = TradingConfig()
        assert config.max_position_per_symbol == 10
        assert config.max_margin_usage == 0.8
        assert config.default_order_volume == 1
        assert config.daily_loss_limit == 0.05


class TestDataConfig:
    """数据配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = DataConfig()
        assert config.quote_batch_size == 200
        assert config.save_interval == 3000
        assert config.api_rebuild_interval == 3000
        assert config.kline_data_length == 250
        assert config.cache_ttl_seconds == 60


class TestSchedulerConfig:
    """调度配置测试"""

    def test_default_scheduled_times(self):
        """测试默认调度时间"""
        config = SchedulerConfig()
        assert len(config.scheduled_times) == 13
        assert (20, 40) in config.scheduled_times
        assert (9, 40) in config.scheduled_times

    def test_check_interval(self):
        """测试检查间隔"""
        config = SchedulerConfig()
        assert config.check_interval == 30
        assert config.cooldown_minutes == 5


class TestConfig:
    """全局配置测试"""

    def test_default_run_mode(self):
        """测试默认运行模式"""
        config = Config()
        assert config.run_mode == 2

    def test_run_mode_names(self):
        """测试运行模式名称"""
        config = Config()
        assert config.RUN_MODES[1] == "TqSim 回测"
        assert config.RUN_MODES[2] == "TqKq 快期模拟"
        assert config.RUN_MODES[6] == "金信期货实盘"

    def test_custom_run_mode(self):
        """测试自定义运行模式"""
        config = Config(run_mode=6)
        assert config.run_mode == 6

    def test_sub_configs_exist(self):
        """测试子配置存在"""
        config = Config()
        assert isinstance(config.trading, TradingConfig)
        assert isinstance(config.data, DataConfig)
        assert isinstance(config.scheduler, SchedulerConfig)

    def test_get_account_without_env(self):
        """测试无环境变量时获取账户"""
        config = Config(run_mode=99)
        assert config.get_account() is None