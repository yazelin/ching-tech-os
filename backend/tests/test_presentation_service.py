"""presentation service 測試。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import presentation


@pytest.mark.asyncio
async def test_generate_outline_success_and_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    ok_response = SimpleNamespace(success=True, message='{"title":"T","slides":[]}', error=None)
    monkeypatch.setattr(presentation, "call_claude", AsyncMock(return_value=ok_response))
    outline = await presentation.generate_outline("topic", 3, "uncover")
    assert outline["title"] == "T"

    bad_response = SimpleNamespace(success=True, message='```json\n{bad json}\n```', error=None)
    monkeypatch.setattr(presentation, "call_claude", AsyncMock(return_value=bad_response))
    with pytest.raises(ValueError):
        await presentation.generate_outline("topic")

    fail_response = SimpleNamespace(success=False, message="", error="failed")
    monkeypatch.setattr(presentation, "call_claude", AsyncMock(return_value=fail_response))
    with pytest.raises(ValueError):
        await presentation.generate_outline("topic")


@pytest.mark.asyncio
async def test_fetch_pexels_and_huggingface_and_nanobanana(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Pexels
    class _Resp:
        def __init__(self, payload=None, content=b"img"):
            self._payload = payload or {}
            self.content = content

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, **_kwargs):
            if "search" in url:
                return _Resp({"photos": [{"src": {"large": "https://img"}}]})
            return _Resp(content=b"pexels-image")

    monkeypatch.setattr(presentation, "PEXELS_API_KEY", "token")
    monkeypatch.setattr(presentation.httpx, "AsyncClient", _Client)
    assert await presentation.fetch_pexels_image("cat") == b"pexels-image"

    class _ClientNoPhoto(_Client):
        async def get(self, *_args, **_kwargs):
            return _Resp({"photos": []})

    monkeypatch.setattr(presentation.httpx, "AsyncClient", _ClientNoPhoto)
    assert await presentation.fetch_pexels_image("none") is None

    monkeypatch.setattr(presentation, "PEXELS_API_KEY", "")
    assert await presentation.fetch_pexels_image("none") is None

    # HuggingFace
    monkeypatch.setattr(presentation, "is_fallback_available", lambda: True)
    monkeypatch.setattr(presentation.settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(presentation.settings, "line_files_nas_path", "")
    img_file = tmp_path / "ai-images" / "a.jpg"
    img_file.parent.mkdir(parents=True, exist_ok=True)
    img_file.write_bytes(b"hf")
    monkeypatch.setattr(presentation, "generate_image_with_flux", AsyncMock(return_value=("ai-images/a.jpg", None)))
    assert await presentation.generate_huggingface_image("robot") == b"hf"

    monkeypatch.setattr(presentation, "generate_image_with_flux", AsyncMock(return_value=(None, "err")))
    assert await presentation.generate_huggingface_image("robot") is None
    monkeypatch.setattr(presentation, "is_fallback_available", lambda: False)
    assert await presentation.generate_huggingface_image("robot") is None

    # Nanobanana
    nb_img = tmp_path / "ai-images" / "b.jpg"
    nb_img.write_bytes(b"nb")
    ok = SimpleNamespace(
        success=True,
        error=None,
        tool_calls=[SimpleNamespace(name="mcp__nanobanana__generate_image", output="ai-images/b.jpg")],
    )
    monkeypatch.setattr(presentation, "call_claude", AsyncMock(return_value=ok))
    assert await presentation.generate_nanobanana_image("tree") == b"nb"

    fail = SimpleNamespace(success=False, error="x", tool_calls=[])
    monkeypatch.setattr(presentation, "call_claude", AsyncMock(return_value=fail))
    assert await presentation.generate_nanobanana_image("tree") is None


@pytest.mark.asyncio
async def test_fetch_image_and_marp_markdown() -> None:
    md = presentation.generate_marp_markdown(
        {
            "slides": [
                {"layout": "title", "title": "封面", "subtitle": "副標題"},
                {"layout": "section", "title": "章節"},
                {"layout": "content", "title": "內容", "content": ["重點：說明"], "image_url": "x"},
            ]
        },
        theme="uncover",
        include_images=True,
    )
    assert "marp: true" in md
    assert "![bg right:40%](x)" in md
    assert presentation.sanitize_filename('a<>:"/\\|?*b') == "ab"


@pytest.mark.asyncio
async def test_generate_html_presentation_success_and_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(presentation.settings, "ctos_mount_path", str(tmp_path / "ctos"))
    monkeypatch.setattr(presentation.settings, "nas_host", "host")
    monkeypatch.setattr(presentation.settings, "nas_user", "user")
    monkeypatch.setattr(presentation.settings, "nas_password", "pass")
    monkeypatch.setattr(presentation.settings, "nas_share", "share")

    # marp-cli 轉換成功（fake subprocess）
    def _fake_run(cmd, capture_output, text, timeout):  # noqa: ARG001
        output_path = Path(cmd[cmd.index("-o") + 1])
        if output_path.suffix == ".html":
            output_path.write_text("<html>ok</html>", encoding="utf-8")
        else:
            output_path.write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    orig_exists = presentation.os.path.exists

    def _fake_exists(path):
        if str(path).endswith("node_modules/.bin/marp"):
            return False
        return orig_exists(path)

    monkeypatch.setattr(presentation.os.path, "exists", _fake_exists)

    class _DummySMB:
        def __init__(self, **_kwargs):
            self.uploaded = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def write_file(self, _share, _path, _data):
            return None

    monkeypatch.setattr(presentation, "SMBService", _DummySMB)

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(presentation, "run_in_smb_pool", _run_pool)

    outline = {"title": "Demo", "slides": [{"layout": "content", "title": "S1", "content": ["A"]}]}
    result = await presentation.generate_html_presentation(
        outline_json=outline,
        include_images=False,
        output_format="html",
    )
    assert result["success"] is True
    assert result["format"] == "html"

    # 上傳失敗 fallback 到本機
    class _FailSMB(_DummySMB):
        def write_file(self, *_args):
            raise RuntimeError("upload failed")

    monkeypatch.setattr(presentation, "SMBService", _FailSMB)
    pdf_result = await presentation.generate_html_presentation(
        outline_json=outline,
        include_images=False,
        output_format="pdf",
    )
    assert pdf_result["format"] == "pdf"


@pytest.mark.asyncio
async def test_generate_html_presentation_marp_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_run(_cmd, **_kwargs):
        return SimpleNamespace(returncode=1, stderr="bad")

    monkeypatch.setattr("subprocess.run", _fail_run)
    monkeypatch.setattr(presentation.os.path, "exists", lambda _p: False)

    with pytest.raises(RuntimeError):
        await presentation.generate_html_presentation(
            outline_json={"title": "T", "slides": []},
            include_images=False,
            output_format="html",
        )
