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


# PR 7（bot 切到往來與物料模組）之後，下面三條釘住的是「現況」不是「期望」：
# extends/erpnext/skills/{project-mgmt,inventory} 還在 submodule 裡，SkillManager
# 掃 extends/*/skills/* 時不看 ENABLED_MODULES，所以動態工具 prompt 仍然會出現
# mcp__erpnext__*。PR 8 移除那個 submodule 之後這三條會翻掉——用 xfail(strict=False)
# 標起來，翻掉時不會擋 CI，也不會有人誤以為 ERPNext 是期望行為。
_ERPNEXT_RESIDUE = pytest.mark.xfail(
    strict=False,
    reason="PR 8 移除 extends/erpnext 後翻掉；這裡釘的是殘留現況，不是期望行為",
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

    @_ERPNEXT_RESIDUE
    @pytest.mark.asyncio
    async def test_project_management_permission(self):
        """有專案管理權限：目前仍拿到 extends/erpnext 的 project-mgmt skill"""
        prompt = await generate_tools_prompt({"project-management": True})
        assert "mcp__erpnext__list_documents" in prompt
        assert "Project" in prompt

    @pytest.mark.asyncio
    async def test_knowledge_base_permission(self):
        """有知識庫權限"""
        prompt = await generate_tools_prompt({"knowledge-base": True})
        assert "search_knowledge" in prompt

    @_ERPNEXT_RESIDUE
    @pytest.mark.asyncio
    async def test_inventory_permission(self):
        """有庫存管理權限：目前仍拿到 extends/erpnext 的 inventory skill"""
        prompt = await generate_tools_prompt({"inventory-management": True})
        assert "mcp__erpnext__get_stock_balance" in prompt

    @pytest.mark.asyncio
    async def test_file_manager_permission(self):
        """有檔案管理權限"""
        prompt = await generate_tools_prompt({"file-manager": True})
        assert "search_nas_files" in prompt

    @_ERPNEXT_RESIDUE
    @pytest.mark.asyncio
    async def test_multiple_permissions(self):
        """多個權限同時啟用（其中兩條 assert 釘的是 ERPNext 殘留）"""
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
    async def test_erp_module_tools_present_for_inventory_permission(self):
        """PR 7 之後的期望行為：只有 inventory-management 也要拿到新模組的工具說明

        （skills/erp 的 requires_app 是 [vendor-management, inventory-management]）
        """
        prompt = await generate_tools_prompt({"inventory-management": True})
        for tool in ("find_item", "get_stock", "create_purchase_order", "find_party"):
            assert tool in prompt

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

    def test_knowledge_tips(self):
        """知識庫使用提示"""
        tips = generate_usage_tips_prompt({"knowledge-base": True})
        assert "search_knowledge" in tips

    def test_erpnext_permissions_no_tips(self):
        """ERPNext 模組化後，project-management / inventory-management 不再產生 tips"""
        tips_project = generate_usage_tips_prompt({"project-management": True})
        tips_inventory = generate_usage_tips_prompt({"inventory-management": True})
        assert tips_project == ""
        assert tips_inventory == ""


class TestAgentConstants:
    """測試 Agent 名稱常數"""

    def test_personal_agent_name(self):
        # 值由 BOT_DEFAULT_PERSONAL_AGENT 環境變數決定，預設 linebot-personal
        assert isinstance(AGENT_LINEBOT_PERSONAL, str)
        assert len(AGENT_LINEBOT_PERSONAL) > 0

    def test_group_agent_name(self):
        # 值由 BOT_DEFAULT_GROUP_AGENT 環境變數決定，預設 linebot-group
        assert isinstance(AGENT_LINEBOT_GROUP, str)
        assert len(AGENT_LINEBOT_GROUP) > 0
