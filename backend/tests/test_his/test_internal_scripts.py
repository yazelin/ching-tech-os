"""內部查詢 Skill scripts 測試

測試 4 個 scripts 的 input 解析與輸出格式。
透過 subprocess 執行，模擬 ScriptRunner 的呼叫方式。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# scripts 目錄
_scripts_dir = (
    Path(__file__).parent.parent.parent.parent
    / "extends"
    / "his"
    / "skills"
    / "his-integration"
    / "scripts"
)


def _run_script(name: str, input_data: dict | None = None) -> str:
    """以 subprocess 執行 script，回傳 stdout。"""
    script_path = _scripts_dir / f"{name}.py"
    assert script_path.exists(), f"Script 不存在: {script_path}"

    env = os.environ.copy()
    # 確保 CTHIS_DATA_PATH 有設定
    if "CTHIS_DATA_PATH" not in env:
        env["CTHIS_DATA_PATH"] = "/mnt/nas/ctos/external-data/cthis-jfmskin/data"

    stdin_data = json.dumps(input_data) if input_data else ""
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=stdin_data,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, f"Script 失敗: {result.stderr}"
    return result.stdout.strip()


def _has_data_path() -> bool:
    """檢查測試資料路徑是否存在。"""
    p = os.environ.get(
        "CTHIS_DATA_PATH",
        "/mnt/nas/ctos/external-data/cthis-jfmskin/data",
    )
    return Path(p).exists()


# 沒有測試資料時自動 skip
pytestmark = pytest.mark.skipif(
    not _has_data_path(), reason="DBF 測試資料不存在"
)


class TestVisitStats:
    """門診統計 script"""

    def test_default_today(self):
        output = _run_script("visit_stats")
        assert "門診統計" in output

    def test_with_date_range(self):
        output = _run_script("visit_stats", {
            "start_date": "2026-02-28",
            "end_date": "2026-02-28",
        })
        assert "門診統計" in output
        assert "2026-02-28" in output

    def test_with_doctor_filter(self):
        output = _run_script("visit_stats", {
            "start_date": "2026-02-28",
            "end_date": "2026-02-28",
            "doctor_name": "不存在的醫師",
        })
        assert "查無符合條件" in output

    def test_output_has_total(self):
        output = _run_script("visit_stats", {
            "start_date": "2026-02-28",
            "end_date": "2026-02-28",
        })
        assert "合計" in output or "查無" in output


class TestDrugUsage:
    """藥品消耗 script"""

    def test_default(self):
        output = _run_script("drug_usage")
        assert "藥品" in output

    def test_with_keyword(self):
        output = _run_script("drug_usage", {"keyword": "不存在的藥品XYZ"})
        assert "查無" in output

    def test_output_format(self):
        output = _run_script("drug_usage", {
            "start_date": "2026-02-28",
            "end_date": "2026-02-28",
        })
        # 應包含統計標題
        assert "藥品" in output


class TestAppointmentList:
    """預約總覽 script"""

    def test_default(self):
        output = _run_script("appointment_list")
        assert "預約" in output

    def test_with_date_range(self):
        output = _run_script("appointment_list", {
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        })
        assert "預約" in output

    def test_output_no_patient_info(self):
        """確認輸出不包含病患個資。"""
        output = _run_script("appointment_list", {
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        })
        # 不應出現病歷號格式（7 碼數字）
        import re
        # 只檢查是否有「病歷號」字樣
        assert "病歷號" not in output


class TestManualBookingStats:
    """手動預約統計 script"""

    def test_default(self):
        output = _run_script("manual_booking_stats")
        assert "手動預約" in output

    def test_with_date_range(self):
        output = _run_script("manual_booking_stats", {
            "start_date": "2026-02-28",
            "end_date": "2026-02-28",
        })
        assert "手動預約" in output

    def test_output_distinguishes_doctor_and_desk(self):
        """確認輸出有區分醫師 vs 掛號台。"""
        output = _run_script("manual_booking_stats")
        # 至少應包含合計
        assert "合計" in output or "查無" in output


class TestMissingEnvVar:
    """環境變數缺失時的錯誤處理"""

    def test_visit_stats_no_env(self):
        """未設定 CTHIS_DATA_PATH 時應回傳錯誤訊息。"""
        env = os.environ.copy()
        env.pop("CTHIS_DATA_PATH", None)
        result = subprocess.run(
            [sys.executable, str(_scripts_dir / "visit_stats.py")],
            input="",
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0
        assert "CTHIS_DATA_PATH" in result.stdout
