#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时监控配置生成模块。

功能：
从 wisecoin-货权联动.xlsx 提取标的合约并生成 wisecoin-symbol-live.json 配置文件。

Usage:
    python3 -m data.live_symbol
"""
import json
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from common.logger import StructuredLogger

logger = StructuredLogger("live_symbol")


class LiveSymbolGenerator:
    """实时监控配置生成器。"""

    # 默认配置
    DEFAULT_INPUT_FILE = "wisecoin-货权联动.xlsx"
    DEFAULT_SHEET_NAME = "货权联动"
    DEFAULT_OUTPUT_FILE = "wisecoin-symbol-live.json"
    DEFAULT_MIN_OPTION_OI = 0.3   # 最小期权沉淀(亿)
    DEFAULT_MIN_FUTURE_OI = 8.0   # 最小期货沉淀(亿)

    def __init__(
        self,
        input_file: Optional[str] = None,
        sheet_name: Optional[str] = None,
        output_file: Optional[str] = None,
        min_option_oi: Optional[float] = None,
        min_future_oi: Optional[float] = None,
        work_dir: Optional[str] = None
    ):
        """
        初始化生成器。

        Args:
            input_file: 输入Excel文件名
            sheet_name: 工作表名称
            output_file: 输出JSON文件名
            min_option_oi: 最小期权沉淀(亿)
            min_future_oi: 最小期货沉淀(亿)
            work_dir: 工作目录，默认为项目根目录
        """
        self.input_file = input_file or self.DEFAULT_INPUT_FILE
        self.sheet_name = sheet_name or self.DEFAULT_SHEET_NAME
        self.output_file = output_file or self.DEFAULT_OUTPUT_FILE
        self.min_option_oi = min_option_oi or self.DEFAULT_MIN_OPTION_OI
        self.min_future_oi = min_future_oi or self.DEFAULT_MIN_FUTURE_OI
        self.work_dir = Path(work_dir) if work_dir else PROJECT_ROOT

    def generate(self) -> List[str]:
        """
        生成实时监控标的配置。

        Returns:
            标的合约列表
        """
        input_path = self.work_dir / self.input_file

        # 检查输入文件
        if not input_path.exists():
            logger.error(f"未找到核心文件: {input_path}")
            return []

        logger.info(f"正在读取 {input_path}...")

        # 读取Excel
        try:
            df = pd.read_excel(input_path, sheet_name=self.sheet_name)
        except Exception as e:
            logger.error(f"读取Excel失败: {e}")
            return []

        if df.empty:
            logger.warning(f"分页 {self.sheet_name} 为空")
            return []

        # 检查必要列 - 支持多种列名
        # 优先使用分列，回退使用合并列
        if "期权沉淀(亿)" in df.columns and "期货沉淀(亿)" in df.columns:
            df['期权沉淀(亿)'] = pd.to_numeric(df['期权沉淀(亿)'], errors='coerce')
            df['期货沉淀(亿)'] = pd.to_numeric(df['期货沉淀(亿)'], errors='coerce')
        elif "沉淀资金(亿)" in df.columns:
            # 回退：使用合并的沉淀资金列
            logger.info("使用 '沉淀资金(亿)' 列进行筛选")
            df['期权沉淀(亿)'] = pd.to_numeric(df['沉淀资金(亿)'], errors='coerce')
            df['期货沉淀(亿)'] = 0  # 设为0，仅使用沉淀资金筛选
        else:
            # 检查是否有其他可能的列名
            possible_oi_cols = ['沉淀资金(亿)', '沉淀资金', 'OpenInterest']
            found_col = None
            for col in possible_oi_cols:
                if col in df.columns:
                    found_col = col
                    break

            if found_col:
                logger.info(f"使用 '{found_col}' 列进行筛选")
                df['期权沉淀(亿)'] = pd.to_numeric(df[found_col], errors='coerce')
                df['期货沉淀(亿)'] = 0
            else:
                logger.error(f"缺失必要的列，可用列: {list(df.columns)}")
                return []

        # 筛选条件: 期权沉淀 > min_option_oi OR 期货沉淀 > min_future_oi
        condition = (
            (df['期权沉淀(亿)'] > self.min_option_oi) |
            (df['期货沉淀(亿)'] > self.min_future_oi)
        )
        filtered_df = df[condition].copy()

        logger.info(f"筛选条件: 期权沉淀(亿) > {self.min_option_oi} 或 期货沉淀(亿) > {self.min_future_oi}")
        logger.info(f"原始记录数: {len(df)}, 筛选后记录数: {len(filtered_df)}")

        # 提取标的合约并去重
        live_symbols = []
        seen_symbols = set()

        for symbol in filtered_df['标的合约']:
            symbol = str(symbol).strip()
            if symbol and symbol != "nan" and symbol not in seen_symbols:
                live_symbols.append(symbol)
                seen_symbols.add(symbol)

        if not live_symbols:
            logger.warning("未能提取到任何有效标的合约")
            return []

        # 保存JSON
        output_path = self.work_dir / self.output_file
        logger.info(f"正在导出 {len(live_symbols)} 个标的合约到 {output_path}...")

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(live_symbols, f, ensure_ascii=False, indent=4)

        logger.info(f"✅ 配置文件生成成功: {output_path}")

        return live_symbols


def main():
    """命令行入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="生成实时监控标的配置文件"
    )
    parser.add_argument(
        "--input", "-i",
        default=LiveSymbolGenerator.DEFAULT_INPUT_FILE,
        help=f"输入Excel文件 (默认: {LiveSymbolGenerator.DEFAULT_INPUT_FILE})"
    )
    parser.add_argument(
        "--sheet", "-s",
        default=LiveSymbolGenerator.DEFAULT_SHEET_NAME,
        help=f"工作表名称 (默认: {LiveSymbolGenerator.DEFAULT_SHEET_NAME})"
    )
    parser.add_argument(
        "--output", "-o",
        default=LiveSymbolGenerator.DEFAULT_OUTPUT_FILE,
        help=f"输出JSON文件 (默认: {LiveSymbolGenerator.DEFAULT_OUTPUT_FILE})"
    )
    parser.add_argument(
        "--min-option-oi",
        type=float,
        default=LiveSymbolGenerator.DEFAULT_MIN_OPTION_OI,
        help=f"最小期权沉淀(亿) (默认: {LiveSymbolGenerator.DEFAULT_MIN_OPTION_OI})"
    )
    parser.add_argument(
        "--min-future-oi",
        type=float,
        default=LiveSymbolGenerator.DEFAULT_MIN_FUTURE_OI,
        help=f"最小期货沉淀(亿) (默认: {LiveSymbolGenerator.DEFAULT_MIN_FUTURE_OI})"
    )

    args = parser.parse_args()

    generator = LiveSymbolGenerator(
        input_file=args.input,
        sheet_name=args.sheet,
        output_file=args.output,
        min_option_oi=args.min_option_oi,
        min_future_oi=args.min_future_oi
    )

    symbols = generator.generate()
    print(f"\n生成 {len(symbols)} 个标的合约")

    return 0 if symbols else 1


if __name__ == "__main__":
    sys.exit(main())