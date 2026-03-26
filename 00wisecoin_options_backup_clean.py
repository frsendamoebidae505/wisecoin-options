"""
期权数据备份目录清理工具 by playbonze
清理 wisecoin_options_backup 目录中非 _0940 和 _2040 结尾的文件夹
"""

import os
import shutil
from datetime import datetime


def move_to_trash(target_path):
    trash_dir = os.path.expanduser("~/.Trash")
    os.makedirs(trash_dir, exist_ok=True)
    base_name = os.path.basename(target_path.rstrip(os.sep))
    dest_path = os.path.join(trash_dir, base_name)
    if os.path.exists(dest_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        counter = 1
        while True:
            candidate = f"{base_name}_{timestamp}_{counter}"
            candidate_path = os.path.join(trash_dir, candidate)
            if not os.path.exists(candidate_path):
                dest_path = candidate_path
                break
            counter += 1
    shutil.move(target_path, dest_path)
    return dest_path


def clean_backup_directories(backup_root_dir):
    if not os.path.exists(backup_root_dir):
        print(f"⚠️  备份根目录不存在: {backup_root_dir}")
        return

    keep_suffixes = ("_0940", "_2040")
    moved_count = 0
    kept_count = 0
    failed_count = 0

    print("\n开始清理旧备份目录...")
    for name in os.listdir(backup_root_dir):
        dir_path = os.path.join(backup_root_dir, name)
        if not os.path.isdir(dir_path):
            continue
        if name.endswith(keep_suffixes):
            kept_count += 1
            continue
        try:
            dest_path = move_to_trash(dir_path)
            print(f"  🗑️  已移动到回收站: {name} -> {dest_path}")
            moved_count += 1
        except Exception as e:
            print(f"  ❌ 移动到回收站失败 {name}: {e}")
            failed_count += 1

    print("\n" + "="*60)
    print("🧹 清理完成!")
    print(f"✅ 保留目录: {kept_count} 个")
    print(f"🗑️  已移动到回收站: {moved_count} 个")
    print(f"❌ 移动失败: {failed_count} 个")
    print("="*60 + "\n")


if __name__ == "__main__":
    print("="*60)
    print("WiseCoin 期权备份目录清理工具")
    print("="*60 + "\n")
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        backup_root_dir = os.path.join(script_dir, "wisecoin_options_backup")
        clean_backup_directories(backup_root_dir)
    except Exception as e:
        print(f"\n❌ 清理过程出错: {e}")
        import traceback
        traceback.print_exc()
