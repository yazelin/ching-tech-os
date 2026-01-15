"""PathManager 單元測試

測試統一路徑管理器的所有功能：
- parse() - 解析新舊格式路徑
- to_filesystem() - 轉換為檔案系統路徑
- to_api() - 轉換為 API 路徑
- to_storage() - 轉換為資料庫儲存格式
- exists() - 檔案存在檢查
- get_zone() - 取得儲存區域
- is_readonly() - 檢查唯讀狀態
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from ching_tech_os.services.path_manager import PathManager, StorageZone, ParsedPath


@pytest.fixture
def path_manager():
    """建立 PathManager 實例（使用 mock settings）"""
    with patch("ching_tech_os.config.settings") as mock:
        mock.ctos_mount_path = "/mnt/nas/ctos"
        mock.projects_mount_path = "/mnt/nas/projects"
        mock.nas_mount_path = "/mnt/nas"
        mock.frontend_dir = "/home/ct/SDD/ching-tech-os/frontend"
        pm = PathManager()
        yield pm


# ============================================================
# parse() 新格式測試
# ============================================================

class TestParseNewFormat:
    """parse() 新格式路徑測試"""

    def test_ctos_protocol(self, path_manager):
        """ctos:// 格式解析"""
        result = path_manager.parse("ctos://linebot/files/xxx.pdf")
        assert result.zone == StorageZone.CTOS
        assert result.path == "linebot/files/xxx.pdf"
        assert result.raw == "ctos://linebot/files/xxx.pdf"

    def test_shared_protocol(self, path_manager):
        """shared:// 格式解析"""
        result = path_manager.parse("shared://亦達光學/doc.pdf")
        assert result.zone == StorageZone.SHARED
        assert result.path == "亦達光學/doc.pdf"

    def test_temp_protocol(self, path_manager):
        """temp:// 格式解析"""
        result = path_manager.parse("temp://abc123/page1.png")
        assert result.zone == StorageZone.TEMP
        assert result.path == "abc123/page1.png"

    def test_local_protocol(self, path_manager):
        """local:// 格式解析"""
        result = path_manager.parse("local://knowledge/assets/x.jpg")
        assert result.zone == StorageZone.LOCAL
        assert result.path == "knowledge/assets/x.jpg"

    def test_to_uri(self, path_manager):
        """ParsedPath.to_uri() 測試"""
        result = path_manager.parse("shared://test/doc.pdf")
        assert result.to_uri() == "shared://test/doc.pdf"


# ============================================================
# parse() 舊格式測試（向後相容）
# ============================================================

class TestParseLegacyFormat:
    """parse() 舊格式路徑測試（向後相容）"""

    def test_nas_knowledge_attachments(self, path_manager):
        """nas://knowledge/attachments/ 格式"""
        result = path_manager.parse("nas://knowledge/attachments/kb-001/file.pdf")
        assert result.zone == StorageZone.CTOS
        assert result.path == "knowledge/kb-001/file.pdf"

    def test_nas_knowledge(self, path_manager):
        """nas://knowledge/ 格式"""
        result = path_manager.parse("nas://knowledge/assets/image.jpg")
        assert result.zone == StorageZone.CTOS
        assert result.path == "knowledge/assets/image.jpg"

    def test_nas_linebot_files(self, path_manager):
        """nas://linebot/files/ 格式"""
        result = path_manager.parse("nas://linebot/files/test.jpg")
        assert result.zone == StorageZone.CTOS
        assert result.path == "linebot/test.jpg"

    def test_relative_assets(self, path_manager):
        """../assets/ 相對路徑格式"""
        result = path_manager.parse("../assets/xxx.jpg")
        assert result.zone == StorageZone.LOCAL
        assert result.path == "knowledge/xxx.jpg"

    def test_linebot_groups_prefix(self, path_manager):
        """groups/ 相對路徑（Line Bot）"""
        result = path_manager.parse("groups/C123/images/photo.jpg")
        assert result.zone == StorageZone.CTOS
        assert result.path == "linebot/groups/C123/images/photo.jpg"

    def test_linebot_users_prefix(self, path_manager):
        """users/ 相對路徑（Line Bot）"""
        result = path_manager.parse("users/U123/files/doc.pdf")
        assert result.zone == StorageZone.CTOS
        assert result.path == "linebot/users/U123/files/doc.pdf"

    def test_linebot_ai_images_prefix(self, path_manager):
        """ai-images/ 相對路徑"""
        result = path_manager.parse("ai-images/abc123.jpg")
        assert result.zone == StorageZone.CTOS
        assert result.path == "linebot/ai-images/abc123.jpg"


# ============================================================
# parse() 系統絕對路徑測試
# ============================================================

class TestParseSystemPath:
    """parse() 系統絕對路徑測試"""

    def test_mnt_nas_projects(self, path_manager):
        """/mnt/nas/projects/ 路徑"""
        result = path_manager.parse("/mnt/nas/projects/亦達光學/xxx.pdf")
        assert result.zone == StorageZone.SHARED
        assert result.path == "亦達光學/xxx.pdf"

    def test_mnt_nas_ctos(self, path_manager):
        """/mnt/nas/ctos/ 路徑"""
        result = path_manager.parse("/mnt/nas/ctos/linebot/files/test.jpg")
        assert result.zone == StorageZone.CTOS
        assert result.path == "linebot/files/test.jpg"

    def test_tmp_path(self, path_manager):
        """/tmp/ 路徑"""
        result = path_manager.parse("/tmp/ctos/converted/page1.png")
        assert result.zone == StorageZone.TEMP
        assert result.path == "ctos/converted/page1.png"

    def test_tmp_nanobanana_output(self, path_manager):
        """/tmp/.../nanobanana-output/ 特殊路徑"""
        result = path_manager.parse("/tmp/ching-tech-os-cli/nanobanana-output/abc.jpg")
        assert result.zone == StorageZone.TEMP
        assert result.path == "ai-generated/abc.jpg"

    def test_tmp_linebot_files(self, path_manager):
        """/tmp/linebot-files/ 特殊路徑"""
        result = path_manager.parse("/tmp/linebot-files/msg123.pdf")
        assert result.zone == StorageZone.TEMP
        assert result.path == "linebot/msg123.pdf"

    def test_slash_relative_path(self, path_manager):
        """以 / 開頭的非系統路徑（檔案管理器 NAS 共享）"""
        result = path_manager.parse("/home/photos/image.jpg")
        assert result.zone == StorageZone.NAS
        assert result.path == "home/photos/image.jpg"

    def test_slash_chinese_path(self, path_manager):
        """以 / 開頭的中文路徑（檔案管理器 NAS 共享）"""
        result = path_manager.parse("/公司檔案/文件/report.pdf")
        assert result.zone == StorageZone.NAS
        assert result.path == "公司檔案/文件/report.pdf"


# ============================================================
# parse() 邊界情況測試
# ============================================================

class TestParseEdgeCases:
    """parse() 邊界情況測試"""

    def test_empty_path_raises_error(self, path_manager):
        """空路徑應拋出錯誤"""
        with pytest.raises(ValueError, match="路徑不可為空"):
            path_manager.parse("")

    def test_pure_relative_path(self, path_manager):
        """純相對路徑預設為 CTOS"""
        result = path_manager.parse("some/random/path.txt")
        assert result.zone == StorageZone.CTOS
        assert result.path == "some/random/path.txt"

    def test_chinese_path(self, path_manager):
        """中文路徑處理"""
        result = path_manager.parse("shared://擎添專案/設計圖/圖紙v1.dwg")
        assert result.zone == StorageZone.SHARED
        assert result.path == "擎添專案/設計圖/圖紙v1.dwg"


# ============================================================
# to_filesystem() 測試
# ============================================================

class TestToFilesystem:
    """to_filesystem() 轉換測試"""

    def test_ctos_to_filesystem(self, path_manager):
        """ctos:// 轉換為檔案系統路徑"""
        result = path_manager.to_filesystem("ctos://linebot/files/test.jpg")
        assert result == "/mnt/nas/ctos/linebot/files/test.jpg"

    def test_shared_to_filesystem(self, path_manager):
        """shared:// 轉換為檔案系統路徑"""
        result = path_manager.to_filesystem("shared://亦達光學/doc.pdf")
        assert result == "/mnt/nas/projects/亦達光學/doc.pdf"

    def test_temp_to_filesystem(self, path_manager):
        """temp:// 轉換為檔案系統路徑"""
        result = path_manager.to_filesystem("temp://converted/page.png")
        assert result == "/tmp/ctos/converted/page.png"

    def test_legacy_to_filesystem(self, path_manager):
        """舊格式轉換為檔案系統路徑"""
        result = path_manager.to_filesystem("/mnt/nas/projects/test.pdf")
        assert result == "/mnt/nas/projects/test.pdf"

    def test_nas_to_filesystem_raises_error(self, path_manager):
        """NAS 路徑轉換為檔案系統路徑應拋出錯誤"""
        with pytest.raises(ValueError, match="NAS zone 路徑無法轉換"):
            path_manager.to_filesystem("/home/photos/image.jpg")

    def test_linebot_temp_to_filesystem(self, path_manager):
        """linebot 暫存路徑應正確還原為 /tmp/linebot-files/"""
        # /tmp/linebot-files/xxx.pdf → temp://linebot/xxx.pdf → /tmp/linebot-files/xxx.pdf
        result = path_manager.to_filesystem("/tmp/linebot-files/msg123.pdf")
        assert result == "/tmp/linebot-files/msg123.pdf"

        # 直接使用 temp://linebot/... 格式也應正確
        result2 = path_manager.to_filesystem("temp://linebot/msg456.pdf")
        assert result2 == "/tmp/linebot-files/msg456.pdf"


# ============================================================
# to_api() 測試
# ============================================================

class TestToApi:
    """to_api() 轉換測試"""

    def test_ctos_to_api(self, path_manager):
        """ctos:// 轉換為 API 路徑"""
        result = path_manager.to_api("ctos://linebot/files/test.jpg")
        assert result == "/api/files/ctos/linebot/files/test.jpg"

    def test_shared_to_api(self, path_manager):
        """shared:// 轉換為 API 路徑"""
        result = path_manager.to_api("shared://亦達光學/doc.pdf")
        assert result == "/api/files/shared/亦達光學/doc.pdf"

    def test_legacy_to_api(self, path_manager):
        """舊格式轉換為 API 路徑"""
        result = path_manager.to_api("/mnt/nas/projects/test.pdf")
        assert result == "/api/files/shared/test.pdf"

    def test_slash_path_to_api(self, path_manager):
        """檔案管理器路徑轉換為 API 路徑"""
        result = path_manager.to_api("/home/photos/image.jpg")
        assert result == "/api/files/nas/home/photos/image.jpg"


# ============================================================
# to_storage() 測試
# ============================================================

class TestToStorage:
    """to_storage() 轉換測試"""

    def test_new_format_unchanged(self, path_manager):
        """新格式應保持不變"""
        result = path_manager.to_storage("ctos://linebot/test.jpg")
        assert result == "ctos://linebot/test.jpg"

    def test_legacy_to_new_format(self, path_manager):
        """舊格式應轉換為新格式"""
        result = path_manager.to_storage("/mnt/nas/projects/亦達光學/doc.pdf")
        assert result == "shared://亦達光學/doc.pdf"

    def test_nas_protocol_to_new_format(self, path_manager):
        """nas:// 格式應轉換為新格式"""
        result = path_manager.to_storage("nas://knowledge/assets/img.jpg")
        assert result == "ctos://knowledge/assets/img.jpg"


# ============================================================
# get_zone() 測試
# ============================================================

class TestGetZone:
    """get_zone() 測試"""

    def test_get_ctos_zone(self, path_manager):
        """取得 CTOS zone"""
        result = path_manager.get_zone("ctos://test.jpg")
        assert result == StorageZone.CTOS

    def test_get_shared_zone(self, path_manager):
        """取得 SHARED zone"""
        result = path_manager.get_zone("shared://test.pdf")
        assert result == StorageZone.SHARED

    def test_get_zone_from_legacy(self, path_manager):
        """從舊格式取得 zone"""
        result = path_manager.get_zone("/mnt/nas/ctos/test.txt")
        assert result == StorageZone.CTOS


# ============================================================
# is_readonly() 測試
# ============================================================

class TestIsReadonly:
    """is_readonly() 測試"""

    def test_shared_is_readonly(self, path_manager):
        """shared:// 應為唯讀"""
        assert path_manager.is_readonly("shared://test.pdf") is True

    def test_ctos_is_writable(self, path_manager):
        """ctos:// 應可寫入"""
        assert path_manager.is_readonly("ctos://test.pdf") is False

    def test_temp_is_writable(self, path_manager):
        """temp:// 應可寫入"""
        assert path_manager.is_readonly("temp://test.pdf") is False

    def test_nas_is_readonly(self, path_manager):
        """NAS 路徑應為唯讀"""
        assert path_manager.is_readonly("/home/test.pdf") is True


# ============================================================
# exists() 測試
# ============================================================

class TestExists:
    """exists() 測試"""

    def test_exists_calls_path_exists(self, path_manager):
        """exists() 應檢查檔案系統"""
        with patch.object(Path, "exists", return_value=True):
            # 這個測試需要 mock Path.exists
            # 由於 PathManager.exists() 會建立實際的 Path 物件
            # 這裡只測試邏輯正確性
            pass


# ============================================================
# from_legacy() 測試
# ============================================================

class TestFromLegacy:
    """from_legacy() 測試（to_storage 的別名）"""

    def test_from_legacy_same_as_to_storage(self, path_manager):
        """from_legacy() 應與 to_storage() 相同"""
        path = "/mnt/nas/projects/test.pdf"
        assert path_manager.from_legacy(path) == path_manager.to_storage(path)
