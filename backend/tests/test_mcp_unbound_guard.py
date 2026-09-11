"""未綁定 CTOS 帳號的 bot 使用者不得使用專案／往來／物料／NAS 檔案工具（issue #201）。

背景：`check_mcp_tool_permission` 對 `ctos_user_id is None`（LINE／Telegram 未綁定帳號）
和 `row is None`（ctos_user_id 存在但帳號已不在資料庫）兩段都用 `DEFAULT_APP_PERMISSIONS`
判斷——這三個 app 預設全部開放，等同任何陌生人都能查員工、聯絡人、庫存／採購資料。

本檔驗證：
- `APPS_REQUIRE_BOUND_USER` 涵蓋的 app，未綁定／帳號不存在一律拒絕，且對應 service 完全
  沒被呼叫（不是「查了但濾掉結果」）。
- 已綁定一般使用者、admin 行為不變（沿用既有 per-app 權限）。
- 知識庫（knowledge-base）未綁定維持放行——現狀已用條目層級控管，釘住不動。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import permissions as permissions_module
from ching_tech_os.services.mcp import server as mcp_server
from ching_tech_os.services.mcp import nas_tools

# hotfix 分支（從 0b982f1 切出）沒有 ERP／專案工具，對應測試跳過
try:
    from ching_tech_os.services.mcp import erp_tools, project_tools
except ImportError:  # pragma: no cover
    erp_tools = None
    project_tools = None
_needs_erp = pytest.mark.skipif(erp_tools is None, reason="hotfix 分支沒有 ERP／專案工具")


class _ConnCtx:
    """最小 async context manager，包一個假的 connection。"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


# 每個 app 至少一支代表工具，涵蓋 APPS_REQUIRE_BOUND_USER 全集合
_REQUIRED_APP_TOOLS = [
    *([("project-management", "get_project"), ("project-management", "list_tasks"),
       ("vendor-management", "find_party"), ("inventory-management", "get_stock")]
      if erp_tools is not None else []),
    ("file-manager", "search_nas_files"),
]


@pytest.fixture(autouse=True)
def _no_env_identity(monkeypatch: pytest.MonkeyPatch):
    """避免本機／CI 環境殘留 CTOS_USER_ID 污染未綁定測試。"""
    monkeypatch.delenv("CTOS_USER_ID", raising=False)


# ============================================================
# 1. APPS_REQUIRE_BOUND_USER 集合本身
# ============================================================


def test_apps_require_bound_user_set() -> None:
    """釘住第 3 點查證的結論：這四個 app 的工具會回人名／聯絡方式／內部檔案內容。"""
    assert permissions_module.APPS_REQUIRE_BOUND_USER == {
        "project-management",
        "vendor-management",
        "inventory-management",
        "file-manager",
    }


# ============================================================
# 2. check_mcp_tool_permission 直接測試（ctos_user_id is None）
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("required_app, tool_name", _REQUIRED_APP_TOOLS)
async def test_unbound_user_denied_for_required_apps(
    required_app: str, tool_name: str
) -> None:
    allowed, message = await mcp_server.check_mcp_tool_permission(tool_name, None)
    assert allowed is False
    assert "綁定" in message
    assert message == permissions_module.BOUND_USER_REQUIRED_MESSAGE


@pytest.mark.asyncio
async def test_unbound_user_denial_message_matches_real_bind_flow() -> None:
    """訊息要對應 bot 實際的綁定流程（登入 CTOS 系統→Bot 管理頁面→驗證碼），
    不是隨口寫的「輸入『綁定』」（沒有這個指令）。"""
    _, message = await mcp_server.check_mcp_tool_permission("search_nas_files", None)
    assert "驗證碼" in message
    assert "輸入「綁定」" not in message


@pytest.mark.asyncio
async def test_unbound_user_search_knowledge_still_allowed() -> None:
    """負向測試的對照：knowledge-base 維持現狀，不受這次修改影響（釘住現狀）。"""
    allowed, message = await mcp_server.check_mcp_tool_permission(
        "search_knowledge", None
    )
    assert allowed is True
    assert message == ""


# ============================================================
# 3. check_mcp_tool_permission 直接測試（row is None，帳號不存在）
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("required_app, tool_name", _REQUIRED_APP_TOOLS)
async def test_missing_user_row_denied_for_required_apps(
    monkeypatch: pytest.MonkeyPatch, required_app: str, tool_name: str
) -> None:
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value=None))
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))

    allowed, message = await mcp_server.check_mcp_tool_permission(tool_name, 999999)
    assert allowed is False
    assert message == permissions_module.BOUND_USER_REQUIRED_MESSAGE


# ============================================================
# 4. 已綁定使用者行為不變
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("required_app, tool_name", _REQUIRED_APP_TOOLS)
async def test_bound_normal_user_still_allowed(
    monkeypatch: pytest.MonkeyPatch, required_app: str, tool_name: str
) -> None:
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"role": "user", "preferences": {}})
    )
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))

    allowed, message = await mcp_server.check_mcp_tool_permission(tool_name, 1)
    assert allowed is True
    assert message == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("required_app, tool_name", _REQUIRED_APP_TOOLS)
async def test_bound_admin_still_allowed(
    monkeypatch: pytest.MonkeyPatch, required_app: str, tool_name: str
) -> None:
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"role": "admin", "preferences": {}})
    )
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))

    allowed, message = await mcp_server.check_mcp_tool_permission(tool_name, 1)
    assert allowed is True
    assert message == ""


# ============================================================
# 5. 端到端：未綁定打真實工具函式，service 完全沒被呼叫
# ============================================================


@pytest.mark.asyncio
@_needs_erp
async def test_get_project_unbound_denied_and_service_not_awaited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(project_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        project_tools,
        "_resolve_project",
        AsyncMock(side_effect=AssertionError("service 不該被呼叫")),
    )

    result = await project_tools.get_project(name="亦達自動化", ctos_user_id=None)

    assert result == {"ok": False, "error": permissions_module.BOUND_USER_REQUIRED_MESSAGE}
    project_tools._resolve_project.assert_not_awaited()


@pytest.mark.asyncio
@_needs_erp
async def test_list_tasks_unbound_denied_and_service_not_awaited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(project_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        project_tools,
        "_resolve_project",
        AsyncMock(side_effect=AssertionError("service 不該被呼叫")),
    )

    result = await project_tools.list_tasks(project="亦達自動化", ctos_user_id=None)

    assert result == {"ok": False, "error": permissions_module.BOUND_USER_REQUIRED_MESSAGE}
    project_tools._resolve_project.assert_not_awaited()


@pytest.mark.asyncio
@_needs_erp
async def test_find_party_unbound_denied_and_service_not_awaited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(erp_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        erp_tools.erp_core,
        "find_parties",
        AsyncMock(side_effect=AssertionError("service 不該被呼叫")),
    )

    result = await erp_tools.find_party(query="鴻佰", ctos_user_id=None)

    assert result == {"ok": False, "error": permissions_module.BOUND_USER_REQUIRED_MESSAGE}
    erp_tools.erp_core.find_parties.assert_not_awaited()


@pytest.mark.asyncio
@_needs_erp
async def test_get_stock_unbound_denied_and_service_not_awaited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(erp_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        erp_tools.inventory_service,
        "get_stock",
        AsyncMock(side_effect=AssertionError("service 不該被呼叫")),
    )

    result = await erp_tools.get_stock(ctos_user_id=None)

    assert result == {"ok": False, "error": permissions_module.BOUND_USER_REQUIRED_MESSAGE}
    erp_tools.inventory_service.get_stock.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_nas_files_unbound_denied_and_service_not_awaited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nas_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        nas_tools,
        "_get_user_shared_mounts",
        AsyncMock(side_effect=AssertionError("service 不該被呼叫")),
    )

    result = await nas_tools.search_nas_files(keywords="配電盤", ctos_user_id=None)

    assert result == f"❌ {permissions_module.BOUND_USER_REQUIRED_MESSAGE}"
    nas_tools._get_user_shared_mounts.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_knowledge_unbound_still_reaches_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """對照組：knowledge-base 未綁定要放行到 service（不是被擋在 guard）。"""
    from ching_tech_os.services.mcp import knowledge_tools

    monkeypatch.setattr(knowledge_tools, "ensure_db_connection", AsyncMock())

    class _FakeResult:
        items: list = []

    called = {}

    def _fake_search_knowledge(**kwargs):
        called["kwargs"] = kwargs
        return _FakeResult()

    import ching_tech_os.services.knowledge as kb_service

    monkeypatch.setattr(kb_service, "search_knowledge", _fake_search_knowledge)

    result = await knowledge_tools.search_knowledge(query="測試", ctos_user_id=None)

    assert called.get("kwargs", {}).get("public_only") is True
    assert "找不到" in result or "沒有公開" in result or "目前沒有" in result
