"""ClawHub client 測試。"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from ching_tech_os.services.clawhub_client import (
    ClawHubClient,
    ClawHubError,
    _MAX_ZIP_SIZE,
    get_clawhub_client_di,
    validate_slug,
)


class _FakeResponse:
    def __init__(self, payload=None, status_code: int = 200):
        self._payload = payload or {}
        self.status_code = status_code
        self.request = httpx.Request("GET", "https://example.com")
        self.response = httpx.Response(status_code, request=self.request)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=self.request,
                response=self.response,
            )

    def json(self):
        return self._payload


class _FakeStreamResponse:
    def __init__(self, chunks: list[bytes], status_code: int = 200):
        self._chunks = chunks
        self.status_code = status_code
        self.request = httpx.Request("GET", "https://example.com/download")
        self.response = httpx.Response(status_code, request=self.request)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=self.request,
                response=self.response,
            )

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeClient:
    def __init__(self, get_response: _FakeResponse | None = None, chunks: list[bytes] | None = None):
        self._get_response = get_response or _FakeResponse({})
        self._chunks = chunks or [b"ok"]

    async def get(self, *_args, **_kwargs):
        return self._get_response

    def stream(self, *_args, **_kwargs):
        return _FakeStreamResponse(self._chunks)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_search_and_get_skill_success() -> None:
    client = ClawHubClient(base_url="https://example.com")
    await client._client.aclose()
    client._client = _FakeClient(get_response=_FakeResponse({"results": [{"slug": "demo"}]}))
    assert await client.search("demo") == [{"slug": "demo"}]

    client._client = _FakeClient(get_response=_FakeResponse({"skill": {"slug": "demo"}}))
    assert (await client.get_skill("demo"))["skill"]["slug"] == "demo"


@pytest.mark.asyncio
async def test_search_and_get_skill_errors() -> None:
    client = ClawHubClient(base_url="https://example.com")
    await client._client.aclose()
    client._client = _FakeClient(get_response=_FakeResponse(status_code=500))
    with pytest.raises(ClawHubError):
        await client.search("x")

    client._client = _FakeClient(get_response=_FakeResponse(status_code=404))
    with pytest.raises(ClawHubError):
        await client.get_skill("missing")


@pytest.mark.asyncio
async def test_download_zip_and_extract_file(tmp_path: Path) -> None:
    client = ClawHubClient(base_url="https://example.com")
    await client._client.aclose()
    client._client = _FakeClient(chunks=[b"abc", b"def"])

    zip_path = await client.download_zip("demo", "1.0.0")
    assert zip_path.exists()
    assert zip_path.read_bytes() == b"abcdef"
    zip_path.unlink()

    # 測試 extract_file_from_zip（使用 zip_data，避免再走下載）
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("SKILL.md", "# Demo")
    text = await client.extract_file_from_zip("demo", "1.0.0", "SKILL.md", zip_data=buf.getvalue())
    assert text == "# Demo"

    missing = await client.extract_file_from_zip("demo", "1.0.0", "NOPE.md", zip_data=buf.getvalue())
    assert missing is None


@pytest.mark.asyncio
async def test_download_zip_too_large(tmp_path: Path) -> None:
    client = ClawHubClient(base_url="https://example.com")
    await client._client.aclose()
    client._client = _FakeClient(chunks=[b"x" * (_MAX_ZIP_SIZE + 1)])

    with pytest.raises(ClawHubError, match="ZIP 檔案過大"):
        await client.download_zip("demo", "1.0.0")


@pytest.mark.asyncio
async def test_download_and_extract_with_zip_slip_protection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = ClawHubClient(base_url="https://example.com")

    # 安全 ZIP
    safe_zip = tmp_path / "safe.zip"
    with zipfile.ZipFile(safe_zip, "w") as zf:
        zf.writestr("folder/SKILL.md", "ok")

    async def _download_safe(_slug: str, _version: str) -> Path:
        return safe_zip

    monkeypatch.setattr(client, "download_zip", _download_safe)
    result = await client.download_and_extract("demo", "1.0.0", tmp_path / "out")
    assert result["slug"] == "demo"
    assert (tmp_path / "out" / "folder" / "SKILL.md").exists()

    # Zip Slip
    slip_zip = tmp_path / "slip.zip"
    with zipfile.ZipFile(slip_zip, "w") as zf:
        zf.writestr("../evil.txt", "bad")

    async def _download_slip(_slug: str, _version: str) -> Path:
        return slip_zip

    monkeypatch.setattr(client, "download_zip", _download_slip)
    with pytest.raises(ClawHubError, match="Zip slip"):
        await client.download_and_extract("demo", "1.0.0", tmp_path / "out2")


def test_validate_slug_and_di() -> None:
    assert validate_slug("valid-slug-1") is True
    assert validate_slug("InvalidSlug") is False
    assert validate_slug("x" * 101) is False

    fake_client = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(clawhub_client=fake_client)))
    assert get_clawhub_client_di(request) is fake_client
