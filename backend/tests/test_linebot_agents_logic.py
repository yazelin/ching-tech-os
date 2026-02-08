"""測試 LineBot Agent 管理邏輯

測試對象：linebot_agents.py 中的純函式
- generate_tools_prompt: 根據權限生成工具 prompt
- generate_usage_tips_prompt: 根據權限生成使用說明

用法：
    cd backend
    uv run pytest tests/test_linebot_agents_logic.py -v

"""

import pytest

from ching_tech_os.services.linebot_agents import (
    generate_tools_prompt,
    generate_usage_tips_prompt,
    AGENT_LINEBOT_PERSONAL,
    AGENT_LINEBOT_GROUP,
)


class TestGenerateToolsPrompt:
    """測試根據權限動態生成工具 prompt"""

    @pytest.mark.asyncio
    async def test_no_permissions(self):
        """無任何權限時只有基礎工具"""
        prompt = await generate_tools_prompt({})
        # 應該包含基礎工具
        assert len(prompt) > 0
        # 不應包含專案管理工具
        assert "query_project" not in prompt

    @pytest.mark.asyncio
    async def test_project_management_permission(self):
        """有專案管理權限（已遷移至 ERPNext）"""
        prompt = await generate_tools_prompt({"project-management": True})
        assert "mcp__erpnext__list_documents" in prompt
        assert "Project" in prompt

    @pytest.mark.asyncio
    async def test_knowledge_base_permission(self):
        """有知識庫權限"""
        prompt = await generate_tools_prompt({"knowledge-base": True})
        assert "search_knowledge" in prompt

    @pytest.mark.asyncio
    async def test_inventory_permission(self):
        """有庫存管理權限（已遷移至 ERPNext）"""
        prompt = await generate_tools_prompt({"inventory-management": True})
        assert "mcp__erpnext__get_stock_balance" in prompt

    @pytest.mark.asyncio
    async def test_file_manager_permission(self):
        """有檔案管理權限"""
        prompt = await generate_tools_prompt({"file-manager": True})
        assert "search_nas_files" in prompt

    @pytest.mark.asyncio
    async def test_multiple_permissions(self):
        """多個權限同時啟用"""
        perms = {
            "project-management": True,
            "knowledge-base": True,
            "inventory-management": True,
        }
        prompt = await generate_tools_prompt(perms)
        assert "mcp__erpnext__list_documents" in prompt
        assert "search_knowledge" in prompt
        assert "mcp__erpnext__get_stock_balance" in prompt

    @pytest.mark.asyncio
    async def test_disabled_permission(self):
        """權限設為 False"""
        prompt = await generate_tools_prompt({"project-management": False})
        assert "query_project" not in prompt


class TestGenerateUsageTipsPrompt:
    """測試使用說明 prompt 生成"""

    def test_no_permissions(self):
        """無權限時無提示"""
        tips = generate_usage_tips_prompt({})
        assert tips == ""

    def test_project_tips(self):
        """專案管理使用提示（已遷移至 ERPNext）"""
        tips = generate_usage_tips_prompt({"project-management": True})
        assert "mcp__erpnext__list_documents" in tips

    def test_knowledge_tips(self):
        """知識庫使用提示"""
        tips = generate_usage_tips_prompt({"knowledge-base": True})
        assert "search_knowledge" in tips

    def test_inventory_tips(self):
        """庫存管理使用提示（已遷移至 ERPNext）"""
        tips = generate_usage_tips_prompt({"inventory-management": True})
        assert "mcp__erpnext__get_stock_balance" in tips


class TestAgentConstants:
    """測試 Agent 名稱常數"""

    def test_personal_agent_name(self):
        assert AGENT_LINEBOT_PERSONAL == "linebot-personal"

    def test_group_agent_name(self):
        assert AGENT_LINEBOT_GROUP == "linebot-group"
