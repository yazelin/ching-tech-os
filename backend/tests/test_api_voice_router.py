"""測試 api/voice_router.py"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api.voice_router import (
    router,
    VoiceSettingsBody,
    DeleteSettingsBody,
    PreviewBody,
    _preview_timestamps,
)
from ching_tech_os.models.auth import SessionData


def _create_app():
    app = FastAPI()
    app.include_router(router)
    return app


def _mock_session(user_id=1, role="user"):
    from datetime import datetime, timedelta

    return SessionData(
        username="testuser",
        password="testpass",
        nas_host="localhost",
        user_id=user_id,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(hours=1),
        role=role,
    )


# 統一覆寫 auth dependency
def _override_auth(session):
    from ching_tech_os.api.voice_router import _get_user_id
    from ching_tech_os.api.auth import get_current_session

    app = _create_app()
    app.dependency_overrides[get_current_session] = lambda: session
    app.dependency_overrides[_get_user_id] = lambda: session.user_id
    return app


# ============================================
# GET /api/voice/voices
# ============================================


class TestGetVoices:
    def test_voice_not_installed(self):
        app = _override_auth(_mock_session())
        with patch(
            "ching_tech_os.services.bot.voice_bridge.get_voice_tts",
            return_value=None,
        ):
            client = TestClient(app)
            resp = client.get("/api/voice/voices")
            assert resp.status_code == 503


# ============================================
# GET /api/voice/scopes
# ============================================


class TestGetVoiceScopes:
    def test_scopes(self):
        """取得語音設定範圍"""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="admin")
        conn.fetchrow = AsyncMock(return_value={"id": "uuid-123"})
        conn.fetch = AsyncMock(return_value=[
            {"id": "g1", "name": "群組1", "platform_type": "line"},
        ])

        # 第二次 fetch 回傳 agents
        call_count = 0
        original_fetch = conn.fetch

        async def _fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"id": "g1", "name": "群組1", "platform_type": "line"}]
            return [{"id": "a1", "name": "bot", "display_name": "Bot Agent"}]

        conn.fetch = _fetch

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session(role="admin"))
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.get("/api/voice/scopes")
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_admin"] is True


# ============================================
# GET /api/voice/settings
# ============================================


class TestGetVoiceSettings:
    def test_user_scope(self):
        """取得使用者語音設定"""
        settings_json = json.dumps({"tts_engine": "edge", "tts_params": {}})

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=settings_json)

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session())
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.resolve_voice_settings",
                new_callable=AsyncMock,
                return_value={"tts_engine": "edge", "tts_params": {}},
            ):
                client = TestClient(app)
                resp = client.get("/api/voice/settings?scope=user")
                assert resp.status_code == 200
                data = resp.json()
                assert data["scope"] == "user"
                assert data["current"]["tts_engine"] == "edge"

    def test_no_settings(self):
        """無設定時 current 為 None"""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session())
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.resolve_voice_settings",
                new_callable=AsyncMock,
                return_value={"tts_engine": "edge", "tts_params": {}},
            ):
                client = TestClient(app)
                resp = client.get("/api/voice/settings?scope=user")
                assert resp.status_code == 200
                assert resp.json()["current"] is None


# ============================================
# PUT /api/voice/settings
# ============================================


class TestSaveVoiceSettings:
    def test_save_user_settings(self):
        """儲存使用者設定"""
        conn = AsyncMock()
        conn.execute = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session())
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.put(
                "/api/voice/settings",
                json={"scope": "user", "tts_engine": "azure", "tts_params": {}},
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    def test_save_group_settings(self):
        """儲存群組設定"""
        conn = AsyncMock()
        conn.execute = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session())
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.put(
                "/api/voice/settings",
                json={
                    "scope": "group",
                    "scope_id": "group-123",
                    "tts_engine": "edge",
                    "tts_params": {},
                },
            )
            assert resp.status_code == 200

    def test_save_agent_settings_non_admin(self):
        """非管理員不能修改 Agent 設定"""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="user")
        conn.execute = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session(role="user"))
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.put(
                "/api/voice/settings",
                json={
                    "scope": "agent",
                    "scope_id": "agent-123",
                    "tts_engine": "edge",
                    "tts_params": {},
                },
            )
            assert resp.status_code == 403

    def test_save_agent_settings_admin(self):
        """管理員可以修改 Agent 設定"""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="admin")
        conn.execute = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session(role="admin"))
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.put(
                "/api/voice/settings",
                json={
                    "scope": "agent",
                    "scope_id": "agent-123",
                    "tts_engine": "edge",
                    "tts_params": {},
                },
            )
            assert resp.status_code == 200

    def test_invalid_scope(self):
        """無效的 scope"""
        conn = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session())
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.put(
                "/api/voice/settings",
                json={"scope": "invalid", "tts_engine": "edge", "tts_params": {}},
            )
            assert resp.status_code == 400


# ============================================
# DELETE /api/voice/settings
# ============================================


class TestDeleteVoiceSettings:
    def test_delete_user_settings(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session())
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.request(
                "DELETE",
                "/api/voice/settings",
                json={"scope": "user"},
            )
            assert resp.status_code == 200

    def test_delete_group_settings(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session())
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.request(
                "DELETE",
                "/api/voice/settings",
                json={"scope": "group", "scope_id": "g1"},
            )
            assert resp.status_code == 200

    def test_delete_agent_non_admin(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="user")

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session())
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.request(
                "DELETE",
                "/api/voice/settings",
                json={"scope": "agent", "scope_id": "a1"},
            )
            assert resp.status_code == 403

    def test_delete_agent_admin(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="admin")
        conn.execute = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        app = _override_auth(_mock_session(role="admin"))
        with patch("ching_tech_os.api.voice_router.get_connection", return_value=ctx):
            client = TestClient(app)
            resp = client.request(
                "DELETE",
                "/api/voice/settings",
                json={"scope": "agent", "scope_id": "a1"},
            )
            assert resp.status_code == 200


# ============================================
# POST /api/voice/preview
# ============================================


class TestPreviewVoice:
    def test_voice_not_installed(self):
        _preview_timestamps.clear()
        app = _override_auth(_mock_session())
        with patch(
            "ching_tech_os.services.bot.voice_bridge.get_voice_tts",
            return_value=None,
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/voice/preview",
                json={"engine": "edge", "params": {}, "text": "test"},
            )
            assert resp.status_code == 503

    def test_rate_limit(self):
        """試聽冷卻中"""
        import time

        _preview_timestamps[1] = time.time()  # 剛剛才試聽過
        app = _override_auth(_mock_session(user_id=1))
        client = TestClient(app)
        resp = client.post(
            "/api/voice/preview",
            json={"engine": "edge", "params": {}, "text": "test"},
        )
        assert resp.status_code == 429
        _preview_timestamps.clear()
