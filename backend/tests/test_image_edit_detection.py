"""Unit tests for _detect_image_edit_references — the shared multi-image
reference collector for both LINE and Telegram bots.

The detector is platform-agnostic: it takes an asyncpg connection,
user / group identifiers, the optional quoted_message_id, and the
current text — and returns 0..N reference temp paths.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from ching_tech_os.services.image_edit_detection import (
    _detect_image_edit_references,
    _IMAGE_EDIT_KEYWORDS,
)


@pytest.fixture
def mock_conn():
    """A fake asyncpg connection with fetchval + fetch we can prime."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    return conn


@pytest.fixture
def patch_ensure_temp_image():
    """Replace ensure_temp_image with an identity-like passthrough that
    returns a fake temp path for any non-empty nas_path."""
    async def fake(line_message_id: str, nas_path: str) -> str | None:
        return f"/tmp/test/{line_message_id}.jpg" if nas_path else None

    with patch(
        "ching_tech_os.services.image_edit_detection.ensure_temp_image",
        new=fake,
    ):
        yield


@pytest.fixture
def patch_image_info_lookup():
    """Replace get_image_info_by_line_message_id with a fake lookup."""
    lookups = {}

    async def fake(line_message_id: str) -> dict | None:
        return lookups.get(line_message_id)

    with patch(
        "ching_tech_os.services.image_edit_detection.get_image_info_by_line_message_id",
        new=fake,
    ):
        yield lookups


@pytest.mark.asyncio
class TestDetectImageEditReferences:

    async def test_quoted_reply_to_image_returns_single(
        self, mock_conn, patch_ensure_temp_image, patch_image_info_lookup,
    ):
        patch_image_info_lookup["MSG_QUOTED"] = {"nas_path": "/nas/a.jpg"}
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id="MSG_QUOTED",
            text="改成黑白",
        )
        assert result == ["/tmp/test/MSG_QUOTED.jpg"]
        mock_conn.fetch.assert_not_awaited()   # quoted-reply short-circuits

    async def test_quoted_reply_to_text_falls_through(
        self, mock_conn, patch_ensure_temp_image, patch_image_info_lookup,
    ):
        # quoted_message_id present but not an image → fall through to text branch
        # text has no edit keyword → return []
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id="MSG_TEXT",
            text="今天天氣不錯",
        )
        assert result == []

    async def test_no_keyword_returns_empty(
        self, mock_conn, patch_ensure_temp_image,
    ):
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="今天天氣不錯",
        )
        assert result == []
        mock_conn.fetch.assert_not_awaited()

    async def test_keyword_with_no_recent_uploads_returns_empty(
        self, mock_conn, patch_ensure_temp_image,
    ):
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 1, tzinfo=timezone.utc)
        )
        mock_conn.fetch = AsyncMock(return_value=[])
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="幫我改一下",
        )
        assert result == []

    async def test_keyword_with_three_recent_uploads_returns_all_chronological(
        self, mock_conn, patch_ensure_temp_image,
    ):
        # Mock returns rows in chronological order (DB query uses ORDER BY ASC)
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 20, tzinfo=timezone.utc)
        )
        mock_conn.fetch = AsyncMock(return_value=[
            {"line_message_id": "MSG_A", "nas_path": "/nas/a.jpg"},
            {"line_message_id": "MSG_B", "nas_path": "/nas/b.jpg"},
            {"line_message_id": "MSG_C", "nas_path": "/nas/c.jpg"},
        ])
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="幫我合成這幾張",
        )
        assert result == [
            "/tmp/test/MSG_A.jpg",
            "/tmp/test/MSG_B.jpg",
            "/tmp/test/MSG_C.jpg",
        ]

    async def test_keyword_set_contains_合成_and_組合(self):
        # Sanity: keywords for the dominant "merge / compose" intent must exist
        assert "合成" in _IMAGE_EDIT_KEYWORDS
        assert "組合" in _IMAGE_EDIT_KEYWORDS

    async def test_no_count_cap(
        self, mock_conn, patch_ensure_temp_image,
    ):
        # Detector must not silently truncate. 20 rows → 20 results.
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 20, tzinfo=timezone.utc)
        )
        rows = [
            {"line_message_id": f"MSG_{i}", "nas_path": f"/nas/{i}.jpg"}
            for i in range(20)
        ]
        mock_conn.fetch = AsyncMock(return_value=rows)
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="合成",
        )
        assert len(result) == 20

    async def test_ensure_temp_image_failure_drops_that_path(
        self, mock_conn,
    ):
        """If ensure_temp_image returns None for some path, that row is skipped
        and others continue."""
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 20, tzinfo=timezone.utc)
        )
        mock_conn.fetch = AsyncMock(return_value=[
            {"line_message_id": "MSG_OK", "nas_path": "/nas/a.jpg"},
            {"line_message_id": "MSG_BAD", "nas_path": ""},   # ensure returns None
            {"line_message_id": "MSG_OK2", "nas_path": "/nas/c.jpg"},
        ])

        async def fake_ensure(mid, nas_path):
            return f"/tmp/test/{mid}.jpg" if nas_path else None

        with patch(
            "ching_tech_os.services.image_edit_detection.ensure_temp_image",
            new=fake_ensure,
        ):
            result = await _detect_image_edit_references(
                mock_conn,
                user_id="USR_X",
                group_id=None,
                quoted_message_id=None,
                text="改一下",
            )
        assert result == ["/tmp/test/MSG_OK.jpg", "/tmp/test/MSG_OK2.jpg"]

    async def test_current_message_uuid_passed_into_anchor_query(
        self, mock_conn, patch_ensure_temp_image,
    ):
        """偵測器必須把 current_message_uuid 排除在「上一則文字」錨點 SQL 外。

        LINE 流程會先把當前文字訊息寫進 bot_messages 再呼叫偵測器，若
        anchor 查詢沒排除它，MAX(created_at) 永遠指向當前訊息，圖片
        清單會回空陣列（PR #145 review high-priority bug）。
        """
        current_uuid = uuid4()
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 20, tzinfo=timezone.utc)
        )
        mock_conn.fetch = AsyncMock(return_value=[])
        await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="合成",
            current_message_uuid=current_uuid,
        )
        # 驗證 SQL 參數含當前訊息 UUID
        anchor_call = mock_conn.fetchval.await_args
        assert current_uuid in anchor_call.args, (
            f"current_message_uuid 必須傳進 anchor SQL；實際 args={anchor_call.args}"
        )

    async def test_current_message_uuid_optional_back_compat(
        self, mock_conn, patch_ensure_temp_image,
    ):
        """不傳 current_message_uuid 也要能跑（Telegram handler 沒這個值）。"""
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 20, tzinfo=timezone.utc)
        )
        mock_conn.fetch = AsyncMock(return_value=[
            {"line_message_id": "MSG_A", "nas_path": "/nas/a.jpg"},
        ])
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="合成",
        )
        assert result == ["/tmp/test/MSG_A.jpg"]
