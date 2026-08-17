"""MCP nas tools 擴充測試：補齊搜尋/檔案資訊/文件讀取/發送/歸檔的錯誤與邊界分支。"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services.mcp import nas_tools


class _ConnCtx:
    """模擬 asyncpg 連線的 async context manager。"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _allow(
    monkeypatch: pytest.MonkeyPatch,
    allowed: bool = True,
    mounts: dict[str, str] | None = None,
    patch_mounts: bool = True,
):
    """通用前置：patch 掉 DB 連線、權限檢查與 shared 掛載查詢。"""
    from ching_tech_os.config import settings

    monkeypatch.setattr(nas_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        nas_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(allowed, "DENY")),
    )
    if patch_mounts:
        default = {
            "projects": settings.projects_mount_path,
            "circuits": settings.circuits_mount_path,
        }
        monkeypatch.setattr(
            nas_tools,
            "_get_user_shared_mounts",
            AsyncMock(side_effect=lambda _uid: dict(mounts if mounts is not None else default)),
        )


class _Proc:
    """模擬 find 子行程。"""

    def __init__(self, out: str):
        self._out = out.encode()

    async def communicate(self):
        return self._out, b""

    def kill(self):
        return None


class _BrokenProc:
    """communicate 會爆 OSError、kill 會爆 ProcessLookupError 的子行程。"""

    async def communicate(self):
        raise OSError("boom")

    def kill(self):
        raise ProcessLookupError()


# ============================================================
# 內部輔助函式
# ============================================================


@pytest.mark.asyncio
async def test_get_user_shared_mounts_bound_and_unbound(monkeypatch: pytest.MonkeyPatch) -> None:
    """_get_user_shared_mounts：綁定用戶不過濾；未綁定用戶依 Agent 允許來源做交集。"""
    import ching_tech_os.services.path_manager as pm

    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setenv("AGENT_ALLOWED_SHARED_SOURCES", json.dumps(["projects"]))
    all_mounts = {"projects": "/a", "circuits": "/b"}
    monkeypatch.setattr(pm.path_manager, "get_shared_mounts", lambda: dict(all_mounts))
    monkeypatch.setattr(
        nas_tools,
        "get_allowed_shared_mounts_for_user",
        AsyncMock(return_value=dict(all_mounts)),
    )

    # 綁定用戶：即使有 Agent 限制環境變數，也不做交集
    out = await nas_tools._get_user_shared_mounts(1)
    assert out == all_mounts

    # 未綁定用戶：只保留 Agent 允許的來源
    out2 = await nas_tools._get_user_shared_mounts(None)
    assert out2 == {"projects": "/a"}

    # 未綁定且無 Agent 限制：全部保留
    monkeypatch.delenv("AGENT_ALLOWED_SHARED_SOURCES", raising=False)
    out3 = await nas_tools._get_user_shared_mounts(None)
    assert out3 == all_mounts


def test_get_knowledge_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """_get_knowledge_paths：回傳 base/entries/assets/index 四個路徑。"""
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "knowledge_data_path", str(tmp_path))
    base, entries, assets, index = nas_tools._get_knowledge_paths()
    assert base == tmp_path
    assert entries == tmp_path / "entries"
    assert assets == tmp_path / "assets"
    assert index == tmp_path / "index.json"


def test_sanitize_and_deduplicate(tmp_path: Path) -> None:
    """_sanitize_path_segment 與 _deduplicate_filename 邊界。"""
    assert nas_tools._sanitize_path_segment("../..//a\\b") == "ab"
    assert nas_tools._sanitize_path_segment(". 隱藏") == "隱藏"
    assert nas_tools._sanitize_path_segment("a\x00b\x1fc") == "abc"

    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    (tmp_path / "f-2.txt").write_text("x", encoding="utf-8")
    assert nas_tools._deduplicate_filename(tmp_path, "f.txt") == "f-3.txt"
    assert nas_tools._deduplicate_filename(tmp_path, "new.txt") == "new.txt"


@pytest.mark.asyncio
async def test_check_library_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    """_check_library_permission：有無 library 掛載的兩種結果。"""
    from ching_tech_os.config import settings

    monkeypatch.setattr(
        nas_tools, "_get_user_shared_mounts", AsyncMock(return_value={"library": "/lib"})
    )
    ok, result = await nas_tools._check_library_permission(1)
    assert ok is True and result == settings.library_mount_path

    monkeypatch.setattr(
        nas_tools, "_get_user_shared_mounts", AsyncMock(return_value={"projects": "/p"})
    )
    ok2, msg = await nas_tools._check_library_permission(1)
    assert ok2 is False and "權限不足" in msg


# ============================================================
# search_nas_files
# ============================================================


@pytest.mark.asyncio
async def test_search_nas_files_permission_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """search_nas_files：工具權限被拒。"""
    _allow(monkeypatch, allowed=False)
    out = await nas_tools.search_nas_files("demo", ctos_user_id=1)
    assert out.startswith("❌")


@pytest.mark.asyncio
async def test_search_nas_files_no_existing_mounts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """search_nas_files：掛載點皆不存在時回報無可用來源。"""
    _allow(monkeypatch, mounts={"projects": str(tmp_path / "not-exist")})
    out = await nas_tools.search_nas_files("demo", ctos_user_id=1)
    assert "沒有可用的搜尋來源掛載點" in out


@pytest.mark.asyncio
async def test_search_nas_files_invalid_keywords(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """search_nas_files：關鍵字清理後為空。"""
    _allow(monkeypatch, mounts={"projects": str(tmp_path)})
    out = await nas_tools.search_nas_files("[]*?", ctos_user_id=1)
    assert "有效的關鍵字" in out


@pytest.mark.asyncio
async def test_search_nas_files_agent_library_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """search_nas_files：未綁定用戶套用 Agent library 子路徑限制。"""
    lib = tmp_path / "library"
    sub = lib / "教育訓練"
    sub.mkdir(parents=True)
    f = sub / "課程demo.pdf"
    f.write_bytes(b"x" * 2048)  # 2KB，觸發 KB 大小顯示

    _allow(monkeypatch, mounts={"library": str(lib)})
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setenv(
        "AGENT_ALLOWED_LIBRARY_PATHS", json.dumps(["教育訓練", "不存在的子路徑"])
    )

    async def _fake_subproc(*args, **_kwargs):
        if "-type" in args:
            t = args[args.index("-type") + 1]
            if t == "d":
                return _Proc(str(sub))
            return _Proc(str(f))
        return _Proc("")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subproc)
    out = await nas_tools.search_nas_files("demo", ctos_user_id=None)
    assert "shared://library/教育訓練/" in out
    assert "KB" in out


@pytest.mark.asyncio
async def test_search_nas_files_file_types_limit_and_edge_lines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """search_nas_files：類型過濾、去重、來源不符、stat 失敗、limit 上限與 MB 顯示。"""
    projects = tmp_path / "projects"
    d = projects / "DemoDir"
    d.mkdir(parents=True)
    big = d / "big-demo.pdf"
    big.write_bytes(b"x" * (1024 * 1024 + 200 * 1024))  # >1MB，觸發 MB 顯示
    ghost = d / "ghost-demo.pdf"  # 不落地，觸發 stat OSError

    _allow(monkeypatch, mounts={"projects": str(projects)})

    find_output = "\n".join([
        str(big),
        str(big),  # 重複行，觸發去重
        "/elsewhere/none-demo.pdf",  # 來源不符，跳過
        str(ghost),
    ])

    async def _fake_subproc(*args, **_kwargs):
        if "-type" in args:
            t = args[args.index("-type") + 1]
            if t == "d":
                return _Proc(str(d))
            return _Proc(find_output)
        return _Proc("")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subproc)
    out = await nas_tools.search_nas_files(
        "demo", file_types="pdf, txt", limit=2, ctos_user_id=1
    )
    assert "MB" in out
    assert "已達上限 2 筆" in out

    # limit=1：迴圈中途 break
    out2 = await nas_tools.search_nas_files("demo", file_types="pdf", limit=1, ctos_user_id=1)
    assert "找到 1 個檔案" in out2


@pytest.mark.asyncio
async def test_search_nas_files_phase2_phase3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """search_nas_files：淺層找不到目錄時擴展到 3 層，再全掃檔名。"""
    projects = tmp_path / "projects"
    d = projects / "a" / "b" / "demo"
    d.mkdir(parents=True)
    f = d / "demo.txt"
    f.write_text("x", encoding="utf-8")

    _allow(monkeypatch, mounts={"projects": str(projects)})

    async def _fake_subproc(*args, **_kwargs):
        if "-type" in args:
            t = args[args.index("-type") + 1]
            if t == "d":
                # 只有 maxdepth 3 才找得到目錄
                if "-maxdepth" in args and args[args.index("-maxdepth") + 1] == "3":
                    return _Proc(str(d))
                return _Proc("")
            return _Proc(str(f))
        return _Proc("")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subproc)
    out = await nas_tools.search_nas_files("demo", ctos_user_id=1)
    assert "shared://projects" in out

    # 階段 3：目錄搜尋全空，直接全掃檔名
    async def _fake_subproc3(*args, **_kwargs):
        if "-type" in args and args[args.index("-type") + 1] == "f":
            return _Proc(str(f))
        return _Proc("")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subproc3)
    out3 = await nas_tools.search_nas_files("demo", ctos_user_id=1)
    assert "shared://projects" in out3


@pytest.mark.asyncio
async def test_search_nas_files_not_found_and_run_find_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """search_nas_files：find 子行程失敗（OSError + kill 失敗）時回報找不到。"""
    projects = tmp_path / "projects"
    projects.mkdir()
    _allow(monkeypatch, mounts={"projects": str(projects)})

    async def _fake_subproc(*_args, **_kwargs):
        return _BrokenProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subproc)
    out = await nas_tools.search_nas_files("demo", file_types="pdf", ctos_user_id=1)
    assert "找不到符合" in out
    assert "類型：pdf" in out


@pytest.mark.asyncio
async def test_search_nas_files_permission_and_generic_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """search_nas_files：搜尋階段丟出 PermissionError 與一般例外的分支。"""
    projects = tmp_path / "projects"
    projects.mkdir()
    _allow(monkeypatch, mounts={"projects": str(projects)})

    async def _fake_subproc(*_args, **_kwargs):
        return _Proc("")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subproc)

    async def _gather_permission(*tasks, **_kw):
        for t in tasks:
            t.close()  # 關閉未執行的 coroutine 避免警告
        raise PermissionError("denied")

    monkeypatch.setattr(asyncio, "gather", _gather_permission)
    out = await nas_tools.search_nas_files("demo", ctos_user_id=1)
    assert "沒有權限存取檔案系統" in out

    async def _gather_generic(*tasks, **_kw):
        for t in tasks:
            t.close()
        raise RuntimeError("oops")

    monkeypatch.setattr(asyncio, "gather", _gather_generic)
    out2 = await nas_tools.search_nas_files("demo", ctos_user_id=1)
    assert "搜尋時發生錯誤" in out2


# ============================================================
# get_nas_file_info
# ============================================================


@pytest.mark.asyncio
async def test_get_nas_file_info_error_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """get_nas_file_info：權限拒絕、找不到、拒絕存取、stat 失敗。"""
    import ching_tech_os.services.share as share_module
    from ching_tech_os.services.share import NasFileNotFoundError, NasFileAccessDenied

    _allow(monkeypatch, allowed=False)
    out = await nas_tools.get_nas_file_info("shared://projects/x.pdf", ctos_user_id=1)
    assert out.startswith("❌")

    _allow(monkeypatch, allowed=True)

    def _raise_not_found(_p, **_k):
        raise NasFileNotFoundError("找不到檔案")

    monkeypatch.setattr(share_module, "validate_nas_file_path", _raise_not_found)
    out2 = await nas_tools.get_nas_file_info("shared://projects/x.pdf", ctos_user_id=1)
    assert "找不到檔案" in out2

    def _raise_denied(_p, **_k):
        raise NasFileAccessDenied("拒絕存取")

    monkeypatch.setattr(share_module, "validate_nas_file_path", _raise_denied)
    out3 = await nas_tools.get_nas_file_info("shared://projects/x.pdf", ctos_user_id=1)
    assert "拒絕存取" in out3

    # stat 失敗：validate 回傳不存在的路徑
    ghost = tmp_path / "ghost.pdf"
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: ghost)
    out4 = await nas_tools.get_nas_file_info("shared://projects/ghost.pdf", ctos_user_id=1)
    assert "無法讀取檔案資訊" in out4


@pytest.mark.asyncio
async def test_get_nas_file_info_size_formats(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """get_nas_file_info：MB 與 KB 大小顯示分支。"""
    import ching_tech_os.services.share as share_module

    _allow(monkeypatch, allowed=True)
    big = tmp_path / "big.dwg"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: big)
    out = await nas_tools.get_nas_file_info("shared://projects/big.dwg", ctos_user_id=1)
    assert "MB" in out and "AutoCAD 圖檔" in out

    mid = tmp_path / "mid.xyz"
    mid.write_bytes(b"x" * 2048)
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: mid)
    out2 = await nas_tools.get_nas_file_info("shared://projects/mid.xyz", ctos_user_id=1)
    assert "KB" in out2 and ".xyz 檔案" in out2


# ============================================================
# read_document
# ============================================================


def _patch_parse(monkeypatch: pytest.MonkeyPatch, zone, path: str = "projects/x.pdf"):
    """輔助：patch path_manager.parse 回傳指定 zone。"""
    import ching_tech_os.services.path_manager as pm

    monkeypatch.setattr(
        pm.path_manager, "parse", lambda _p: SimpleNamespace(zone=zone, path=path)
    )
    return pm


@pytest.mark.asyncio
async def test_read_document_error_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """read_document：權限拒絕、解析失敗、來源權限不足、路徑與格式錯誤。"""
    import ching_tech_os.services.path_manager as pm
    from ching_tech_os.services.path_manager import StorageZone
    from ching_tech_os.services.shared_source_permissions import SharedSourceAccessDeniedError
    from ching_tech_os.config import settings

    _allow(monkeypatch, allowed=False)
    out = await nas_tools.read_document("shared://projects/x.pdf", ctos_user_id=1)
    assert out.startswith("❌")

    _allow(monkeypatch, allowed=True)
    monkeypatch.setenv("CTOS_USER_ID", "1")

    # parse 失敗
    def _parse_fail(_p):
        raise ValueError("路徑格式錯誤")

    monkeypatch.setattr(pm.path_manager, "parse", _parse_fail)
    out2 = await nas_tools.read_document("bad://x", ctos_user_id=1)
    assert "路徑格式錯誤" in out2

    # to_filesystem 丟 SharedSourceAccessDeniedError
    _patch_parse(monkeypatch, StorageZone.SHARED)

    def _fs_denied(_p, **_k):
        raise SharedSourceAccessDeniedError("來源權限不足")

    monkeypatch.setattr(pm.path_manager, "to_filesystem", _fs_denied)
    out3 = await nas_tools.read_document("shared://projects/x.pdf", ctos_user_id=1)
    assert "來源權限不足" in out3

    # to_filesystem 丟 ValueError
    def _fs_value_error(_p, **_k):
        raise ValueError("無法轉換")

    monkeypatch.setattr(pm.path_manager, "to_filesystem", _fs_value_error)
    out4 = await nas_tools.read_document("shared://projects/x.pdf", ctos_user_id=1)
    assert "無法轉換" in out4

    # 路徑不在 NAS 掛載點下
    nas_root = tmp_path / "nas"
    nas_root.mkdir()
    monkeypatch.setattr(settings, "nas_mount_path", str(nas_root))
    outside = tmp_path / "outside" / "x.pdf"
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p, **_k: str(outside))
    out5 = await nas_tools.read_document("shared://projects/x.pdf", ctos_user_id=1)
    assert "不允許存取此路徑" in out5

    # 路徑含非法字元：resolve 失敗 → 無效的路徑
    monkeypatch.setattr(
        pm.path_manager, "to_filesystem", lambda _p, **_k: str(nas_root) + "/\x00bad.pdf"
    )
    out5b = await nas_tools.read_document("shared://projects/bad.pdf", ctos_user_id=1)
    assert "無效的路徑" in out5b

    # 檔案不存在
    ghost = nas_root / "ghost.pdf"
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p, **_k: str(ghost))
    out6 = await nas_tools.read_document("shared://projects/ghost.pdf", ctos_user_id=1)
    assert "檔案不存在" in out6

    # 路徑是資料夾不是檔案
    folder = nas_root / "dir"
    folder.mkdir()
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p, **_k: str(folder))
    out7 = await nas_tools.read_document("shared://projects/dir", ctos_user_id=1)
    assert "不是檔案" in out7

    # 舊版格式
    legacy = nas_root / "old.doc"
    legacy.write_text("x", encoding="utf-8")
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p, **_k: str(legacy))
    out8 = await nas_tools.read_document("shared://projects/old.doc", ctos_user_id=1)
    assert "舊版格式" in out8

    # 不支援的格式
    weird = nas_root / "x.xyz"
    weird.write_text("x", encoding="utf-8")
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p, **_k: str(weird))
    out9 = await nas_tools.read_document("shared://projects/x.xyz", ctos_user_id=1)
    assert "不支援的檔案格式" in out9


@pytest.mark.asyncio
async def test_read_document_agent_library_restriction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """read_document：未綁定用戶讀取 library 檔案時檢查 Agent 允許範圍。"""
    import ching_tech_os.services.path_manager as pm
    from ching_tech_os.services.path_manager import StorageZone

    _allow(monkeypatch, allowed=True)
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setenv("AGENT_ALLOWED_LIBRARY_PATHS", json.dumps(["教育訓練"]))

    _patch_parse(monkeypatch, StorageZone.SHARED, path="library/機密區/secret.pdf")
    monkeypatch.setattr(
        pm.path_manager, "to_filesystem", lambda _p, **_k: str(tmp_path / "secret.pdf")
    )
    out = await nas_tools.read_document("shared://library/機密區/secret.pdf", ctos_user_id=None)
    assert "不在允許的搜尋範圍內" in out


@pytest.mark.asyncio
async def test_read_document_truncation_and_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """read_document：內容截斷、xlsx 工作表數、截斷旗標與部分錯誤註記。"""
    import ching_tech_os.services.path_manager as pm
    import ching_tech_os.services.workers as workers
    from ching_tech_os.services.path_manager import StorageZone
    from ching_tech_os.config import settings

    _allow(monkeypatch, allowed=True)
    monkeypatch.setenv("CTOS_USER_ID", "1")
    nas_root = tmp_path / "nas"
    nas_root.mkdir()
    monkeypatch.setattr(settings, "nas_mount_path", str(nas_root))
    doc = nas_root / "book.xlsx"
    doc.write_text("x", encoding="utf-8")
    _patch_parse(monkeypatch, StorageZone.SHARED, path="projects/book.xlsx")
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p, **_k: str(doc))
    monkeypatch.setattr(
        workers,
        "run_in_doc_pool",
        AsyncMock(
            return_value=SimpleNamespace(
                text="A" * 100, format="xlsx", page_count=3, truncated=True, error="部分頁面失敗"
            )
        ),
    )
    out = await nas_tools.read_document(
        "shared://projects/book.xlsx", max_chars=10, ctos_user_id=1
    )
    assert "內容已截斷" in out
    assert "工作表數：3" in out
    assert "部分頁面失敗" in out


@pytest.mark.asyncio
async def test_read_document_reader_exceptions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """read_document：文件解析各種例外對應的錯誤訊息。"""
    import ching_tech_os.services.path_manager as pm
    import ching_tech_os.services.workers as workers
    from ching_tech_os.services import document_reader as dr
    from ching_tech_os.services.path_manager import StorageZone
    from ching_tech_os.config import settings

    _allow(monkeypatch, allowed=True)
    monkeypatch.setenv("CTOS_USER_ID", "1")
    nas_root = tmp_path / "nas"
    nas_root.mkdir()
    monkeypatch.setattr(settings, "nas_mount_path", str(nas_root))
    doc = nas_root / "x.pdf"
    doc.write_text("x", encoding="utf-8")
    _patch_parse(monkeypatch, StorageZone.SHARED, path="projects/x.pdf")
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p, **_k: str(doc))

    cases = [
        (dr.FileTooLargeError("檔案過大"), "檔案過大"),
        (dr.PasswordProtectedError(), "密碼保護"),
        (dr.CorruptedFileError("壞掉了"), "文件損壞"),
        (dr.UnsupportedFormatError("不支援"), "不支援"),
        (RuntimeError("爆炸"), "讀取文件失敗"),
    ]
    for exc, expected in cases:
        monkeypatch.setattr(workers, "run_in_doc_pool", AsyncMock(side_effect=exc))
        out = await nas_tools.read_document("shared://projects/x.pdf", ctos_user_id=1)
        assert expected in out


# ============================================================
# send_nas_file
# ============================================================


def _setup_send(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, filename: str = "a.jpg", size: int = 100
):
    """輔助：準備 send_nas_file 的檔案與分享連結 mock。"""
    import ching_tech_os.services.share as share_module

    _allow(monkeypatch, allowed=True)
    f = tmp_path / filename
    f.write_bytes(b"x" * size)
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: f)
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(return_value=SimpleNamespace(full_url="https://x/s/abc", token="abc")),
    )
    return share_module, f


@pytest.mark.asyncio
async def test_send_nas_file_basic_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """send_nas_file：權限拒絕、缺少目標、檔案驗證失敗、分享連結失敗。"""
    import ching_tech_os.services.share as share_module
    from ching_tech_os.services.share import NasFileNotFoundError, NasFileAccessDenied

    _allow(monkeypatch, allowed=False)
    out = await nas_tools.send_nas_file("shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1)
    assert out.startswith("❌")

    _allow(monkeypatch, allowed=True)
    out2 = await nas_tools.send_nas_file("shared://projects/a.jpg", ctos_user_id=1)
    assert "對話識別" in out2

    def _raise_not_found(_p, **_k):
        raise NasFileNotFoundError("不存在")

    monkeypatch.setattr(share_module, "validate_nas_file_path", _raise_not_found)
    out3 = await nas_tools.send_nas_file("shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1)
    assert "不存在" in out3

    def _raise_denied(_p, **_k):
        raise NasFileAccessDenied("拒絕")

    monkeypatch.setattr(share_module, "validate_nas_file_path", _raise_denied)
    out4 = await nas_tools.send_nas_file("shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1)
    assert "拒絕" in out4

    # 分享連結建立失敗
    _setup_send(monkeypatch, tmp_path)
    monkeypatch.setattr(
        share_module, "create_share_link", AsyncMock(side_effect=RuntimeError("DB down"))
    )
    out5 = await nas_tools.send_nas_file("shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1)
    assert "建立分享連結失敗" in out5


@pytest.mark.asyncio
async def test_send_nas_file_telegram_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """send_nas_file：Telegram 未設定、檔案發送、圖片失敗 fallback、fallback 也失敗。"""
    import ching_tech_os.services.bot_telegram.adapter as tg_adapter
    from ching_tech_os.config import settings

    _setup_send(monkeypatch, tmp_path, filename="doc.bin", size=100)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    out = await nas_tools.send_nas_file("shared://projects/doc.bin", telegram_chat_id="1", ctos_user_id=1)
    assert "Telegram Bot 未設定" in out

    monkeypatch.setattr(settings, "telegram_bot_token", "tok")
    calls: list[str] = []

    class _TG:
        def __init__(self, token):
            self.token = token

        async def send_image(self, *_a):
            calls.append("image")
            raise RuntimeError("image fail")

        async def send_file(self, *_a):
            calls.append("file")
            return None

        async def send_text(self, *_a):
            calls.append("text")
            return None

    monkeypatch.setattr(tg_adapter, "TelegramBotAdapter", _TG)

    # 非圖片：send_file 成功
    out2 = await nas_tools.send_nas_file("shared://projects/doc.bin", telegram_chat_id="1", ctos_user_id=1)
    assert "已發送檔案" in out2 and "file" in calls

    # 圖片發送失敗 → fallback 發連結成功
    _setup_send(monkeypatch, tmp_path, filename="a.jpg", size=100)
    out3 = await nas_tools.send_nas_file("shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1)
    assert "已改發連結" in out3

    class _TGAllFail(_TG):
        async def send_text(self, *_a):
            raise RuntimeError("text fail")

    monkeypatch.setattr(tg_adapter, "TelegramBotAdapter", _TGAllFail)
    out4 = await nas_tools.send_nas_file("shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1)
    assert "無法直接發送" in out4 and "https://x/s/abc" in out4


@pytest.mark.asyncio
async def test_send_nas_file_line_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """send_nas_file：Line 群組查無、目標為空、圖片 fallback、文字發送與例外。"""
    import ching_tech_os.services.bot_line as line_module

    group_uuid = "00000000-0000-0000-0000-000000000001"

    # 群組不存在
    _setup_send(monkeypatch, tmp_path)
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value=None))
    monkeypatch.setattr(nas_tools, "get_connection", lambda: _ConnCtx(conn))
    out = await nas_tools.send_nas_file("shared://projects/a.jpg", line_group_id=group_uuid, ctos_user_id=1)
    assert "找不到群組" in out

    # 群組存在但 platform_group_id 為空 → 無法確定發送目標
    conn2 = SimpleNamespace(fetchrow=AsyncMock(return_value={"platform_group_id": None}))
    monkeypatch.setattr(nas_tools, "get_connection", lambda: _ConnCtx(conn2))
    out2 = await nas_tools.send_nas_file("shared://projects/a.jpg", line_group_id=group_uuid, ctos_user_id=1)
    assert "無法確定發送目標" in out2

    # 圖片發送失敗 → fallback 文字成功
    monkeypatch.setattr(line_module, "push_image", AsyncMock(return_value=(None, "quota")))
    monkeypatch.setattr(line_module, "push_text", AsyncMock(return_value=("m2", None)))
    out3 = await nas_tools.send_nas_file("shared://projects/a.jpg", line_user_id="U1", ctos_user_id=1)
    assert "已改發連結" in out3

    # 圖片與 fallback 皆失敗
    monkeypatch.setattr(line_module, "push_text", AsyncMock(return_value=(None, "err2")))
    out4 = await nas_tools.send_nas_file("shared://projects/a.jpg", line_user_id="U1", ctos_user_id=1)
    assert "無法直接發送" in out4

    # 非圖片：文字連結成功 / 失敗
    _setup_send(monkeypatch, tmp_path, filename="doc.bin", size=2048)
    monkeypatch.setattr(line_module, "push_text", AsyncMock(return_value=("m3", None)))
    out5 = await nas_tools.send_nas_file("shared://projects/doc.bin", line_user_id="U1", ctos_user_id=1)
    assert "已發送檔案連結" in out5

    monkeypatch.setattr(line_module, "push_text", AsyncMock(return_value=(None, "err3")))
    out6 = await nas_tools.send_nas_file("shared://projects/doc.bin", line_user_id="U1", ctos_user_id=1)
    assert "無法直接發送" in out6

    # 發送過程丟例外
    monkeypatch.setattr(line_module, "push_text", AsyncMock(side_effect=RuntimeError("net")))
    out7 = await nas_tools.send_nas_file("shared://projects/doc.bin", line_user_id="U1", ctos_user_id=1)
    assert "發送訊息失敗" in out7


# ============================================================
# prepare_file_message
# ============================================================


@pytest.mark.asyncio
async def test_prepare_file_message_knowledge_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """prepare_file_message：知識庫附件的解析失敗、不存在、kb_id 缺失與 NAS 附件格式。"""
    import ching_tech_os.services.path_manager as pm
    import ching_tech_os.services.share as share_module
    from ching_tech_os.services.path_manager import StorageZone
    from ching_tech_os.config import settings

    _allow(monkeypatch, allowed=True)
    monkeypatch.setattr(settings, "public_url", "https://x")

    # parse 失敗
    def _parse_fail(_p):
        raise ValueError("bad path")

    monkeypatch.setattr(pm.path_manager, "parse", _parse_fail)
    out = await nas_tools.prepare_file_message("local://knowledge/assets/images/x.png", ctos_user_id=1)
    assert "無法解析路徑" in out

    # 檔案不存在
    monkeypatch.setattr(
        pm.path_manager,
        "parse",
        lambda _p: SimpleNamespace(zone=StorageZone.LOCAL, path="knowledge/assets/images/kb-001-x.png"),
    )
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(tmp_path / "no.png"))
    out2 = await nas_tools.prepare_file_message("local://knowledge/assets/images/kb-001-x.png", ctos_user_id=1)
    assert "檔案不存在" in out2

    # 無法識別 kb_id（檔名沒有 kb-NNN 前綴）
    noid = tmp_path / "noprefix.png"
    noid.write_bytes(b"img")
    monkeypatch.setattr(
        pm.path_manager,
        "parse",
        lambda _p: SimpleNamespace(zone=StorageZone.LOCAL, path="knowledge/assets/images/noprefix.png"),
    )
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(noid))
    out3 = await nas_tools.prepare_file_message("local://knowledge/assets/images/noprefix.png", ctos_user_id=1)
    assert "無法從路徑中識別知識庫 ID" in out3

    # NAS 附件（ctos://）：從路徑提取 kb_id，非圖片走檔案分支
    att = tmp_path / "spec.pdf"
    att.write_bytes(b"pdf")
    monkeypatch.setattr(
        pm.path_manager,
        "parse",
        lambda _p: SimpleNamespace(zone=StorageZone.CTOS, path="knowledge/attachments/kb-002/spec.pdf"),
    )
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(att))
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(return_value=SimpleNamespace(full_url="https://x/s/t", token="t")),
    )
    out4 = await nas_tools.prepare_file_message("ctos://knowledge/attachments/kb-002/spec.pdf", ctos_user_id=1)
    assert "[FILE_MESSAGE:" in out4 and "知識庫檔案" in out4

    # 知識庫分享連結建立失敗
    monkeypatch.setattr(
        share_module, "create_share_link", AsyncMock(side_effect=RuntimeError("DB down"))
    )
    out5 = await nas_tools.prepare_file_message("ctos://knowledge/attachments/kb-002/spec.pdf", ctos_user_id=1)
    assert "建立分享連結失敗" in out5


@pytest.mark.asyncio
async def test_prepare_file_message_nas_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """prepare_file_message：NAS 檔案的驗證失敗、連結失敗與非 linebot 路徑。"""
    import ching_tech_os.services.share as share_module
    from ching_tech_os.services.share import NasFileNotFoundError, NasFileAccessDenied
    from ching_tech_os.config import settings

    _allow(monkeypatch, allowed=True)
    monkeypatch.setattr(settings, "ctos_mount_path", str(tmp_path / "ctos"))
    monkeypatch.setattr(settings, "line_files_nas_path", "linebot/files")

    def _raise_not_found(_p, **_k):
        raise NasFileNotFoundError("不存在")

    monkeypatch.setattr(share_module, "validate_nas_file_path", _raise_not_found)
    out = await nas_tools.prepare_file_message("shared://projects/x.bin", ctos_user_id=1)
    assert "不存在" in out

    def _raise_denied(_p, **_k):
        raise NasFileAccessDenied("拒絕")

    monkeypatch.setattr(share_module, "validate_nas_file_path", _raise_denied)
    out2 = await nas_tools.prepare_file_message("shared://projects/x.bin", ctos_user_id=1)
    assert "拒絕" in out2

    # 檔案在 linebot 路徑之外：nas_path 保持完整路徑
    outside = tmp_path / "projects" / "x.bin"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"x" * 10)
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: outside)
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(return_value=SimpleNamespace(full_url="https://x/s/t", token="t")),
    )
    out3 = await nas_tools.prepare_file_message("shared://projects/x.bin", ctos_user_id=1)
    assert "[FILE_MESSAGE:" in out3
    assert str(outside) in out3  # nas_path 保留原完整路徑

    # NAS 分享連結建立失敗
    monkeypatch.setattr(
        share_module, "create_share_link", AsyncMock(side_effect=RuntimeError("DB down"))
    )
    out4 = await nas_tools.prepare_file_message("shared://projects/x.bin", ctos_user_id=1)
    assert "建立分享連結失敗" in out4


# ============================================================
# list_library_folders / _walk_tree
# ============================================================


def _build_library(tmp_path: Path) -> Path:
    """輔助：建立測試用圖書館目錄結構。"""
    lib = tmp_path / "library"
    tech = lib / "技術文件"
    motor = tech / "馬達"
    motor.mkdir(parents=True)
    (motor / "spec-a.pdf").write_text("x", encoding="utf-8")
    (motor / "spec-b.pdf").write_text("x", encoding="utf-8")
    for i in range(12):
        (tech / f"f{i:02d}.txt").write_text("x", encoding="utf-8")
    (lib / "產品資料").mkdir()
    (lib / "root.txt").write_text("x", encoding="utf-8")
    return lib


@pytest.mark.asyncio
async def test_list_library_folders_bound_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """list_library_folders：綁定用戶瀏覽根目錄與子路徑、各種路徑錯誤。"""
    from ching_tech_os.config import settings

    lib = _build_library(tmp_path)
    monkeypatch.setattr(settings, "library_mount_path", str(lib))
    _allow(monkeypatch, mounts={"library": str(lib)})
    monkeypatch.setenv("CTOS_USER_ID", "1")

    out = await nas_tools.list_library_folders(ctos_user_id=1)
    assert "技術文件" in out and "產品資料" in out
    assert "個檔案" in out
    assert "還有 2 個檔案" in out  # 12 個檔案只顯示 10 個

    out2 = await nas_tools.list_library_folders(path="技術文件", ctos_user_id=1)
    assert "馬達" in out2

    out3 = await nas_tools.list_library_folders(path="../..", ctos_user_id=1)
    assert "路徑無效" in out3

    out4 = await nas_tools.list_library_folders(path="不存在的分類", ctos_user_id=1)
    assert "路徑不存在" in out4

    out5 = await nas_tools.list_library_folders(path="root.txt", ctos_user_id=1)
    assert "路徑不是資料夾" in out5

    # 工具權限被拒
    _allow(monkeypatch, allowed=False, mounts={"library": str(lib)})
    out6 = await nas_tools.list_library_folders(ctos_user_id=1)
    assert out6.startswith("❌")

    # 沒有 library 掛載權限
    _allow(monkeypatch, mounts={"projects": "/p"})
    out7 = await nas_tools.list_library_folders(ctos_user_id=1)
    assert "權限不足" in out7


@pytest.mark.asyncio
async def test_list_library_folders_unbound_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """list_library_folders：未綁定用戶只看得到公開資料夾，Agent 限制優先。"""
    from ching_tech_os.config import settings

    lib = _build_library(tmp_path)
    monkeypatch.setattr(settings, "library_mount_path", str(lib))
    monkeypatch.setattr(settings, "library_public_folders", ["技術文件"])
    _allow(monkeypatch, mounts={"library": str(lib)})
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.delenv("AGENT_ALLOWED_LIBRARY_PATHS", raising=False)

    out = await nas_tools.list_library_folders(ctos_user_id=None)
    assert "技術文件" in out
    assert "產品資料" not in out

    # 非公開資料夾
    out2 = await nas_tools.list_library_folders(path="產品資料", ctos_user_id=None)
    assert "不對外開放" in out2

    # 公開資料夾的子路徑可以瀏覽
    out3 = await nas_tools.list_library_folders(path="技術文件", ctos_user_id=None)
    assert "馬達" in out3

    # Agent library 路徑限制優先於 settings 公開清單
    monkeypatch.setenv(
        "AGENT_ALLOWED_LIBRARY_PATHS", json.dumps(["產品資料/型錄", "產品資料/報價"])
    )
    out4 = await nas_tools.list_library_folders(ctos_user_id=None)
    assert "產品資料" in out4
    assert "技術文件" not in out4


@pytest.mark.asyncio
async def test_list_library_folders_empty_and_permission_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """list_library_folders：空目錄顯示 (空)；無權限目錄顯示提示。"""
    from ching_tech_os.config import settings

    lib = tmp_path / "empty-lib"
    lib.mkdir()
    monkeypatch.setattr(settings, "library_mount_path", str(lib))
    _allow(monkeypatch, mounts={"library": str(lib)})
    monkeypatch.setenv("CTOS_USER_ID", "1")

    out = await nas_tools.list_library_folders(ctos_user_id=1)
    assert "(空)" in out

    # 無權限子目錄：rglob 計數失敗、遞迴 iterdir 失敗
    secret = lib / "秘密"
    secret.mkdir()
    os.chmod(secret, 0o000)
    try:
        out2 = await nas_tools.list_library_folders(ctos_user_id=1)
        assert "秘密/" in out2
        assert "(無權限)" in out2
    finally:
        os.chmod(secret, 0o755)


def test_walk_tree_rglob_permission_error() -> None:
    """_walk_tree：子目錄檔案計數遇 PermissionError 時視為空。"""

    class _FakeSubDir:
        name = "受限"

        def is_dir(self):
            return True

        def is_file(self):
            return False

        def rglob(self, _pattern):
            raise PermissionError("denied")

    class _FakeRoot:
        def iterdir(self):
            return iter([_FakeSubDir()])

    lines: list[str] = []
    nas_tools._walk_tree(_FakeRoot(), lines, prefix="", current_depth=0, max_depth=1)
    assert lines == ["└── 受限/ (空)"]


# ============================================================
# archive_to_library
# ============================================================


def _setup_archive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """輔助：準備 archive_to_library 的圖書館與來源檔案。"""
    import ching_tech_os.services.path_manager as pm
    from ching_tech_os.services.path_manager import StorageZone
    from ching_tech_os.config import settings

    lib = tmp_path / "library"
    lib.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "library_mount_path", str(lib))
    _allow(monkeypatch, mounts={"library": str(lib)})

    src = tmp_path / "upload" / "原始檔.pdf"
    src.parent.mkdir(exist_ok=True)
    src.write_bytes(b"x" * 2048)
    monkeypatch.setattr(
        pm.path_manager,
        "parse",
        lambda _p: SimpleNamespace(zone=StorageZone.CTOS, path="linebot/files/原始檔.pdf"),
    )
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(src))
    return lib, src, pm


@pytest.mark.asyncio
async def test_archive_to_library_success_and_dedup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """archive_to_library：成功歸檔（含子資料夾）與檔名去重。"""
    lib, _src, _pm = _setup_archive(monkeypatch, tmp_path)

    out = await nas_tools.archive_to_library(
        "ctos://linebot/files/原始檔.pdf",
        category="技術文件",
        filename="品牌-型號-規格書.pdf",
        folder="馬達規格",
        ctos_user_id=1,
    )
    assert "✅ 已歸檔：shared://library/技術文件/馬達規格/品牌-型號-規格書.pdf" in out
    assert (lib / "技術文件" / "馬達規格" / "品牌-型號-規格書.pdf").exists()

    # 同名檔案：自動加數字後綴
    out2 = await nas_tools.archive_to_library(
        "ctos://linebot/files/原始檔.pdf",
        category="技術文件",
        filename="品牌-型號-規格書.pdf",
        folder="馬達規格",
        ctos_user_id=1,
    )
    assert "品牌-型號-規格書-2.pdf" in out2

    # filename 清理後為空 → fallback 用來源檔名
    out3 = await nas_tools.archive_to_library(
        "ctos://linebot/files/原始檔.pdf",
        category="其他",
        filename="../",
        ctos_user_id=1,
    )
    assert "shared://library/其他/原始檔.pdf" in out3


@pytest.mark.asyncio
async def test_archive_to_library_error_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """archive_to_library：權限、分類、來源路徑與複製失敗的各種錯誤。"""
    import ching_tech_os.services.path_manager as pm
    from ching_tech_os.services.path_manager import StorageZone

    lib, src, _pm = _setup_archive(monkeypatch, tmp_path)

    # 工具權限被拒
    _allow(monkeypatch, allowed=False, mounts={"library": str(lib)})
    out = await nas_tools.archive_to_library("ctos://x", "技術文件", "a.pdf", ctos_user_id=1)
    assert out.startswith("❌")

    # 沒有 library 掛載
    _allow(monkeypatch, mounts={"projects": "/p"})
    out2 = await nas_tools.archive_to_library("ctos://x", "技術文件", "a.pdf", ctos_user_id=1)
    assert "權限不足" in out2

    _allow(monkeypatch, mounts={"library": str(lib)})

    # 無效分類
    out3 = await nas_tools.archive_to_library("ctos://x", "亂七八糟", "a.pdf", ctos_user_id=1)
    assert "無效的分類" in out3

    # parse 失敗
    def _parse_fail(_p):
        raise ValueError("格式錯誤")

    monkeypatch.setattr(pm.path_manager, "parse", _parse_fail)
    out4 = await nas_tools.archive_to_library("bad://x", "技術文件", "a.pdf", ctos_user_id=1)
    assert "無效的來源路徑" in out4

    # 非 CTOS 區域
    monkeypatch.setattr(
        pm.path_manager,
        "parse",
        lambda _p: SimpleNamespace(zone=StorageZone.SHARED, path="projects/x.pdf"),
    )
    out5 = await nas_tools.archive_to_library("shared://projects/x.pdf", "技術文件", "a.pdf", ctos_user_id=1)
    assert "必須是 CTOS 區域" in out5

    # 路徑轉換失敗
    monkeypatch.setattr(
        pm.path_manager,
        "parse",
        lambda _p: SimpleNamespace(zone=StorageZone.CTOS, path="linebot/files/x.pdf"),
    )

    def _fs_fail(_p):
        raise ValueError("轉換失敗")

    monkeypatch.setattr(pm.path_manager, "to_filesystem", _fs_fail)
    out6 = await nas_tools.archive_to_library("ctos://linebot/files/x.pdf", "技術文件", "a.pdf", ctos_user_id=1)
    assert "路徑轉換失敗" in out6

    # 來源檔案不存在
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(tmp_path / "no.pdf"))
    out7 = await nas_tools.archive_to_library("ctos://linebot/files/no.pdf", "技術文件", "a.pdf", ctos_user_id=1)
    assert "來源檔案不存在" in out7

    # 來源不是檔案
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(src.parent))
    out8 = await nas_tools.archive_to_library("ctos://linebot/files", "技術文件", "a.pdf", ctos_user_id=1)
    assert "不是檔案" in out8

    # 複製失敗：PermissionError 與一般例外
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(src))

    def _copy_permission(_s, _t):
        raise PermissionError("read-only")

    monkeypatch.setattr(nas_tools.shutil, "copy2", _copy_permission)
    out9 = await nas_tools.archive_to_library("ctos://linebot/files/原始檔.pdf", "技術文件", "a.pdf", ctos_user_id=1)
    assert "沒有寫入權限" in out9

    def _copy_fail(_s, _t):
        raise RuntimeError("disk full")

    monkeypatch.setattr(nas_tools.shutil, "copy2", _copy_fail)
    out10 = await nas_tools.archive_to_library("ctos://linebot/files/原始檔.pdf", "技術文件", "a.pdf", ctos_user_id=1)
    assert "複製失敗" in out10
