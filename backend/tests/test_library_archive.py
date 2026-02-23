"""擎添圖書館歸檔工具單元測試。"""

from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from ching_tech_os.services.mcp.nas_tools import (
    LIBRARY_CATEGORIES,
    _sanitize_path_segment,
    _deduplicate_filename,
    _walk_tree,
)
from ching_tech_os.services.path_manager import StorageZone


# ============================================================
# _sanitize_path_segment 測試
# ============================================================

class TestSanitizePathSegment:
    """路徑片段清理。"""

    def test_normal_string(self):
        assert _sanitize_path_segment("馬達規格") == "馬達規格"

    def test_removes_double_dots(self):
        assert _sanitize_path_segment("..馬達規格") == "馬達規格"
        assert _sanitize_path_segment("../../../etc/passwd") == "etcpasswd"

    def test_removes_slashes(self):
        assert _sanitize_path_segment("a/b/c") == "abc"
        assert _sanitize_path_segment("a\\b\\c") == "abc"

    def test_removes_leading_dots_and_spaces(self):
        assert _sanitize_path_segment("...hidden") == "hidden"
        assert _sanitize_path_segment("  spaced  ") == "spaced"

    def test_removes_control_characters(self):
        assert _sanitize_path_segment("hello\x00world") == "helloworld"
        assert _sanitize_path_segment("tab\there") == "tabhere"

    def test_empty_after_clean(self):
        assert _sanitize_path_segment("../../") == ""
        assert _sanitize_path_segment("...") == ""


# ============================================================
# _deduplicate_filename 測試
# ============================================================

class TestDeduplicateFilename:
    """檔名去重。"""

    def test_no_conflict(self, tmp_path):
        assert _deduplicate_filename(tmp_path, "report.pdf") == "report.pdf"

    def test_single_conflict(self, tmp_path):
        (tmp_path / "report.pdf").touch()
        assert _deduplicate_filename(tmp_path, "report.pdf") == "report-2.pdf"

    def test_multiple_conflicts(self, tmp_path):
        (tmp_path / "report.pdf").touch()
        (tmp_path / "report-2.pdf").touch()
        (tmp_path / "report-3.pdf").touch()
        assert _deduplicate_filename(tmp_path, "report.pdf") == "report-4.pdf"


# ============================================================
# _walk_tree 測試
# ============================================================

class TestWalkTree:
    """資料夾樹狀結構。"""

    def test_empty_directory(self, tmp_path):
        lines = []
        _walk_tree(tmp_path, lines, prefix="", current_depth=0, max_depth=2)
        assert lines == []

    def test_with_subdirs_and_files(self, tmp_path):
        (tmp_path / "技術文件").mkdir()
        (tmp_path / "技術文件" / "test.pdf").touch()
        (tmp_path / "產品資料").mkdir()

        lines = []
        _walk_tree(tmp_path, lines, prefix="", current_depth=0, max_depth=2)
        text = "\n".join(lines)
        assert "技術文件/" in text
        assert "產品資料/" in text
        assert "(1 個檔案)" in text
        assert "(空)" in text


# ============================================================
# MCP 工具整合測試的共用 mock 裝飾器
# ============================================================

def _common_patches(library_root_str, lib_allowed=True, tool_allowed=True):
    """回傳共用的 mock patch context managers。"""
    lib_result = (lib_allowed, library_root_str if lib_allowed else "權限不足：無法存取圖書館")
    tool_result = (tool_allowed, "" if tool_allowed else "權限不足")
    return (
        patch("ching_tech_os.services.mcp.nas_tools.ensure_db_connection", new_callable=AsyncMock),
        patch("ching_tech_os.services.mcp.nas_tools.check_mcp_tool_permission", new_callable=AsyncMock, return_value=tool_result),
        patch("ching_tech_os.services.mcp.nas_tools._check_library_permission", new_callable=AsyncMock, return_value=lib_result),
    )


# ============================================================
# list_library_folders 測試
# ============================================================

@pytest.mark.asyncio
async def test_list_library_folders_success(tmp_path):
    """正常瀏覽圖書館結構。"""
    (tmp_path / "技術文件").mkdir()
    (tmp_path / "技術文件" / "PLC程式").mkdir()
    (tmp_path / "技術文件" / "PLC程式" / "手冊.pdf").touch()

    p1, p2, p3 = _common_patches(str(tmp_path))
    with p1, p2, p3:
        from ching_tech_os.services.mcp.nas_tools import list_library_folders
        result = await list_library_folders(path="", max_depth=2, ctos_user_id=1)

    assert "擎添圖書館/" in result
    assert "技術文件/" in result
    assert "PLC程式/" in result


@pytest.mark.asyncio
async def test_list_library_folders_permission_denied():
    """權限不足時回傳錯誤。"""
    p1, p2, p3 = _common_patches("", lib_allowed=False)
    with p1, p2, p3:
        from ching_tech_os.services.mcp.nas_tools import list_library_folders
        result = await list_library_folders(ctos_user_id=1)

    assert "權限不足" in result


# ============================================================
# archive_to_library 測試
# ============================================================

@pytest.fixture
def library_env(tmp_path):
    """建立模擬的 library 和 source 環境。"""
    library_root = tmp_path / "library"
    library_root.mkdir()
    source_dir = tmp_path / "ctos" / "linebot"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "msg_12345.pdf"
    source_file.write_bytes(b"%PDF-1.4 test content")
    return library_root, source_file


def _mock_path_manager(source_file_path: str, zone: StorageZone = StorageZone.CTOS):
    """建立 mock path_manager。"""
    mock_pm = MagicMock()
    mock_parsed = MagicMock()
    mock_parsed.zone = zone
    mock_pm.parse.return_value = mock_parsed
    mock_pm.to_filesystem.return_value = source_file_path
    return mock_pm


@pytest.mark.asyncio
async def test_archive_success(library_env):
    """正常歸檔流程。"""
    library_root, source_file = library_env
    mock_pm = _mock_path_manager(str(source_file))

    p1, p2, p3 = _common_patches(str(library_root))
    with p1, p2, p3, \
         patch("ching_tech_os.services.path_manager.path_manager", mock_pm):
        from ching_tech_os.services.mcp.nas_tools import archive_to_library
        result = await archive_to_library(
            source_path="ctos://linebot/msg_12345.pdf",
            category="技術文件",
            filename="三菱FX5U-使用手冊.pdf",
            folder="PLC程式",
            ctos_user_id=1,
        )

    assert "✅ 已歸檔" in result
    assert "shared://library/技術文件/PLC程式/三菱FX5U-使用手冊.pdf" in result
    assert (library_root / "技術文件" / "PLC程式" / "三菱FX5U-使用手冊.pdf").exists()


@pytest.mark.asyncio
async def test_archive_invalid_category(library_env):
    """無效的 category。"""
    library_root, source_file = library_env

    p1, p2, p3 = _common_patches(str(library_root))
    with p1, p2, p3:
        from ching_tech_os.services.mcp.nas_tools import archive_to_library
        result = await archive_to_library(
            source_path="ctos://linebot/test.pdf",
            category="不存在的分類",
            filename="test.pdf",
            ctos_user_id=1,
        )

    assert "無效的分類" in result


@pytest.mark.asyncio
async def test_archive_non_ctos_source(library_env):
    """source 不在 CTOS zone。"""
    library_root, _ = library_env
    mock_pm = _mock_path_manager("/mnt/nas/projects/test.pdf", zone=StorageZone.SHARED)

    p1, p2, p3 = _common_patches(str(library_root))
    with p1, p2, p3, \
         patch("ching_tech_os.services.path_manager.path_manager", mock_pm):
        from ching_tech_os.services.mcp.nas_tools import archive_to_library
        result = await archive_to_library(
            source_path="shared://projects/test.pdf",
            category="技術文件",
            filename="test.pdf",
            ctos_user_id=1,
        )

    assert "CTOS 區域" in result


@pytest.mark.asyncio
async def test_archive_source_not_found(library_env):
    """來源檔案不存在。"""
    library_root, _ = library_env
    mock_pm = _mock_path_manager("/nonexistent/file.pdf")

    p1, p2, p3 = _common_patches(str(library_root))
    with p1, p2, p3, \
         patch("ching_tech_os.services.path_manager.path_manager", mock_pm):
        from ching_tech_os.services.mcp.nas_tools import archive_to_library
        result = await archive_to_library(
            source_path="ctos://linebot/missing.pdf",
            category="技術文件",
            filename="test.pdf",
            ctos_user_id=1,
        )

    assert "不存在" in result


@pytest.mark.asyncio
async def test_archive_filename_dedup(library_env):
    """檔名重複時自動加後綴。"""
    library_root, source_file = library_env
    mock_pm = _mock_path_manager(str(source_file))

    # 預先建立同名檔案
    target_dir = library_root / "技術文件"
    target_dir.mkdir(parents=True)
    (target_dir / "report.pdf").touch()

    p1, p2, p3 = _common_patches(str(library_root))
    with p1, p2, p3, \
         patch("ching_tech_os.services.path_manager.path_manager", mock_pm):
        from ching_tech_os.services.mcp.nas_tools import archive_to_library
        result = await archive_to_library(
            source_path="ctos://linebot/msg.pdf",
            category="技術文件",
            filename="report.pdf",
            ctos_user_id=1,
        )

    assert "report-2.pdf" in result
    assert (target_dir / "report-2.pdf").exists()


@pytest.mark.asyncio
async def test_archive_no_folder(library_env):
    """不指定 folder，直接放在 category 底下。"""
    library_root, source_file = library_env
    mock_pm = _mock_path_manager(str(source_file))

    p1, p2, p3 = _common_patches(str(library_root))
    with p1, p2, p3, \
         patch("ching_tech_os.services.path_manager.path_manager", mock_pm):
        from ching_tech_os.services.mcp.nas_tools import archive_to_library
        result = await archive_to_library(
            source_path="ctos://linebot/msg.pdf",
            category="其他",
            filename="misc.pdf",
            ctos_user_id=1,
        )

    assert "shared://library/其他/misc.pdf" in result
    assert (library_root / "其他" / "misc.pdf").exists()
