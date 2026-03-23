"""測試 image_fallback.py 未覆蓋的部分"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ching_tech_os.services.image_fallback import (
    get_hf_token,
    generate_image_with_huggingface,
    generate_image_with_fallback,
    get_fallback_notification,
)


class TestGetHfToken:
    def test_with_token(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-test")
        assert get_hf_token() == "hf-test"

    def test_without_token(self, monkeypatch):
        monkeypatch.delenv("HUGGINGFACE_API_TOKEN", raising=False)
        assert get_hf_token() is None


class TestGenerateImageWithHuggingface:
    @pytest.mark.asyncio
    async def test_no_token(self, monkeypatch):
        monkeypatch.delenv("HUGGINGFACE_API_TOKEN", raising=False)
        path, err = await generate_image_with_huggingface("test")
        assert path is None
        assert "HUGGINGFACE_API_TOKEN" in err

    @pytest.mark.asyncio
    async def test_import_error(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-test")
        with patch(
            "builtins.__import__",
            side_effect=_selective_import_error("huggingface_hub"),
        ):
            path, err = await generate_image_with_huggingface("test")
            assert path is None
            assert "huggingface_hub" in err

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-test")

        mock_image = MagicMock()
        mock_client = MagicMock()
        mock_client.text_to_image.return_value = mock_image

        with patch(
            "huggingface_hub.InferenceClient",
            return_value=mock_client,
            create=True,
        ):
            with patch(
                "ching_tech_os.services.image_fallback._nas_ai_images_dir",
                tmp_path,
            ):
                path, err = await generate_image_with_huggingface("a cat")
                assert err is None
                assert path is not None
                assert "ai-images/" in path

    @pytest.mark.asyncio
    async def test_auth_error(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-bad")

        mock_client = MagicMock()
        mock_client.text_to_image.side_effect = Exception("401 Unauthorized")

        with patch(
            "huggingface_hub.InferenceClient",
            return_value=mock_client,
            create=True,
        ):
            path, err = await generate_image_with_huggingface("test")
            assert path is None
            assert "Token 無效" in err

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-test")

        mock_client = MagicMock()
        mock_client.text_to_image.side_effect = Exception("429 rate limit exceeded")

        with patch(
            "huggingface_hub.InferenceClient",
            return_value=mock_client,
            create=True,
        ):
            path, err = await generate_image_with_huggingface("test")
            assert path is None
            assert "速率限制" in err

    @pytest.mark.asyncio
    async def test_timeout_error(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-test")

        mock_client = MagicMock()
        mock_client.text_to_image.side_effect = Exception("connection timeout")

        with patch(
            "huggingface_hub.InferenceClient",
            return_value=mock_client,
            create=True,
        ):
            path, err = await generate_image_with_huggingface("test")
            assert path is None
            assert "超時" in err

    @pytest.mark.asyncio
    async def test_generic_error(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-test")

        mock_client = MagicMock()
        mock_client.text_to_image.side_effect = Exception("something broke")

        with patch(
            "huggingface_hub.InferenceClient",
            return_value=mock_client,
            create=True,
        ):
            path, err = await generate_image_with_huggingface("test")
            assert path is None
            assert "Hugging Face 錯誤" in err


class TestGenerateImageWithFallback:
    @pytest.mark.asyncio
    async def test_hf_success(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-test")

        with patch(
            "ching_tech_os.services.image_fallback.generate_image_with_huggingface",
            new_callable=AsyncMock,
            return_value=("ai-images/test.png", None),
        ):
            path, service, err = await generate_image_with_fallback(
                "test", nanobanana_error="timeout"
            )
            assert path == "ai-images/test.png"
            assert service == "Hugging Face FLUX"
            assert err is None

    @pytest.mark.asyncio
    async def test_all_fail(self, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf-test")

        with patch(
            "ching_tech_os.services.image_fallback.generate_image_with_huggingface",
            new_callable=AsyncMock,
            return_value=(None, "HF 錯誤"),
        ):
            path, service, err = await generate_image_with_fallback(
                "test", nanobanana_error="nanobanana 錯誤"
            )
            assert path is None
            assert "nanobanana" in err
            assert "Hugging Face" in err

    @pytest.mark.asyncio
    async def test_no_hf_token(self, monkeypatch):
        monkeypatch.delenv("HUGGINGFACE_API_TOKEN", raising=False)

        path, service, err = await generate_image_with_fallback("test")
        assert path is None
        assert "沒有可用" in err

    @pytest.mark.asyncio
    async def test_no_errors_no_services(self, monkeypatch):
        monkeypatch.delenv("HUGGINGFACE_API_TOKEN", raising=False)

        path, service, err = await generate_image_with_fallback("test")
        assert err is not None


class TestGetFallbackNotification:
    def test_flux_service(self):
        assert get_fallback_notification("Hugging Face FLUX") == "（使用備用服務）"

    def test_other_service(self):
        assert get_fallback_notification("nanobanana") is None

    def test_empty(self):
        assert get_fallback_notification("") is None


def _selective_import_error(blocked: str):
    _original = __import__

    def _side_effect(name, *args, **kwargs):
        if name == blocked:
            raise ImportError(f"No module named '{blocked}'")
        return _original(name, *args, **kwargs)

    return _side_effect
