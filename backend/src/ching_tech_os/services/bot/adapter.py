"""Bot Adapter Protocol 定義

定義所有訊息平台必須實作的標準化介面，
以及可選的擴展 Protocol（訊息編輯、進度通知等）。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class SentMessage:
    """已發送訊息的結果"""
    message_id: str
    platform_type: str


@runtime_checkable
class BotAdapter(Protocol):
    """所有平台必須實作的標準化介面

    每個平台 Adapter 必須提供以下方法：
    - send_text: 發送文字訊息
    - send_image: 發送圖片訊息
    - send_file: 發送檔案訊息
    - send_messages: 批次發送多則訊息
    """

    platform_type: str

    async def send_text(
        self,
        target: str,
        text: str,
        *,
        reply_to: str | None = None,
        mention_user_id: str | None = None,
    ) -> SentMessage:
        """發送文字訊息

        Args:
            target: 發送目標（群組 ID 或用戶 ID）
            text: 文字內容
            reply_to: 回覆的訊息 ID（如 Line reply_token）
            mention_user_id: 要 mention 的用戶 ID
        """
        ...

    async def send_image(
        self,
        target: str,
        image_url: str,
        *,
        reply_to: str | None = None,
        preview_url: str | None = None,
    ) -> SentMessage:
        """發送圖片訊息

        Args:
            target: 發送目標
            image_url: 圖片 URL
            reply_to: 回覆的訊息 ID
            preview_url: 預覽圖 URL（部分平台需要）
        """
        ...

    async def send_file(
        self,
        target: str,
        file_url: str,
        file_name: str,
        *,
        reply_to: str | None = None,
        file_size: str | None = None,
    ) -> SentMessage:
        """發送檔案訊息

        Args:
            target: 發送目標
            file_url: 檔案 URL
            file_name: 檔案名稱
            reply_to: 回覆的訊息 ID
            file_size: 檔案大小描述
        """
        ...

    async def send_messages(
        self,
        target: str,
        messages: list,
        *,
        reply_to: str | None = None,
    ) -> list[SentMessage]:
        """批次發送多則訊息

        Args:
            target: 發送目標
            messages: 平台原生訊息物件列表
            reply_to: 回覆的訊息 ID
        """
        ...


@runtime_checkable
class EditableMessageAdapter(Protocol):
    """可選：支援訊息編輯/刪除的平台（如 Telegram）"""

    async def edit_message(
        self,
        target: str,
        message_id: str,
        new_text: str,
    ) -> None:
        """編輯已發送的訊息"""
        ...

    async def delete_message(
        self,
        target: str,
        message_id: str,
    ) -> None:
        """刪除已發送的訊息"""
        ...


@runtime_checkable
class ProgressNotifier(Protocol):
    """可選：支援即時進度更新的平台

    用於 AI 處理期間的 tool 執行狀態通知。
    實作此 Protocol 的平台可以做到「送出通知 → 即時更新 → 完成後刪除」。
    """

    async def send_progress(
        self,
        target: str,
        text: str,
    ) -> SentMessage:
        """發送進度通知訊息

        Returns:
            SentMessage，後續可用 message_id 更新或刪除
        """
        ...

    async def update_progress(
        self,
        target: str,
        message_id: str,
        text: str,
    ) -> None:
        """更新進度通知內容"""
        ...

    async def finish_progress(
        self,
        target: str,
        message_id: str,
    ) -> None:
        """完成進度通知（通常是刪除該訊息）"""
        ...
