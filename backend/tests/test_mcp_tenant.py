"""MCP 工具租戶測試

測試 MCP Server 工具的租戶隔離功能：
- 租戶 ID 解析
- 專案工具租戶過濾
- 知識庫工具租戶過濾
- 庫存工具租戶過濾
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID

# 直接測試 _get_tenant_id 輔助函數
from ching_tech_os.services.mcp_server import _get_tenant_id, DEFAULT_TENANT_ID


# 測試用租戶 ID
TEST_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")


# ============================================================
# _get_tenant_id 輔助函數測試
# ============================================================

class TestGetTenantId:
    """_get_tenant_id 輔助函數測試"""

    def test_none_returns_default(self):
        """None 參數應返回預設租戶 ID"""
        result = _get_tenant_id(None)
        assert result == DEFAULT_TENANT_ID

    def test_valid_uuid_string(self):
        """有效的 UUID 字串應正確轉換"""
        uuid_str = "11111111-1111-1111-1111-111111111111"
        result = _get_tenant_id(uuid_str)
        assert result == UUID(uuid_str)

    def test_invalid_uuid_returns_default(self):
        """無效的 UUID 字串應返回預設租戶 ID"""
        result = _get_tenant_id("invalid-uuid")
        assert result == DEFAULT_TENANT_ID

    def test_empty_string_returns_default(self):
        """空字串應返回預設租戶 ID"""
        result = _get_tenant_id("")
        assert result == DEFAULT_TENANT_ID


# ============================================================
# 專案工具租戶過濾測試
# ============================================================

class TestProjectToolsTenantIsolation:
    """專案相關 MCP 工具租戶隔離測試"""

    @pytest.mark.asyncio
    async def test_query_project_uses_tenant_id(self):
        """query_project 應使用租戶 ID 過濾"""
        from ching_tech_os.services.mcp_server import query_project

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_conn.fetch.return_value = []

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            await query_project(keyword="test", ctos_tenant_id=str(TEST_TENANT_ID))

            # 驗證查詢使用了 tenant_id
            mock_conn.fetch.assert_called()
            call_args = str(mock_conn.fetch.call_args)
            assert "tenant_id" in call_args

    @pytest.mark.asyncio
    async def test_create_project_uses_tenant_id(self):
        """create_project 應將租戶 ID 傳遞給服務層"""
        from ching_tech_os.services.mcp_server import create_project

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.svc_create_project", new_callable=AsyncMock) as mock_create:

            mock_create.return_value = MagicMock(
                id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                name="測試專案",
            )

            await create_project(
                name="測試專案",
                ctos_tenant_id=str(TEST_TENANT_ID),
            )

            # 驗證傳遞了 tenant_id 參數
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert "tenant_id" in call_kwargs
            assert call_kwargs["tenant_id"] == str(TEST_TENANT_ID)


# ============================================================
# 知識庫工具租戶過濾測試
# ============================================================

class TestKnowledgeToolsTenantIsolation:
    """知識庫相關 MCP 工具租戶隔離測試"""

    @pytest.mark.asyncio
    async def test_search_knowledge_uses_tenant_id(self):
        """search_knowledge 應使用租戶 ID 過濾"""
        from ching_tech_os.services.mcp_server import search_knowledge

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.knowledge_search") as mock_search:

            mock_search.return_value = []

            await search_knowledge(
                query="test",
                ctos_tenant_id=str(TEST_TENANT_ID),
            )

            # 驗證呼叫了搜尋函數
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_note_uses_tenant_id(self):
        """add_note 應使用租戶 ID"""
        from ching_tech_os.services.mcp_server import add_note

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.knowledge_add") as mock_add:

            mock_add.return_value = "kb-001"

            await add_note(
                title="測試筆記",
                content="內容",
                ctos_tenant_id=str(TEST_TENANT_ID),
            )

            # 驗證呼叫了新增函數
            mock_add.assert_called_once()


# ============================================================
# 庫存工具租戶過濾測試
# ============================================================

class TestInventoryToolsTenantIsolation:
    """庫存相關 MCP 工具租戶隔離測試"""

    @pytest.mark.asyncio
    async def test_query_inventory_uses_tenant_id(self):
        """query_inventory 應使用租戶 ID 過濾"""
        from ching_tech_os.services.mcp_server import query_inventory

        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            await query_inventory(
                keyword="test",
                ctos_tenant_id=str(TEST_TENANT_ID),
            )

            # 驗證查詢使用了 tenant_id
            mock_conn.fetch.assert_called()
            call_args = str(mock_conn.fetch.call_args)
            assert "tenant_id" in call_args

    @pytest.mark.asyncio
    async def test_query_vendors_uses_tenant_id(self):
        """query_vendors 應使用租戶 ID 過濾"""
        from ching_tech_os.services.mcp_server import query_vendors

        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            await query_vendors(
                keyword="test",
                ctos_tenant_id=str(TEST_TENANT_ID),
            )

            # 驗證查詢
            mock_conn.fetch.assert_called()


# ============================================================
# 專案里程碑工具租戶過濾測試
# ============================================================

class TestMilestoneToolsTenantIsolation:
    """專案里程碑工具租戶隔離測試"""

    @pytest.mark.asyncio
    async def test_get_project_milestones_uses_tenant_id(self):
        """get_project_milestones 應使用租戶 ID 過濾"""
        from ching_tech_os.services.mcp_server import get_project_milestones

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.svc_list_milestones", new_callable=AsyncMock) as mock_list:

            mock_list.return_value = []

            await get_project_milestones(
                project_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                ctos_tenant_id=str(TEST_TENANT_ID),
            )

            # 驗證呼叫了服務函數
            mock_list.assert_called_once()


# ============================================================
# 專案成員工具租戶過濾測試
# ============================================================

class TestMemberToolsTenantIsolation:
    """專案成員工具租戶隔離測試"""

    @pytest.mark.asyncio
    async def test_get_project_members_uses_tenant_id(self):
        """get_project_members 應使用租戶 ID 過濾"""
        from ching_tech_os.services.mcp_server import get_project_members

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.svc_list_members", new_callable=AsyncMock) as mock_list:

            mock_list.return_value = []

            await get_project_members(
                project_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                ctos_tenant_id=str(TEST_TENANT_ID),
            )

            # 驗證呼叫了服務函數
            mock_list.assert_called_once()


# ============================================================
# 專案會議工具租戶過濾測試
# ============================================================

class TestMeetingToolsTenantIsolation:
    """專案會議工具租戶隔離測試"""

    @pytest.mark.asyncio
    async def test_get_project_meetings_uses_tenant_id(self):
        """get_project_meetings 應使用租戶 ID 過濾"""
        from ching_tech_os.services.mcp_server import get_project_meetings

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.svc_list_meetings", new_callable=AsyncMock) as mock_list:

            mock_list.return_value = []

            await get_project_meetings(
                project_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                ctos_tenant_id=str(TEST_TENANT_ID),
            )

            # 驗證呼叫了服務函數
            mock_list.assert_called_once()


# ============================================================
# 預設租戶隔離測試
# ============================================================

class TestDefaultTenantIsolation:
    """預設租戶隔離測試"""

    @pytest.mark.asyncio
    async def test_none_tenant_uses_default(self):
        """不提供租戶 ID 時應使用預設租戶"""
        from ching_tech_os.services.mcp_server import query_project

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_conn.fetch.return_value = []

        with patch("ching_tech_os.services.mcp_server.ensure_db_connection", new_callable=AsyncMock), \
             patch("ching_tech_os.services.mcp_server.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            # 不提供 ctos_tenant_id
            await query_project(keyword="test")

            # 驗證查詢仍然使用了 tenant_id（預設值）
            mock_conn.fetch.assert_called()
            call_args = str(mock_conn.fetch.call_args)
            assert "tenant_id" in call_args
