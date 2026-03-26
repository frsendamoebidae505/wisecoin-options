"""
期权数据备份工具 by playbonze
自动备份期权和期货相关的Excel文件及配置文件
"""

import os
import shutil
from datetime import datetime


def backup_wisecoin_data():
    """
    备份 WiseCoin 期权数据文件
    
    运行逻辑：
    1. 在 wisecoin_options_backup 目录下创建带时间戳的子目录（格式：20260104_0947）
    2. 移动指定的9个 .xlsx 文件到该目录
    3. 拷贝 wisecoin-symbol-params.json 到该目录
    """
    
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 备份根目录
    backup_root_dir = os.path.join(script_dir, "wisecoin_options_backup")
    
    # 创建备份根目录（如果不存在）
    if not os.path.exists(backup_root_dir):
        os.makedirs(backup_root_dir)
        print(f"✅ 创建备份根目录: {backup_root_dir}")
    
    # 生成时间戳目录名（格式：20260104_0947）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_dir = os.path.join(backup_root_dir, timestamp)
    
    # 创建带时间戳的备份目录
    os.makedirs(backup_dir, exist_ok=True)
    print(f"✅ 创建备份目录: {backup_dir}")
    
    # 需要移动的 Excel 文件列表
    excel_files_to_move = [
        "wisecoin-货权联动.xlsx",
        "wisecoin-期货行情-无期权.xlsx",
        "wisecoin-期货行情.xlsx",
        "wisecoin-期权参考.xlsx",
        "wisecoin-期权排行.xlsx",
        "wisecoin-期权品种.xlsx",
        "wisecoin-期权行情.xlsx",
        "wisecoin-市场概览.xlsx",
        "wisecoin-openctp数据.xlsx"
    ]
    
    # 需要拷贝的 JSON 文件
    json_file_to_copy = "wisecoin-symbol-params.json"
    
    # 统计结果
    moved_count = 0
    skipped_count = 0
    
    # 移动 Excel 文件
    print("\n开始移动 Excel 文件...")
    for filename in excel_files_to_move:
        source_path = os.path.join(script_dir, filename)
        dest_path = os.path.join(backup_dir, filename)
        
        if os.path.exists(source_path):
            try:
                shutil.move(source_path, dest_path)
                print(f"  ✅ 已移动: {filename}")
                moved_count += 1
            except Exception as e:
                print(f"  ❌ 移动失败 {filename}: {e}")
                skipped_count += 1
        else:
            print(f"  ⚠️  文件不存在: {filename}")
            skipped_count += 1
    
    # 拷贝 JSON 配置文件
    print("\n开始拷贝配置文件...")
    json_source = os.path.join(script_dir, json_file_to_copy)
    json_dest = os.path.join(backup_dir, json_file_to_copy)
    
    if os.path.exists(json_source):
        try:
            shutil.copy2(json_source, json_dest)
            print(f"  ✅ 已拷贝: {json_file_to_copy}")
        except Exception as e:
            print(f"  ❌ 拷贝失败 {json_file_to_copy}: {e}")
    else:
        print(f"  ⚠️  文件不存在: {json_file_to_copy}")
    
    # 输出备份结果摘要
    print("\n" + "="*60)
    print(f"📦 备份完成!")
    print(f"📁 备份位置: {backup_dir}")
    print(f"✅ 成功移动: {moved_count} 个文件")
    print(f"⚠️  跳过/失败: {skipped_count} 个文件")
    print("="*60 + "\n")


if __name__ == "__main__":
    print("="*60)
    print("WiseCoin 期权数据备份工具")
    print("="*60 + "\n")
    
    try:
        backup_wisecoin_data()
    except Exception as e:
        print(f"\n❌ 备份过程出错: {e}")
        import traceback
        traceback.print_exc()
