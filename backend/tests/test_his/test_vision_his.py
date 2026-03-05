"""vision_his 查詢層測試"""

import sys
from datetime import date
from pathlib import Path

import pytest

# 將 extends/his 加入 sys.path
_his_root = Path(__file__).parent.parent.parent.parent / "extends" / "his"
if str(_his_root) not in sys.path:
    sys.path.insert(0, str(_his_root))

from core.services.vision_his import (
    query_patient,
    query_visits,
    query_appointments,
    query_prescriptions,
    get_doctor_name,
    query_vislog_bookings,
)


# === 病患查詢 ===


class TestQueryPatient:
    """查詢病患資料（CO01M）"""

    @pytest.mark.asyncio
    async def test_existing_patient(self, dbf_data_path):
        """查詢已知病歷號"""
        # CO05O 資料中出現的病歷號
        result = await query_patient(
            "0022931", dbf_base_path=str(dbf_data_path)
        )
        assert result is not None
        assert result["patient_id"] == "0022931"
        assert result["name"]  # 有姓名
        assert "birth_date" in result

    @pytest.mark.asyncio
    async def test_nonexistent_patient(self, dbf_data_path):
        """查詢不存在的病歷號"""
        result = await query_patient(
            "9999999", dbf_base_path=str(dbf_data_path)
        )
        assert result is None


# === 就診紀錄查詢 ===


class TestQueryVisits:
    """查詢就診紀錄（CO05O）"""

    @pytest.mark.asyncio
    async def test_by_patient(self, dbf_data_path):
        """依病歷號查詢"""
        results = await query_visits(
            "0022931", dbf_base_path=str(dbf_data_path)
        )
        assert len(results) > 0
        assert all(r["patient_id"] == "0022931" for r in results)

    @pytest.mark.asyncio
    async def test_by_date_range(self, dbf_data_path):
        """依日期範圍查詢"""
        results = await query_visits(
            start_date=date(2026, 2, 28),
            end_date=date(2026, 2, 28),
            dbf_base_path=str(dbf_data_path),
        )
        assert len(results) > 0
        assert all(r["visit_date"] == date(2026, 2, 28) for r in results)

    @pytest.mark.asyncio
    async def test_by_doctor(self, dbf_data_path):
        """依醫師（TIDS）過濾"""
        results = await query_visits(
            doctor_id="15",
            start_date=date(2026, 2, 28),
            end_date=date(2026, 2, 28),
            dbf_base_path=str(dbf_data_path),
        )
        assert len(results) > 0
        assert all(r["doctor_id"] == "15" for r in results)

    @pytest.mark.asyncio
    async def test_status_filter(self, dbf_data_path):
        """依狀態過濾"""
        results = await query_visits(
            status="F",
            start_date=date(2026, 2, 28),
            end_date=date(2026, 2, 28),
            dbf_base_path=str(dbf_data_path),
        )
        assert all(r["status"] == "F" for r in results)

    @pytest.mark.asyncio
    async def test_limit(self, dbf_data_path):
        """回傳筆數限制"""
        results = await query_visits(
            dbf_base_path=str(dbf_data_path), limit=5
        )
        assert len(results) <= 5


# === 預約查詢 ===


class TestQueryAppointments:
    """查詢預約紀錄（co05b）"""

    @pytest.mark.asyncio
    async def test_query(self, dbf_data_path):
        """基本預約查詢"""
        results = await query_appointments(
            dbf_base_path=str(dbf_data_path), limit=10
        )
        assert isinstance(results, list)
        # co05b 有 1815 筆，應該能查到資料
        assert len(results) > 0


# === 處方查詢 ===


class TestQueryPrescriptions:
    """查詢處方明細（CO02M）"""

    @pytest.mark.asyncio
    async def test_by_patient(self, dbf_data_path):
        """依病歷號查詢"""
        results = await query_prescriptions(
            "0022931", dbf_base_path=str(dbf_data_path)
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_limit(self, dbf_data_path):
        """回傳筆數限制"""
        results = await query_prescriptions(
            dbf_base_path=str(dbf_data_path), limit=5
        )
        assert len(results) <= 5


# === 醫師姓名 ===


class TestGetDoctorName:
    """查詢醫師姓名（VIS00）"""

    @pytest.mark.asyncio
    async def test_existing_doctor(self, dbf_data_path):
        """查詢存在的醫師"""
        # TIDS="15" 是資料中常見的醫師
        name = await get_doctor_name(
            "15", dbf_base_path=str(dbf_data_path)
        )
        assert name is not None
        assert len(name.strip()) > 0

    @pytest.mark.asyncio
    async def test_nonexistent_doctor(self, dbf_data_path):
        """查詢不存在的醫師"""
        name = await get_doctor_name(
            "99", dbf_base_path=str(dbf_data_path)
        )
        assert name is None


# === VISLOG 手動預約統計 ===


class TestQueryVislogBookings:
    """統計醫師手動預約次數（VISLOG）"""

    @pytest.mark.asyncio
    async def test_query_all(self, dbf_data_path):
        """查詢所有手動預約"""
        results = await query_vislog_bookings(
            dbf_base_path=str(dbf_data_path)
        )
        assert isinstance(results, list)
        # 測試資料中有預約紀錄
        if results:
            assert "name" in results[0]
            assert "count" in results[0]
            assert "is_doctor" in results[0]

    @pytest.mark.asyncio
    async def test_date_filter(self, dbf_data_path):
        """依日期範圍過濾"""
        results = await query_vislog_bookings(
            start_date=date(2026, 2, 28),
            end_date=date(2026, 2, 28),
            dbf_base_path=str(dbf_data_path),
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_operator_parsing(self, dbf_data_path):
        """驗證操作者名稱解析"""
        results = await query_vislog_bookings(
            dbf_base_path=str(dbf_data_path)
        )
        for r in results:
            if r["is_doctor"]:
                # 醫師名稱不應包含末尾數字
                assert not r["name"][-1].isdigit() if r["name"] else True
            else:
                assert r["name"] == "掛號台"
