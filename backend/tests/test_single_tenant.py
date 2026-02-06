"""單一租戶架構測試

測試移除多租戶後的簡化行為：
1. 認證流程不需要 tenant_code
2. 角色系統只有 admin/user
3. Bot 設定使用 bot_settings 表
4. 路徑不包含 tenant 層級
"""
import pytest
from unittest.mock import AsyncMock, patch


# ============================================================
# 認證相關測試
# ============================================================

class TestSimplifiedAuth:
    """簡化後的認證流程"""

    def test_login_request_no_tenant_code(self):
        """登入請求不需要 tenant_code"""
        from ching_tech_os.models.auth import LoginRequest

        # 只需要 username 和 password
        request = LoginRequest(
            username="testuser",
            password="testpass"
        )

        assert request.username == "testuser"
        assert request.password == "testpass"

    def test_session_data_no_tenant_id(self):
        """SessionData 不包含 tenant_id 欄位"""
        from ching_tech_os.models.auth import SessionData
        from datetime import datetime, timedelta

        # 建立 session 時不需要 tenant_id
        session = SessionData(
            username="testuser",
            password="testpass",
            nas_host="nas.local",
            user_id=1,
            role="admin",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=8),
            app_permissions={}
        )

        # 檢查 tenant_id 欄位不存在
        assert not hasattr(session, 'tenant_id'), "SessionData should not have tenant_id field"


class TestSimplifiedRoles:
    """簡化後的角色系統"""

    def test_only_admin_and_user_roles(self):
        """只有 admin 和 user 兩種角色"""
        valid_roles = {'admin', 'user'}
        invalid_roles = {'platform_admin', 'tenant_admin'}

        for role in invalid_roles:
            assert role not in valid_roles, f"{role} should not be a valid role"


# ============================================================
# Bot 設定測試
# ============================================================

class TestBotSettings:
    """Bot 憑證設定（需要新建 bot_settings.py）"""

    def test_bot_settings_module_exists(self):
        """bot_settings 模組應存在且可正常匯入"""
        from ching_tech_os.services.bot_settings import (
            get_line_credentials,
            get_telegram_credentials,
            get_bot_credentials,
            update_bot_credentials,
            delete_bot_credentials,
            get_bot_credentials_status,
            SUPPORTED_PLATFORMS,
        )
        assert "line" in SUPPORTED_PLATFORMS
        assert "telegram" in SUPPORTED_PLATFORMS


# ============================================================
# 路徑管理測試
# ============================================================

class TestSimplifiedPaths:
    """簡化後的路徑結構"""

    def test_knowledge_path_no_tenant(self):
        """知識庫路徑不包含 tenant 層級"""
        from ching_tech_os.services.path_manager import path_manager

        knowledge_path = path_manager.knowledge_base_path

        # 路徑不應該包含 tenants 目錄
        assert 'tenants' not in knowledge_path, f"Path should not contain 'tenants': {knowledge_path}"

    def test_linebot_path_no_tenant(self):
        """Line Bot 路徑不包含 tenant 層級"""
        from ching_tech_os.services.path_manager import path_manager

        linebot_path = path_manager.linebot_base_path

        # 路徑不應該包含 tenants 目錄
        assert 'tenants' not in linebot_path, f"Path should not contain 'tenants': {linebot_path}"


# ============================================================
# 服務層測試 - 不包含 tenant_id
# ============================================================

class TestUserServiceNoTenantId:
    """使用者服務不需要 tenant_id"""

    @pytest.mark.asyncio
    async def test_upsert_user_no_tenant_id_param(self):
        """upsert_user 不需要 tenant_id 參數"""
        from ching_tech_os.services.user import upsert_user
        import inspect

        sig = inspect.signature(upsert_user)
        params = list(sig.parameters.keys())

        # tenant_id 不應該是必要參數
        assert 'tenant_id' not in params, f"upsert_user should not have tenant_id param: {params}"

    @pytest.mark.asyncio
    async def test_get_user_no_tenant_filter(self):
        """get_user_by_username 不需要 tenant_id 參數"""
        from ching_tech_os.services.user import get_user_by_username
        import inspect

        sig = inspect.signature(get_user_by_username)
        params = list(sig.parameters.keys())

        # tenant_id 不應該是必要參數
        assert 'tenant_id' not in params, f"get_user_by_username should not have tenant_id param: {params}"


class TestAiManagerNoTenantId:
    """AI 管理服務不需要 tenant_id"""

    @pytest.mark.asyncio
    async def test_get_agent_no_tenant_id(self):
        """取得 Agent 不需要 tenant_id"""
        from ching_tech_os.services.ai_manager import get_agent_by_name
        import inspect

        sig = inspect.signature(get_agent_by_name)
        params = list(sig.parameters.keys())

        assert 'tenant_id' not in params, f"get_agent_by_name should not have tenant_id param: {params}"


# ============================================================
# MCP 工具測試
# ============================================================

class TestMcpToolsNoTenantId:
    """MCP 工具不需要 ctos_tenant_id 參數"""

    def test_mcp_tools_signature(self):
        """檢查 MCP 工具函數簽名不包含 ctos_tenant_id"""
        from ching_tech_os.services.mcp_server import mcp
        import inspect

        # 取得所有工具
        tools = mcp._tool_manager._tools
        assert len(tools) > 0, "應有至少一個 MCP 工具"

        for tool_name, tool in tools.items():
            sig = inspect.signature(tool.fn)
            params = list(sig.parameters.keys())

            assert 'ctos_tenant_id' not in params, \
                f"Tool {tool_name} should not have ctos_tenant_id param"


# ============================================================
# 資料庫相關測試
# ============================================================

class TestDatabaseSchema:
    """資料庫結構測試"""

    @pytest.mark.asyncio
    async def test_bot_settings_table_exists(self):
        """bot_settings 表應該存在"""
        try:
            from ching_tech_os.database import get_connection

            async with get_connection() as conn:
                result = await conn.fetchrow("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'bot_settings'
                    )
                """)
                assert result['exists'], "bot_settings table should exist"
        except Exception:
            pytest.skip("Database not available or migration not run")

    @pytest.mark.asyncio
    async def test_tenants_table_not_exists(self):
        """tenants 表應該不存在"""
        try:
            from ching_tech_os.database import get_connection

            async with get_connection() as conn:
                result = await conn.fetchrow("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'tenants'
                    )
                """)
                assert not result['exists'], "tenants table should not exist"
        except Exception:
            pytest.skip("Database not available or migration not run")
