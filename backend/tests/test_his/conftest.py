"""ct-his 測試共用 fixtures

HIS 測試使用 CTHIS_TEST_DATA_PATH（非 CTHIS_DATA_PATH）作為測試資料路徑，
避免被 .env 的正式資料路徑污染。
"""

import os
from pathlib import Path

import pytest

# HIS 測試專用資料路徑
_DEFAULT_TEST_DATA = "/mnt/nas/ctos/external-data/cthis-jfmskin/data"

# 測試環境：移除 .env 的 CTHIS_DATA_PATH，避免測試讀到正式資料
_original_cthis_data_path = os.environ.pop("CTHIS_DATA_PATH", None)


@pytest.fixture
def dbf_data_path() -> Path:
    """DBF 測試資料路徑。

    使用 CTHIS_TEST_DATA_PATH 環境變數，
    如果路徑不存在，自動 skip。
    """
    data_path = Path(
        os.environ.get("CTHIS_TEST_DATA_PATH", _DEFAULT_TEST_DATA)
    )
    if not data_path.exists():
        pytest.skip(f"DBF 測試資料不存在: {data_path}")
    return data_path
