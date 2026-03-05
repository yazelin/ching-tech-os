"""診間叫號進度測試"""

import sys
from datetime import date
from pathlib import Path

import pytest

_his_root = Path(__file__).parent.parent.parent.parent / "extends" / "his"
if str(_his_root) not in sys.path:
    sys.path.insert(0, str(_his_root))

from core.services.vision_his import get_queue_status


class TestGetQueueStatus:
    """計算看診進度"""

    @pytest.mark.asyncio
    async def test_known_date(self, dbf_data_path):
        """用測試資料中已知的日期查詢"""
        # 1150228 = 2026-02-28，測試資料最新一天
        result = await get_queue_status(
            target_date=date(2026, 2, 28),
            dbf_base_path=str(dbf_data_path),
        )
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "period_id" in item
            assert "doctor_name" in item
            assert "completed" in item
            assert "total" in item
            assert item["completed"] >= 0
            assert item["total"] >= item["completed"]

    @pytest.mark.asyncio
    async def test_no_data_date(self, dbf_data_path):
        """無看診資料的日期"""
        result = await get_queue_status(
            target_date=date(2020, 1, 1),
            dbf_base_path=str(dbf_data_path),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_periods(self, dbf_data_path):
        """2026-02-28 應有上午和下午兩個時段"""
        result = await get_queue_status(
            target_date=date(2026, 2, 28),
            dbf_base_path=str(dbf_data_path),
        )
        period_ids = [r["period_id"] for r in result]
        # 應該有 "15"（上午）和 "03"（下午）
        assert "15" in period_ids
        assert "03" in period_ids
