#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# data/klines.py
"""
K线数据获取模块。

从期权行情文件中提取标的期货合约，获取其K线数据。
支持CSV和XLSX格式的期权行情文件。

等价于原 14wisecoin_options_client_data_klines.py。

Example:
    >>> from data.klines import FuturesKlineFetcher
    >>> async with TqSdkClient() as client:
    ...     fetcher = FuturesKlineFetcher(client.api)
    ...     await fetcher.fetch_and_save(
    ...         quote_file="wisecoin-期权行情.csv",
    ...         output_file="wisecoin-期货K线.csv"
    ...     )

Usage:
    python3 -m data.klines
"""
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
from openpyxl.utils import get_column_letter

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.logger import StructuredLogger

# TqSDK 导入（延迟导入以支持测试）
try:
    from tqsdk import TqApi, TqAuth, TqKq
    from tqsdk.tafunc import time_to_str
    TQSDK_AVAILABLE = True
except ImportError:
    TQSDK_AVAILABLE = False
    TqApi = None
    TqAuth = None
    TqKq = None
    time_to_str = None


# 默认文件路径
TEMP_DIR = ""
DEFAULT_QUOTE_FILE = os.path.join(TEMP_DIR, "wisecoin-期权行情.csv")  # 改用CSV格式
DEFAULT_QUOTE_FILE_XLSX = os.path.join(TEMP_DIR, "wisecoin-期权行情.xlsx")  # 兼容旧格式
DEFAULT_OUTPUT_FILE = os.path.join(TEMP_DIR, "wisecoin-期货K线.csv")  # 改用CSV格式
DEFAULT_OUTPUT_FILE_XLSX = os.path.join(TEMP_DIR, "wisecoin-期货K线.xlsx")  # 兼容旧格式


class FuturesKlineFetcher:
    """
    期货K线数据获取器。

    从期权行情文件中提取标的期货合约代码，获取其日K线数据并导出到Excel。

    Attributes:
        api: TqApi 实例。
        logger: 日志器实例。
        default_data_length: 默认K线数据长度。
        default_duration: 默认K线周期（秒）。

    Example:
        >>> from data.tqsdk_client import TqSdkClient
        >>> async with TqSdkClient(run_mode=2) as client:
        ...     fetcher = FuturesKlineFetcher(client.api)
        ...     result = await fetcher.fetch_and_save("quotes.xlsx", "klines.xlsx")
        ...     print(f"成功: {result['success']}, 失败: {result['fail']}")
    """

    # 默认参数
    DEFAULT_DATA_LENGTH = 250  # 默认获取250个日K
    DEFAULT_DURATION = 24 * 60 * 60  # 日K线周期（秒）

    # 跳过的Sheet名称
    SKIP_SHEETS = {"Summary", "Progress", "Summary_Stats"}

    def __init__(
        self,
        api: 'TqApi',
        logger: Optional[StructuredLogger] = None,
    ):
        """
        初始化K线获取器。

        Args:
            api: TqApi 实例。
            logger: 日志器实例（可选，默认创建新实例）。

        Raises:
            ImportError: 如果 TqSDK 未安装。
        """
        if not TQSDK_AVAILABLE:
            raise ImportError("TqSDK 未安装，请运行: pip install tqsdk")

        self.api = api
        self.logger = logger or StructuredLogger("klines")

    async def fetch_and_save(
        self,
        quote_file: str,
        output_file: str,
        data_length: int = DEFAULT_DATA_LENGTH,
        duration: int = DEFAULT_DURATION,
    ) -> Dict[str, int]:
        """
        获取期货K线数据并保存到Excel。

        从期权行情文件中提取所有唯一的 underlying_symbol，获取其日K线数据，
        保存到指定的Excel文件中，每个合约一个Sheet。

        Args:
            quote_file: 期权行情Excel文件路径。
            output_file: 输出K线Excel文件路径。
            data_length: K线数据长度，默认250。
            duration: K线周期（秒），默认86400（日K）。

        Returns:
            包含成功/失败计数的字典:
                - success: 成功获取的合约数
                - fail: 获取失败的合约数

        Raises:
            FileNotFoundError: 如果行情文件不存在。
        """
        if not os.path.exists(quote_file):
            self.logger.warning(f"未找到期权行情文件: {quote_file}")
            return {"success": 0, "fail": 0, "error": "文件不存在"}

        try:
            # 1. 提取标的合约列表
            underlyings = self._extract_underlyings(quote_file)
            if not underlyings:
                self.logger.warning("未在期权行情中发现有效的标的期货合约")
                return {"success": 0, "fail": 0, "error": "无有效标的"}

            self.logger.info(
                f"获取到 {len(underlyings)} 个标的期货合约，"
                f"准备获取{data_length}个日K线数据..."
            )

            # 2. 获取所有K线数据
            all_klines, counts = await self._fetch_all_klines(
                underlyings, data_length, duration
            )

            if not all_klines:
                self.logger.error("未能获取到任何期货K线数据")
                return {"success": 0, "fail": counts["fail"], "error": "无数据"}

            # 3. 导出到文件（优先CSV格式）
            if output_file.endswith('.csv'):
                self._export_to_csv(all_klines, output_file)
            else:
                self._export_to_excel(all_klines, output_file)

            self.logger.info(
                f"期货K线保存完成: {output_file}, "
                f"成功: {counts['success']}个合约, 失败: {counts['fail']}个合约"
            )

            return counts

        except Exception as e:
            self.logger.error(f"获取期货K线异常: {e}")
            return {"success": 0, "fail": 0, "error": str(e)}

    def _extract_underlyings(self, quote_file: str) -> List[str]:
        """
        从期权行情文件中提取唯一的标的期货合约代码。

        支持CSV和XLSX格式。

        Args:
            quote_file: 期权行情文件路径。

        Returns:
            排序后的标的合约代码列表。
        """
        self.logger.info(f"正在读取 {quote_file} 以获取标的期货列表...")

        all_underlyings: Set[str] = set()

        if quote_file.endswith('.csv'):
            # CSV格式：直接读取单个文件
            try:
                df = pd.read_csv(quote_file)
                if 'underlying_symbol' in df.columns:
                    symbols = df['underlying_symbol'].dropna().unique().tolist()
                    for s in symbols:
                        if s and isinstance(s, str) and '.' in s:
                            all_underlyings.add(s)
            except Exception as e:
                self.logger.warning(f"读取CSV文件失败: {e}")
        else:
            # XLSX格式：读取多个sheet
            xls = pd.ExcelFile(quote_file)
            for sheet_name in xls.sheet_names:
                if sheet_name in self.SKIP_SHEETS:
                    continue

                df = pd.read_excel(xls, sheet_name=sheet_name)
                if 'underlying_symbol' not in df.columns:
                    continue

                symbols = df['underlying_symbol'].dropna().unique().tolist()
                for s in symbols:
                    if s and isinstance(s, str) and '.' in s:
                        all_underlyings.add(s)

        return sorted(list(all_underlyings))

    async def _fetch_all_klines(
        self,
        symbols: List[str],
        data_length: int,
        duration: int,
    ) -> tuple:
        """
        批量获取多个合约的K线数据。

        Args:
            symbols: 合约代码列表。
            data_length: K线数据长度。
            duration: K线周期（秒）。

        Returns:
            元组 (all_klines_dict, counts_dict):
                - all_klines_dict: 合约代码 -> DataFrame 的映射
                - counts_dict: {"success": int, "fail": int}
        """
        all_klines: Dict[str, pd.DataFrame] = {}
        success_count = 0
        fail_count = 0

        for idx, symbol in enumerate(symbols):
            sym_str = str(symbol).strip()
            try:
                self.logger.info(
                    f"[{idx + 1}/{len(symbols)}] 获取 {sym_str} 的日K线数据..."
                )

                klines = await self._fetch_single_kline(
                    sym_str, data_length, duration
                )

                if klines is None or klines.empty:
                    self.logger.warning(f"合约 {sym_str} K线数据为空，跳过")
                    fail_count += 1
                    continue

                # 添加合约标识
                klines['symbol'] = sym_str
                klines['product'] = self._extract_product(sym_str)

                # 转换时间戳为可读格式
                if 'datetime' in klines.columns:
                    klines['datetime_str'] = klines['datetime'].apply(
                        lambda x: time_to_str(x) if pd.notna(x) and x > 0 else ''
                    )

                all_klines[sym_str] = klines
                success_count += 1

            except asyncio.TimeoutError:
                self.logger.warning(f"获取合约 {sym_str} K线数据超时，跳过")
                fail_count += 1
            except Exception as e:
                self.logger.warning(f"获取合约 {sym_str} K线数据失败: {e}")
                fail_count += 1

        return all_klines, {"success": success_count, "fail": fail_count}

    async def _fetch_single_kline(
        self,
        symbol: str,
        data_length: int,
        duration: int,
    ) -> Optional[pd.DataFrame]:
        """
        获取单个合约的K线数据。

        Args:
            symbol: 合约代码。
            data_length: K线数据长度。
            duration: K线周期（秒）。

        Returns:
            K线DataFrame，失败返回None。
        """
        # 使用 get_kline_serial 获取K线数据
        klines = await self.api.get_kline_serial(
            symbol,
            duration_seconds=duration,
            data_length=data_length
        )

        if klines is None:
            return None

        # 转换为 DataFrame
        return klines.copy()

    def _extract_product(self, symbol: str) -> str:
        """
        从合约代码中提取品种代码。

        Args:
            symbol: 合约代码 (如 "SHFE.au2406")。

        Returns:
            品种代码 (如 "SHFE.au")。
        """
        if '.' not in symbol:
            return "Unknown"

        parts = symbol.split('.')
        exchange = parts[0]
        code_match = re.match(r'^[a-zA-Z]+', parts[1])

        if code_match:
            return f"{exchange}.{code_match.group(0)}"

        return symbol

    def _export_to_csv(
        self,
        all_klines: Dict[str, pd.DataFrame],
        output_file: str,
    ):
        """
        将K线数据导出到CSV文件（高效格式）。

        将所有合约的K线数据合并到一个CSV文件中，
        添加 symbol 列用于区分不同合约。

        Args:
            all_klines: 合约代码 -> DataFrame 的映射。
            output_file: 输出文件路径。
        """
        self.logger.info(f"正在将期货K线导出到 {output_file}...")

        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        all_rows = []
        for symbol, klines_df in all_klines.items():
            if klines_df.empty:
                continue
            # 确保 symbol 列存在
            df_copy = klines_df.copy()
            if 'symbol' not in df_copy.columns:
                df_copy['symbol'] = symbol
            all_rows.append(df_copy)

        if not all_rows:
            self.logger.warning("没有K线数据需要导出")
            return

        # 合并所有数据
        combined_df = pd.concat(all_rows, ignore_index=True)

        # 按 symbol 和 datetime 排序
        sort_cols = []
        if 'symbol' in combined_df.columns:
            sort_cols.append('symbol')
        if 'datetime' in combined_df.columns:
            sort_cols.append('datetime')

        if sort_cols:
            combined_df = combined_df.sort_values(sort_cols)

        # 保存为CSV
        combined_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        self.logger.info(f"已保存 {len(combined_df)} 条K线记录到 {output_file}")

    def _export_to_excel(
        self,
        all_klines: Dict[str, pd.DataFrame],
        output_file: str,
    ):
        """
        将K线数据导出到Excel文件。

        每个合约一个Sheet，另有一个Summary Sheet汇总最新数据。

        Args:
            all_klines: 合约代码 -> DataFrame 的映射。
            output_file: 输出文件路径。
        """
        self.logger.info(f"正在将期货K线导出到 {output_file}...")

        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # 1. Summary Sheet - 汇总所有合约的最新K线
            self._write_summary_sheet(writer, all_klines)

            # 2. 每个合约一个Sheet
            for symbol, klines_df in all_klines.items():
                self._write_symbol_sheet(writer, symbol, klines_df)

    def _write_summary_sheet(
        self,
        writer: pd.ExcelWriter,
        all_klines: Dict[str, pd.DataFrame],
    ):
        """
        写入Summary Sheet，汇总所有合约的最新K线数据。

        Args:
            writer: pandas Excel writer。
            all_klines: K线数据字典。
        """
        summary_rows = []
        for symbol, klines_df in all_klines.items():
            if not klines_df.empty:
                latest = klines_df.iloc[-1].to_dict()
                summary_rows.append(latest)

        if not summary_rows:
            return

        summary_df = pd.DataFrame(summary_rows)

        # 按 product 排序
        if 'product' in summary_df.columns:
            summary_df = summary_df.sort_values('product')

        summary_df.to_excel(writer, sheet_name='Summary', index=False)

        # 调整列宽
        ws = writer.sheets['Summary']
        self._adjust_column_width(ws, summary_df)

    def _write_symbol_sheet(
        self,
        writer: pd.ExcelWriter,
        symbol: str,
        klines_df: pd.DataFrame,
    ):
        """
        写入单个合约的K线Sheet。

        Args:
            writer: pandas Excel writer。
            symbol: 合约代码。
            klines_df: K线数据DataFrame。
        """
        # 生成Sheet名称（Excel限制31字符）
        sheet_name = symbol.replace('.', '_')[:31]

        # 按时间升序排列（最早的在前）
        if 'datetime' in klines_df.columns:
            klines_df = klines_df.sort_values('datetime', ascending=True)

        klines_df.to_excel(writer, sheet_name=sheet_name, index=False)

        # 调整格式
        ws = writer.sheets[sheet_name]
        ws.freeze_panes = 'A2'  # 冻结表头
        self._adjust_column_width(ws, klines_df)

    def _adjust_column_width(
        self,
        worksheet,
        df: pd.DataFrame,
        max_width: int = 40,
    ):
        """
        自动调整Excel列宽。

        Args:
            worksheet: openpyxl worksheet。
            df: DataFrame。
            max_width: 最大列宽。
        """
        for col_idx, col in enumerate(df.columns, 1):
            try:
                max_len = max(
                    df[col].astype(str).map(len).max()
                    if not df[col].empty else 0,
                    len(str(col))
                ) + 2
            except Exception:
                max_len = 15

            worksheet.column_dimensions[get_column_letter(col_idx)].width = min(
                max_len, max_width
            )


async def fetch_futures_klines(
    api: 'TqApi',
    quote_file: str,
    output_file: str,
    data_length: int = 250,
    logger: Optional[StructuredLogger] = None,
) -> Dict[str, int]:
    """
    便捷函数：获取期货K线数据并保存。

    这是一个简化的接口，直接使用TqApi获取K线数据。

    Args:
        api: TqApi 实例。
        quote_file: 期权行情Excel文件路径。
        output_file: 输出K线Excel文件路径。
        data_length: K线数据长度，默认250。
        logger: 日志器实例（可选）。

    Returns:
        包含成功/失败计数的字典。

    Example:
        >>> from data.tqsdk_client import TqSdkClient
        >>> async with TqSdkClient(run_mode=2) as client:
        ...     result = await fetch_futures_klines(
        ...         client.api,
        ...         "quotes.xlsx",
        ...         "klines.xlsx"
        ...     )
    """
    fetcher = FuturesKlineFetcher(api, logger)
    return await fetcher.fetch_and_save(quote_file, output_file, data_length)


async def run_klines_fetcher(
    quote_file: str = DEFAULT_QUOTE_FILE,
    output_file: str = DEFAULT_OUTPUT_FILE,
    data_length: int = 250,
    run_mode: int = 2,
) -> Dict[str, int]:
    """
    运行K线获取任务（内部使用，需要传入 api 实例）。

    Args:
        quote_file: 期权行情文件路径
        output_file: 输出K线文件路径
        data_length: K线数据长度
        run_mode: TqSDK运行模式 (2=快期模拟)

    Returns:
        结果字典
    """
    # 这个函数需要在外部创建 api 后调用
    # 参见 main() 函数的实现
    pass


def main():
    """
    命令行入口。

    等价于原 14wisecoin_options_client_data_klines.py。
    """
    logger = StructuredLogger("klines")

    if not TQSDK_AVAILABLE:
        print("错误: TqSDK 未安装，请运行: pip install tqsdk")
        return 1

    # 检查行情文件（优先CSV格式，兼容XLSX格式）
    quote_file = DEFAULT_QUOTE_FILE
    if not os.path.exists(quote_file):
        quote_file = DEFAULT_QUOTE_FILE_XLSX
    if not os.path.exists(quote_file):
        quote_file = "wisecoin-期权行情.csv"
    if not os.path.exists(quote_file):
        quote_file = "wisecoin-期权行情.xlsx"

    if not os.path.exists(quote_file):
        logger.error(f"期权行情文件不存在")
        return 1

    output_file = DEFAULT_OUTPUT_FILE

    # 确保临时目录存在
    temp_dir = os.path.dirname(output_file)
    if temp_dir and not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)

    logger.info("=" * 60)
    logger.info("开始获取期货K线数据...")
    logger.info("=" * 60)

    try:
        # 创建 TqApi 实例（同步方式，与原始脚本一致）
        api = TqApi(TqKq(), auth=TqAuth('huaying', 'bonze13'))

        # 创建 K线获取器
        fetcher = FuturesKlineFetcher(api, logger)

        # 定义异步任务（与原始脚本模式一致）
        async def run_task():
            result = await fetcher.fetch_and_save(quote_file, output_file, 250)
            logger.info("=" * 60)
            logger.info("期货K线数据获取完成!")
            logger.info(f"输出文件: {output_file}")
            logger.info(f"成功: {result.get('success', 0)}, 失败: {result.get('fail', 0)}")
            logger.info("=" * 60)
            api.close()
            sys.exit(0)

        # 创建任务
        api.create_task(run_task())

        # 等待更新
        while True:
            api.wait_update()

    except SystemExit:
        # 正常退出
        return 0
    except Exception as e:
        logger.error(f"获取K线数据异常: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())