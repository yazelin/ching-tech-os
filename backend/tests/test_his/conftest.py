"""ct-his 測試共用 fixtures"""

import os
from pathlib import Path

import pytest


@pytest.fixture
def dbf_data_path() -> Path:
    """DBF 測試資料路徑（從 CTHIS_DATA_PATH 環境變數讀取）。

    如果環境變數未設定或路徑不存在，自動 skip。
    """
    data_path = Path(
        os.environ.get(
            "CTHIS_DATA_PATH",
            "/mnt/nas/ctos/external-data/cthis-jfmskin/data",
        )
    )
    if not data_path.exists():
        pytest.skip(f"DBF 測試資料不存在: {data_path}")
    return data_path
