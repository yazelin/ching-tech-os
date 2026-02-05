"""認證流程整合測試（含租戶）

測試多租戶認證流程：
- 單租戶模式登入
- 多租戶模式登入（需提供 tenant_code）
- 租戶管理員角色識別
- Session 包含 tenant_id

注意：多租戶功能已移除，這些測試暫時跳過
"""

import pytest

pytestmark = pytest.mark.skip(reason="多租戶功能已移除，測試待刪除或重構")
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from ching_tech_os.api.auth import router, get_current_session
from ching_tech_os.models.auth import SessionData
from ching_tech_os.config import DEFAULT_TENANT_UUID


# 建立測試用 FastAPI 應用程式
def create_test_app():
    app = FastAPI()
    app.include_router(router)
    return app


# 模擬租戶資料
MOCK_TENANT = {
    "id": UUID("11111111-1111-1111-1111-111111111111"),
    "code": "test_tenant",
    "name": "測試租戶",
    "status": "active",
    "plan": "basic",
}

MOCK_DEFAULT_TENANT = {
    "id": UUID(DEFAULT_TENANT_UUID),
    "code": "default",
    "name": "預設租戶",
    "status": "active",
    "plan": "enterprise",
}

# 模擬使用者資料（密碼認證）
MOCK_USER_DATA = {
    "id": 1,
    "username": "testuser",
    "display_name": "Test User",
    "password_hash": "$2b$12$fakehash",
    "is_active": True,
    "must_change_password": False,
    "role": "user",
    "tenant_id": UUID(DEFAULT_TENANT_UUID),
}


def _login_patches():
    """共用的 login 函數 mock 組合"""
    return {
        "resolve_tenant_id": patch("ching_tech_os.api.auth.resolve_tenant_id", new_callable=AsyncMock),
        "get_user_for_auth": patch("ching_tech_os.api.auth.get_user_for_auth", new_callable=AsyncMock),
        "verify_password": patch("ching_tech_os.api.auth.verify_password"),
        "update_last_login": patch("ching_tech_os.api.auth.update_last_login", new_callable=AsyncMock),
        "get_user_role": patch("ching_tech_os.api.auth.get_user_role", new_callable=AsyncMock),
        "get_tenant_by_id": patch("ching_tech_os.api.auth.get_tenant_by_id", new_callable=AsyncMock),
        "record_login": patch("ching_tech_os.api.auth.record_login", new_callable=AsyncMock),
        "log_message": patch("ching_tech_os.api.auth.log_message", new_callable=AsyncMock),
        "emit_new_message": patch("ching_tech_os.api.auth.emit_new_message", new_callable=AsyncMock),
        "emit_unread_count": patch("ching_tech_os.api.auth.emit_unread_count", new_callable=AsyncMock),
        "resolve_ip_location": patch("ching_tech_os.api.auth.resolve_ip_location"),
        "parse_device_info": patch("ching_tech_os.api.auth.parse_device_info"),
        "get_user_app_permissions_sync": patch("ching_tech_os.services.permissions.get_user_app_permissions_sync"),
    }


# ============================================================
# 登入流程測試
# ============================================================

class TestLoginWithTenant:
    """登入流程測試（含租戶）"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()
        self.client = TestClient(self.app)

    def test_login_single_tenant_mode(self):
        """單租戶模式登入成功"""
        patches = _login_patches()
        mocks = {}
        with patches["resolve_tenant_id"] as m_resolve, \
             patches["get_user_for_auth"] as m_get_user, \
             patches["verify_password"] as m_verify, \
             patches["update_last_login"] as m_update, \
             patches["get_user_role"] as m_role, \
             patches["get_tenant_by_id"] as m_tenant, \
             patches["record_login"], patches["log_message"], \
             patches["emit_new_message"], patches["emit_unread_count"], \
             patches["resolve_ip_location"] as m_geo, \
             patches["parse_device_info"] as m_device, \
             patches["get_user_app_permissions_sync"] as m_perms:

            m_resolve.return_value = UUID(DEFAULT_TENANT_UUID)
            m_get_user.return_value = MOCK_USER_DATA
            m_verify.return_value = True
            m_role.return_value = "user"
            m_tenant.return_value = MOCK_DEFAULT_TENANT
            m_geo.return_value = None
            m_device.return_value = None
            m_perms.return_value = {}

            response = self.client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpass"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["token"] is not None
            assert data["username"] == "testuser"

    def test_login_multi_tenant_mode_with_code(self):
        """多租戶模式登入（提供 tenant_code）"""
        patches = _login_patches()
        with patches["resolve_tenant_id"] as m_resolve, \
             patches["get_user_for_auth"] as m_get_user, \
             patches["verify_password"] as m_verify, \
             patches["update_last_login"], \
             patches["get_user_role"] as m_role, \
             patches["get_tenant_by_id"] as m_tenant, \
             patches["record_login"], patches["log_message"], \
             patches["emit_new_message"], patches["emit_unread_count"], \
             patches["resolve_ip_location"] as m_geo, \
             patches["parse_device_info"] as m_device, \
             patches["get_user_app_permissions_sync"] as m_perms:

            m_resolve.return_value = MOCK_TENANT["id"]
            m_get_user.return_value = MOCK_USER_DATA
            m_verify.return_value = True
            m_role.return_value = "user"
            m_tenant.return_value = MOCK_TENANT
            m_geo.return_value = None
            m_device.return_value = None
            m_perms.return_value = {}

            response = self.client.post(
                "/api/auth/login",
                json={
                    "username": "testuser",
                    "password": "testpass",
                    "tenant_code": "test_tenant",
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["tenant"] is not None
            assert data["tenant"]["code"] == "test_tenant"

    def test_login_invalid_tenant_code(self):
        """無效的租戶代碼應登入失敗"""
        from ching_tech_os.services.tenant import TenantNotFoundError

        with patch("ching_tech_os.api.auth.resolve_tenant_id", new_callable=AsyncMock) as mock_resolve, \
             patch("ching_tech_os.api.auth.resolve_ip_location") as m_geo, \
             patch("ching_tech_os.api.auth.parse_device_info") as m_device:
            mock_resolve.side_effect = TenantNotFoundError("租戶不存在")
            m_geo.return_value = None
            m_device.return_value = None

            response = self.client.post(
                "/api/auth/login",
                json={
                    "username": "testuser",
                    "password": "testpass",
                    "tenant_code": "invalid_tenant",
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "租戶" in data["error"]

    def test_login_suspended_tenant(self):
        """停用的租戶應無法登入"""
        from ching_tech_os.services.tenant import TenantSuspendedError

        with patch("ching_tech_os.api.auth.resolve_tenant_id", new_callable=AsyncMock) as mock_resolve, \
             patch("ching_tech_os.api.auth.resolve_ip_location") as m_geo, \
             patch("ching_tech_os.api.auth.parse_device_info") as m_device:
            mock_resolve.side_effect = TenantSuspendedError("租戶已停用")
            m_geo.return_value = None
            m_device.return_value = None

            response = self.client.post(
                "/api/auth/login",
                json={
                    "username": "testuser",
                    "password": "testpass",
                    "tenant_code": "suspended_tenant",
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "停用" in data["error"]


# ============================================================
# 租戶管理員角色測試
# ============================================================

class TestTenantAdminRole:
    """租戶管理員角色識別測試"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()
        self.client = TestClient(self.app)

    def test_tenant_admin_role_in_session(self):
        """租戶管理員應在 session 中標記 role"""
        patches = _login_patches()
        with patches["resolve_tenant_id"] as m_resolve, \
             patches["get_user_for_auth"] as m_get_user, \
             patches["verify_password"] as m_verify, \
             patches["update_last_login"], \
             patches["get_user_role"] as m_role, \
             patches["get_tenant_by_id"] as m_tenant, \
             patches["record_login"], patches["log_message"], \
             patches["emit_new_message"], patches["emit_unread_count"], \
             patches["resolve_ip_location"] as m_geo, \
             patches["parse_device_info"] as m_device, \
             patches["get_user_app_permissions_sync"] as m_perms, \
             patch("ching_tech_os.api.auth.session_manager") as mock_session_mgr:

            m_resolve.return_value = MOCK_TENANT["id"]
            m_get_user.return_value = MOCK_USER_DATA
            m_verify.return_value = True
            m_role.return_value = "tenant_admin"
            m_tenant.return_value = MOCK_TENANT
            m_geo.return_value = None
            m_device.return_value = None
            m_perms.return_value = {}
            mock_session_mgr.create_session.return_value = "test_token"

            response = self.client.post(
                "/api/auth/login",
                json={"username": "admin_user", "password": "testpass"}
            )

            # 驗證 session 建立時傳入了 role="tenant_admin"
            mock_session_mgr.create_session.assert_called_once()
            call_kwargs = mock_session_mgr.create_session.call_args
            assert call_kwargs[1]["role"] == "tenant_admin"

    def test_normal_user_role(self):
        """一般使用者應標記 role=user"""
        patches = _login_patches()
        with patches["resolve_tenant_id"] as m_resolve, \
             patches["get_user_for_auth"] as m_get_user, \
             patches["verify_password"] as m_verify, \
             patches["update_last_login"], \
             patches["get_user_role"] as m_role, \
             patches["get_tenant_by_id"] as m_tenant, \
             patches["record_login"], patches["log_message"], \
             patches["emit_new_message"], patches["emit_unread_count"], \
             patches["resolve_ip_location"] as m_geo, \
             patches["parse_device_info"] as m_device, \
             patches["get_user_app_permissions_sync"] as m_perms, \
             patch("ching_tech_os.api.auth.session_manager") as mock_session_mgr:

            m_resolve.return_value = MOCK_TENANT["id"]
            m_get_user.return_value = MOCK_USER_DATA
            m_verify.return_value = True
            m_role.return_value = "user"
            m_tenant.return_value = MOCK_TENANT
            m_geo.return_value = None
            m_device.return_value = None
            m_perms.return_value = {}
            mock_session_mgr.create_session.return_value = "test_token"

            response = self.client.post(
                "/api/auth/login",
                json={"username": "normal_user", "password": "testpass"}
            )

            # 驗證 session 建立時傳入了 role="user"
            mock_session_mgr.create_session.assert_called_once()
            call_kwargs = mock_session_mgr.create_session.call_args
            assert call_kwargs[1]["role"] == "user"


# ============================================================
# Session 租戶驗證測試
# ============================================================

class TestSessionTenantValidation:
    """Session 租戶驗證測試"""

    def test_session_contains_tenant_id(self):
        """Session 應包含 tenant_id"""
        from ching_tech_os.services.session import session_manager

        with patch("ching_tech_os.services.session.settings") as mock_settings:
            mock_settings.session_ttl_hours = 8
            mock_settings.nas_host = "test-nas"
            mock_settings.multi_tenant_mode = True

            token = session_manager.create_session(
                username="testuser",
                password="testpass",
                user_id=1,
                tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
                role="user",
            )

            session = session_manager.get_session(token)
            assert session is not None
            assert session.tenant_id == UUID("11111111-1111-1111-1111-111111111111")
            assert session.role == "user"

            # 清理
            session_manager.delete_session(token)

    def test_session_tenant_admin_role(self):
        """租戶管理員的 session 應標記 role"""
        from ching_tech_os.services.session import session_manager

        with patch("ching_tech_os.services.session.settings") as mock_settings:
            mock_settings.session_ttl_hours = 8
            mock_settings.nas_host = "test-nas"
            mock_settings.multi_tenant_mode = True

            token = session_manager.create_session(
                username="admin",
                password="adminpass",
                user_id=1,
                tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
                role="tenant_admin",
            )

            session = session_manager.get_session(token)
            assert session is not None
            assert session.role == "tenant_admin"

            # 清理
            session_manager.delete_session(token)


# ============================================================
# get_current_session 依賴測試
# ============================================================

class TestGetCurrentSession:
    """get_current_session 依賴測試"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()

    def create_session_override(self, username: str, user_id: int, tenant_id: UUID, role: str = "user"):
        """建立 session 覆寫函數"""
        async def override():
            now = datetime.now()
            return SessionData(
                username=username,
                password="test-password",
                nas_host="test-nas",
                user_id=user_id,
                tenant_id=tenant_id,
                role=role,
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
        return override

    def test_session_with_tenant_id(self):
        """Session 應能正確傳遞 tenant_id"""
        tenant_id = UUID("11111111-1111-1111-1111-111111111111")

        # 新增一個測試端點來驗證 session
        @self.app.get("/test/session")
        async def test_session(session: SessionData = Depends(get_current_session)):
            return {
                "username": session.username,
                "user_id": session.user_id,
                "tenant_id": str(session.tenant_id),
                "role": session.role,
            }

        self.app.dependency_overrides[get_current_session] = self.create_session_override(
            "testuser", 1, tenant_id, "user"
        )

        client = TestClient(self.app)
        response = client.get("/test/session")

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == str(tenant_id)
        assert data["role"] == "user"

    def test_tenant_admin_session(self):
        """租戶管理員的 session 應包含 tenant_admin role"""
        tenant_id = UUID("11111111-1111-1111-1111-111111111111")

        @self.app.get("/test/admin-session")
        async def test_admin_session(session: SessionData = Depends(get_current_session)):
            return {
                "username": session.username,
                "role": session.role,
            }

        self.app.dependency_overrides[get_current_session] = self.create_session_override(
            "admin", 1, tenant_id, "tenant_admin"
        )

        client = TestClient(self.app)
        response = client.get("/test/admin-session")

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "tenant_admin"
