"""share service smoke 測試。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.models.share import ShareLinkCreate
from ching_tech_os.services import share


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _row(**kwargs):
    now = datetime.now(timezone.utc)
    base = {
        "id": uuid4(),
        "token": "abc123",
        "resource_type": "content",
        "resource_id": "",
        "created_by": "admin",
        "expires_at": now + timedelta(hours=1),
        "access_count": 0,
        "created_at": now,
        "content": "hello",
        "content_type": "text/plain",
        "filename": "note.txt",
        "password_hash": None,
        "attempt_count": 0,
        "locked_at": None,
        "storage_path": "x",
        "file_type": "text/plain",
        "project_id": uuid4(),
        "file_size": 10,
    }
    base.update(kwargs)
    return base


def test_share_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    token = share.generate_token(8)
    assert len(token) == 8
    pwd = share.generate_password(4)
    assert len(pwd) == 4 and pwd.isdigit()

    hashed = share.hash_password("1234")
    assert share.verify_password("1234", hashed) is True
    assert share.verify_password("9999", hashed) is False

    assert share.parse_expires_in("1h") is not None
    assert share.parse_expires_in("24h") is not None
    assert share.parse_expires_in("7d") is not None
    assert share.parse_expires_in(None) is None
    assert share.parse_expires_in("bad") is not None

    monkeypatch.setattr(share.settings, "public_url", "https://example.com")
    assert share.get_full_url("abc") == "https://example.com/s/abc"

    # validate_nas_file_path：nanobanana 特殊路徑
    monkeypatch.setattr(share.settings, "ctos_mount_path", str(tmp_path / "ctos"))
    monkeypatch.setattr(share.settings, "nas_mount_path", str(tmp_path))
    target = tmp_path / "ctos" / "linebot" / "files" / "ai-images" / "x.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"img")
    result = share.validate_nas_file_path("/tmp/abc/nanobanana-output/x.jpg")
    assert result.name == "x.jpg"


@pytest.mark.asyncio
async def test_create_list_revoke_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=[None])  # token 唯一
    conn.fetchrow = AsyncMock(return_value=_row())
    conn.fetch = AsyncMock(return_value=[_row(resource_type="content", resource_id="")])
    conn.execute = AsyncMock(return_value="DELETE 2")
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(share, "get_resource_title", AsyncMock(return_value="標題"))
    monkeypatch.setattr(share.settings, "public_url", "https://example.com")

    link = await share.create_share_link(
        ShareLinkCreate(resource_type="content", content="hello", filename="a.txt"),
        created_by="admin",
    )
    assert link.token == "abc123"
    assert link.full_url.endswith("/s/abc123")

    my_links = await share.list_my_links("admin")
    assert len(my_links.links) == 1

    all_links = await share.list_all_links()
    assert len(all_links.links) == 1

    await share.revoke_link("abc123", username="admin", is_admin=False)
    deleted = await share.cleanup_expired_links()
    assert deleted == 2


@pytest.mark.asyncio
async def test_revoke_and_get_public_resource_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    # revoke: 連結不存在 / 權限不足
    conn.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(share.ShareLinkNotFoundError):
        await share.revoke_link("x", "u1", False)

    conn.fetchrow = AsyncMock(return_value={"created_by": "other"})
    with pytest.raises(share.ShareError):
        await share.revoke_link("x", "u1", False)

    # get_public_resource: 不存在 / 過期
    conn.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(share.ShareLinkNotFoundError):
        await share.get_public_resource("nope")

    conn.fetchrow = AsyncMock(return_value=_row(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    with pytest.raises(share.ShareLinkExpiredError):
        await share.get_public_resource("expired")


@pytest.mark.asyncio
async def test_get_public_resource_password_and_content(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    # 需要密碼但未提供
    conn.fetchrow = AsyncMock(return_value=_row(password_hash=share.hash_password("1234"), attempt_count=0))
    need_pwd = await share.get_public_resource("abc")
    assert isinstance(need_pwd, share.PasswordRequiredResponse)

    # 密碼錯誤
    conn.fetchrow = AsyncMock(return_value=_row(password_hash=share.hash_password("1234"), attempt_count=1))
    with pytest.raises(share.PasswordIncorrectError):
        await share.get_public_resource("abc", password="9999")

    # 錯誤次數達上限 -> 鎖定
    conn.fetchrow = AsyncMock(return_value=_row(password_hash=share.hash_password("1234"), attempt_count=4))
    with pytest.raises(share.ShareLinkLockedError):
        await share.get_public_resource("abc", password="9999")

    # 密碼正確 + content 類型
    conn.fetchrow = AsyncMock(return_value=_row(password_hash=share.hash_password("1234"), attempt_count=1))
    result = await share.get_public_resource("abc", password="1234")
    assert isinstance(result, share.PublicResourceResponse)
    assert result.type == "content"
    assert result.data["content"] == "hello"


@pytest.mark.asyncio
async def test_resource_title_and_link_info(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(share, "get_knowledge", lambda _rid: SimpleNamespace(title="KB"))
    monkeypatch.setattr(share.settings, "ctos_mount_path", str(tmp_path / "ctos"))
    monkeypatch.setattr(share.settings, "nas_mount_path", str(tmp_path))

    fp = tmp_path / "ctos" / "linebot" / "files" / "ai-images" / "t.jpg"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(b"x")

    assert await share.get_resource_title("knowledge", "k1") == "KB"
    assert await share.get_resource_title("content", "", "memo.txt") == "memo.txt"
    assert await share.get_resource_title("unknown", "x") == "未知資源"

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"resource_type": "content", "resource_id": "r1", "expires_at": None})
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))
    info = await share.get_link_info("abc")
    assert info["resource_type"] == "content"

    conn.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(share.ShareLinkNotFoundError):
        await share.get_link_info("missing")


@pytest.mark.asyncio
async def test_get_public_resource_for_non_content_types(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    now = datetime.now(timezone.utc)
    knowledge = SimpleNamespace(
        id="kb1",
        title="知識標題",
        content="內容",
        attachments=[
            SimpleNamespace(model_dump=lambda: {"path": "../assets/images/a.png"}),
            SimpleNamespace(model_dump=lambda: {"path": "local/images/b.png"}),
        ],
        related=["kb2"],
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(share, "get_knowledge", lambda _rid: knowledge)
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="knowledge", resource_id="kb1", password_hash=None))
    res_kb = await share.get_public_resource("tk-kb")
    assert res_kb.type == "knowledge"
    assert res_kb.data["attachments"][0]["path"] == "local/images/a.png"

    nas_file = tmp_path / "demo.bin"
    nas_file.write_bytes(b"123456")
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _rid: nas_file)
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="x", password_hash=None))
    res_nas = await share.get_public_resource("tk-nas")
    assert res_nas.type == "nas_file"
    assert res_nas.data["file_name"] == "demo.bin"
    assert res_nas.data["download_url"] == "/api/public/tk-nas/download"



@pytest.mark.asyncio
async def test_get_public_resource_non_content_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="knowledge", resource_id="kb1", password_hash=None))
    monkeypatch.setattr(share, "get_knowledge", lambda _rid: (_ for _ in ()).throw(share.KnowledgeNotFoundError("x")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-kb")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="x", password_hash=None))
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _rid: (_ for _ in ()).throw(share.NasFileNotFoundError("missing")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-nas1")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="x", password_hash=None))
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _rid: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-nas2")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="unknown_type", password_hash=None))
    with pytest.raises(share.ShareError):
        await share.get_public_resource("e-unknown")


@pytest.mark.asyncio
async def test_link_info_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    conn.fetchrow = AsyncMock(return_value={
        "resource_type": "content",
        "resource_id": "r1",
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    })
    with pytest.raises(share.ShareLinkExpiredError):
        await share.get_link_info("expired-link")


@pytest.mark.asyncio
async def test_share_locked_and_deleted_title_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    # PasswordRequiredError 分支
    err = share.PasswordRequiredError()
    assert err.code == "PASSWORD_REQUIRED"
    assert err.status_code == 401

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    # locked_at 分支
    conn.fetchrow = AsyncMock(return_value=_row(locked_at=datetime.now(timezone.utc)))
    with pytest.raises(share.ShareLinkLockedError):
        await share.get_public_resource("locked")

    # list_my_links / list_all_links 的（已刪除）分支
    conn.fetch = AsyncMock(return_value=[_row(resource_type="knowledge", resource_id="kb-x")])
    monkeypatch.setattr(share, "get_resource_title", AsyncMock(side_effect=share.ResourceNotFoundError("missing")))
    my_links = await share.list_my_links("admin")
    all_links = await share.list_all_links()
    assert my_links.links[0].resource_title == "（已刪除）"
    assert all_links.links[0].resource_title == "（已刪除）"


@pytest.mark.asyncio
async def test_public_resource_size_format_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    # nas_file: MB / KB
    large_file = tmp_path / "large.bin"
    large_file.write_bytes(b"x" * (2 * 1024 * 1024))
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _rid: large_file)
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="n1", password_hash=None))
    res_mb = await share.get_public_resource("tok-mb")
    assert res_mb.data["file_size_str"].endswith("MB")

    kb_file = tmp_path / "kb.bin"
    kb_file.write_bytes(b"x" * 2048)
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _rid: kb_file)
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="n2", password_hash=None))
    res_kb = await share.get_public_resource("tok-kb")
    assert res_kb.data["file_size_str"].endswith("KB")


def _setup_nas_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """把 ctos / nas 掛載路徑指向 tmp_path，避免碰到真實 NAS"""
    monkeypatch.setattr(share.settings, "ctos_mount_path", str(tmp_path / "ctos"))
    monkeypatch.setattr(share.settings, "nas_mount_path", str(tmp_path))
    return tmp_path


def test_validate_nas_file_path_ai_images_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """validate_nas_file_path：ai-images/ 相對路徑分支"""
    _setup_nas_paths(monkeypatch, tmp_path)
    target = tmp_path / "ctos" / "linebot" / "files" / "ai-images" / "pic.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"img")

    result = share.validate_nas_file_path("ai-images/pic.jpg")
    assert result.name == "pic.jpg"


def test_validate_nas_file_path_path_manager_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """validate_nas_file_path：走 PathManager 解析的各種錯誤分支"""
    from ching_tech_os.services import path_manager as pm_module
    from ching_tech_os.services.path_manager import StorageZone
    from ching_tech_os.services.shared_source_permissions import SharedSourceAccessDeniedError

    _setup_nas_paths(monkeypatch, tmp_path)
    pm = pm_module.path_manager

    # parse 失敗 -> NasFileAccessDenied
    monkeypatch.setattr(pm, "parse", lambda _p: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(share.NasFileAccessDenied):
        share.validate_nas_file_path("weird://path")

    # 不允許的區域（temp）-> NasFileAccessDenied
    monkeypatch.setattr(pm, "parse", lambda _p: SimpleNamespace(zone=StorageZone.TEMP))
    with pytest.raises(share.NasFileAccessDenied):
        share.validate_nas_file_path("temp://x.txt")

    # to_filesystem 丟 SharedSourceAccessDeniedError -> NasFileAccessDenied
    monkeypatch.setattr(pm, "parse", lambda _p: SimpleNamespace(zone=StorageZone.CTOS))
    monkeypatch.setattr(
        pm,
        "to_filesystem",
        lambda _p, source_permissions=None: (_ for _ in ()).throw(SharedSourceAccessDeniedError("denied")),
    )
    with pytest.raises(share.NasFileAccessDenied):
        share.validate_nas_file_path("ctos://x.txt")

    # to_filesystem 丟 ValueError -> NasFileAccessDenied
    monkeypatch.setattr(
        pm,
        "to_filesystem",
        lambda _p, source_permissions=None: (_ for _ in ()).throw(ValueError("bad path")),
    )
    with pytest.raises(share.NasFileAccessDenied):
        share.validate_nas_file_path("ctos://y.txt")

    # 解析出的路徑在 NAS 掛載點之外 -> NasFileAccessDenied
    monkeypatch.setattr(pm, "to_filesystem", lambda _p, source_permissions=None: "/etc/passwd")
    with pytest.raises(share.NasFileAccessDenied):
        share.validate_nas_file_path("ctos://escape.txt")

    # 檔案不存在 -> NasFileNotFoundError
    monkeypatch.setattr(
        pm, "to_filesystem", lambda _p, source_permissions=None: str(tmp_path / "missing.bin")
    )
    with pytest.raises(share.NasFileNotFoundError):
        share.validate_nas_file_path("ctos://missing.bin")

    # 路徑是目錄不是檔案 -> NasFileNotFoundError
    folder = tmp_path / "a-folder"
    folder.mkdir()
    monkeypatch.setattr(pm, "to_filesystem", lambda _p, source_permissions=None: str(folder))
    with pytest.raises(share.NasFileNotFoundError):
        share.validate_nas_file_path("ctos://a-folder")

    # 掛載點路徑含 null byte，resolve 丟例外 -> NasFileAccessDenied（generic except 分支）
    ok_file = tmp_path / "ok.bin"
    ok_file.write_bytes(b"x")
    monkeypatch.setattr(pm, "to_filesystem", lambda _p, source_permissions=None: str(ok_file))
    monkeypatch.setattr(share.settings, "nas_mount_path", "bad\0path")
    with pytest.raises(share.NasFileAccessDenied):
        share.validate_nas_file_path("ctos://ok.bin")


@pytest.mark.asyncio
async def test_get_resource_title_nas_and_error_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """get_resource_title：nas_file 成功與各種錯誤映射為 ResourceNotFoundError"""
    # nas_file 成功分支
    nas_file = tmp_path / "圖面.pdf"
    nas_file.write_bytes(b"pdf")
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _p: nas_file)
    assert await share.get_resource_title("nas_file", "圖面.pdf") == "圖面.pdf"

    # 知識庫不存在 -> ResourceNotFoundError
    monkeypatch.setattr(
        share, "get_knowledge", lambda _rid: (_ for _ in ()).throw(share.KnowledgeNotFoundError("x"))
    )
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_resource_title("knowledge", "kb-x")

    # NAS 檔案不存在 -> ResourceNotFoundError
    monkeypatch.setattr(
        share, "validate_nas_file_path", lambda _p: (_ for _ in ()).throw(share.NasFileNotFoundError("gone"))
    )
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_resource_title("nas_file", "gone.txt")

    # NAS 存取被拒 -> ResourceNotFoundError
    monkeypatch.setattr(
        share, "validate_nas_file_path", lambda _p: (_ for _ in ()).throw(share.NasFileAccessDenied("no"))
    )
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_resource_title("nas_file", "secret.txt")


@pytest.mark.asyncio
async def test_create_share_link_edge_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_share_link：content 缺內容、token 產生失敗、自訂密碼、非 content 類型"""
    # content 類型缺 content -> ShareError
    with pytest.raises(share.ShareError):
        await share.create_share_link(
            ShareLinkCreate(resource_type="content"), created_by="admin"
        )

    conn = AsyncMock()
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(share.settings, "public_url", "https://example.com")

    # token 連續 10 次撞號 -> ShareError
    conn.fetchval = AsyncMock(return_value=1)
    with pytest.raises(share.ShareError):
        await share.create_share_link(
            ShareLinkCreate(resource_type="content", content="hi"), created_by="admin"
        )

    # 非 content 類型 + 自訂密碼：呼叫 get_resource_title 並回傳 has_password
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="/f.txt"))
    monkeypatch.setattr(share, "get_resource_title", AsyncMock(return_value="f.txt"))

    link = await share.create_share_link(
        ShareLinkCreate(resource_type="nas_file", resource_id="/f.txt", password="5678"),
        created_by="admin",
    )
    assert link.resource_title == "f.txt"
    assert link.has_password is True
    assert link.password == "5678"

    # content 類型未給密碼：自動產生 4 位數字密碼
    conn.fetchrow = AsyncMock(return_value=_row())
    auto = await share.create_share_link(
        ShareLinkCreate(resource_type="content", content="hi"), created_by="admin"
    )
    assert auto.has_password is True
    assert auto.password is not None and auto.password.isdigit()

