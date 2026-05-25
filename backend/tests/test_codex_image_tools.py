"""Unit tests for the unified codex_image_tool MCP wrapper."""

from __future__ import annotations

import base64
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock


@pytest.fixture
def reference_files(tmp_path, monkeypatch):
    """Make two real PNG files in a fake NAS root.

    Patches ctos_mount_path + line_files_nas_path so that
    settings.linebot_local_path == tmp_path.
    """
    from ching_tech_os.config import settings
    monkeypatch.setattr(settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(settings, "line_files_nas_path", "")
    a = tmp_path / "files" / "uploads" / "a.png"
    b = tmp_path / "files" / "uploads" / "b.png"
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_bytes(b"\x89PNG\r\n\x1a\nA")
    b.write_bytes(b"\x89PNG\r\n\x1a\nB")
    return a, b


@pytest.fixture
def codex_enabled(monkeypatch):
    from ching_tech_os.config import settings
    monkeypatch.setattr(settings, "codex_image_base_url", "http://codex.example/")
    monkeypatch.setattr(settings, "codex_image_api_key", "cimg_test")


@pytest.mark.asyncio
async def test_text_to_image_no_references(codex_enabled):
    """No reference_images → just text-to-image; no bytes loaded."""
    from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
    with patch(
        "ching_tech_os.services.mcp.codex_image_tools.generate_image_with_codex",
        new=AsyncMock(return_value=("ai-images/x.png", None)),
    ) as gen:
        result = await codex_image_tool(prompt="a cat")
    gen.assert_awaited_once()
    kwargs = gen.await_args.kwargs
    assert kwargs.get("reference_bytes_list") is None
    assert "圖片已生成" in result


@pytest.mark.asyncio
async def test_single_reference_path_loaded_and_passed(codex_enabled, reference_files):
    a, _ = reference_files
    with patch(
        "ching_tech_os.services.mcp.codex_image_tools.generate_image_with_codex",
        new=AsyncMock(return_value=("ai-images/x.png", None)),
    ) as gen:
        from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
        result = await codex_image_tool(
            prompt="edit it",
            reference_images=[str(a)],
        )
    kwargs = gen.await_args.kwargs
    assert kwargs["reference_bytes_list"] == [a.read_bytes()]
    assert "圖片已生成" in result


@pytest.mark.asyncio
async def test_multiple_references_loaded_in_order(codex_enabled, reference_files):
    a, b = reference_files
    with patch(
        "ching_tech_os.services.mcp.codex_image_tools.generate_image_with_codex",
        new=AsyncMock(return_value=("ai-images/x.png", None)),
    ) as gen:
        from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
        await codex_image_tool(
            prompt="composite",
            reference_images=[str(a), str(b)],
        )
    kwargs = gen.await_args.kwargs
    assert kwargs["reference_bytes_list"] == [a.read_bytes(), b.read_bytes()]


@pytest.mark.asyncio
async def test_nas_relative_path_resolved_against_linebot_local_path(
    codex_enabled, reference_files, tmp_path,
):
    """Path like 'files/uploads/a.png' resolves against settings.linebot_local_path."""
    with patch(
        "ching_tech_os.services.mcp.codex_image_tools.generate_image_with_codex",
        new=AsyncMock(return_value=("ai-images/x.png", None)),
    ) as gen:
        from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
        await codex_image_tool(
            prompt="edit",
            reference_images=["files/uploads/a.png"],   # relative
        )
    kwargs = gen.await_args.kwargs
    assert len(kwargs["reference_bytes_list"]) == 1
    assert kwargs["reference_bytes_list"][0] == b"\x89PNG\r\n\x1a\nA"


@pytest.mark.asyncio
async def test_missing_reference_returns_error_without_calling_codex(codex_enabled):
    from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
    with patch(
        "ching_tech_os.services.mcp.codex_image_tools.generate_image_with_codex",
        new=AsyncMock(),
    ) as gen:
        result = await codex_image_tool(
            prompt="edit",
            reference_images=["/no/such/file.png"],
        )
    gen.assert_not_awaited()
    assert "reference 圖檔不存在" in result


@pytest.mark.asyncio
async def test_oversized_reference_rejected(codex_enabled, tmp_path, monkeypatch):
    from ching_tech_os.config import settings
    monkeypatch.setattr(settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(settings, "line_files_nas_path", "")
    huge = tmp_path / "huge.png"
    huge.write_bytes(b"x" * (10 * 1024 * 1024 + 1))   # > 10 MB
    from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
    with patch(
        "ching_tech_os.services.mcp.codex_image_tools.generate_image_with_codex",
        new=AsyncMock(),
    ) as gen:
        result = await codex_image_tool(
            prompt="edit",
            reference_images=[str(huge)],
        )
    gen.assert_not_awaited()
    assert "超過 10 MB" in result


@pytest.mark.asyncio
async def test_codex_not_configured_returns_skip_message():
    """When codex_image_base_url isn't set, return a clear skip message."""
    from ching_tech_os.config import settings
    settings.codex_image_base_url = ""
    settings.codex_image_api_key = ""
    from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
    result = await codex_image_tool(prompt="anything")
    assert "Codex 未設定" in result


@pytest.mark.asyncio
async def test_legacy_tool_names_no_longer_exported():
    """The old codex_generate_image_tool / codex_edit_image_tool symbols are gone."""
    from ching_tech_os.services.mcp import codex_image_tools
    assert not hasattr(codex_image_tools, "codex_generate_image_tool")
    assert not hasattr(codex_image_tools, "codex_edit_image_tool")


@pytest.mark.asyncio
async def test_absolute_path_outside_allowed_roots_rejected(
    codex_enabled, tmp_path, monkeypatch,
):
    """系統檔案絕對路徑（/etc/passwd 等）必須被拒絕，避免 LFI。

    PR #145 review security-high：reference_images 沒檢查路徑是否
    在允許範圍內，AI 若被 prompt-injection 騙著傳系統路徑，
    程式會 read_bytes() 整個檔案再上傳給 OpenAI。
    """
    # 設好 NAS 根目錄（讓 settings.linebot_local_path 指向 tmp_path）
    monkeypatch.setattr("ching_tech_os.config.settings.ctos_mount_path", str(tmp_path))
    monkeypatch.setattr("ching_tech_os.config.settings.line_files_nas_path", "")

    # 在禁區建一個真實檔案：tmp_path 上一層
    forbidden_dir = tmp_path.parent / "forbidden_root"
    forbidden_dir.mkdir(exist_ok=True)
    secret = forbidden_dir / "secret.png"
    secret.write_bytes(b"\x89PNG\r\n\x1a\nSECRET")

    from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
    with patch(
        "ching_tech_os.services.mcp.codex_image_tools.generate_image_with_codex",
        new=AsyncMock(),
    ) as gen:
        result = await codex_image_tool(
            prompt="edit",
            reference_images=[str(secret)],
        )
    gen.assert_not_awaited()
    assert "非法路徑" in result or "不存在" in result


@pytest.mark.asyncio
async def test_bot_images_temp_dir_accepted(codex_enabled, tmp_path, monkeypatch):
    """`/tmp/bot-images/` 是 bot 下載 LINE/Telegram 圖片的固定暫存區，
    必須被視為合法 root（detector 回傳的就是這條路徑）。"""
    monkeypatch.setattr("ching_tech_os.config.settings.ctos_mount_path", str(tmp_path))
    monkeypatch.setattr("ching_tech_os.config.settings.line_files_nas_path", "")

    # 假裝 bot 已把圖片下載到 /tmp/bot-images（用 monkeypatch 改路徑常數，避免污染真實 /tmp）
    fake_bot_dir = tmp_path / "fake-bot-images"
    fake_bot_dir.mkdir()
    img = fake_bot_dir / "618.jpg"
    img.write_bytes(b"\x89PNG\r\n\x1a\nA")
    monkeypatch.setattr(
        "ching_tech_os.services.mcp.codex_image_tools._BOT_TEMP_IMAGE_DIR",
        fake_bot_dir,
    )

    from ching_tech_os.services.mcp.codex_image_tools import codex_image_tool
    with patch(
        "ching_tech_os.services.mcp.codex_image_tools.generate_image_with_codex",
        new=AsyncMock(return_value=("ai-images/x.png", None)),
    ) as gen:
        result = await codex_image_tool(
            prompt="edit",
            reference_images=[str(img)],
        )
    gen.assert_awaited_once()
    assert "圖片已生成" in result
