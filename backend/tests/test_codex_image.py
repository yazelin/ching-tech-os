"""Codex Image Service client 單元測試（mock httpx，不打真 HTTP）。"""

import base64
import struct
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ching_tech_os.services.codex_image import (
    _CODEX_SIZE_BY_ASPECT,
    edit_image_with_codex,
    generate_image_with_codex,
    is_codex_image_available,
)


# ─ helpers ──────────────────────────────────────────────────────────────────


def _make_png_bytes() -> bytes:
    """最小可解析 1×1 PNG，給 reference / download 用。"""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


@pytest.fixture(autouse=True)
def _codex_settings(monkeypatch, tmp_path):
    """設定 codex 開啟、輸出目錄指向 tmp，避免噴到真實 NAS。"""
    from ching_tech_os.config import settings as cfg
    from ching_tech_os.services import codex_image as mod

    monkeypatch.setattr(cfg, "codex_image_base_url", "https://codex.example.com/codex-image")
    monkeypatch.setattr(cfg, "codex_image_api_key", "cimg_fake-bearer-token-for-test")
    monkeypatch.setattr(cfg, "codex_image_quality", "medium")
    # 不要存到真實 NAS — 改寫 module-level 目錄
    monkeypatch.setattr(mod, "_nas_ai_images_dir", tmp_path / "ai-images")


@pytest.fixture
def codex_disabled(monkeypatch):
    """測試「未設定」分支用的反向 fixture。"""
    from ching_tech_os.config import settings as cfg
    monkeypatch.setattr(cfg, "codex_image_base_url", "")
    monkeypatch.setattr(cfg, "codex_image_api_key", "")


def _mock_post_resp(status: int = 200, json_body: dict | None = None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body or {}
    resp.text = text
    return resp


def _mock_get_resp(status: int = 200, content: bytes = b""):
    resp = MagicMock()
    resp.status_code = status
    resp.content = content
    return resp


class _FakeClient:
    """Replaces httpx.AsyncClient as an async context manager that returns
    pre-canned responses for .post() and .get() calls."""

    def __init__(self, post_resp=None, get_resp=None):
        self._post_resp = post_resp
        self._get_resp = get_resp
        self.post_calls: list[tuple] = []
        self.get_calls: list[tuple] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self._post_resp

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self._get_resp


def _success_payload(image_url: str = "https://codex.example.com/codex-image/generated/ig.png") -> dict:
    return {
        "id": "img_test",
        "status": "succeeded",
        "images": [{"url": image_url, "expires_at": "2099-01-01T00:00:00+00:00"}],
        "created_at": "2026-05-20T00:00:00+00:00",
    }


# ─ tests ────────────────────────────────────────────────────────────────────


class TestAvailability:
    def test_available_when_both_set(self):
        assert is_codex_image_available() is True

    def test_not_available_when_unset(self, codex_disabled):
        assert is_codex_image_available() is False


class TestGenerateText:
    @pytest.mark.asyncio
    async def test_happy_path_saves_to_ai_images(self, tmp_path):
        png = _make_png_bytes()
        post_resp = _mock_post_resp(200, json_body=_success_payload())
        get_resp = _mock_get_resp(200, content=png)
        fake = _FakeClient(post_resp=post_resp, get_resp=get_resp)

        with patch("ching_tech_os.services.codex_image.httpx.AsyncClient",
                   side_effect=lambda **kw: fake):
            path, error = await generate_image_with_codex(
                "a tiny ceramic teacup", aspect_ratio="1:1"
            )

        assert error is None
        assert path is not None
        assert path.startswith("ai-images/codex_") and path.endswith(".png")
        # POST body should carry prompt + size + bearer header
        url, kwargs = fake.post_calls[0]
        assert url == "https://codex.example.com/codex-image/v1/images/generate"
        body = kwargs["json"]
        assert body["prompt"] == "a tiny ceramic teacup"
        assert body["size"] == "1024x1024"
        assert body["quality"] == "medium"
        assert "reference_image_base64" not in body
        assert kwargs["headers"]["Authorization"] == "Bearer cimg_fake-bearer-token-for-test"

    @pytest.mark.asyncio
    async def test_unset_returns_skip_message(self, codex_disabled):
        path, error = await generate_image_with_codex("anything")
        assert path is None
        assert "未設定" in error

    @pytest.mark.asyncio
    async def test_401_surfaces_clear_error(self):
        fake = _FakeClient(post_resp=_mock_post_resp(401, text='{"detail":"Invalid API key"}'))
        with patch("ching_tech_os.services.codex_image.httpx.AsyncClient",
                   side_effect=lambda **kw: fake):
            path, error = await generate_image_with_codex("anything")
        assert path is None
        assert "401" in error and "cimg_" in error

    @pytest.mark.asyncio
    @pytest.mark.parametrize("aspect,expected_size", [
        ("1:1", "1024x1024"),
        ("16:9", "1536x1024"),
        ("9:16", "1024x1536"),
        ("4:3", "1536x1024"),
        ("3:4", "1024x1536"),
    ])
    async def test_aspect_ratio_maps_to_codex_size(self, aspect, expected_size):
        post_resp = _mock_post_resp(200, json_body=_success_payload())
        get_resp = _mock_get_resp(200, content=_make_png_bytes())
        fake = _FakeClient(post_resp=post_resp, get_resp=get_resp)
        with patch("ching_tech_os.services.codex_image.httpx.AsyncClient",
                   side_effect=lambda **kw: fake):
            await generate_image_with_codex("test", aspect_ratio=aspect)
        assert fake.post_calls[0][1]["json"]["size"] == expected_size


class TestEdit:
    @pytest.mark.asyncio
    async def test_edit_passes_base64_reference_in_body(self):
        ref_bytes = _make_png_bytes()
        post_resp = _mock_post_resp(200, json_body=_success_payload())
        get_resp = _mock_get_resp(200, content=_make_png_bytes())
        fake = _FakeClient(post_resp=post_resp, get_resp=get_resp)
        with patch("ching_tech_os.services.codex_image.httpx.AsyncClient",
                   side_effect=lambda **kw: fake):
            path, error = await generate_image_with_codex(
                "replace the background", reference_bytes=ref_bytes
            )
        assert error is None
        body = fake.post_calls[0][1]["json"]
        assert "reference_image_base64" in body
        assert base64.b64decode(body["reference_image_base64"]) == ref_bytes

    @pytest.mark.asyncio
    async def test_edit_helper_reads_file_off_disk(self, tmp_path):
        ref_path = tmp_path / "ref.png"
        ref_bytes = _make_png_bytes()
        ref_path.write_bytes(ref_bytes)

        post_resp = _mock_post_resp(200, json_body=_success_payload())
        get_resp = _mock_get_resp(200, content=_make_png_bytes())
        fake = _FakeClient(post_resp=post_resp, get_resp=get_resp)
        with patch("ching_tech_os.services.codex_image.httpx.AsyncClient",
                   side_effect=lambda **kw: fake):
            path, error = await edit_image_with_codex(
                "tweak it", reference_path=str(ref_path)
            )
        assert error is None
        body = fake.post_calls[0][1]["json"]
        assert base64.b64decode(body["reference_image_base64"]) == ref_bytes

    @pytest.mark.asyncio
    async def test_edit_helper_missing_file_returns_error(self):
        path, error = await edit_image_with_codex(
            "tweak it", reference_path="/nonexistent/file.png"
        )
        assert path is None
        assert "不存在" in error
