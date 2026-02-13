"""bot.media 網路圖片與工具函式測試。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import ching_tech_os.services.bot.media as media


def test_is_document_file_empty_and_ensure_temp_dir(tmp_path: Path):
    assert media.is_document_file("") is False
    assert media.is_document_file(None) is False

    target = tmp_path / "nested" / "folder"
    media.ensure_temp_dir(str(target))
    assert target.exists()


def test_extract_image_urls_dedup():
    text = (
        "參考圖 https://a.example.com/cat.jpg "
        "重複 https://a.example.com/cat.jpg "
        "以及 https://b.example.com/dog.png?size=1 "
        "和非圖檔 https://c.example.com/page.html"
    )
    urls = media.extract_image_urls(text)
    assert urls == [
        "https://a.example.com/cat.jpg",
        "https://b.example.com/dog.png?size=1",
    ]


class _FakeAsyncClient:
    def __init__(self, response=None, error: Exception | None = None, **_kwargs):
        self._response = response
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False

    async def get(self, _url: str):
        if self._error:
            raise self._error
        return self._response


@pytest.mark.asyncio
async def test_download_image_from_url_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(media, "DOWNLOADED_IMAGE_DIR", str(tmp_path))
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "image/png"},
        content=b"img-bytes",
    )

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(response=response, **kwargs))

    file_path = await media.download_image_from_url("https://example.com/pic.png?x=1")
    assert file_path is not None
    assert file_path.endswith(".png")
    assert Path(file_path).read_bytes() == b"img-bytes"


@pytest.mark.asyncio
async def test_download_image_from_url_non_200(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(media, "DOWNLOADED_IMAGE_DIR", str(tmp_path))
    response = SimpleNamespace(
        status_code=404,
        headers={"content-type": "image/jpeg"},
        content=b"",
    )

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(response=response, **kwargs))
    assert await media.download_image_from_url("https://example.com/missing.jpg") is None


@pytest.mark.asyncio
async def test_download_image_from_url_non_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(media, "DOWNLOADED_IMAGE_DIR", str(tmp_path))
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "text/html"},
        content=b"<html></html>",
    )

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(response=response, **kwargs))
    assert await media.download_image_from_url("https://example.com/not-image.jpg") is None


@pytest.mark.asyncio
async def test_download_image_from_url_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(media, "DOWNLOADED_IMAGE_DIR", str(tmp_path))

    import httpx

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(error=RuntimeError("boom"), **kwargs),
    )
    assert await media.download_image_from_url("https://example.com/error.webp") is None
