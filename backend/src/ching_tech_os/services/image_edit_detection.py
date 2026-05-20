"""Shared multi-image reference collector for LINE / Telegram bot handlers.

Hybrid rule:
  1. quoted_message_id points to an image → return [that image]
     (Strong explicit signal — user replied to a specific photo.)
  2. text contains an edit keyword AND the user has uploaded image(s)
     since their previous text message → return those images chronologically
     (LINE / Telegram natural pattern: drop N photos, then type "合成")
  3. otherwise → return []

No count cap — the OpenAI API (~16 for gpt-image edit) is the real
ceiling. Per-image 10 MB cap lives at the MCP tool layer.

The detector is platform-agnostic; both `linebot_ai.py` and the
Telegram handler call it the same way. Telegram's `media_group_id`
branch lives in its own handler — see telegram_album_images() below.
"""

from __future__ import annotations

import logging
from typing import Protocol

from .bot_line.file_handler import (
    ensure_temp_image,
    get_image_info_by_line_message_id,
)

logger = logging.getLogger(__name__)


class _AsyncpgLike(Protocol):
    async def fetchval(self, query: str, *args): ...
    async def fetch(self, query: str, *args): ...


_IMAGE_EDIT_KEYWORDS = (
    # Direct edit verbs
    "修", "改", "換", "加", "變", "調整", "微調",
    # Preservation / framing
    "保留", "不要改", "原樣", "原圖", "原本",
    # Removal
    "去掉", "刪", "拿掉",
    # Style / colour / background tweaks
    "顏色", "背景", "黑白", "色調",
    # Re-render variants
    "再生一張", "再畫一張", "重新", "重畫",
    # The dominant multi-image composition verbs (added 2026-05 for
    # ctos-lite; ching-tech-os benefits from the same coverage)
    "合成", "組合",
)


async def _detect_image_edit_references(
    conn: _AsyncpgLike,
    *,
    user_id: str,
    group_id: str | None,
    quoted_message_id: str | None,
    text: str,
) -> list[str]:
    """Return absolute temp paths of reference images to attach to this turn.

    Args:
        conn:                  asyncpg connection / pool member
        user_id:               platform_user_id from bot_users (LINE userId or
                               Telegram user id stringified)
        group_id:              bot_groups.id UUID or None for personal chat
        quoted_message_id:     LINE quotedMessageId or Telegram reply-to message
                               id (string); None when the user didn't reply
        text:                  the user's text message content (pre-cleanup)

    Returns:
        List of temp paths in chronological order (oldest first). Empty list
        when the turn shouldn't trigger multi-image edit mode.
    """
    # Branch 1: explicit quoted reply — single image, strong signal
    if quoted_message_id:
        info = await get_image_info_by_line_message_id(quoted_message_id)
        if info and info.get("nas_path"):
            temp = await ensure_temp_image(quoted_message_id, info["nas_path"])
            if temp:
                logger.info(
                    "image edit detect: quoted reply → 1 image (%s)", temp,
                )
                return [temp]
        # quoted message wasn't an image — fall through to keyword branch

    # Branch 2: keyword + recent uploads
    if not any(kw in text for kw in _IMAGE_EDIT_KEYWORDS):
        return []

    # Find the user's previous text-message timestamp (anchor for the batch)
    if group_id is not None:
        last_text_at = await conn.fetchval(
            """
            SELECT COALESCE(MAX(m.created_at), '1970-01-01'::timestamptz)
            FROM bot_messages m
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id = $1
              AND u.platform_user_id = $2
              AND m.is_from_bot = false
              AND m.message_type = 'text'
              AND m.content IS NOT NULL
              AND m.content <> ''
            """,
            group_id, user_id,
        )
        rows = await conn.fetch(
            """
            SELECT m.message_id as line_message_id, f.nas_path
            FROM bot_messages m
            JOIN bot_files f ON f.message_id = m.id
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id = $1
              AND u.platform_user_id = $2
              AND m.is_from_bot = false
              AND m.message_type = 'image'
              AND f.file_type = 'image'
              AND m.created_at > $3
            ORDER BY m.created_at ASC
            """,
            group_id, user_id, last_text_at,
        )
    else:
        last_text_at = await conn.fetchval(
            """
            SELECT COALESCE(MAX(m.created_at), '1970-01-01'::timestamptz)
            FROM bot_messages m
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id IS NULL
              AND u.platform_user_id = $1
              AND m.is_from_bot = false
              AND m.message_type = 'text'
              AND m.content IS NOT NULL
              AND m.content <> ''
            """,
            user_id,
        )
        rows = await conn.fetch(
            """
            SELECT m.message_id as line_message_id, f.nas_path
            FROM bot_messages m
            JOIN bot_files f ON f.message_id = m.id
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id IS NULL
              AND u.platform_user_id = $1
              AND m.is_from_bot = false
              AND m.message_type = 'image'
              AND f.file_type = 'image'
              AND m.created_at > $2
            ORDER BY m.created_at ASC
            """,
            user_id, last_text_at,
        )

    if not rows:
        return []

    paths: list[str] = []
    for row in rows:
        temp = await ensure_temp_image(row["line_message_id"], row["nas_path"])
        if temp:
            paths.append(temp)
    if paths:
        logger.info(
            "image edit detect: keyword %r + %d uploads since %s",
            text[:30], len(paths), last_text_at,
        )
    return paths
