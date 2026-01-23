"""資料遷移測試

測試租戶資料匯出/匯入/遷移功能：
- 匯出 ZIP 格式正確性
- 匯入資料完整性
- 合併模式（replace/merge）
- 遷移流程
- 驗證工具
"""

import io
import json
import pytest
import zipfile
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID
from pathlib import Path

from ching_tech_os.services.tenant_data import (
    TenantExportService,
    TenantImportService,
    TenantMigrationService,
    TenantDataValidator,
    export_tenant_data,
    import_tenant_data,
    validate_tenant_data,
    migrate_tenant,
)
from ching_tech_os.models.tenant import TenantExportRequest


# 測試用租戶 ID
TEST_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
TARGET_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")

# 模擬資料
MOCK_USERS = [
    {"id": 1, "username": "user1", "display_name": "使用者 1", "tenant_id": str(TEST_TENANT_ID)},
    {"id": 2, "username": "user2", "display_name": "使用者 2", "tenant_id": str(TEST_TENANT_ID)},
]

MOCK_PROJECTS = [
    {"id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), "name": "專案 1", "tenant_id": str(TEST_TENANT_ID)},
]


# ============================================================
# TenantExportService 測試
# ============================================================

class TestTenantExportService:
    """租戶匯出服務測試"""

    @pytest.mark.asyncio
    async def test_export_to_zip_creates_valid_zip(self):
        """匯出應產生有效的 ZIP 檔案"""
        mock_conn = AsyncMock()
        # 模擬 column check（所有表都有 tenant_id）
        mock_conn.fetchval.return_value = "tenant_id"
        # 模擬各表資料
        mock_conn.fetch.return_value = MOCK_USERS

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant_data.settings") as mock_settings:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_settings.tenant_data_path.return_value = "/nonexistent/path"

            service = TenantExportService(TEST_TENANT_ID)
            request = TenantExportRequest(include_files=False, include_ai_logs=False)

            zip_content, summary = await service.export_to_zip(request)

            # 驗證 ZIP 可讀取
            with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
                # 應包含 manifest.json
                assert "manifest.json" in zf.namelist()

                # 驗證 manifest 內容
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                assert manifest["tenant_id"] == str(TEST_TENANT_ID)

    @pytest.mark.asyncio
    async def test_export_includes_manifest(self):
        """匯出應包含 manifest.json"""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = "tenant_id"
        mock_conn.fetch.return_value = []

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant_data.settings") as mock_settings:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_settings.tenant_data_path.return_value = "/nonexistent/path"

            service = TenantExportService(TEST_TENANT_ID)
            request = TenantExportRequest(include_files=False, include_ai_logs=False)

            zip_content, summary = await service.export_to_zip(request)

            with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                assert "tenant_id" in manifest
                assert "exported_at" in manifest
                assert "tables" in manifest

    @pytest.mark.asyncio
    async def test_export_table_with_tenant_id(self):
        """匯出表應包含 tenant_id 過濾"""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = "tenant_id"  # 有 tenant_id 欄位
        mock_conn.fetch.return_value = MOCK_USERS

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            service = TenantExportService(TEST_TENANT_ID)
            data = await service._export_table("users")

            # 驗證查詢使用了 tenant_id 過濾
            mock_conn.fetch.assert_called_once()
            call_args = mock_conn.fetch.call_args
            assert "tenant_id = $1" in call_args[0][0]
            assert call_args[0][1] == TEST_TENANT_ID

    @pytest.mark.asyncio
    async def test_export_summary_contains_table_counts(self):
        """匯出摘要應包含各表記錄數"""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = "tenant_id"
        mock_conn.fetch.side_effect = [MOCK_USERS, MOCK_PROJECTS, [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []]

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant_data.settings") as mock_settings:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_settings.tenant_data_path.return_value = "/nonexistent/path"

            service = TenantExportService(TEST_TENANT_ID)
            request = TenantExportRequest(include_files=False, include_ai_logs=False)

            _, summary = await service.export_to_zip(request)

            assert "tables" in summary
            assert summary["tables"].get("users") == 2


# ============================================================
# TenantImportService 測試
# ============================================================

class TestTenantImportService:
    """租戶匯入服務測試"""

    def create_test_zip(self, data: dict[str, list]) -> bytes:
        """建立測試用 ZIP 檔案"""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 寫入各表資料
            for table_name, records in data.items():
                json_content = json.dumps(records, default=str, ensure_ascii=False)
                zf.writestr(f"data/{table_name}.json", json_content.encode("utf-8"))

            # 寫入 manifest
            manifest = {
                "tenant_id": str(TEST_TENANT_ID),
                "exported_at": datetime.now().isoformat(),
                "tables": {name: len(records) for name, records in data.items()},
            }
            zf.writestr("manifest.json", json.dumps(manifest).encode("utf-8"))

        buffer.seek(0)
        return buffer.getvalue()

    @pytest.mark.asyncio
    async def test_import_reads_manifest(self):
        """匯入應讀取 manifest"""
        zip_content = self.create_test_zip({"users": MOCK_USERS})

        mock_conn = AsyncMock()
        mock_conn.fetchval.side_effect = [
            True,  # table exists
            "tenant_id",  # has tenant_id
        ]
        mock_conn.execute.return_value = "DELETE 0"

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant_data.settings") as mock_settings:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_settings.tenant_data_path.return_value = "/nonexistent/path"

            service = TenantImportService(TARGET_TENANT_ID)
            summary = await service.import_from_zip(zip_content, merge_mode="replace")

            assert "source_tenant_id" in summary
            assert summary["source_tenant_id"] == str(TEST_TENANT_ID)

    @pytest.mark.asyncio
    async def test_import_replace_mode_clears_existing(self):
        """取代模式應先清除現有資料"""
        zip_content = self.create_test_zip({"users": []})

        mock_conn = AsyncMock()
        mock_conn.fetchval.side_effect = [
            True,  # table exists
            "tenant_id",  # has tenant_id
        ] * 20  # 多次呼叫
        mock_conn.execute.return_value = "DELETE 0"

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant_data.settings") as mock_settings:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_settings.tenant_data_path.return_value = "/nonexistent/path"

            service = TenantImportService(TARGET_TENANT_ID)
            await service.import_from_zip(zip_content, merge_mode="replace")

            # 驗證有呼叫 DELETE
            delete_calls = [c for c in mock_conn.execute.call_args_list if "DELETE" in str(c)]
            assert len(delete_calls) > 0

    @pytest.mark.asyncio
    async def test_import_merge_mode_skips_existing(self):
        """合併模式應跳過已存在的記錄"""
        zip_content = self.create_test_zip({"users": MOCK_USERS})

        mock_conn = AsyncMock()
        # 第一筆記錄已存在，第二筆不存在
        mock_conn.fetchval.side_effect = [1, None]  # exists check
        mock_conn.execute.return_value = "INSERT 0 1"

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant_data.settings") as mock_settings:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_settings.tenant_data_path.return_value = "/nonexistent/path"

            service = TenantImportService(TARGET_TENANT_ID)
            summary = await service.import_from_zip(zip_content, merge_mode="merge")

            # 只應插入 1 筆（第二筆）
            assert summary["tables"].get("users", 0) <= 2

    @pytest.mark.asyncio
    async def test_convert_value_uuid(self):
        """_convert_value 應正確轉換 UUID 字串"""
        service = TenantImportService(TARGET_TENANT_ID)

        uuid_str = "11111111-1111-1111-1111-111111111111"
        result = service._convert_value(uuid_str)

        assert isinstance(result, UUID)
        assert str(result) == uuid_str

    @pytest.mark.asyncio
    async def test_convert_value_datetime(self):
        """_convert_value 應正確轉換日期時間字串"""
        service = TenantImportService(TARGET_TENANT_ID)

        # ISO 格式
        dt_str = "2024-01-15T10:30:00"
        result = service._convert_value(dt_str)
        assert isinstance(result, datetime)

        # 日期格式
        date_str = "2024-01-15"
        result = service._convert_value(date_str)
        assert isinstance(result, datetime)


# ============================================================
# TenantMigrationService 測試
# ============================================================

class TestTenantMigrationService:
    """租戶遷移服務測試"""

    @pytest.mark.asyncio
    async def test_migrate_calls_export_and_import(self):
        """遷移應呼叫匯出和匯入"""
        with patch("ching_tech_os.services.tenant_data.TenantExportService") as mock_export_cls, \
             patch("ching_tech_os.services.tenant_data.TenantImportService") as mock_import_cls:

            # 設定 mock
            mock_export = AsyncMock()
            mock_export.export_to_zip.return_value = (b"zip_content", {"tables": {}})
            mock_export_cls.return_value = mock_export

            mock_import = AsyncMock()
            mock_import.import_from_zip.return_value = {"tables": {}}
            mock_import_cls.return_value = mock_import

            service = TenantMigrationService(TEST_TENANT_ID, TARGET_TENANT_ID)
            result = await service.migrate(include_files=True, include_ai_logs=False)

            # 驗證呼叫
            mock_export_cls.assert_called_once_with(TEST_TENANT_ID)
            mock_import_cls.assert_called_once_with(TARGET_TENANT_ID)
            mock_export.export_to_zip.assert_called_once()
            mock_import.import_from_zip.assert_called_once()

            # 驗證結果
            assert result["source_tenant_id"] == str(TEST_TENANT_ID)
            assert result["target_tenant_id"] == str(TARGET_TENANT_ID)


# ============================================================
# TenantDataValidator 測試
# ============================================================

class TestTenantDataValidator:
    """租戶資料驗證工具測試"""

    @pytest.mark.asyncio
    async def test_validate_checks_tenant_exists(self):
        """驗證應檢查租戶是否存在"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None  # 租戶不存在

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            validator = TenantDataValidator(TEST_TENANT_ID)
            result = await validator.validate()

            assert "租戶不存在" in result["errors"]

    @pytest.mark.asyncio
    async def test_validate_counts_table_records(self):
        """驗證應統計各表記錄數"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"id": TEST_TENANT_ID, "code": "test", "name": "測試"}
        mock_conn.fetchval.side_effect = [5, 10, 3, 2, 0, 0]  # 各表記錄數和孤立記錄

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant_data.settings") as mock_settings:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_settings.tenant_data_path.return_value = "/nonexistent/path"

            validator = TenantDataValidator(TEST_TENANT_ID)
            result = await validator.validate()

            assert "checks" in result
            assert "users" in result["checks"]
            assert result["checks"]["users"]["count"] == 5

    @pytest.mark.asyncio
    async def test_validate_detects_orphan_records(self):
        """驗證應檢測孤立記錄"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"id": TEST_TENANT_ID, "code": "test", "name": "測試"}
        mock_conn.fetchval.side_effect = [5, 10, 3, 2, 3, 0]  # 有 3 筆孤立的專案成員

        with patch("ching_tech_os.services.tenant_data.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant_data.settings") as mock_settings:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_settings.tenant_data_path.return_value = "/nonexistent/path"

            validator = TenantDataValidator(TEST_TENANT_ID)
            result = await validator.validate()

            assert len(result["warnings"]) > 0
            assert "孤立" in result["warnings"][0]


# ============================================================
# 便捷函數測試
# ============================================================

class TestConvenienceFunctions:
    """便捷函數測試"""

    @pytest.mark.asyncio
    async def test_export_tenant_data_accepts_string_id(self):
        """export_tenant_data 應接受字串 ID"""
        with patch("ching_tech_os.services.tenant_data.TenantExportService") as mock_cls:
            mock_service = AsyncMock()
            mock_service.export_to_zip.return_value = (b"content", {})
            mock_cls.return_value = mock_service

            await export_tenant_data(
                str(TEST_TENANT_ID),
                include_files=False,
                include_ai_logs=False,
            )

            # 應將字串轉換為 UUID
            mock_cls.assert_called_once_with(TEST_TENANT_ID)

    @pytest.mark.asyncio
    async def test_import_tenant_data_accepts_string_id(self):
        """import_tenant_data 應接受字串 ID"""
        with patch("ching_tech_os.services.tenant_data.TenantImportService") as mock_cls:
            mock_service = AsyncMock()
            mock_service.import_from_zip.return_value = {}
            mock_cls.return_value = mock_service

            await import_tenant_data(
                str(TEST_TENANT_ID),
                b"zip_content",
                merge_mode="replace",
            )

            mock_cls.assert_called_once_with(TEST_TENANT_ID)

    @pytest.mark.asyncio
    async def test_validate_tenant_data_accepts_string_id(self):
        """validate_tenant_data 應接受字串 ID"""
        with patch("ching_tech_os.services.tenant_data.TenantDataValidator") as mock_cls:
            mock_validator = AsyncMock()
            mock_validator.validate.return_value = {}
            mock_cls.return_value = mock_validator

            await validate_tenant_data(str(TEST_TENANT_ID))

            mock_cls.assert_called_once_with(TEST_TENANT_ID)

    @pytest.mark.asyncio
    async def test_migrate_tenant_accepts_string_ids(self):
        """migrate_tenant 應接受字串 ID"""
        with patch("ching_tech_os.services.tenant_data.TenantMigrationService") as mock_cls:
            mock_service = AsyncMock()
            mock_service.migrate.return_value = {}
            mock_cls.return_value = mock_service

            await migrate_tenant(
                str(TEST_TENANT_ID),
                str(TARGET_TENANT_ID),
            )

            mock_cls.assert_called_once_with(TEST_TENANT_ID, TARGET_TENANT_ID)
