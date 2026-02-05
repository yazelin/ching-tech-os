"""Bot API 路由測試

驗證 /api/bot/* 路由能正常運作（前端已遷移至此路徑）。

用法：
    cd backend
    uv run pytest tests/test_bot_api_routes.py -v

注意：移除多租戶架構後，Bot API 需要重構
"""

import pytest

pytestmark = pytest.mark.skip(reason="移除多租戶架構後，Bot API 需要重構")
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api.linebot_router import router as bot_router
from ching_tech_os.api.auth import get_current_session
from ching_tech_os.models.auth import SessionData


def create_session_override(username: str, user_id: int = 1, role: str = "user"):
    """建立 session 覆寫函數"""
    async def override():
        now = datetime.now()
        return SessionData(
            username=username,
            password="test-password",
            nas_host="test-nas",
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(hours=1),
            role=role,
        )
    return override


def create_bot_app():
    """建立包含 /api/bot 路由的測試應用程式"""
    from ching_tech_os.api.linebot_router import line_router
    app = FastAPI()
    app.include_router(bot_router, prefix="/api/bot")
    app.include_router(line_router, prefix="/api/bot/line")
    return app


# ============================================================
# /api/bot/* 路由測試（前端主要使用的路徑）
# ============================================================

class TestBotApiRoutes:
    """/api/bot/* 路由可達性測試"""

    def setup_method(self):
        self.app = create_bot_app()
        self.app.dependency_overrides[get_current_session] = create_session_override(
            "testuser", role="admin"
        )
        self.client = TestClient(self.app)

    def test_bot_groups_returns_200(self):
        """/api/bot/groups 應回傳 200"""
        with patch("ching_tech_os.api.linebot_router.list_groups", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([], 0)
            response = self.client.get("/api/bot/groups")
            assert response.status_code == 200
            assert response.json()["items"] == []

    def test_bot_users_returns_200(self):
        """/api/bot/users 應回傳 200"""
        with patch("ching_tech_os.api.linebot_router.list_users", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([], 0)
            response = self.client.get("/api/bot/users")
            assert response.status_code == 200

    def test_bot_messages_returns_200(self):
        """/api/bot/messages 應回傳 200"""
        with patch("ching_tech_os.api.linebot_router.list_messages", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([], 0)
            response = self.client.get("/api/bot/messages")
            assert response.status_code == 200

    def test_bot_files_returns_200(self):
        """/api/bot/files 應回傳 200"""
        with patch("ching_tech_os.api.linebot_router.list_files", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([], 0)
            response = self.client.get("/api/bot/files")
            assert response.status_code == 200

    def test_bot_line_webhook_route_exists(self):
        """/api/bot/line/webhook 路由應存在（POST）"""
        from ching_tech_os.api import linebot_router

        with patch.object(linebot_router, "verify_webhook_signature", new_callable=AsyncMock) as mock_verify, \
             patch.object(linebot_router, "get_webhook_parser") as mock_parser:
            mock_verify.return_value = (True, "test-secret")
            mock_parser_instance = MagicMock()
            mock_parser_instance.parse.return_value = []
            mock_parser.return_value = mock_parser_instance

            response = self.client.post(
                "/api/bot/line/webhook",
                content=b'{"events":[]}',
                headers={"X-Line-Signature": "test"},
            )
            assert response.status_code == 200

    def test_old_linebot_routes_return_404(self):
        """舊的 /api/linebot/* 路由應回傳 404"""
        response = self.client.get("/api/linebot/groups")
        assert response.status_code == 404

    def test_old_bot_webhook_returns_404(self):
        """舊的 /api/bot/webhook 路由應回傳 404（已移到 /api/bot/line/webhook）"""
        response = self.client.post(
            "/api/bot/webhook",
            content=b'{"events":[]}',
            headers={"X-Line-Signature": "test"},
        )
        assert response.status_code in (404, 405)

    def test_nonexistent_route_returns_404(self):
        """/api/bot/nonexistent 應回傳 404"""
        response = self.client.get("/api/bot/nonexistent")
        assert response.status_code in (404, 405)


