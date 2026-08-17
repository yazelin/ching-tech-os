"""使用者管理 API 路由測試（admin_router）。

使用 httpx AsyncClient + ASGI transport 測試 api/user.py 的管理員端點，
以 dependency_overrides 覆寫 require_admin，並以 AsyncMock 隔離 service 層。
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import ching_tech_os.api.user as user_api
from ching_tech_os.models.auth import SessionData


# ── 共用 fixtures ─────────────────────────────────────────────

ADMIN_USER_ID = 1
TARGET_USER_ID = 2


def _admin_session(user_id: int = ADMIN_USER_ID) -> SessionData:
    """回傳 mock 管理員 session"""
    now = datetime.now(timezone.utc)
    return SessionData(
        username="admin",
        password="xxx",
        nas_host="localhost",
        user_id=user_id,
        created_at=now,
        expires_at=now,
        role="admin",
    )


def _user_row(**overrides) -> dict:
    """建立模擬的使用者資料列"""
    now = datetime.now(timezone.utc)
    data = {
        "id": TARGET_USER_ID,
        "username": "target",
        "display_name": "Target",
        "created_at": now,
        "last_login_at": now,
        "password_hash": "hashed",
        "preferences": {},
        "role": "user",
        "is_active": True,
    }
    data.update(overrides)
    return data


@pytest.fixture
def app_admin() -> FastAPI:
    """建立使用管理員 session 的測試 app"""
    app = FastAPI()
    app.include_router(user_api.admin_router)
    app.dependency_overrides[user_api.require_admin] = lambda: _admin_session()
    return app


async def _request(app: FastAPI, method: str, url: str, **kwargs):
    """以 ASGI transport 發送請求"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


# ============================================================
# PATCH /api/admin/users/{user_id}/permissions
# ============================================================


@pytest.mark.asyncio
async def test_update_permissions_self_forbidden(app_admin: FastAPI) -> None:
    """不能修改自己的權限 → 403"""
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{ADMIN_USER_ID}/permissions",
        json={"apps": {"file-manager": True}},
    )
    assert resp.status_code == 403
    assert "自己" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_permissions_target_not_found(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """目標使用者不存在 → 404"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=None))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}/permissions",
        json={"apps": {"file-manager": True}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_permissions_empty_update(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """未提供任何權限更新 → 400"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}/permissions",
        json={},
    )
    assert resp.status_code == 400
    assert "未提供" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_permissions_success(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """更新 apps 權限成功"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(
        user_api,
        "update_user_permissions",
        AsyncMock(return_value={"apps": {"file-manager": True}, "knowledge": {}}),
    )
    monkeypatch.setattr(
        user_api,
        "get_user_permissions_for_role",
        lambda _role, _prefs: {"apps": {"file-manager": True}, "knowledge": {}},
    )
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}/permissions",
        json={"apps": {"file-manager": True}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["permissions"]["apps"]["file-manager"] is True


# ============================================================
# GET /api/admin/default-permissions
# ============================================================


@pytest.mark.asyncio
async def test_get_default_permissions(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """取得預設權限設定"""
    monkeypatch.setattr(
        user_api,
        "get_default_permissions",
        lambda: {"apps": {"file-manager": True}, "knowledge": {"read": True}},
    )
    monkeypatch.setattr(
        user_api,
        "get_app_display_names",
        lambda: {"file-manager": "檔案管理"},
    )
    resp = await _request(app_admin, "GET", "/api/admin/default-permissions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["apps"]["file-manager"] is True
    assert data["app_names"]["file-manager"] == "檔案管理"


# ============================================================
# POST /api/admin/users（建立使用者）
# ============================================================


@pytest.mark.asyncio
async def test_create_user_invalid_role(app_admin: FastAPI) -> None:
    """角色不合法 → 400"""
    resp = await _request(
        app_admin,
        "POST",
        "/api/admin/users",
        json={"username": "newuser", "password": "Passw0rd!", "role": "superuser"},
    )
    assert resp.status_code == 400
    assert "角色" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_user_weak_password(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """密碼強度不足 → 400"""
    monkeypatch.setattr(
        user_api, "validate_password_strength", lambda _pw: (False, "密碼強度不足")
    )
    resp = await _request(
        app_admin,
        "POST",
        "/api/admin/users",
        json={"username": "newuser", "password": "weakpass", "role": "user"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "密碼強度不足"


@pytest.mark.asyncio
async def test_create_user_duplicate(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """service 層拋出 ValueError（如帳號重複）→ 400"""
    monkeypatch.setattr(user_api, "validate_password_strength", lambda _pw: (True, None))
    monkeypatch.setattr(user_api, "hash_password", lambda _pw: "hashed")
    monkeypatch.setattr(
        user_api, "create_user", AsyncMock(side_effect=ValueError("使用者名稱已存在"))
    )
    resp = await _request(
        app_admin,
        "POST",
        "/api/admin/users",
        json={"username": "dupuser", "password": "Passw0rd!", "role": "user"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "使用者名稱已存在"


@pytest.mark.asyncio
async def test_create_user_success(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """建立使用者成功"""
    monkeypatch.setattr(user_api, "validate_password_strength", lambda _pw: (True, None))
    monkeypatch.setattr(user_api, "hash_password", lambda _pw: "hashed")
    create_mock = AsyncMock(return_value=99)
    monkeypatch.setattr(user_api, "create_user", create_mock)
    resp = await _request(
        app_admin,
        "POST",
        "/api/admin/users",
        json={
            "username": "newuser",
            "password": "Passw0rd!",
            "display_name": "新使用者",
            "role": "admin",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["id"] == 99
    assert data["username"] == "newuser"
    assert data["role"] == "admin"
    # 確認強制下次登入變更密碼
    assert create_mock.await_args.kwargs["must_change_password"] is True


# ============================================================
# PATCH /api/admin/users/{user_id}（編輯使用者資訊）
# ============================================================


@pytest.mark.asyncio
async def test_update_user_info_not_found(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """目標使用者不存在 → 404"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=None))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}",
        json={"display_name": "新名稱"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_user_info_self_demote(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """管理員不能降級自己的角色 → 400"""
    monkeypatch.setattr(
        user_api, "get_user_by_id", AsyncMock(return_value=_user_row(id=ADMIN_USER_ID))
    )
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{ADMIN_USER_ID}",
        json={"role": "user"},
    )
    assert resp.status_code == 400
    assert "降級" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_user_info_invalid_role(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """角色不合法 → 400"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}",
        json={"role": "superuser"},
    )
    assert resp.status_code == 400
    assert "角色" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_user_info_failure(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """service 層更新失敗 → 500"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "update_user_info", AsyncMock(return_value=None))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}",
        json={"display_name": "新名稱"},
    )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_user_info_success(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """編輯使用者資訊成功"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(
        user_api, "update_user_info", AsyncMock(return_value=_user_row(display_name="新名稱"))
    )
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}",
        json={"display_name": "新名稱", "email": "a@b.c", "role": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ============================================================
# POST /api/admin/users/{user_id}/reset-password
# ============================================================


@pytest.mark.asyncio
async def test_reset_password_not_found(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """目標使用者不存在 → 404"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=None))
    resp = await _request(
        app_admin,
        "POST",
        f"/api/admin/users/{TARGET_USER_ID}/reset-password",
        json={"new_password": "Passw0rd!"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reset_password_weak(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """密碼強度不足 → 400"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(
        user_api, "validate_password_strength", lambda _pw: (False, "密碼強度不足")
    )
    resp = await _request(
        app_admin,
        "POST",
        f"/api/admin/users/{TARGET_USER_ID}/reset-password",
        json={"new_password": "weakpass"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "密碼強度不足"


@pytest.mark.asyncio
async def test_reset_password_failure(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """service 層重設失敗 → 500"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "validate_password_strength", lambda _pw: (True, None))
    monkeypatch.setattr(user_api, "hash_password", lambda _pw: "hashed")
    # reset_user_password 是端點內延遲 import，需 patch service 模組
    monkeypatch.setattr(
        "ching_tech_os.services.user.reset_user_password", AsyncMock(return_value=False)
    )
    resp = await _request(
        app_admin,
        "POST",
        f"/api/admin/users/{TARGET_USER_ID}/reset-password",
        json={"new_password": "Passw0rd!"},
    )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_reset_password_success(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """重設密碼成功"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "validate_password_strength", lambda _pw: (True, None))
    monkeypatch.setattr(user_api, "hash_password", lambda _pw: "hashed")
    reset_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("ching_tech_os.services.user.reset_user_password", reset_mock)
    resp = await _request(
        app_admin,
        "POST",
        f"/api/admin/users/{TARGET_USER_ID}/reset-password",
        json={"new_password": "Passw0rd!"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # 確認強制下次登入變更密碼
    assert reset_mock.await_args.kwargs["must_change"] is True


# ============================================================
# PATCH /api/admin/users/{user_id}/status（停用/啟用）
# ============================================================


@pytest.mark.asyncio
async def test_update_status_self_deactivate(app_admin: FastAPI) -> None:
    """管理員不能停用自己 → 400"""
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{ADMIN_USER_ID}/status",
        json={"is_active": False},
    )
    assert resp.status_code == 400
    assert "自己" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_status_not_found(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """目標使用者不存在 → 404"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=None))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}/status",
        json={"is_active": False},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_status_activate_success(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """啟用帳號成功"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "activate_user", AsyncMock(return_value=True))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}/status",
        json={"is_active": True},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "帳號已啟用"


@pytest.mark.asyncio
async def test_update_status_deactivate_success(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """停用帳號成功"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "deactivate_user", AsyncMock(return_value=True))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}/status",
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "帳號已停用"


@pytest.mark.asyncio
async def test_update_status_failure(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """service 層操作失敗 → 500"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "activate_user", AsyncMock(return_value=False))
    resp = await _request(
        app_admin,
        "PATCH",
        f"/api/admin/users/{TARGET_USER_ID}/status",
        json={"is_active": True},
    )
    assert resp.status_code == 500


# ============================================================
# POST /api/admin/users/{user_id}/clear-password
# ============================================================


@pytest.mark.asyncio
async def test_clear_password_self(app_admin: FastAPI) -> None:
    """管理員不能清除自己的密碼 → 400"""
    resp = await _request(
        app_admin, "POST", f"/api/admin/users/{ADMIN_USER_ID}/clear-password"
    )
    assert resp.status_code == 400
    assert "自己" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_clear_password_nas_auth_disabled(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NAS 認證未啟用 → 400"""
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "enable_nas_auth", False)
    resp = await _request(
        app_admin, "POST", f"/api/admin/users/{TARGET_USER_ID}/clear-password"
    )
    assert resp.status_code == 400
    assert "NAS" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_clear_password_not_found(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """目標使用者不存在 → 404"""
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "enable_nas_auth", True)
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=None))
    resp = await _request(
        app_admin, "POST", f"/api/admin/users/{TARGET_USER_ID}/clear-password"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_clear_password_failure(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """service 層清除失敗 → 500"""
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "enable_nas_auth", True)
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "clear_user_password", AsyncMock(return_value=False))
    resp = await _request(
        app_admin, "POST", f"/api/admin/users/{TARGET_USER_ID}/clear-password"
    )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_clear_password_success(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """清除密碼成功，恢復 NAS 認證"""
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "enable_nas_auth", True)
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "clear_user_password", AsyncMock(return_value=True))
    resp = await _request(
        app_admin, "POST", f"/api/admin/users/{TARGET_USER_ID}/clear-password"
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ============================================================
# DELETE /api/admin/users/{user_id}
# ============================================================


@pytest.mark.asyncio
async def test_delete_user_self(app_admin: FastAPI) -> None:
    """管理員不能刪除自己 → 400"""
    resp = await _request(app_admin, "DELETE", f"/api/admin/users/{ADMIN_USER_ID}")
    assert resp.status_code == 400
    assert "自己" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_user_not_found(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """目標使用者不存在 → 404"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=None))
    resp = await _request(app_admin, "DELETE", f"/api/admin/users/{TARGET_USER_ID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_failure(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """service 層刪除失敗 → 500"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "delete_user", AsyncMock(return_value=False))
    resp = await _request(app_admin, "DELETE", f"/api/admin/users/{TARGET_USER_ID}")
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_delete_user_success(
    app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """刪除使用者成功"""
    monkeypatch.setattr(user_api, "get_user_by_id", AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(user_api, "delete_user", AsyncMock(return_value=True))
    resp = await _request(app_admin, "DELETE", f"/api/admin/users/{TARGET_USER_ID}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
