"""PathManager 單元測試。"""

from pathlib import Path
from unittest.mock import patch

import pytest

from ching_tech_os.services.path_manager import PathManager, StorageZone
from ching_tech_os.services.shared_source_permissions import (
    SHARED_SOURCE_ACCESS_DENIED_MESSAGE,
    SharedSourceAccessDeniedError,
)


@pytest.fixture
def path_manager():
    """建立 PathManager 實例（使用 mock settings）。"""
    with patch("ching_tech_os.config.settings") as mock:
        mock.ctos_mount_path = "/mnt/nas/ctos"
        mock.projects_mount_path = "/mnt/nas/projects"
        mock.circuits_mount_path = "/mnt/nas/circuits"
        mock.library_mount_path = "/mnt/nas/library"
        mock.nas_mount_path = "/mnt/nas"
        mock.frontend_dir = "/home/ct/SDD/ching-tech-os/frontend"
        yield PathManager()


class TestParseNewFormat:
    """新格式分組。"""

    def test_ctos(self, path_manager):
        parsed = path_manager.parse("ctos://linebot/files/a.jpg")
        assert parsed.zone == StorageZone.CTOS
        assert parsed.path == "linebot/files/a.jpg"

    def test_shared(self, path_manager):
        parsed = path_manager.parse("shared://projects/demo/a.pdf")
        assert parsed.zone == StorageZone.SHARED
        assert parsed.path == "projects/demo/a.pdf"

    def test_temp(self, path_manager):
        parsed = path_manager.parse("temp://bot/msg1.pdf")
        assert parsed.zone == StorageZone.TEMP
        assert parsed.path == "bot/msg1.pdf"

    def test_local(self, path_manager):
        parsed = path_manager.parse("local://knowledge/assets/a.png")
        assert parsed.zone == StorageZone.LOCAL
        assert parsed.path == "knowledge/assets/a.png"


class TestParseLegacyCompatibility:
    """舊格式相容分組。"""

    def test_legacy_nas_knowledge(self, path_manager):
        parsed = path_manager.parse("nas://knowledge/attachments/kb-001/a.pdf")
        assert parsed.zone == StorageZone.CTOS
        assert parsed.path == "knowledge/kb-001/a.pdf"

    def test_legacy_relative_assets(self, path_manager):
        parsed = path_manager.parse("../assets/demo.png")
        assert parsed.zone == StorageZone.LOCAL
        assert parsed.path == "knowledge/demo.png"

    def test_legacy_linebot_groups(self, path_manager):
        parsed = path_manager.parse("groups/C1/files/a.txt")
        assert parsed.zone == StorageZone.CTOS
        assert parsed.path == "linebot/groups/C1/files/a.txt"


class TestSharedSubSources:
    """shared 子來源與 fallback。"""

    def test_shared_projects_sub_source(self, path_manager):
        assert (
            path_manager.to_filesystem("shared://projects/team-a/spec.pdf")
            == "/mnt/nas/projects/team-a/spec.pdf"
        )

    def test_shared_circuits_sub_source(self, path_manager):
        assert (
            path_manager.to_filesystem("shared://circuits/c1/layout.dwg")
            == "/mnt/nas/circuits/c1/layout.dwg"
        )

    def test_shared_library_sub_source(self, path_manager):
        assert (
            path_manager.to_filesystem("shared://library/Python入門/book.pdf")
            == "/mnt/nas/library/Python入門/book.pdf"
        )

    def test_shared_legacy_fallback_to_projects(self, path_manager):
        assert (
            path_manager.to_filesystem("shared://team-a/spec.pdf")
            == "/mnt/nas/projects/team-a/spec.pdf"
        )

    def test_shared_source_permission_filter(self, path_manager):
        with pytest.raises(SharedSourceAccessDeniedError, match=SHARED_SOURCE_ACCESS_DENIED_MESSAGE):
            path_manager.to_filesystem(
                "shared://circuits/c1/layout.dwg",
                source_permissions={"projects": True, "circuits": False},
            )

    def test_shared_fallback_permission_filter(self, path_manager):
        with pytest.raises(SharedSourceAccessDeniedError, match=SHARED_SOURCE_ACCESS_DENIED_MESSAGE):
            path_manager.to_filesystem(
                "shared://team-a/spec.pdf",
                source_permissions={"projects": False, "circuits": True},
            )

    def test_shared_source_implicit_permission_denial(self, path_manager):
        """未在權限中定義的來源應被隱性拒絕（deny-by-default）。"""
        with pytest.raises(SharedSourceAccessDeniedError, match=SHARED_SOURCE_ACCESS_DENIED_MESSAGE):
            path_manager.to_filesystem(
                "shared://circuits/c1/layout.dwg",
                source_permissions={"projects": True},  # 只允許 projects，circuits 未定義
            )

    def test_shared_library_permission_allowed(self, path_manager):
        """library 來源允許存取時應正常解析。"""
        assert (
            path_manager.to_filesystem(
                "shared://library/Python入門/book.pdf",
                source_permissions={"projects": True, "circuits": True, "library": True},
            )
            == "/mnt/nas/library/Python入門/book.pdf"
        )

    def test_shared_library_permission_denied(self, path_manager):
        """library 來源被拒絕時應拋出錯誤。"""
        with pytest.raises(SharedSourceAccessDeniedError, match=SHARED_SOURCE_ACCESS_DENIED_MESSAGE):
            path_manager.to_filesystem(
                "shared://library/Python入門/book.pdf",
                source_permissions={"projects": True, "circuits": True, "library": False},
            )


class TestConversions:
    """to_filesystem/to_api/to_storage 期望值。"""

    def test_to_filesystem(self, path_manager):
        assert (
            path_manager.to_filesystem("/mnt/nas/projects/demo/a.pdf")
            == "/mnt/nas/projects/demo/a.pdf"
        )
        assert (
            path_manager.to_filesystem("temp://bot/msg1.pdf")
            == "/tmp/bot-files/msg1.pdf"
        )

    def test_to_api(self, path_manager):
        assert (
            path_manager.to_api("/mnt/nas/projects/demo/a.pdf")
            == "/api/files/shared/projects/demo/a.pdf"
        )
        assert (
            path_manager.to_api("/home/photos/a.jpg")
            == "/api/files/nas/home/photos/a.jpg"
        )

    def test_to_storage(self, path_manager):
        assert (
            path_manager.to_storage("/mnt/nas/circuits/c1/layout.dwg")
            == "shared://circuits/c1/layout.dwg"
        )
        assert (
            path_manager.to_storage("/mnt/nas/projects/demo/a.pdf")
            == "shared://projects/demo/a.pdf"
        )
        assert (
            path_manager.to_storage("/mnt/nas/library/Python入門/book.pdf")
            == "shared://library/Python入門/book.pdf"
        )


def test_exists_for_nas_zone(path_manager):
    """nas:// 路徑由上層處理，這裡固定回傳 True。"""
    assert path_manager.exists("/home/photos/a.jpg") is True


def test_exists_for_local_path(path_manager):
    """非 nas:// 路徑會走 Path.exists。"""
    with patch.object(Path, "exists", return_value=True):
        assert path_manager.exists("ctos://linebot/files/a.jpg") is True
