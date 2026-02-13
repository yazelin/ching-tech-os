"""auth API 模組測試。"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from ching_tech_os.api import auth
from ching_tech_os.models.auth import DeviceInfo, LoginRequest, SessionData
from ching_tech_os.services import permissions as permissions_service
from ching_tech_os.services import password as password_service
from ching_tech_os.services import user as user_service
from ching_tech_os.services.smb import SMBAuthError, SMBConnectionError


def _session(role: str = "user", user_id: int | None = 1) -> SessionData:
    now = datetime.now()
    return SessionData(
        username="u1",
        password="pw",
        nas_host="h",
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role=role,
        app_permissions={"knowledge-base": True},
    )


def _request(headers: dict[str, str] | None = None, host: str = "127.0.0.1") -> Request:
    raw_headers = []
    for k, v in (headers or {}).items():
        raw_headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))
    scope = {"type": "http", "headers": raw_headers, "client": (host, 12345)}
    return Request(scope)


@pytest.mark.asyncio
async def test_auth_dependency_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as e1:
        auth.get_token(None)
    assert e1.value.status_code == 401
    assert auth.get_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")) == "tok"

    monkeypatch.setattr(auth.session_manager, "get_session", AsyncMock(return_value=_session()))
    assert (await auth.get_current_session("tok")).username == "u1"

    monkeypatch.setattr(auth.session_manager, "get_session", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as e2:
        await auth.get_current_session("bad")
    assert e2.value.status_code == 401

    monkeypatch.setattr(auth.session_manager, "get_session", AsyncMock(return_value=_session()))
    got = await auth.get_session_from_token_or_query(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="h1"),
        token="q1",
    )
    assert got.username == "u1"
    got2 = await auth.get_session_from_token_or_query(credentials=None, token="q1")
    assert got2.username == "u1"
    with pytest.raises(HTTPException):
        await auth.get_session_from_token_or_query(credentials=None, token=None)

    assert auth.get_role_level("admin") > auth.get_role_level("user")
    assert auth.can_manage_user("admin", "user") is True
    assert auth.can_manage_user("user", "admin") is False

    assert (await auth.require_admin(_session("admin"))).role == "admin"
    with pytest.raises(HTTPException):
        await auth.require_admin(_session("user"))

    await auth.require_can_manage_target(_session("admin"), "user")
    with pytest.raises(HTTPException):
        await auth.require_can_manage_target(_session("user"), "user")

    assert auth.get_client_ip(_request({"x-forwarded-for": "1.2.3.4, 5.6.7.8"})) == "1.2.3.4"
    assert auth.get_client_ip(_request({"x-real-ip": "9.9.9.9"})) == "9.9.9.9"
    assert auth.get_client_ip(_request(host="8.8.8.8")) == "8.8.8.8"


@pytest.mark.asyncio
async def test_login_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    req = _request({"user-agent": "pytest-agent"})
    login_req = LoginRequest(username="u1", password="p1", device=DeviceInfo(device_type="desktop", browser="Chrome"))
    geo = SimpleNamespace(country="TW", city="Taipei")
    ua_device = SimpleNamespace(device_type=SimpleNamespace(value="desktop"), browser="Firefox", os="Linux")

    monkeypatch.setattr(auth, "resolve_ip_location", lambda _ip: geo)
    monkeypatch.setattr(auth, "parse_device_info", lambda _ua: ua_device)
    monkeypatch.setattr(auth, "record_login", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "log_message", AsyncMock(return_value=99))
    monkeypatch.setattr(auth, "emit_new_message", AsyncMock())
    monkeypatch.setattr(auth, "emit_unread_count", AsyncMock())
    monkeypatch.setattr(auth.session_manager, "create_session", AsyncMock(return_value="token-1"))
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="user"))
    monkeypatch.setattr(permissions_service, "get_user_app_permissions_sync", lambda _r, _u: {"knowledge-base": True})

    # 密碼認證成功
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1,
        "password_hash": "h",
        "is_active": True,
        "must_change_password": True,
        "preferences": {},
    }))
    monkeypatch.setattr(auth, "verify_password", lambda _pw, _h: True)
    monkeypatch.setattr(auth, "update_last_login", AsyncMock())
    ok = await auth.login(login_req, req)
    assert ok.success is True and ok.token == "token-1" and ok.must_change_password is True

    # 帳號停用
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1,
        "password_hash": "h",
        "is_active": False,
    }))
    disabled = await auth.login(login_req, req)
    assert disabled.success is False and "停用" in (disabled.error or "")

    # 密碼錯誤（失敗訊息路徑）
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 2,
        "password_hash": "h",
        "is_active": True,
    }))
    monkeypatch.setattr(auth, "verify_password", lambda _pw, _h: False)
    bad_pw = await auth.login(login_req, req)
    assert bad_pw.success is False

    # SMB 認證成功 + upsert_user
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "create_smb_service", lambda _u, _p: SimpleNamespace(test_auth=lambda: None))
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "upsert_user", AsyncMock(return_value=77))
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="admin"))
    smb_ok = await auth.login(login_req, req)
    assert smb_ok.success is True and smb_ok.role == "admin"

    # SMB 認證失敗
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(side_effect=SMBAuthError("bad")))
    smb_bad = await auth.login(login_req, req)
    assert smb_bad.success is False

    # SMB 連線錯誤
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(side_effect=SMBConnectionError("down")))
    with pytest.raises(HTTPException) as e1:
        await auth.login(login_req, req)
    assert e1.value.status_code == 503

    # NAS auth disabled + user 不存在
    monkeypatch.setattr(auth.settings, "enable_nas_auth", False)
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value=None))
    no_user = await auth.login(login_req, req)
    assert no_user.success is False and "不存在" in (no_user.error or "")

    # NAS auth disabled + user 存在但無密碼
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={"id": 3, "password_hash": None}))
    no_pwd = await auth.login(login_req, req)
    assert no_pwd.success is False and "帳號或密碼錯誤" in (no_pwd.error or "")

    # upsert_user 失敗
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "upsert_user", AsyncMock(side_effect=RuntimeError("db down")))
    with pytest.raises(HTTPException) as e2:
        await auth.login(login_req, req)
    assert e2.value.status_code == 500

    # 記錄流程失敗不影響回應
    monkeypatch.setattr(auth, "upsert_user", AsyncMock(return_value=88))
    monkeypatch.setattr(auth, "record_login", AsyncMock(side_effect=RuntimeError("ignore")))
    fallback_ok = await auth.login(login_req, req)
    assert fallback_ok.success is True


@pytest.mark.asyncio
async def test_logout_and_change_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.session_manager, "delete_session", AsyncMock(return_value=True))
    out = await auth.logout("tok")
    assert out.success is True

    # user_id=None 且 upsert 失敗
    monkeypatch.setattr(user_service, "upsert_user", AsyncMock(side_effect=RuntimeError("x")))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password=None, new_password="Abcdef123!"),
        session=_session("user", user_id=None),
    )
    assert resp.success is False

    # 已有密碼但未提供 current_password
    monkeypatch.setattr(user_service, "get_user_for_auth", AsyncMock(return_value={"password_hash": "h"}))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password=None, new_password="Abcdef123!"),
        session=_session("user", user_id=1),
    )
    assert resp.success is False and "目前密碼" in (resp.error or "")

    # current_password 錯誤
    monkeypatch.setattr(password_service, "verify_password", lambda _c, _h: False)
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password="bad", new_password="Abcdef123!"),
        session=_session("user", user_id=1),
    )
    assert resp.success is False and "錯誤" in (resp.error or "")

    # 新密碼強度不足
    monkeypatch.setattr(password_service, "verify_password", lambda _c, _h: True)
    monkeypatch.setattr(password_service, "validate_password_strength", lambda _n: (False, "weak"))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password="ok", new_password="weak"),
        session=_session("user", user_id=1),
    )
    assert resp.success is False and resp.error == "weak"

    # set_user_password 失敗
    monkeypatch.setattr(password_service, "validate_password_strength", lambda _n: (True, None))
    monkeypatch.setattr(password_service, "hash_password", lambda _n: "hashed")
    monkeypatch.setattr(user_service, "set_user_password", AsyncMock(return_value=False))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password="ok", new_password="Abcdef123!"),
        session=_session("user", user_id=1),
    )
    assert resp.success is False and "更新失敗" in (resp.error or "")

    # 成功（首次設定密碼）
    monkeypatch.setattr(user_service, "get_user_for_auth", AsyncMock(return_value={"password_hash": None}))
    monkeypatch.setattr(user_service, "set_user_password", AsyncMock(return_value=True))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password=None, new_password="Abcdef123!"),
        session=_session("user", user_id=1),
    )
    assert resp.success is True
