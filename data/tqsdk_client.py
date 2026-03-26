# data/tqsdk_client.py
"""
TqSDK 客户端模块。

封装 TqApi 的创建和生命周期管理，支持多种运行模式。

Example:
    >>> async with TqSdkClient(run_mode=2) as client:
    ...     quote = client.api.get_quote("SHFE.au2406")
"""
from typing import Optional
from contextlib import asynccontextmanager

from common.config import Config, AccountConfig
from common.exceptions import APIConnectionError, ConfigurationError
from common.logger import StructuredLogger

# TqSDK 导入（延迟导入以支持测试）
try:
    from tqsdk import TqApi, TqAuth, TqAccount, TqKq, TqSim
    TQSDK_AVAILABLE = True
except ImportError:
    TQSDK_AVAILABLE = False
    TqApi = None
    TqAuth = None
    TqAccount = None
    TqKq = None
    TqSim = None


class TqSdkClient:
    """
    TqSDK 客户端。

    统一管理 TqApi 实例的创建和生命周期。
    支持多种运行模式（回测、模拟、实盘）。

    Attributes:
        run_mode: 运行模式。
        config: 配置实例。

    Example:
        >>> async with TqSdkClient(run_mode=2) as client:
        ...     api = client.api
    """

    # 运行模式定义
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

    def __init__(
        self,
        run_mode: int = 2,
        config: Optional[Config] = None,
        logger: Optional[StructuredLogger] = None,
    ):
        """
        初始化客户端。

        Args:
            run_mode: 运行模式，默认 2（快期模拟）。
            config: 配置实例（可选）。
            logger: 日志器实例（可选）。

        Raises:
            ConfigurationError: 如果 TqSDK 不可用。
        """
        if not TQSDK_AVAILABLE:
            raise ConfigurationError(
                "TqSDK 未安装，请运行: pip install tqsdk"
            )

        self.run_mode = run_mode
        self.config = config or Config(run_mode=run_mode)
        self.logger = logger or StructuredLogger("tqsdk_client")

        self._api: Optional[TqApi] = None
        self._auth: Optional[TqAuth] = None

    async def __aenter__(self) -> 'TqSdkClient':
        """进入异步上下文，初始化 API。"""
        self._api = self._create_api()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出时关闭连接。"""
        self.close()

    @property
    def api(self) -> TqApi:
        """
        获取 TqApi 实例。

        Returns:
            TqApi 实例。

        Raises:
            APIConnectionError: 如果 API 未初始化。
        """
        if self._api is None:
            raise APIConnectionError(
                "API 未初始化，请使用 'async with TqSdkClient()' 上下文管理器"
            )
        return self._api

    def _create_api(self) -> TqApi:
        """
        根据运行模式创建 TqApi。

        Returns:
            TqApi 实例。
        """
        self.logger.info(f"创建 TqApi, 运行模式: {self.RUN_MODES.get(self.run_mode)}")

        # TqAuth 认证（从环境变量或配置获取）
        auth = self._get_auth()

        # 根据运行模式创建不同的 TqApi
        if self.run_mode == 1:
            # TqSim 回测
            return TqApi(TqSim(), auth=auth)

        elif self.run_mode == 2:
            # TqKq 快期模拟
            return TqApi(TqKq(), auth=auth)

        elif self.run_mode in (3, 4, 5, 6, 7, 8):
            # 实盘或 Simnow
            account = self.config.get_account()
            if account is None:
                self.logger.warning(
                    f"运行模式 {self.run_mode} 需要账户配置，"
                    f"请设置环境变量 TQ_BROKER_{self.run_mode}, "
                    f"TQ_ACCOUNT_{self.run_mode}, TQ_PASSWORD_{self.run_mode}"
                )
                # 回退到模拟模式
                return TqApi(TqKq(), auth=auth)

            return TqApi(
                TqAccount(account.broker, account.account, account.password),
                auth=auth
            )

        else:
            raise ConfigurationError(f"无效的运行模式: {self.run_mode}")

    def _get_auth(self) -> Optional[TqAuth]:
        """
        获取 TqAuth 认证。

        Returns:
            TqAuth 实例或 None。
        """
        auth_config = self.config.get_tq_auth()

        if auth_config and auth_config.user and auth_config.password and TqAuth:
            return TqAuth(auth_config.user, auth_config.password)

        return None

    def rebuild_api(self) -> TqApi:
        """
        重建 API 连接（防止超时）。

        Returns:
            新的 TqApi 实例。
        """
        self.logger.info("重建 API 连接")
        self.close()
        self._api = self._create_api()
        return self._api

    def close(self):
        """关闭连接。"""
        if self._api is not None:
            try:
                self._api.close()
            except Exception as e:
                self.logger.warning(f"关闭 API 时出错: {e}")
            finally:
                self._api = None

    @classmethod
    @asynccontextmanager
    async def create(cls, run_mode: int = 2, **kwargs):
        """
        便捷方法：创建客户端上下文。

        Args:
            run_mode: 运行模式。
            **kwargs: 其他参数。

        Yields:
            TqSdkClient 实例。
        """
        client = cls(run_mode=run_mode, **kwargs)
        async with client:
            yield client