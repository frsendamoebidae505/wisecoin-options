# tests/test_excel_io.py
"""Excel 读写模块测试"""
import os
import pytest
import pandas as pd
from common.excel_io import ExcelWriter, ExcelReader


class TestExcelWriter:
    """Excel 写入器测试"""

    @pytest.fixture
    def sample_df(self):
        """测试数据"""
        return pd.DataFrame({
            'symbol': ['SHFE.au2406', 'SHFE.ag2406'],
            'price': [480.0, 6000.0],
            'volume': [100, 50],
        })

    @pytest.fixture
    def temp_file(self, tmp_path):
        """临时文件路径"""
        return str(tmp_path / "test.xlsx")

    def test_write_dataframe(self, sample_df, temp_file):
        """测试写入单个 DataFrame"""
        writer = ExcelWriter()
        writer.write_dataframe(sample_df, file_path=temp_file)
        assert os.path.exists(temp_file)

    def test_write_multiple_sheets(self, temp_file):
        """测试写入多个 Sheet"""
        df1 = pd.DataFrame({'a': [1, 2]})
        df2 = pd.DataFrame({'b': [3, 4]})

        writer = ExcelWriter()
        writer.write_multiple({
            'Sheet1': df1,
            'Sheet2': df2,
        }, file_path=temp_file)

        # 验证
        reader = ExcelReader()
        sheets = reader.read_all_sheets(temp_file)
        assert 'Sheet1' in sheets
        assert 'Sheet2' in sheets


class TestExcelReader:
    """Excel 读取器测试"""

    @pytest.fixture
    def sample_excel(self, tmp_path):
        """创建测试 Excel 文件"""
        file_path = str(tmp_path / "sample.xlsx")
        df = pd.DataFrame({
            'symbol': ['A', 'B'],
            'price': [100.0, 200.0],
        })
        df.to_excel(file_path, index=False)
        return file_path

    def test_read_sheet(self, sample_excel):
        """测试读取单个 Sheet"""
        reader = ExcelReader()
        df = reader.read_sheet(sample_excel)
        assert len(df) == 2
        assert 'symbol' in df.columns

    def test_read_all_sheets(self, sample_excel):
        """测试读取所有 Sheet"""
        reader = ExcelReader()
        sheets = reader.read_all_sheets(sample_excel)
        assert isinstance(sheets, dict)