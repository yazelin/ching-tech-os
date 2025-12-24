"""管理員 API 權限檢查測試

測試：
- 非管理員無法存取 /api/admin/* 端點
- 管理員可以正常存取
- 權限更新功能
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api.user import router, admin_router
from ching_tech_os.api.auth import get_current_session
from ching_tech_os.models.auth import SessionData


# 建立測試用 FastAPI 應用程式
def create_test_app():
    app = FastAPI()
    app.include_router(router)
    app.include_router(admin_router)
    return app


def create_session_override(username: str, user_id: int = 1):
    """建立 session 覆寫函數（共用）"""
    async def override():
        now = datetime.now()
        return SessionData(
            username=username,
            password="test-password",
            nas_host="test-nas",
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
    return override


# 模擬使用者資料
MOCK_ADMIN_USER = {
    "id": 1,
    "username": "admin",
    "display_name": "管理員",
    "created_at": "2024-01-01T00:00:00",
    "last_login_at": "2024-01-01T00:00:00",
    "preferences": None,
}

MOCK_NORMAL_USER = {
    "id": 2,
    "username": "user1",
    "display_name": "一般使用者",
    "created_at": "2024-01-01T00:00:00",
    "last_login_at": "2024-01-01T00:00:00",
    "preferences": None,
}

MOCK_USER_WITH_PERMS = {
    "id": 3,
    "username": "user2",
    "display_name": "有權限使用者",
    "created_at": "2024-01-01T00:00:00",
    "last_login_at": "2024-01-01T00:00:00",
    "preferences": {
        "permissions": {
            "apps": {"terminal": True},
            "knowledge": {"global_write": True},
        }
    },
}


# ============================================================
# 管理員權限檢查測試
# ============================================================

class TestAdminAccessControl:
    """管理員存取控制測試"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()

    def test_admin_can_access_users_list(self):
        """管理員可以存取使用者列表"""
        with patch("ching_tech_os.api.user.is_admin", return_value=True), \
             patch("ching_tech_os.api.user.get_all_users", new_callable=AsyncMock) as mock_get_all:
            mock_get_all.return_value = [MOCK_ADMIN_USER, MOCK_NORMAL_USER]

            self.app.dependency_overrides[get_current_session] = create_session_override("admin")
            client = TestClient(self.app)

            response = client.get("/api/admin/users")
            assert response.status_code == 200
            data = response.json()
            assert "users" in data
            assert len(data["users"]) == 2

    def test_non_admin_cannot_access_users_list(self):
        """非管理員無法存取使用者列表"""
        with patch("ching_tech_os.api.user.is_admin", return_value=False):
            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.get("/api/admin/users")
            assert response.status_code == 403
            assert "需要管理員權限" in response.json()["detail"]

    def test_admin_can_access_default_permissions(self):
        """管理員可以存取預設權限設定"""
        with patch("ching_tech_os.api.user.is_admin", return_value=True):
            self.app.dependency_overrides[get_current_session] = create_session_override("admin")
            client = TestClient(self.app)

            response = client.get("/api/admin/default-permissions")
            assert response.status_code == 200
            data = response.json()
            assert "apps" in data
            assert "knowledge" in data
            assert "app_names" in data

    def test_non_admin_cannot_access_default_permissions(self):
        """非管理員無法存取預設權限設定"""
        with patch("ching_tech_os.api.user.is_admin", return_value=False):
            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.get("/api/admin/default-permissions")
            assert response.status_code == 403


# ============================================================
# 權限更新測試
# ============================================================

class TestPermissionsUpdate:
    """權限更新功能測試"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()

    def test_admin_can_update_user_permissions(self):
        """管理員可以更新使用者權限"""
        with patch("ching_tech_os.api.user.is_admin") as mock_is_admin, \
             patch("ching_tech_os.api.user.get_user_by_id", new_callable=AsyncMock) as mock_get_user, \
             patch("ching_tech_os.api.user.update_user_permissions", new_callable=AsyncMock) as mock_update:

            # admin 檢查時返回 True，目標使用者檢查時返回 False
            mock_is_admin.side_effect = lambda username: username == "admin"
            mock_get_user.return_value = MOCK_NORMAL_USER
            mock_update.return_value = {"permissions": {"apps": {"terminal": True}}}

            self.app.dependency_overrides[get_current_session] = create_session_override("admin")
            client = TestClient(self.app)

            response = client.patch(
                "/api/admin/users/2/permissions",
                json={"apps": {"terminal": True}}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_non_admin_cannot_update_permissions(self):
        """非管理員無法更新權限"""
        with patch("ching_tech_os.api.user.is_admin", return_value=False):
            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.patch(
                "/api/admin/users/3/permissions",
                json={"apps": {"terminal": True}}
            )
            assert response.status_code == 403

    def test_cannot_update_admin_permissions(self):
        """無法修改管理員的權限"""
        with patch("ching_tech_os.api.user.is_admin") as mock_is_admin, \
             patch("ching_tech_os.api.user.get_user_by_id", new_callable=AsyncMock) as mock_get_user:

            # 當前使用者是 admin，目標使用者也是 admin
            mock_is_admin.return_value = True
            mock_get_user.return_value = MOCK_ADMIN_USER

            self.app.dependency_overrides[get_current_session] = create_session_override("admin")
            client = TestClient(self.app)

            response = client.patch(
                "/api/admin/users/1/permissions",
                json={"apps": {"terminal": True}}
            )
            assert response.status_code == 400
            assert "無法修改管理員的權限" in response.json()["detail"]

    def test_update_nonexistent_user(self):
        """更新不存在的使用者應返回 404"""
        with patch("ching_tech_os.api.user.is_admin", return_value=True), \
             patch("ching_tech_os.api.user.get_user_by_id", new_callable=AsyncMock) as mock_get_user:

            mock_get_user.return_value = None

            self.app.dependency_overrides[get_current_session] = create_session_override("admin")
            client = TestClient(self.app)

            response = client.patch(
                "/api/admin/users/999/permissions",
                json={"apps": {"terminal": True}}
            )
            assert response.status_code == 404
            assert "使用者不存在" in response.json()["detail"]

    def test_update_empty_permissions(self):
        """更新空的權限應返回 400"""
        with patch("ching_tech_os.api.user.is_admin") as mock_is_admin, \
             patch("ching_tech_os.api.user.get_user_by_id", new_callable=AsyncMock) as mock_get_user:

            mock_is_admin.side_effect = lambda username: username == "admin"
            mock_get_user.return_value = MOCK_NORMAL_USER

            self.app.dependency_overrides[get_current_session] = create_session_override("admin")
            client = TestClient(self.app)

            response = client.patch(
                "/api/admin/users/2/permissions",
                json={}
            )
            assert response.status_code == 400
            assert "未提供任何權限更新" in response.json()["detail"]


# ============================================================
# 使用者 API 測試
# ============================================================

class TestUserApi:
    """使用者 API 測試"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()

    def test_get_current_user_returns_permissions(self):
        """取得目前使用者應包含權限資訊"""
        with patch("ching_tech_os.api.user.get_user_by_username", new_callable=AsyncMock) as mock_get, \
             patch("ching_tech_os.api.user.is_admin", return_value=False):

            mock_get.return_value = MOCK_NORMAL_USER

            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.get("/api/user/me")
            assert response.status_code == 200
            data = response.json()
            assert "is_admin" in data
            assert "permissions" in data
            assert data["is_admin"] is False

    def test_admin_user_has_full_permissions(self):
        """管理員應有完整權限"""
        with patch("ching_tech_os.api.user.get_user_by_username", new_callable=AsyncMock) as mock_get, \
             patch("ching_tech_os.api.user.is_admin", return_value=True), \
             patch("ching_tech_os.services.permissions.is_admin", return_value=True):

            mock_get.return_value = MOCK_ADMIN_USER

            self.app.dependency_overrides[get_current_session] = create_session_override("admin")
            client = TestClient(self.app)

            response = client.get("/api/user/me")
            assert response.status_code == 200
            data = response.json()
            assert data["is_admin"] is True
            # 管理員應有所有應用程式權限
            assert data["permissions"]["apps"]["terminal"] is True
            assert data["permissions"]["apps"]["code-editor"] is True
