"""Test that bot-generated images are recorded in bot_files.

When the LINE bot replies with an AI-generated image, the send pathway in
``process_message_with_ai`` must INSERT a ``bot_files`` row so that
``get_image_info_by_line_message_id`` can later find the image when the user
replies to it (e.g. "再加皇冠").

Without that INSERT, the multi-image detector's quoted-reply branch returns
None and silently falls through.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from ching_tech_os.services import linebot_ai


# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

_BOT_MSG_UUID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
_LINE_IMG_MSG_ID = "LINE_MSG_BOT_IMG_001"
_NAS_PATH = "ai-images/codex_abc12345.png"
_FILE_NAME = "codex_abc12345.png"

_IMAGE_FILE_MESSAGE = {
    "type": "image",
    "url": "https://nas.example.com/ai-images/codex_abc12345.png",
    "original_url": "https://nas.example.com/ai-images/codex_abc12345.png",
    "name": _FILE_NAME,
    "nas_path": _NAS_PATH,
}


def _make_fake_agent() -> dict:
    """Return a minimal agent dict that satisfies linebot_ai.process_message_with_ai."""
    return {
        "id": uuid4(),
        "name": "test-agent",
        "model": "claude-3-5-sonnet-20241022",
        "system_prompt": {"id": uuid4(), "content": "sys"},
        "tools": [],
        "settings": {},
    }


def _make_fake_response(file_message_dict: dict) -> object:
    return type("Resp", (), {
        "success": True,
        "message": (
            "圖片已生成！"
            f'[FILE_MESSAGE:{json.dumps(file_message_dict, ensure_ascii=False)}]'
        ),
        "tool_calls": [],
        "error": None,
    })()


def _make_fake_db_ctx():
    """Return a fake async context manager for get_connection()."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield conn

    return _ctx


def _apply_common_patches(monkeypatch, *, file_message: dict, sent_ids: list[str]):
    """Apply the common set of monkeypatches needed by both tests."""
    # ---- core AI trigger ----
    monkeypatch.setattr(linebot_ai, "should_trigger_ai", lambda *a, **kw: True)
    monkeypatch.setattr(linebot_ai, "is_bot_message", AsyncMock(return_value=False))

    # ---- agent config ----
    monkeypatch.setattr(
        linebot_ai, "get_linebot_agent",
        AsyncMock(return_value=_make_fake_agent()),
    )

    # ---- user / permissions (all DB-backed) ----
    monkeypatch.setattr(linebot_ai, "get_line_user_record", AsyncMock(return_value=None))
    # build_system_prompt is imported at module level; patch via the module
    monkeypatch.setattr(linebot_ai, "build_system_prompt", AsyncMock(return_value="sys prompt"))
    # get_mcp_tools_for_user and get_user_app_permissions_sync are imported inside
    # the function body; patch via the linebot_ai module namespace is not possible
    # for local imports, so patch their original modules instead.
    monkeypatch.setattr(
        "ching_tech_os.services.permissions.get_mcp_tools_for_user",
        lambda *a, **kw: [],
    )
    monkeypatch.setattr(
        "ching_tech_os.services.permissions.get_user_app_permissions_sync",
        lambda *a, **kw: {},
    )
    monkeypatch.setattr(
        "ching_tech_os.services.codex_image.is_codex_image_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ching_tech_os.services.linebot_agents.get_mcp_servers_for_user",
        AsyncMock(return_value=[]),
    )

    # ---- conversation history ----
    monkeypatch.setattr(
        linebot_ai, "get_conversation_context",
        AsyncMock(return_value=([], [], [])),
    )

    # ---- DB connection (used by detection + mark_message_ai_processed etc.) ----
    monkeypatch.setattr(linebot_ai, "get_connection", _make_fake_db_ctx())

    # ---- Claude CLI ----
    monkeypatch.setattr(linebot_ai, "call_ai", AsyncMock(return_value=_make_fake_response(file_message)))
    monkeypatch.setattr(linebot_ai, "_extract_research_tool_feedback", lambda *a, **kw: None)
    monkeypatch.setattr(
        linebot_ai, "auto_prepare_generated_images",
        AsyncMock(side_effect=lambda text, tool_calls: text),
    )
    monkeypatch.setattr(
        linebot_ai, "auto_extract_voice_messages",
        lambda text, tool_calls: text,
    )

    # ---- post-send DB writes ----
    monkeypatch.setattr(linebot_ai, "mark_message_ai_processed", AsyncMock())
    monkeypatch.setattr(linebot_ai, "send_ai_response", AsyncMock(return_value=sent_ids))
    monkeypatch.setattr(linebot_ai, "log_linebot_ai_call", AsyncMock())
    monkeypatch.setattr(
        linebot_ai, "compose_prompt_with_history",
        lambda prompt, history, **kw: prompt,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bot_image_inserts_bot_files_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """process_message_with_ai saves a bot_files row for each image the bot sends."""

    # sent_ids: first = text msg, second = image msg
    _apply_common_patches(
        monkeypatch,
        file_message=_IMAGE_FILE_MESSAGE,
        sent_ids=["LINE_MSG_TEXT_001", _LINE_IMG_MSG_ID],
    )

    # save_bot_response: first call → text (random UUID), second call → image
    _call_count = {"n": 0}

    async def _fake_save_bot_response(**kwargs):
        _call_count["n"] += 1
        return _BOT_MSG_UUID if _call_count["n"] == 2 else uuid4()

    monkeypatch.setattr(linebot_ai, "save_bot_response", _fake_save_bot_response)

    # Capture save_file_record
    save_file_record_mock = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(linebot_ai, "save_file_record", save_file_record_mock)

    with patch(
        "ching_tech_os.services.image_edit_detection._detect_image_edit_references",
        new=AsyncMock(return_value=[]),
    ):
        result = await linebot_ai.process_message_with_ai(
            message_uuid=uuid4(),
            content="畫一隻貓",
            line_group_id=None,
            line_user_id="U_testuser",
            reply_token="fake_reply_token",
            user_display_name="Test User",
        )

    assert result is not None, "process_message_with_ai should return the text response"

    # save_file_record must have been called exactly once (for the image)
    save_file_record_mock.assert_awaited_once()
    call_kwargs = save_file_record_mock.await_args.kwargs

    assert call_kwargs["message_uuid"] == _BOT_MSG_UUID
    assert call_kwargs["file_type"] == "image"
    assert call_kwargs["nas_path"] == _NAS_PATH
    assert call_kwargs["file_name"] == _FILE_NAME


@pytest.mark.asyncio
async def test_bot_image_without_nas_path_skips_bot_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the file_message has no nas_path, save_file_record must NOT be called.

    Guards against regression: we only record rows we can later look up by nas_path.
    """
    image_without_nas = {
        "type": "image",
        "url": "https://nas.example.com/ai-images/nonas.png",
        "original_url": "https://nas.example.com/ai-images/nonas.png",
        "name": "nonas.png",
        # intentionally no nas_path
    }

    _apply_common_patches(
        monkeypatch,
        file_message=image_without_nas,
        sent_ids=["LINE_MSG_TEXT_001", "LINE_MSG_IMG_001"],
    )
    monkeypatch.setattr(linebot_ai, "save_bot_response", AsyncMock(return_value=uuid4()))

    save_file_record_mock = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(linebot_ai, "save_file_record", save_file_record_mock)

    with patch(
        "ching_tech_os.services.image_edit_detection._detect_image_edit_references",
        new=AsyncMock(return_value=[]),
    ):
        await linebot_ai.process_message_with_ai(
            message_uuid=uuid4(),
            content="畫一隻貓",
            line_group_id=None,
            line_user_id="U_testuser",
            reply_token="fake_reply_token",
        )

    save_file_record_mock.assert_not_awaited()
