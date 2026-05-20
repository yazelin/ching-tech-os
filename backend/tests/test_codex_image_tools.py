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
