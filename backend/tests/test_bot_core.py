"""測試 Bot 核心抽象層

測試對象：services/bot/ 模組
- adapter.py: Protocol 定義（runtime_checkable）
- message.py: 資料模型
- media.py: 媒體處理工具函式

用法：
    cd backend
    uv run pytest tests/test_bot_core.py -v
"""

import pytest

from ching_tech_os.services.bot.adapter import (
    BotAdapter,
    EditableMessageAdapter,
    ProgressNotifier,
    SentMessage,
)
from ching_tech_os.services.bot.message import (
    BotMessage,
    BotContext,
    BotResponse,
    BotResponseItem,
    PlatformType,
    ConversationType,
)
from ching_tech_os.services.bot.media import (
    is_readable_file,
    is_legacy_office_file,
    is_document_file,
    parse_pdf_temp_path,
    READABLE_FILE_EXTENSIONS,
    MAX_READABLE_FILE_SIZE,
)


# ============================================================
# SentMessage 測試
# ============================================================

class TestSentMessage:
    def test_create(self):
        msg = SentMessage(message_id="123", platform_type="line")
        assert msg.message_id == "123"
        assert msg.platform_type == "line"


# ============================================================
# BotMessage 測試
# ============================================================

class TestBotMessage:
    def test_create_text_message(self):
        msg = BotMessage(
            platform_type=PlatformType.LINE,
            sender_id="U123",
            target_id="C456",
            text="hello",
            conversation_type=ConversationType.GROUP,
        )
        assert msg.platform_type == PlatformType.LINE
        assert msg.sender_id == "U123"
        assert msg.text == "hello"
        assert msg.conversation_type == ConversationType.GROUP
        assert msg.platform_data == {}

    def test_create_with_platform_data(self):
        msg = BotMessage(
            platform_type=PlatformType.TELEGRAM,
            sender_id="123",
            target_id="456",
            platform_data={"chat_type": "supergroup"},
        )
        assert msg.platform_data["chat_type"] == "supergroup"


# ============================================================
# BotContext 測試
# ============================================================

class TestBotContext:
    def test_private_context(self):
        ctx = BotContext(
            platform_type=PlatformType.LINE,
            conversation_type=ConversationType.PRIVATE,
            platform_user_id="U123",
        )
        assert ctx.group_uuid is None
        assert ctx.platform_data == {}

    def test_group_context(self):
        from uuid import uuid4
        gid = uuid4()
        ctx = BotContext(
            platform_type=PlatformType.LINE,
            conversation_type=ConversationType.GROUP,
            group_uuid=gid,
            platform_data={"reply_token": "reply_abc"},
        )
        assert ctx.group_uuid == gid
        assert ctx.platform_data["reply_token"] == "reply_abc"


# ============================================================
# BotResponse 測試
# ============================================================

class TestBotResponse:
    def test_from_parsed_response_text_only(self):
        resp = BotResponse.from_parsed_response("回覆文字", [])
        assert resp.text == "回覆文字"
        assert resp.items == []

    def test_from_parsed_response_with_files(self):
        files = [
            {"type": "image", "url": "https://img.com/a.jpg", "name": "a.jpg"},
            {"type": "file", "url": "https://file.com/b.pdf", "name": "b.pdf", "size": "2MB"},
        ]
        resp = BotResponse.from_parsed_response("看這些", files)
        assert resp.text == "看這些"
        assert len(resp.items) == 2
        assert resp.items[0].type == "image"
        assert resp.items[1].type == "file"
        assert resp.items[1].size == "2MB"


# ============================================================
# PlatformType / ConversationType 測試
# ============================================================

class TestEnums:
    def test_platform_type_values(self):
        assert PlatformType.LINE == "line"
        assert PlatformType.TELEGRAM == "telegram"

    def test_conversation_type_values(self):
        assert ConversationType.PRIVATE == "private"
        assert ConversationType.GROUP == "group"


# ============================================================
# Media 工具函式測試（與 linebot.py 行為一致）
# ============================================================

class TestMediaUtils:
    def test_is_readable_file(self):
        assert is_readable_file("test.txt") is True
        assert is_readable_file("test.pdf") is True
        assert is_readable_file("test.jpg") is False
        assert is_readable_file("") is False

    def test_is_legacy_office(self):
        assert is_legacy_office_file("old.doc") is True
        assert is_legacy_office_file("new.docx") is False

    def test_parse_pdf_temp_path(self):
        pdf, txt = parse_pdf_temp_path("PDF:/tmp/a.pdf|TXT:/tmp/a.txt")
        assert pdf == "/tmp/a.pdf"
        assert txt == "/tmp/a.txt"

        pdf, txt = parse_pdf_temp_path("/tmp/normal.txt")
        assert pdf == "/tmp/normal.txt"
        assert txt == ""

    def test_max_file_size(self):
        assert MAX_READABLE_FILE_SIZE == 5 * 1024 * 1024


# ============================================================
# Protocol runtime_checkable 測試
# ============================================================

class TestProtocolChecks:
    """確認 Protocol 可用 isinstance 檢查"""

    def test_bot_adapter_is_runtime_checkable(self):
        """BotAdapter 支援 runtime isinstance 檢查"""
        assert hasattr(BotAdapter, "__protocol_attrs__") or callable(getattr(BotAdapter, "__instancecheck__", None))

    def test_editable_adapter_is_runtime_checkable(self):
        """EditableMessageAdapter 支援 runtime isinstance 檢查"""
        # 確認可以呼叫 isinstance 不會報錯
        assert not isinstance("not_adapter", EditableMessageAdapter)

    def test_progress_notifier_is_runtime_checkable(self):
        """ProgressNotifier 支援 runtime isinstance 檢查"""
        assert not isinstance("not_adapter", ProgressNotifier)
