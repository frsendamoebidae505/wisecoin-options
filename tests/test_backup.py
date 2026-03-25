# tests/test_backup.py
"""备份模块测试"""
import pytest
import os
import tempfile
import shutil
from data.backup import BackupManager


class TestBackupManager:
    """备份管理器测试"""

    @pytest.fixture
    def temp_dirs(self):
        """创建临时目录"""
        source = tempfile.mkdtemp()
        backup = tempfile.mkdtemp()
        yield source, backup
        shutil.rmtree(source, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)

    def test_create_backup_manager(self, temp_dirs):
        """测试创建备份管理器"""
        source, backup = temp_dirs
        manager = BackupManager(source_dir=source, backup_dir=backup)
        assert manager is not None

    def test_create_backup(self, temp_dirs):
        """测试创建备份"""
        source, backup = temp_dirs
        # 在源目录创建文件
        with open(os.path.join(source, "test.txt"), "w") as f:
            f.write("test content")

        manager = BackupManager(source_dir=source, backup_dir=backup)
        backup_path = manager.create_backup()

        assert backup_path is not None
        assert os.path.exists(backup_path)

    def test_clean_old_backups(self, temp_dirs):
        """测试清理旧备份"""
        source, backup = temp_dirs
        manager = BackupManager(source_dir=source, backup_dir=backup)

        # 创建多个备份目录
        os.makedirs(os.path.join(backup, "20260101_0930"))
        os.makedirs(os.path.join(backup, "20260101_0940"))
        os.makedirs(os.path.join(backup, "20260101_1000"))

        # 只保留 _0940 和 _2040 结尾的
        manager.clean_old_backups(keep_suffixes=("_0940", "_2040"))

        remaining = os.listdir(backup)
        assert "20260101_0940" in remaining
        assert "20260101_0930" not in remaining