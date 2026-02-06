"""Bot 訊息與情境資料模型

定義平台無關的訊息格式，用於在核心 AI 處理流程中
統一處理來自不同平台的訊息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID


class PlatformType(str, Enum):
    """支援的平台類型"""
    LINE = "line"
    TELEGRAM = "telegram"


class ConversationType(str, Enum):
    """對話類型"""
    PRIVATE = "private"
    GROUP = "group"


@dataclass
class BotMessage:
    """入站訊息的正規化格式

    所有平台的訊息都會被轉換為此格式，
    供核心 AI 處理流程使用。
    """
    platform_type: PlatformType
    sender_id: str               # 平台原生用戶 ID
    target_id: str               # 平台原生群組/頻道 ID（個人對話等於 sender_id）
    text: str | None = None
    media_url: str | None = None
    media_type: str | None = None  # image, file, video, audio
    conversation_type: ConversationType = ConversationType.PRIVATE
    reply_to_message_id: str | None = None  # 被回覆的訊息 ID
    # 平台特定資料（不強制規格）
    platform_data: dict = field(default_factory=dict)


@dataclass
class BotContext:
    """對話情境

    包含 AI 處理所需的所有情境資訊，
    由平台 Adapter 從平台事件填充。
    """
    platform_type: PlatformType
    conversation_type: ConversationType
    # 內部 UUID（資料庫中的 ID）
    user_uuid: UUID | None = None
    group_uuid: UUID | None = None
    # 平台原生 ID
    platform_user_id: str | None = None
    platform_group_id: str | None = None
    # 使用者資訊
    user_display_name: str | None = None
    ctos_user_id: int | None = None
    # 訊息資訊
    message_uuid: UUID | None = None
    # 平台特定資料（如 Line 的 reply_token、quoted_message_id）
    platform_data: dict = field(default_factory=dict)


@dataclass
class BotResponseItem:
    """單一回應項目"""
    type: str  # "text", "image", "file"
    text: str | None = None
    url: str | None = None
    name: str | None = None
    size: str | None = None


@dataclass
class BotResponse:
    """AI 處理後的回應

    平台無關的回應格式，由各平台 Adapter 轉換為平台原生格式發送。
    """
    text: str | None = None
    items: list[BotResponseItem] = field(default_factory=list)

    @classmethod
    def from_parsed_response(cls, text: str, file_messages: list[dict]) -> BotResponse:
        """從 parse_ai_response 的結果建構

        Args:
            text: 解析後的純文字
            file_messages: 解析出的 FILE_MESSAGE 列表
        """
        items = []
        for fm in file_messages:
            items.append(BotResponseItem(
                type=fm.get("type", "file"),
                url=fm.get("url"),
                name=fm.get("name"),
                size=fm.get("size"),
            ))
        return cls(text=text, items=items)
