"""測試 bot/adapter.py Protocol 定義"""

from dataclasses import dataclass

from ching_tech_os.services.bot.adapter import (
    BotAdapter,
    EditableMessageAdapter,
    ProgressNotifier,
    SentMessage,
)


class TestSentMessage:
    def test_creation(self):
        msg = SentMessage(message_id="msg-1", platform_type="line")
        assert msg.message_id == "msg-1"
        assert msg.platform_type == "line"


class TestBotAdapterProtocol:
    def test_isinstance_check(self):
        """實作 BotAdapter 的 class 可通過 isinstance 檢查"""

        class FakeAdapter:
            platform_type = "test"

            async def send_text(self, target, text, *, reply_to=None, mention_user_id=None):
                return SentMessage(message_id="1", platform_type="test")

            async def send_image(self, target, image_url, *, reply_to=None, preview_url=None):
                return SentMessage(message_id="2", platform_type="test")

            async def send_file(self, target, file_url, file_name, *, reply_to=None, file_size=None):
                return SentMessage(message_id="3", platform_type="test")

            async def send_messages(self, target, messages, *, reply_to=None):
                return []

        adapter = FakeAdapter()
        assert isinstance(adapter, BotAdapter)


class TestEditableMessageAdapterProtocol:
    def test_isinstance_check(self):
        class FakeEditable:
            async def edit_message(self, target, message_id, new_text):
                pass

            async def delete_message(self, target, message_id):
                pass

        obj = FakeEditable()
        assert isinstance(obj, EditableMessageAdapter)


class TestProgressNotifierProtocol:
    def test_isinstance_check(self):
        class FakeNotifier:
            async def send_progress(self, target, text):
                return SentMessage(message_id="p1", platform_type="test")

            async def update_progress(self, target, message_id, text):
                pass

            async def finish_progress(self, target, message_id):
                pass

        obj = FakeNotifier()
        assert isinstance(obj, ProgressNotifier)

    def test_not_matching(self):
        """缺少方法的 class 不匹配"""

        class Incomplete:
            async def send_progress(self, target, text):
                pass

        obj = Incomplete()
        assert not isinstance(obj, ProgressNotifier)
