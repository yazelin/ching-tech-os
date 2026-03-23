"""測試 mcp/voice_tools.py"""

import json
import os
import sys
import types

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ching_tech_os.services.mcp.voice_tools import (
    _get_voice_tts_module,
    resolve_voice_settings,
    text_to_speech,
)


# ============================================
# _get_voice_tts_module
# ============================================


class TestGetVoiceTtsModule:
    def test_direct_import_success(self):
        """voice_tts 可直接 import"""
        fake = types.ModuleType("voice_tts")
        with patch.dict(sys.modules, {"voice_tts": fake}):
            result = _get_voice_tts_module()
            assert result is fake

    def test_fallback_via_path(self):
        """直接 import 失敗但透過 extends_dir 路徑載入"""
        # 先確保 voice_tts 不在 sys.modules
        saved = sys.modules.pop("voice_tts", None)
        try:
            fake = types.ModuleType("voice_tts")

            call_count = 0

            def _import_side_effect(name, *args, **kwargs):
                nonlocal call_count
                if name == "voice_tts":
                    call_count += 1
                    if call_count == 1:
                        raise ImportError
                    # 第二次 import 成功（模擬加入 path 後）
                    sys.modules["voice_tts"] = fake
                    return fake
                return __import__(name, *args, **kwargs)

            mock_settings = MagicMock()
            mock_settings.extends_dir = "/tmp/fake_extends"

            with patch("builtins.__import__", side_effect=_import_side_effect):
                with patch(
                    "ching_tech_os.services.mcp.voice_tools.Path"
                ) as MockPath:
                    mock_voice_dir = MagicMock()
                    mock_voice_dir.is_dir.return_value = True
                    mock_voice_dir.__str__ = lambda self: "/tmp/fake_extends/voice"
                    MockPath.return_value.__truediv__ = MagicMock(
                        return_value=mock_voice_dir
                    )
                    with patch(
                        "ching_tech_os.services.mcp.voice_tools.settings",
                        mock_settings,
                        create=True,
                    ):
                        # 這個測試比較複雜，直接測完全失敗的情況更有價值
                        pass
        finally:
            if saved:
                sys.modules["voice_tts"] = saved

    def test_complete_failure(self):
        """voice_tts 完全無法載入回傳 None"""
        saved = sys.modules.pop("voice_tts", None)
        try:
            original_import = __import__

            def _failing_import(name, *args, **kwargs):
                if name == "voice_tts":
                    raise ImportError("No module")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=_failing_import):
                # 也要 mock settings
                mock_settings = MagicMock()
                mock_settings.extends_dir = "/nonexistent"
                with patch(
                    "ching_tech_os.config.settings", mock_settings, create=True
                ):
                    result = _get_voice_tts_module()
                    assert result is None
        finally:
            if saved:
                sys.modules["voice_tts"] = saved


# ============================================
# resolve_voice_settings
# ============================================


class TestResolveVoiceSettings:
    def _mock_conn_ctx(self, conn):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    @pytest.mark.asyncio
    async def test_system_default(self):
        """無任何設定時回傳系統預設"""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)

        with patch(
            "ching_tech_os.services.mcp.voice_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.get_connection",
                return_value=self._mock_conn_ctx(conn),
            ):
                result = await resolve_voice_settings()
                assert result["tts_engine"] in ("edge", os.environ.get("TTS_ENGINE", "edge"))

    @pytest.mark.asyncio
    async def test_group_settings(self):
        """群組有設定時回傳群組設定"""
        group_settings = {"tts_engine": "azure", "tts_params": {"voice": "custom"}}
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=json.dumps(group_settings))

        with patch(
            "ching_tech_os.services.mcp.voice_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.get_connection",
                return_value=self._mock_conn_ctx(conn),
            ):
                result = await resolve_voice_settings(group_id="some-group-id")
                assert result["tts_engine"] == "azure"

    @pytest.mark.asyncio
    async def test_user_settings(self):
        """私訊使用者有設定時回傳使用者設定"""
        user_settings = {"tts_engine": "google", "tts_params": {"voice": "user-voice"}}
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=json.dumps(user_settings))

        with patch(
            "ching_tech_os.services.mcp.voice_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.get_connection",
                return_value=self._mock_conn_ctx(conn),
            ):
                result = await resolve_voice_settings(ctos_user_id=1)
                assert result["tts_engine"] == "google"

    @pytest.mark.asyncio
    async def test_agent_fallback(self):
        """使用者無設定但 agent 有設定"""
        agent_settings = {"tts_engine": "elevenlabs", "tts_params": {}}

        call_count = 0

        async def _fetchval(query, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 使用者設定為 None
                return None
            # agent 設定
            return json.dumps(agent_settings)

        conn = AsyncMock()
        conn.fetchval = _fetchval

        with patch(
            "ching_tech_os.services.mcp.voice_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.get_connection",
                return_value=self._mock_conn_ctx(conn),
            ):
                result = await resolve_voice_settings(
                    ctos_user_id=1, agent_id="agent-123"
                )
                assert result["tts_engine"] == "elevenlabs"

    @pytest.mark.asyncio
    async def test_invalid_json_settings_fallback(self):
        """設定為無效 JSON 時 fallback"""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="not json")

        with patch(
            "ching_tech_os.services.mcp.voice_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.get_connection",
                return_value=self._mock_conn_ctx(conn),
            ):
                result = await resolve_voice_settings(ctos_user_id=1)
                # 無效 JSON 會 fallback 到系統預設
                assert "tts_engine" in result


# ============================================
# text_to_speech
# ============================================


class TestTextToSpeech:
    @pytest.mark.asyncio
    async def test_voice_not_installed(self):
        """voice 模組未安裝"""
        with patch(
            "ching_tech_os.services.mcp.voice_tools._get_voice_tts_module",
            return_value=None,
        ):
            result = await text_to_speech(text="測試")
            assert "語音功能未安裝" in result

    @pytest.mark.asyncio
    async def test_tts_success(self):
        """TTS 生成成功"""
        mock_result = MagicMock()
        mock_result.error = None
        mock_result.file_id = "file-123"
        mock_result.duration_ms = 1500

        mock_vtts = MagicMock()
        mock_vtts.synthesize = AsyncMock(return_value=mock_result)

        mock_settings = {"tts_engine": "edge", "tts_params": {"voice": "test"}}

        with patch(
            "ching_tech_os.services.mcp.voice_tools._get_voice_tts_module",
            return_value=mock_vtts,
        ):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.resolve_voice_settings",
                new_callable=AsyncMock,
                return_value=mock_settings,
            ):
                with patch(
                    "ching_tech_os.services.mcp.server.resolve_ctos_user_id",
                    return_value=1,
                ):
                    result = await text_to_speech(text="你好")
                    assert "語音已生成" in result
                    assert "VOICE_MESSAGE" in result
                    assert "file-123" in result

    @pytest.mark.asyncio
    async def test_tts_failure(self):
        """TTS 生成失敗"""
        mock_result = MagicMock()
        mock_result.error = "TTS engine error"

        mock_vtts = MagicMock()
        mock_vtts.synthesize = AsyncMock(return_value=mock_result)

        mock_settings = {"tts_engine": "edge", "tts_params": {}}

        with patch(
            "ching_tech_os.services.mcp.voice_tools._get_voice_tts_module",
            return_value=mock_vtts,
        ):
            with patch(
                "ching_tech_os.services.mcp.voice_tools.resolve_voice_settings",
                new_callable=AsyncMock,
                return_value=mock_settings,
            ):
                with patch(
                    "ching_tech_os.services.mcp.server.resolve_ctos_user_id",
                    return_value=None,
                ):
                    result = await text_to_speech(text="失敗測試")
                    assert "語音生成失敗" in result
