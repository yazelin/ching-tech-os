"""Tests for the Telegram media_group_id (album) branch."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from ching_tech_os.services.image_edit_detection import telegram_album_images


@pytest.mark.asyncio
async def test_album_returns_all_images_chronological():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"line_message_id": "MSG_1", "nas_path": "/nas/1.jpg"},
        {"line_message_id": "MSG_2", "nas_path": "/nas/2.jpg"},
        {"line_message_id": "MSG_3", "nas_path": "/nas/3.jpg"},
    ])
    async def fake_ensure(mid, nas_path):
        return f"/tmp/test/{mid}.jpg"
    with patch(
        "ching_tech_os.services.image_edit_detection.ensure_temp_image",
        new=fake_ensure,
    ):
        result = await telegram_album_images(conn, "AGGREGATE_XYZ")
    assert result == [
        "/tmp/test/MSG_1.jpg",
        "/tmp/test/MSG_2.jpg",
        "/tmp/test/MSG_3.jpg",
    ]


@pytest.mark.asyncio
async def test_album_with_no_matching_rows_returns_empty():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    result = await telegram_album_images(conn, "UNKNOWN_GROUP")
    assert result == []
