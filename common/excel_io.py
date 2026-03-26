# common/excel_io.py
"""
WiseCoin Excel 读写模块。

封装 pandas Excel 操作，提供统一的读写接口。

Example:
    >>> writer = ExcelWriter()
    >>> writer.write_dataframe(df, "output.xlsx")

    >>> reader = ExcelReader()
    >>> df = reader.read_sheet("input.xlsx")
"""
from typing import Dict, Optional
import pandas as pd


class ExcelWriter:
    """
    Excel 写入器。

    提供统一的 Excel 写入接口。

    Example:
        >>> writer = ExcelWriter()
        >>> writer.write_dataframe(df, "output.xlsx")
    """

    def write_dataframe(
        self,
        df: pd.DataFrame,
        file_path: str,
        sheet_name: str = 'Sheet1',
        auto_adjust_width: bool = True,
    ):
        """
        写入单个 DataFrame 到 Excel。

        Args:
            df: 要写入的数据。
            file_path: 输出文件路径。
            sheet_name: Sheet 名称，默认 'Sheet1'。
            auto_adjust_width: 是否自动调整列宽，默认 True。
        """
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            if auto_adjust_width:
                self._adjust_column_width(writer, df, sheet_name)

    def write_multiple(
        self,
        data: Dict[str, pd.DataFrame],
        file_path: str,
        auto_adjust_width: bool = True,
    ):
        """
        写入多个 DataFrame 到 Excel 的不同 Sheet。

        Args:
            data: {sheet_name: dataframe} 映射。
            file_path: 输出文件路径。
            auto_adjust_width: 是否自动调整列宽。
        """
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for sheet_name, df in data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)

                if auto_adjust_width:
                    self._adjust_column_width(writer, df, sheet_name)

    def append_sheet(
        self,
        df: pd.DataFrame,
        file_path: str,
        sheet_name: str,
    ):
        """
        追加 Sheet 到已有 Excel 文件。

        Args:
            df: 要写入的数据。
            file_path: Excel 文件路径。
            sheet_name: 新 Sheet 名称。
        """
        with pd.ExcelWriter(
            file_path, engine='openpyxl', mode='a', if_sheet_exists='replace'
        ) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    def _adjust_column_width(self, writer, df: pd.DataFrame, sheet_name: str):
        """
        自动调整列宽。

        Args:
            writer: ExcelWriter 实例。
            df: 数据。
            sheet_name: Sheet 名称。
        """
        worksheet = writer.sheets[sheet_name]
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            ) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)


class ExcelReader:
    """
    Excel 读取器。

    提供统一的 Excel 读取接口。

    Example:
        >>> reader = ExcelReader()
        >>> df = reader.read_sheet("input.xlsx")
    """

    def read_sheet(
        self,
        file_path: str,
        sheet_name: str = 0,
    ) -> pd.DataFrame:
        """
        读取单个 Sheet。

        Args:
            file_path: Excel 文件路径。
            sheet_name: Sheet 名称或索引，默认第一个 Sheet。

        Returns:
            DataFrame 数据。
        """
        return pd.read_excel(file_path, sheet_name=sheet_name)

    def read_all_sheets(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """
        读取所有 Sheet。

        Args:
            file_path: Excel 文件路径。

        Returns:
            {sheet_name: dataframe} 映射。
        """
        return pd.read_excel(file_path, sheet_name=None)