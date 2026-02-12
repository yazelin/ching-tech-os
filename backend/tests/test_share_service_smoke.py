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
