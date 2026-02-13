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
    monkeypatch.setattr(share, "get_project", AsyncMock(return_value=SimpleNamespace(name="PRJ")))
    monkeypatch.setattr(share, "get_project_attachment_info", AsyncMock(return_value={"filename": "a.pdf"}))
    monkeypatch.setattr(share.settings, "ctos_mount_path", str(tmp_path / "ctos"))
    monkeypatch.setattr(share.settings, "nas_mount_path", str(tmp_path))

    fp = tmp_path / "ctos" / "linebot" / "files" / "ai-images" / "t.jpg"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(b"x")

    assert await share.get_resource_title("knowledge", "k1") == "KB"
    assert await share.get_resource_title("project", str(uuid4())) == "PRJ"
    assert await share.get_resource_title("project_attachment", str(uuid4())) == "a.pdf"
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

    project = SimpleNamespace(
        id=uuid4(),
        name="專案A",
        description="desc",
        status="active",
        start_date=now,
        end_date=None,
        milestones=[SimpleNamespace(name="M1", milestone_type="phase", planned_date=now, actual_date=None, status="pending")],
        members=[SimpleNamespace(name="王小明", role="pm")],
    )
    monkeypatch.setattr(share, "get_project", AsyncMock(return_value=project))
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="project", resource_id=str(uuid4()), password_hash=None))
    res_project = await share.get_public_resource("tk-project")
    assert res_project.type == "project"
    assert res_project.data["members"][0]["name"] == "王小明"

    nas_file = tmp_path / "demo.bin"
    nas_file.write_bytes(b"123456")
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _rid: nas_file)
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="x", password_hash=None))
    res_nas = await share.get_public_resource("tk-nas")
    assert res_nas.type == "nas_file"
    assert res_nas.data["file_name"] == "demo.bin"
    assert res_nas.data["download_url"] == "/api/public/tk-nas/download"

    monkeypatch.setattr(
        share,
        "get_project_attachment_info",
        AsyncMock(return_value={"filename": "r.pdf", "file_type": "application/pdf", "file_size": 2048}),
    )
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="project_attachment", resource_id=str(uuid4()), password_hash=None))
    res_att = await share.get_public_resource("tk-att")
    assert res_att.type == "project_attachment"
    assert res_att.data["file_size_str"] == "2.00 KB"


@pytest.mark.asyncio
async def test_get_public_resource_non_content_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="knowledge", resource_id="kb1", password_hash=None))
    monkeypatch.setattr(share, "get_knowledge", lambda _rid: (_ for _ in ()).throw(share.KnowledgeNotFoundError("x")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-kb")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="project", resource_id=str(uuid4()), password_hash=None))
    monkeypatch.setattr(share, "get_project", AsyncMock(side_effect=share.ProjectNotFoundError("x")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-project")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="x", password_hash=None))
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _rid: (_ for _ in ()).throw(share.NasFileNotFoundError("missing")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-nas1")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="nas_file", resource_id="x", password_hash=None))
    monkeypatch.setattr(share, "validate_nas_file_path", lambda _rid: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-nas2")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="project_attachment", resource_id=str(uuid4()), password_hash=None))
    monkeypatch.setattr(share, "get_project_attachment_info", AsyncMock(side_effect=share.ResourceNotFoundError("missing")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-att1")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="project_attachment", resource_id=str(uuid4()), password_hash=None))
    monkeypatch.setattr(share, "get_project_attachment_info", AsyncMock(side_effect=RuntimeError("boom")))
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_public_resource("e-att2")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="unknown_type", password_hash=None))
    with pytest.raises(share.ShareError):
        await share.get_public_resource("e-unknown")


@pytest.mark.asyncio
async def test_attachment_info_and_link_info_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))

    conn.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(share.ResourceNotFoundError):
        await share.get_project_attachment_info(str(uuid4()))

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

    # project_attachment: MB / bytes / 未知
    conn.fetchrow = AsyncMock(return_value=_row(resource_type="project_attachment", resource_id=str(uuid4()), password_hash=None))
    monkeypatch.setattr(
        share,
        "get_project_attachment_info",
        AsyncMock(return_value={"filename": "big.pdf", "file_type": "application/pdf", "file_size": 3 * 1024 * 1024}),
    )
    att_mb = await share.get_public_resource("att-mb")
    assert att_mb.data["file_size_str"].endswith("MB")

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="project_attachment", resource_id=str(uuid4()), password_hash=None))
    monkeypatch.setattr(
        share,
        "get_project_attachment_info",
        AsyncMock(return_value={"filename": "small.txt", "file_type": "text/plain", "file_size": 12}),
    )
    att_bytes = await share.get_public_resource("att-bytes")
    assert att_bytes.data["file_size_str"] == "12 bytes"

    conn.fetchrow = AsyncMock(return_value=_row(resource_type="project_attachment", resource_id=str(uuid4()), password_hash=None))
    monkeypatch.setattr(
        share,
        "get_project_attachment_info",
        AsyncMock(return_value={"filename": "unknown.bin", "file_type": "application/octet-stream", "file_size": 0}),
    )
    att_unknown = await share.get_public_resource("att-unknown")
    assert att_unknown.data["file_size_str"] == "未知"
