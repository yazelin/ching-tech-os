"""linebot_ai 對話上下文與系統提示測試。"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.services import linebot_ai


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_get_conversation_context_group_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    rows_desc = [
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "image", "line_message_id": "img_latest", "nas_path": "nas/img_latest.jpg", "file_name": None, "file_size": None, "actual_file_type": None},
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "file", "line_message_id": "file_pdf_recent", "nas_path": "nas/report.pdf", "file_name": "report.pdf", "file_size": 123, "actual_file_type": "application/pdf"},
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "file", "line_message_id": "file_big", "nas_path": "nas/big.txt", "file_name": "big.txt", "file_size": linebot_ai.MAX_READABLE_FILE_SIZE + 1, "actual_file_type": "text/plain"},
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "file", "line_message_id": "file_pdf_no_txt", "nas_path": "nas/scan.pdf", "file_name": "scan.pdf", "file_size": 321, "actual_file_type": "application/pdf"},
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "file", "line_message_id": "file_normal", "nas_path": "nas/a.txt", "file_name": "a.txt", "file_size": 66, "actual_file_type": "text/plain"},
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "file", "line_message_id": "file_temp_expired", "nas_path": "nas/gone.txt", "file_name": "gone.txt", "file_size": 66, "actual_file_type": "text/plain"},
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "file", "line_message_id": "file_legacy", "nas_path": "nas/legacy.doc", "file_name": "legacy.doc", "file_size": 66, "actual_file_type": "application/msword"},
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "file", "line_message_id": "file_unreadable", "nas_path": "nas/video.mp4", "file_name": "video.mp4", "file_size": 66, "actual_file_type": "video/mp4"},
        {"content": None, "is_from_bot": False, "display_name": "小明", "message_type": "image", "line_message_id": "img_expired", "nas_path": "nas/img_old.jpg", "file_name": None, "file_size": None, "actual_file_type": None},
        {"content": "bot text", "is_from_bot": True, "display_name": None, "message_type": "text", "line_message_id": "t1", "nas_path": None, "file_name": None, "file_size": None, "actual_file_type": None},
        {"content": "user text", "is_from_bot": False, "display_name": "小美", "message_type": "text", "line_message_id": "t2", "nas_path": None, "file_name": None, "file_size": None, "actual_file_type": None},
    ]
    conn.fetch = AsyncMock(return_value=rows_desc)
    monkeypatch.setattr(linebot_ai, "get_connection", lambda: _CM(conn))

    async def _ensure_temp_image(msg_id: str, _nas_path: str):
        return "/tmp/img_latest.jpg" if msg_id == "img_latest" else None

    async def _ensure_temp_file(msg_id: str, _nas_path: str, _filename: str, _size: int | None = None):
        mapping = {
            "file_pdf_recent": "PDF:/tmp/report.pdf|TXT:/tmp/report.txt",
            "file_pdf_no_txt": "PDF:/tmp/scan.pdf",
            "file_normal": "/tmp/a.txt",
            "file_temp_expired": None,
        }
        return mapping.get(msg_id)

    monkeypatch.setattr(linebot_ai, "ensure_temp_image", _ensure_temp_image)
    monkeypatch.setattr(linebot_ai, "ensure_temp_file", _ensure_temp_file)
    monkeypatch.setattr(
        linebot_ai,
        "is_readable_file",
        lambda name: name in {"report.pdf", "big.txt", "scan.pdf", "a.txt", "gone.txt"},
    )
    monkeypatch.setattr(linebot_ai, "is_legacy_office_file", lambda name: name.endswith(".doc"))

    context, images, files = await linebot_ai.get_conversation_context(
        line_group_id=uuid4(),
        line_user_id=None,
        limit=20,
    )

    joined = "\n".join((item["content"] or "") for item in context)
    assert "[上傳圖片（最近）: /tmp/img_latest.jpg]" in joined
    assert "[圖片暫存已過期" in joined
    assert "[上傳 PDF（最近）: /tmp/report.pdf（文字版: /tmp/report.txt）]" in joined
    assert "[上傳 PDF: /tmp/scan.pdf（純圖片，無文字）]" in joined
    assert "[上傳檔案: /tmp/a.txt]" in joined
    assert "big.txt（檔案過大）" in joined
    assert "gone.txt 暫存已過期" in joined
    assert "legacy.doc（不支援舊版格式" in joined
    assert "video.mp4（無法讀取此類型）" in joined
    assert any(item["role"] == "assistant" and item["content"] == "bot text" for item in context)
    assert any(item["sender"] == "小美" for item in context if item["content"] == "user text")
    assert len(images) == 1 and images[0]["line_message_id"] == "img_latest"
    assert {f["line_message_id"] for f in files} == {"file_pdf_recent", "file_pdf_no_txt", "file_normal"}


@pytest.mark.asyncio
async def test_get_conversation_context_user_and_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {
            "content": "u-msg",
            "is_from_bot": False,
            "display_name": "User",
            "message_type": "text",
            "line_message_id": "u1",
            "nas_path": None,
            "file_name": None,
            "file_size": None,
            "actual_file_type": None,
        }
    ])
    monkeypatch.setattr(linebot_ai, "get_connection", lambda: _CM(conn))

    context, images, files = await linebot_ai.get_conversation_context(
        line_group_id=None,
        line_user_id="U1",
        limit=20,
    )
    assert len(context) == 1 and context[0]["content"] == "u-msg"
    assert images == [] and files == []

    context, images, files = await linebot_ai.get_conversation_context(
        line_group_id=None,
        line_user_id=None,
        limit=20,
    )
    assert context == [] and images == [] and files == []


@pytest.mark.asyncio
async def test_build_system_prompt_group(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"name": "測試群"})
    monkeypatch.setattr(linebot_ai, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(linebot_ai, "get_line_user_record", AsyncMock(return_value={"id": "u1", "user_id": 321}))
    monkeypatch.setattr(
        "ching_tech_os.services.linebot_agents.generate_tools_prompt",
        AsyncMock(return_value="TOOL_PROMPT"),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.linebot_agents.generate_usage_tips_prompt",
        lambda *_args, **_kwargs: "USAGE_TIPS",
    )
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_active_group_memories",
        AsyncMock(return_value=[{"content": "請使用繁體中文回應"}]),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_active_user_memories",
        AsyncMock(return_value=[]),
    )

    prompt = await linebot_ai.build_system_prompt(
        line_group_id=uuid4(),
        line_user_id="U1",
        base_prompt="BASE",
        builtin_tools=["WebFetch", "WebSearch"],
        app_permissions={"knowledge-base": True},
        platform_type="telegram",
    )

    assert "BASE" in prompt
    assert "【網頁讀取】" in prompt
    assert "【網路搜尋】" in prompt
    assert "【用戶上傳內容處理】" in prompt
    assert "【公開分享連結】" in prompt
    assert "TOOL_PROMPT" in prompt
    assert "USAGE_TIPS" in prompt
    assert "【自訂記憶】" in prompt
    assert "目前群組：測試群" in prompt
    assert "平台：Telegram" in prompt
    assert "ctos_user_id: 321" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_personal_unbound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_ai, "get_line_user_record", AsyncMock(return_value={"id": "u2", "user_id": None}))
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_active_group_memories",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_active_user_memories",
        AsyncMock(return_value=[{"content": "回答要精簡"}]),
    )

    prompt = await linebot_ai.build_system_prompt(
        line_group_id=None,
        line_user_id="U2",
        base_prompt="BASE2",
        builtin_tools=[],
        app_permissions=None,
        platform_type="line",
    )

    assert "BASE2" in prompt
    assert "line_user_id: U2" in prompt
    assert "ctos_user_id: （未關聯，無法進行專案更新操作）" in prompt
    assert "【自訂記憶】" in prompt
    assert "【網頁讀取】" not in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_group_unbound_and_personal_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    # 群組：未關聯帳號分支（ctos_user_id: （未關聯））
    monkeypatch.setattr(linebot_ai, "get_line_user_record", AsyncMock(return_value={"id": "u3", "user_id": None}))
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_active_group_memories",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_active_user_memories",
        AsyncMock(return_value=[]),
    )
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"name": "群組B"})
    monkeypatch.setattr(linebot_ai, "get_connection", lambda: _CM(conn))
    prompt_group = await linebot_ai.build_system_prompt(
        line_group_id=uuid4(),
        line_user_id="U3",
        base_prompt="G",
    )
    assert "ctos_user_id: （未關聯）" in prompt_group

    # 個人：已關聯帳號分支（ctos_user_id: 777）
    monkeypatch.setattr(linebot_ai, "get_line_user_record", AsyncMock(return_value={"id": "u4", "user_id": 777}))
    prompt_personal = await linebot_ai.build_system_prompt(
        line_group_id=None,
        line_user_id="U4",
        base_prompt="P",
    )
    assert "ctos_user_id: 777" in prompt_personal
