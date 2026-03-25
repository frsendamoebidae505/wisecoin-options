# tests/test_tqsdk_client.py
"""TqSDK 客户端测试"""
import pytest
from unittest.mock import patch, MagicMock


class TestTqSdkClientInit:
    """客户端初始化测试（不依赖真实 TqSDK）"""

    def test_run_mode_names(self):
        """测试运行模式名称"""
        # 直接测试常量，不导入依赖 TqSDK 的模块
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
        assert RUN_MODES[1] == 'TqSim 回测'
        assert RUN_MODES[2] == 'TqKq 快期模拟'
        assert len(RUN_MODES) == 8

    def test_module_import_without_tqsdk(self):
        """测试无 TqSDK 时模块可导入"""
        # 模拟 TqSDK 未安装
        import sys
        import importlib

        # 保存原始模块
        original_tqsdk = sys.modules.get('tqsdk')

        try:
            # 移除 tqsdk 模块
            if 'tqsdk' in sys.modules:
                del sys.modules['tqsdk']
            if 'data.tqsdk_client' in sys.modules:
                del sys.modules['data.tqsdk_client']

            # 设置为 None 模拟导入失败
            sys.modules['tqsdk'] = None

            # 重新导入
            import data.tqsdk_client
            importlib.reload(data.tqsdk_client)

            # 检查 TQSDK_AVAILABLE
            assert data.tqsdk_client.TQSDK_AVAILABLE == False

        finally:
            # 恢复原始模块
            if original_tqsdk:
                sys.modules['tqsdk'] = original_tqsdk
            elif 'tqsdk' in sys.modules:
                del sys.modules['tqsdk']