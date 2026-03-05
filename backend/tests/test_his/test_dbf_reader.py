"""dbf_reader 單元測試"""

from datetime import date

import pytest

# extends/his/core 不在 Python path 中，需要動態 import
import importlib
import sys
from pathlib import Path

# 將 extends/his 加入 sys.path
_his_root = Path(__file__).parent.parent.parent.parent / "extends" / "his"
if str(_his_root) not in sys.path:
    sys.path.insert(0, str(_his_root))

from core.services.dbf_reader import roc_to_date, date_to_roc, read_dbf, read_dbf_schema


# === 民國年轉換測試 ===


class TestRocToDate:
    """民國年 → 西元日期"""

    def test_normal(self):
        assert roc_to_date("1150305") == date(2026, 3, 5)

    def test_roc_89(self):
        """民國 89 年（邊界值）"""
        assert roc_to_date("0890101") == date(2000, 1, 1)

    def test_roc_112(self):
        assert roc_to_date("1121102") == date(2023, 11, 2)

    def test_empty_string(self):
        assert roc_to_date("") is None

    def test_none(self):
        assert roc_to_date(None) is None

    def test_short_string(self):
        assert roc_to_date("115") is None

    def test_non_numeric(self):
        assert roc_to_date("ABCDEFG") is None

    def test_invalid_month(self):
        assert roc_to_date("1151301") is None

    def test_invalid_day(self):
        assert roc_to_date("1150332") is None

    def test_spaces(self):
        """全空白字串"""
        assert roc_to_date("       ") is None


class TestDateToRoc:
    """西元日期 → 民國年"""

    def test_normal(self):
        assert date_to_roc(date(2026, 3, 5)) == "1150305"

    def test_year_2000(self):
        assert date_to_roc(date(2000, 1, 1)) == "0890101"

    def test_single_digit_month_day(self):
        assert date_to_roc(date(2023, 1, 5)) == "1120105"


# === DBF 讀取測試（需要測試資料）===


class TestReadDbf:
    """讀取 DBF 檔案"""

    def test_read_co01m(self, dbf_data_path):
        """讀取 CO01M 病患主檔前幾筆"""
        records = read_dbf(dbf_data_path / "CO01M.DBF")
        assert len(records) > 0
        first = records[0]
        # 確認關鍵欄位存在
        assert "KCSTMR" in first
        assert "MNAME" in first
        assert "MBIRTHDT" in first

    def test_encoding_cp950(self, dbf_data_path):
        """確認中文姓名能正確解碼"""
        records = read_dbf(dbf_data_path / "CO01M.DBF")
        # 找一筆有姓名的
        named = [r for r in records if r.get("MNAME", "").strip()]
        assert len(named) > 0
        # 中文姓名不應包含替換字元
        name = named[0]["MNAME"].strip()
        assert len(name) > 0

    def test_file_not_found(self):
        """不存在的檔案"""
        with pytest.raises(FileNotFoundError):
            read_dbf("/tmp/nonexistent.DBF")


class TestReadDbfSchema:
    """讀取 DBF Schema"""

    def test_schema_co01m(self, dbf_data_path):
        """讀取 CO01M 欄位定義"""
        schema = read_dbf_schema(dbf_data_path / "CO01M.DBF")
        assert len(schema) > 0
        first = schema[0]
        assert "name" in first
        assert "type" in first
        assert "length" in first
        # CO01M 的第一個欄位應該是 KCSTMR
        assert schema[0]["name"] == "KCSTMR"
