"""NAS API 模組測試。"""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from ching_tech_os.api import nas as nas_api
from ching_tech_os.services.smb import SMBAuthError, SMBConnectionError, SMBError


@pytest.mark.asyncio
async def test_nas_connect_disconnect_and_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(user_id=7)

    async def _ok(*_args, **_kwargs):
        return "tok"

    monkeypatch.setattr(nas_api, "run_in_smb_pool", _ok)
    resp = await nas_api.nas_connect(nas_api.NASConnectRequest(host="h", username="u", password="p"), session=session)
    assert resp.success is True and resp.token == "tok"

    async def _auth(*_args, **_kwargs):
        raise SMBAuthError()

    monkeypatch.setattr(nas_api, "run_in_smb_pool", _auth)
    resp = await nas_api.nas_connect(nas_api.NASConnectRequest(host="h", username="u", password="p"), session=session)
    assert resp.success is False

    async def _conn(*_args, **_kwargs):
        raise SMBConnectionError()

    monkeypatch.setattr(nas_api, "run_in_smb_pool", _conn)
    with pytest.raises(HTTPException) as e:
        await nas_api.nas_connect(nas_api.NASConnectRequest(host="h", username="u", password="p"), session=session)
    assert e.value.status_code == 503

    monkeypatch.setattr(nas_api.nas_connection_manager, "close_connection", lambda _t: True)
    assert (await nas_api.nas_disconnect("x", session=session)).success is True

    monkeypatch.setattr(
        nas_api.nas_connection_manager,
        "get_user_connections",
        lambda _uid: [
            {
                "token": "t1",
                "host": "h",
                "username": "u",
                "created_at": "2024",
                "expires_at": "2025",
                "last_used_at": "2024",
            }
        ],
    )
    resp = await nas_api.list_nas_connections(session=session)
    assert len(resp.connections) == 1
    assert (await nas_api.list_nas_connections(session=SimpleNamespace(user_id=None))).connections == []


def test_get_nas_connection_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    smb = object()
    conn = SimpleNamespace(host="h", get_smb_service=lambda: smb)
    monkeypatch.setattr(nas_api.nas_connection_manager, "get_connection", lambda t: conn if t == "ok" else None)
    monkeypatch.setattr(nas_api, "create_smb_service", lambda username, password, host: ("svc", host, username, password))

    session = SimpleNamespace(username="u", password="p", nas_host="h")
    assert nas_api.get_nas_connection("ok", session=session) == (smb, "h")
    with pytest.raises(HTTPException) as e1:
        nas_api.get_nas_connection("bad", session=session)
    assert e1.value.status_code == 401

    assert nas_api.get_nas_connection(None, session=session)[1] == "h"
    with pytest.raises(HTTPException):
        nas_api.get_nas_connection(None, session=SimpleNamespace(username="u", password=None, nas_host="h"))

    # with query parameter
    assert nas_api.get_nas_connection_with_query(None, "ok", session=session) == (smb, "h")
    with pytest.raises(HTTPException):
        nas_api.get_nas_connection_with_query(None, "bad", session=session)


def test_nas_helpers() -> None:
    assert nas_api._parse_path("/share/a.txt") == ("share", "a.txt")
    assert nas_api._parse_path("/share") == ("share", "")
    with pytest.raises(HTTPException):
        nas_api._parse_path("/")
    assert nas_api._get_mime_type("a.txt") == "text/plain"
    assert nas_api._get_mime_type("a.unknown-ext") == "application/octet-stream"


@pytest.mark.asyncio
async def test_list_and_browse_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    smb = object()
    nas_conn = (smb, "h")

    async def _ok(_smb, fn):
        return fn(SimpleNamespace(
            list_shares=lambda: [{"name": "docs", "type": "disk"}],
            browse_directory=lambda *_a: [{"name": "f.txt", "type": "file", "size": 1, "modified": None}],
        ))

    monkeypatch.setattr(nas_api, "_run_smb", _ok)
    shares = await nas_api.list_shares(nas_conn=nas_conn)
    assert shares.shares[0].name == "docs"
    browse = await nas_api.browse_directory(path="/docs", nas_conn=nas_conn)
    assert browse.path == "/docs"

    with pytest.raises(HTTPException):
        await nas_api.browse_directory(path="/", nas_conn=nas_conn)

    async def _conn_err(*_args, **_kwargs):
        raise SMBConnectionError()

    monkeypatch.setattr(nas_api, "_run_smb", _conn_err)
    with pytest.raises(HTTPException) as e1:
        await nas_api.list_shares(nas_conn=nas_conn)
    assert e1.value.status_code == 503

    async def _perm_err(*_args, **_kwargs):
        raise SMBError("沒有權限")

    monkeypatch.setattr(nas_api, "_run_smb", _perm_err)
    with pytest.raises(HTTPException) as e2:
        await nas_api.browse_directory(path="/docs", nas_conn=nas_conn)
    assert e2.value.status_code == 403


@pytest.mark.asyncio
async def test_read_download_and_upload_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    smb = object()
    nas_conn = (smb, "h")
    session = SimpleNamespace(user_id=9)

    async def _read_ok(_smb, fn):
        return fn(SimpleNamespace(read_file=lambda *_a: b"hello", write_file=lambda *_a: None))

    monkeypatch.setattr(nas_api, "_run_smb", _read_ok)
    resp = await nas_api.read_file(path="/docs/a.txt", nas_conn=nas_conn)
    assert resp.media_type == "text/plain"
    dl = await nas_api.download_file(path="/docs/中文.txt", nas_conn=nas_conn)
    assert "Content-Disposition" in dl.headers

    upload = UploadFile(file=BytesIO(b"data"), filename="x.txt")
    monkeypatch.setattr(nas_api, "log_message", AsyncMock())
    up = await nas_api.upload_file(path="/docs", file=upload, nas_conn=nas_conn, session=session)
    assert up.success is True

    # log_message 失敗仍不影響主流程
    upload2 = UploadFile(file=BytesIO(b"data"), filename="y.txt")
    monkeypatch.setattr(nas_api, "log_message", AsyncMock(side_effect=RuntimeError("boom")))
    up2 = await nas_api.upload_file(path="/docs", file=upload2, nas_conn=nas_conn, session=session)
    assert up2.success is True

    with pytest.raises(HTTPException):
        await nas_api.read_file(path="/docs", nas_conn=nas_conn)

    async def _not_found(*_args, **_kwargs):
        raise SMBError("檔案不存在")

    monkeypatch.setattr(nas_api, "_run_smb", _not_found)
    with pytest.raises(HTTPException) as e1:
        await nas_api.read_file(path="/docs/a.txt", nas_conn=nas_conn)
    assert e1.value.status_code == 404

    async def _deny(*_args, **_kwargs):
        raise SMBError("權限不足")

    monkeypatch.setattr(nas_api, "_run_smb", _deny)
    with pytest.raises(HTTPException) as e2:
        await nas_api.download_file(path="/docs/a.txt", nas_conn=nas_conn)
    assert e2.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_rename_mkdir_search_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    smb = object()
    nas_conn = (smb, "h")
    session = SimpleNamespace(user_id=10)

    async def _ok(_smb, fn):
        return fn(
            SimpleNamespace(
                delete_item=lambda *_a, **_k: None,
                rename_item=lambda *_a, **_k: None,
                create_directory=lambda *_a, **_k: None,
                search_files=lambda **_k: [{"name": "a.txt", "path": "/a.txt", "type": "file"}],
            )
        )

    monkeypatch.setattr(nas_api, "_run_smb", _ok)
    monkeypatch.setattr(nas_api, "log_message", AsyncMock())

    assert (await nas_api.delete_file(nas_api.DeleteRequest(path="/docs/a.txt", recursive=False), nas_conn=nas_conn, session=session)).success
    assert (await nas_api.rename_item(nas_api.RenameRequest(path="/docs/a.txt", new_name="b.txt"), nas_conn=nas_conn)).success
    assert (await nas_api.create_directory(nas_api.MkdirRequest(path="/docs/new"), nas_conn=nas_conn)).success
    sr = await nas_api.search_files(path="/docs", query="a", nas_conn=nas_conn, max_depth=99, max_results=999)
    assert sr.total == 1

    with pytest.raises(HTTPException):
        await nas_api.search_files(path="/docs", query=" ", nas_conn=nas_conn)
    with pytest.raises(HTTPException):
        await nas_api.delete_file(nas_api.DeleteRequest(path="/docs", recursive=False), nas_conn=nas_conn, session=session)
    with pytest.raises(HTTPException):
        await nas_api.rename_item(nas_api.RenameRequest(path="/docs", new_name="b"), nas_conn=nas_conn)
    with pytest.raises(HTTPException):
        await nas_api.create_directory(nas_api.MkdirRequest(path="/docs"), nas_conn=nas_conn)

    async def _conflict(*_args, **_kwargs):
        raise SMBError("已存在")

    monkeypatch.setattr(nas_api, "_run_smb", _conflict)
    with pytest.raises(HTTPException) as e1:
        await nas_api.rename_item(nas_api.RenameRequest(path="/docs/a.txt", new_name="b.txt"), nas_conn=nas_conn)
    assert e1.value.status_code == 409

    with pytest.raises(HTTPException) as e2:
        await nas_api.create_directory(nas_api.MkdirRequest(path="/docs/new"), nas_conn=nas_conn)
    assert e2.value.status_code == 409

    async def _not_empty(*_args, **_kwargs):
        raise SMBError("資料夾不是空的")

    monkeypatch.setattr(nas_api, "_run_smb", _not_empty)
    with pytest.raises(HTTPException) as e3:
        await nas_api.delete_file(nas_api.DeleteRequest(path="/docs/a.txt", recursive=False), nas_conn=nas_conn, session=session)
    assert e3.value.status_code == 400

    async def _search_nf(*_args, **_kwargs):
        raise SMBError("路徑不存在")

    monkeypatch.setattr(nas_api, "_run_smb", _search_nf)
    with pytest.raises(HTTPException) as e4:
        await nas_api.search_files(path="/docs", query="a", nas_conn=nas_conn)
    assert e4.value.status_code == 404
