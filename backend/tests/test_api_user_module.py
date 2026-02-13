"""api.user 模組測試。"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import ching_tech_os.api.user as user_api
from ching_tech_os.models.auth import SessionData
from ching_tech_os.models.user import UpdatePermissionsRequest, UpdateUserRequest


def _session(role: str = "user", user_id: int | None = 1) -> SessionData:
    now = datetime.now()
    return SessionData(
        username="tester",
        password="pw",
        nas_host="10.0.0.1",
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role=role,
        app_permissions={},
    )


def _user_row(**overrides):
    now = datetime.now()
    data = {
        "id": 1,
        "username": "tester",
        "display_name": "Tester",
        "created_at": now,
        "last_login_at": now,
        "password_hash": "hashed",
        "preferences": {},
        "role": "user",
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_list_users_simple(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        user_api,
        "get_all_users",
        AsyncMock(return_value=[{"id": 1, "username": "u1", "display_name": "U1"}]),
    )
    result = await user_api.list_users_simple(_session())
    assert len(result.users) == 1
    assert result.users[0].username == "u1"


@pytest.mark.asyncio
async def test_get_current_user_and_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(user_api, "get_user_by_username", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await user_api.get_current_user(_session())
    assert exc.value.status_code == 404

    monkeypatch.setattr(user_api, "get_user_by_username", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "_parse_preferences", lambda _p: {"apps": {}, "knowledge": {}})
    monkeypatch.setattr(
        user_api,
        "get_user_permissions_for_role",
        lambda _role, _prefs: {"apps": {"file-manager": True}, "knowledge": {"read": True}},
    )
    user = await user_api.get_current_user(_session(role="admin"))
    assert user.is_admin is True
    assert user.has_password is True


@pytest.mark.asyncio
async def test_update_current_user_paths(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(user_api, "_parse_preferences", lambda _p: {"apps": {}, "knowledge": {}})
    monkeypatch.setattr(
        user_api,
        "get_user_permissions_for_role",
        lambda _role, _prefs: {"apps": {}, "knowledge": {}},
    )

    monkeypatch.setattr(user_api, "update_user_display_name", AsyncMock(return_value=_user_row(display_name="新名稱")))
    updated = await user_api.update_current_user(UpdateUserRequest(display_name="新名稱"), _session())
    assert updated.display_name == "新名稱"

    monkeypatch.setattr(user_api, "get_user_by_username", AsyncMock(return_value=_user_row(display_name="舊名稱")))
    same = await user_api.update_current_user(UpdateUserRequest(display_name=None), _session())
    assert same.display_name == "舊名稱"

    monkeypatch.setattr(user_api, "get_user_by_username", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await user_api.update_current_user(UpdateUserRequest(display_name=None), _session())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_preferences_endpoints(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(HTTPException) as exc1:
        await user_api.get_preferences(_session(user_id=None))
    assert exc1.value.status_code == 400

    monkeypatch.setattr(user_api, "get_user_preferences", AsyncMock(return_value={"theme": "light"}))
    prefs = await user_api.get_preferences(_session(user_id=2))
    assert prefs.theme == "light"

    with pytest.raises(HTTPException) as exc2:
        await user_api.update_preferences(user_api.PreferencesUpdateRequest(theme="dark"), _session(user_id=None))
    assert exc2.value.status_code == 400

    with pytest.raises(HTTPException) as exc3:
        await user_api.update_preferences(user_api.PreferencesUpdateRequest(theme="blue"), _session(user_id=1))
    assert exc3.value.status_code == 400

    with pytest.raises(HTTPException) as exc4:
        await user_api.update_preferences(user_api.PreferencesUpdateRequest(theme=None), _session(user_id=1))
    assert exc4.value.status_code == 400

    monkeypatch.setattr(user_api, "update_user_preferences", AsyncMock(return_value={"theme": "light"}))
    resp = await user_api.update_preferences(user_api.PreferencesUpdateRequest(theme="light"), _session(user_id=1))
    assert resp.success is True
    assert resp.preferences.theme == "light"


@pytest.mark.asyncio
async def test_update_user_permissions_api_with_knowledge(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value={"role": "user"}))
    monkeypatch.setattr(user_api, "update_user_permissions", AsyncMock(return_value={"apps": {}, "knowledge": {"read": True}}))
    monkeypatch.setattr(
        user_api,
        "get_user_permissions_for_role",
        lambda _role, _prefs: {"apps": {}, "knowledge": {"read": True}},
    )

    response = await user_api.update_user_permissions_api(
        user_id=2,
        request=UpdatePermissionsRequest(knowledge={"read": True}),
        session=_session(role="admin", user_id=1),
    )
    assert response.success is True
    assert response.permissions.knowledge["read"] is True
