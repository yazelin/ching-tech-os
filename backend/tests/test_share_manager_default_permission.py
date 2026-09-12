"""issue #217：`share-manager` 預設關閉，且 REST 建立分享連結端點要真的擋。

背景：#205 讓分享連結走與 `get_knowledge_item` 相同的 read 判斷，但
`check_knowledge_permission_async(action="read")` 對 scope=global 一律放行、
scope=project 不看成員；加上 `share-manager` 當時預設開放，等於「內部讀得到」
＝「可以發到網路上」。這次的最小修法：

1. `DEFAULT_APP_PERMISSIONS["share-manager"]` 改 False，管理員逐人開放。
2. REST `POST /api/share`（建立連結）原本只掛 `get_current_session`，等於完全沒
   檢查 `share-manager` 這道 app 權限——這裡改掛 `require_app_permission("share-manager")`。
   列出／撤銷自己的連結維持 `get_current_session`：權限被收回後，使用者還能撤自己建的連結。
3. MCP `create_share_link` 走的是既有的 `check_mcp_tool_permission()`
   （見 `tests/test_mcp_share_guard.py`），這裡另外釘住預設關閉後、已綁定一般
   使用者被拒絕的訊息。

`tests/test_mcp_share_guard.py` 驗資源存取層（#205 那一層）；本檔只驗 app 權限層
（#217 這一層）本身，兩者分工，不重複造情境。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api.auth import get_current_session
from ching_tech_os.api.share import router as share_router
from ching_tech_os.models.auth import SessionData
from ching_tech_os.services import permissions as permissions_module
from ching_tech_os.services.mcp import server as mcp_server


# ============================================================
# 0. 共用小工具
# ============================================================


class _ConnCtx:
    """最小 async context manager，包一個假的 connection。"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _session(role="user", username="yaze", user_id=1, app_permissions=None):
    now = datetime.now(timezone.utc)
    return SessionData(
        username=username,
        password="test-password",
        nas_host="127.0.0.1",
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role=role,
        app_permissions=app_permissions or {},
    )


def _rest_app(session: SessionData):
    app = FastAPI()
    app.include_router(share_router)
    app.dependency_overrides[get_current_session] = lambda: session
    return app


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch):
    """不碰真的資料庫。"""
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())


# ============================================================
# 1. 常數與 has_app_permission()
# ============================================================


def test_default_app_permission_is_false() -> None:
    assert permissions_module.DEFAULT_APP_PERMISSIONS["share-manager"] is False


def test_has_app_permission_plain_user_no_override_denied() -> None:
    assert (
        permissions_module.has_app_permission(
            role="user", permissions=None, app_id="share-manager"
        )
        is False
    )


def test_has_app_permission_admin_always_allowed() -> None:
    assert (
        permissions_module.has_app_permission(
            role="admin", permissions=None, app_id="share-manager"
        )
        is True
    )


def test_has_app_permission_user_with_explicit_override_allowed() -> None:
    assert (
        permissions_module.has_app_permission(
            role="user",
            permissions={"apps": {"share-manager": True}},
            app_id="share-manager",
        )
        is True
    )


# ============================================================
# 2. REST：POST /api/share（建立）要真的擋
# ============================================================


def _create_content_payload() -> dict:
    """resource_type=content 不用查知識庫／NAS，最單純的建立請求。"""
    return {"resource_type": "content", "content": "hello", "expires_in": "1h"}


def test_rest_create_denies_plain_user_without_permission() -> None:
    """一般使用者沒有 `share-manager`（預設關閉）→ 403，且不是因為別的理由。"""
    client = TestClient(_rest_app(_session(role="user")))
    resp = client.post("/api/share", json=_create_content_payload())

    assert resp.status_code == 403
    assert "分享管理" in resp.json()["detail"]


def test_rest_create_allows_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """admin 不受 `share-manager` 預設值影響，一律放行。"""
    import ching_tech_os.api.share as share_api
    from ching_tech_os.models.share import ShareLinkResponse

    monkeypatch.setattr(
        share_api,
        "create_share_link",
        AsyncMock(
            return_value=ShareLinkResponse(
                token="abc123",
                url="/s/abc123",
                full_url="https://example.com/s/abc123",
                resource_type="content",
                resource_id="abc123",
                resource_title="分享內容",
                expires_at=None,
                created_at=datetime.now(timezone.utc),
            )
        ),
    )

    client = TestClient(_rest_app(_session(role="admin")))
    resp = client.post("/api/share", json=_create_content_payload())

    assert resp.status_code == 201


def test_rest_create_allows_user_with_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """一般使用者被管理員逐人開放 `share-manager` 後可以建立連結。"""
    import ching_tech_os.api.share as share_api
    from ching_tech_os.models.share import ShareLinkResponse

    monkeypatch.setattr(
        share_api,
        "create_share_link",
        AsyncMock(
            return_value=ShareLinkResponse(
                token="def456",
                url="/s/def456",
                full_url="https://example.com/s/def456",
                resource_type="content",
                resource_id="def456",
                resource_title="分享內容",
                expires_at=None,
                created_at=datetime.now(timezone.utc),
            )
        ),
    )

    client = TestClient(
        _rest_app(_session(role="user", app_permissions={"share-manager": True}))
    )
    resp = client.post("/api/share", json=_create_content_payload())

    assert resp.status_code == 201


# ============================================================
# 3. REST：列出／撤銷維持 get_current_session（權限被收回也能撤自己的連結）
# ============================================================


def test_rest_list_links_ignores_share_manager_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """一般使用者沒有 `share-manager` 權限也能列出自己的連結（GET 不受影響）。"""
    import ching_tech_os.api.share as share_api
    from ching_tech_os.models.share import ShareLinkListResponse

    monkeypatch.setattr(
        share_api,
        "list_my_links",
        AsyncMock(return_value=ShareLinkListResponse(links=[], total=0)),
    )

    client = TestClient(_rest_app(_session(role="user")))
    resp = client.get("/api/share")

    assert resp.status_code == 200


def test_rest_revoke_link_ignores_share_manager_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """一般使用者沒有 `share-manager` 權限也能撤自己建立的連結——
    權限被管理員收回之後，使用者仍要能關掉自己已經建立的連結，不能被鎖在外面。
    """
    import ching_tech_os.api.share as share_api

    monkeypatch.setattr(share_api, "revoke_link", AsyncMock(return_value=None))

    client = TestClient(_rest_app(_session(role="user")))
    resp = client.delete("/api/share/abc123")

    assert resp.status_code == 204


# ============================================================
# 4. MCP create_share_link：已綁定一般使用者被拒絕的訊息
# ============================================================


@pytest.mark.asyncio
async def test_mcp_bound_plain_user_denied_with_permission_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已綁定一般使用者（沒有 `share-manager` 覆寫）呼叫 `create_share_link`
    → 拒絕，訊息要指名「分享管理」這個功能權限，不是綁定訊息、也不是別的錯誤。

    這支工具在 `check_mcp_tool_permission` 裡先過 `APPS_REQUIRE_BOUND_USER`
    （已綁定，通過），再走 `check_tool_permission()` 判斷 app 權限本身；
    已綁定但沒有權限時的訊息固定是「您沒有「{app}」功能權限，無法使用此工具」
    （見 `services/mcp/server.py`），與未綁定時的「請先綁定 CTOS 帳號」不同。
    """
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"role": "user", "preferences": {}})
    )
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))

    allowed, message = await mcp_server.check_mcp_tool_permission(
        "create_share_link", 1
    )

    assert allowed is False
    assert "分享管理" in message
    assert "功能權限" in message
    assert message == "您沒有「分享管理」功能權限，無法使用此工具"


@pytest.mark.asyncio
async def test_mcp_bound_admin_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """已綁定的 admin 不受 `share-manager` 預設值影響，一律放行。"""
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"role": "admin", "preferences": {}})
    )
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))

    allowed, message = await mcp_server.check_mcp_tool_permission(
        "create_share_link", 1
    )

    assert allowed is True
    assert message == ""
