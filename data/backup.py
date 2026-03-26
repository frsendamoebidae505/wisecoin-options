# data/backup.py
"""
数据备份模块。

提供数据备份和清理功能。

Example:
    >>> manager = BackupManager(source_dir="./data", backup_dir="./backup")
    >>> manager.create_backup()
"""
import os
import shutil
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

from common.logger import StructuredLogger


class BackupManager:
    """
    备份管理器。

    管理数据备份的创建和清理。

    Attributes:
        source_dir: 源数据目录。
        backup_dir: 备份目录。

    Example:
        >>> manager = BackupManager("./data", "./backup")
        >>> backup_path = manager.create_backup()
    """

    def __init__(
        self,
        source_dir: str,
        backup_dir: str,
        logger: Optional[StructuredLogger] = None,
    ):
        """
        初始化备份管理器。

        Args:
            source_dir: 源数据目录路径。
            backup_dir: 备份目录路径。
            logger: 日志器实例（可选）。
        """
        self.source_dir = Path(source_dir)
        self.backup_dir = Path(backup_dir)
        self.logger = logger or StructuredLogger("backup")

    def create_backup(self, name: Optional[str] = None) -> Optional[str]:
        """
        创建备份。

        Args:
            name: 备份名称（可选），默认使用时间戳。

        Returns:
            备份目录路径，失败返回 None。
        """
        if not self.source_dir.exists():
            self.logger.warning(f"源目录不存在: {self.source_dir}")
            return None

        # 生成备份名称
        if name is None:
            name = datetime.now().strftime("%Y%m%d_%H%M")

        backup_path = self.backup_dir / name

        try:
            # 确保备份目录存在
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # 排除备份目录自身，避免递归复制
            ignore_patterns = shutil.ignore_patterns(
                'backups',           # 排除备份目录
                '__pycache__',       # 排除缓存
                '.venv',             # 排除虚拟环境
                '*.pyc',             # 排除编译文件
            )

            # 复制目录
            shutil.copytree(self.source_dir, backup_path, ignore=ignore_patterns)

            self.logger.info(f"备份创建成功: {backup_path}")
            return str(backup_path)

        except Exception as e:
            self.logger.error(f"备份创建失败: {e}")
            return None

    def clean_old_backups(
        self,
        keep_suffixes: Tuple[str, ...] = ("_0940", "_2040"),
    ) -> Tuple[int, int]:
        """
        清理旧备份，只保留特定后缀的备份。

        Args:
            keep_suffixes: 保留的备份名称后缀。

        Returns:
            (保留数量, 删除数量)
        """
        if not self.backup_dir.exists():
            return 0, 0

        kept = 0
        removed = 0

        for item in self.backup_dir.iterdir():
            if not item.is_dir():
                continue

            if item.name.endswith(keep_suffixes):
                kept += 1
            else:
                try:
                    shutil.rmtree(item)
                    self.logger.info(f"已删除旧备份: {item}")
                    removed += 1
                except Exception as e:
                    self.logger.error(f"删除失败: {item}, {e}")

        self.logger.info(f"清理完成: 保留 {kept} 个, 删除 {removed} 个")
        return kept, removed

    def list_backups(self) -> list:
        """
        列出所有备份。

        Returns:
            备份目录名称列表。
        """
        if not self.backup_dir.exists():
            return []

        return sorted([
            item.name for item in self.backup_dir.iterdir()
            if item.is_dir()
        ])


def main():
    """
    命令行入口。

    等价于原 00wisecoin_options_backup.py。
    """
    import sys

    logger = StructuredLogger("backup")

    # 默认路径
    script_dir = Path(__file__).parent.parent
    source_dir = script_dir
    backup_dir = script_dir / "backups"

    # 解析命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "clean":
            # 清理模式
            manager = BackupManager(str(source_dir), str(backup_dir), logger)
            kept, removed = manager.clean_old_backups()
            print(f"清理完成: 保留 {kept} 个备份, 删除 {removed} 个备份")
            return 0
        elif sys.argv[1] == "list":
            # 列表模式
            manager = BackupManager(str(source_dir), str(backup_dir), logger)
            backups = manager.list_backups()
            if backups:
                print("现有备份:")
                for name in backups:
                    print(f"  - {name}")
            else:
                print("无备份")
            return 0
        else:
            source_dir = Path(sys.argv[1])

    if len(sys.argv) > 2:
        backup_dir = Path(sys.argv[2])

    # 创建备份
    manager = BackupManager(str(source_dir), str(backup_dir), logger)
    backup_path = manager.create_backup()

    if backup_path:
        print(f"备份创建成功: {backup_path}")
        return 0
    else:
        print("备份创建失败")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())