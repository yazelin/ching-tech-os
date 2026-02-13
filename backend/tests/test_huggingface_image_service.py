"""huggingface_image 向後相容測試。"""

from __future__ import annotations

import pytest

import ching_tech_os.services.huggingface_image as huggingface_image
import ching_tech_os.services.image_fallback as image_fallback


def test_is_fallback_available(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(huggingface_image, "get_hf_token", lambda: "token")
    assert huggingface_image.is_fallback_available() is True

    monkeypatch.setattr(huggingface_image, "get_hf_token", lambda: None)
    assert huggingface_image.is_fallback_available() is False


@pytest.mark.asyncio
async def test_generate_image_fallback_success(monkeypatch: pytest.MonkeyPatch):
    async def _ok(_prompt: str, _error: str):
        return "/tmp/a.png", "hf", None

    monkeypatch.setattr(image_fallback, "generate_image_with_fallback", _ok)
    result = await huggingface_image.generate_image_fallback("cat", "boom")
    assert result == ("/tmp/a.png", True, None)


@pytest.mark.asyncio
async def test_generate_image_fallback_error(monkeypatch: pytest.MonkeyPatch):
    async def _err(_prompt: str, _error: str):
        return None, "hf", "failed"

    monkeypatch.setattr(image_fallback, "generate_image_with_fallback", _err)
    result = await huggingface_image.generate_image_fallback("cat", "boom")
    assert result == (None, True, "failed")


@pytest.mark.asyncio
async def test_generate_image_fallback_not_used(monkeypatch: pytest.MonkeyPatch):
    async def _none(_prompt: str, _error: str):
        return None, "none", None

    monkeypatch.setattr(image_fallback, "generate_image_with_fallback", _none)
    result = await huggingface_image.generate_image_fallback("cat", "boom")
    assert result == (None, False, None)
