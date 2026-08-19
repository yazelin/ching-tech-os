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
    """3.2 parity：outline 走 call_ai，JSON 契約（fence 剝除/壞 JSON/失敗）不變。"""
    ok_response = SimpleNamespace(success=True, message='{"title":"T","slides":[]}', error=None)
    call_ai_mock = AsyncMock(return_value=ok_response)
    monkeypatch.setattr(presentation, "call_ai", call_ai_mock)
    outline = await presentation.generate_outline("topic", 3, "uncover")
    assert outline["title"] == "T"
    # routing context 用 caller 事實；model role 維持 sonnet
    kwargs = call_ai_mock.await_args.kwargs
    assert kwargs["routing_context"].context_type == "presentation"
    assert kwargs["model"] == "sonnet"

    # markdown fence 剝除後仍是壞 JSON → ValueError（不得產生格式錯誤的簡報）
    bad_response = SimpleNamespace(success=True, message='```json\n{bad json}\n```', error=None)
    monkeypatch.setattr(presentation, "call_ai", AsyncMock(return_value=bad_response))
    with pytest.raises(ValueError):
        await presentation.generate_outline("topic")

    fail_response = SimpleNamespace(success=False, message="", error="failed")
    monkeypatch.setattr(presentation, "call_ai", AsyncMock(return_value=fail_response))
    with pytest.raises(ValueError):
        await presentation.generate_outline("topic")

    # fence 有效剝除的正常路徑（Codex 常見回覆形式）
    fenced_ok = SimpleNamespace(
        success=True, message='```json\n{"title":"F","slides":[]}\n```', error=None
    )
    monkeypatch.setattr(presentation, "call_ai", AsyncMock(return_value=fenced_ok))
    outline = await presentation.generate_outline("topic")
    assert outline["title"] == "F"


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
async def test_fetch_pexels_image_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pexels API 出錯（連線失敗等）時回傳 None，不往外拋。"""

    class _BoomClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(presentation, "PEXELS_API_KEY", "token")
    monkeypatch.setattr(presentation.httpx, "AsyncClient", _BoomClient)
    assert await presentation.fetch_pexels_image("cat") is None


@pytest.mark.asyncio
async def test_generate_huggingface_image_read_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """FLUX 回傳路徑但檔案不存在 → 讀檔例外 → 回傳 None。"""
    monkeypatch.setattr(presentation, "is_fallback_available", lambda: True)
    monkeypatch.setattr(presentation.settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(presentation.settings, "line_files_nas_path", "")
    monkeypatch.setattr(
        presentation,
        "generate_image_with_flux",
        AsyncMock(return_value=("ai-images/not-exist.jpg", None)),
    )
    assert await presentation.generate_huggingface_image("robot") is None


@pytest.mark.asyncio
async def test_generate_nanobanana_image_edge_cases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Nanobanana 路徑轉換、無有效路徑、例外三種分支。"""
    monkeypatch.setattr(presentation.settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(presentation.settings, "line_files_nas_path", "")

    # nanobanana-output/ 路徑要轉成 ai-images/ 再讀檔
    img = tmp_path / "ai-images" / "c.jpg"
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_bytes(b"nb-converted")
    ok = SimpleNamespace(
        success=True,
        error=None,
        tool_calls=[
            SimpleNamespace(
                name="mcp__nanobanana__generate_image",
                output="生成完成 /tmp/xxx/nanobanana-output/c.jpg",
            )
        ],
    )
    monkeypatch.setattr(presentation, "call_claude", AsyncMock(return_value=ok))
    assert await presentation.generate_nanobanana_image("tree") == b"nb-converted"

    # tool_calls 沒有可解析的圖片路徑 → None
    no_path = SimpleNamespace(
        success=True,
        error=None,
        tool_calls=[SimpleNamespace(name="mcp__nanobanana__generate_image", output="沒有路徑")],
    )
    monkeypatch.setattr(presentation, "call_claude", AsyncMock(return_value=no_path))
    assert await presentation.generate_nanobanana_image("tree") is None

    # call_claude 例外 → None
    monkeypatch.setattr(presentation, "call_claude", AsyncMock(side_effect=RuntimeError("boom")))
    assert await presentation.generate_nanobanana_image("tree") is None


@pytest.mark.asyncio
async def test_generate_codex_image_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Codex 配圖：未設定、成功、失敗、例外四種分支。"""
    from ching_tech_os.services import codex_image

    monkeypatch.setattr(presentation.settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(presentation.settings, "line_files_nas_path", "")

    # 未設定 codex-image-service → None
    monkeypatch.setattr(codex_image, "is_codex_image_available", lambda: False)
    assert await presentation.generate_codex_image("cat") is None

    # 成功：回傳圖片 bytes
    monkeypatch.setattr(codex_image, "is_codex_image_available", lambda: True)
    img = tmp_path / "ai-images" / "cx.png"
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_bytes(b"codex-img")
    monkeypatch.setattr(
        codex_image,
        "generate_image_with_codex",
        AsyncMock(return_value=("ai-images/cx.png", None)),
    )
    assert await presentation.generate_codex_image("cat") == b"codex-img"

    # 服務回傳錯誤 → None
    monkeypatch.setattr(
        codex_image,
        "generate_image_with_codex",
        AsyncMock(return_value=(None, "quota exceeded")),
    )
    assert await presentation.generate_codex_image("cat") is None

    # 呼叫例外 → None
    monkeypatch.setattr(
        codex_image,
        "generate_image_with_codex",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    assert await presentation.generate_codex_image("cat") is None


@pytest.mark.asyncio
async def test_fetch_image_source_ladder(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_image 的來源階梯：pexels 直走、codex → nanobanana → huggingface。"""
    pexels = AsyncMock(return_value=b"pexels")
    monkeypatch.setattr(presentation, "fetch_pexels_image", pexels)

    # source=pexels 直接走 Pexels，不碰 AI 生圖
    codex = AsyncMock(return_value=None)
    monkeypatch.setattr(presentation, "generate_codex_image", codex)
    assert await presentation.fetch_image("cat", "pexels") == b"pexels"
    codex.assert_not_awaited()

    # codex 成功 → 直接回傳，不往下走
    monkeypatch.setattr(presentation, "generate_codex_image", AsyncMock(return_value=b"codex"))
    nano = AsyncMock(return_value=b"nano")
    hf = AsyncMock(return_value=b"hf")
    monkeypatch.setattr(presentation, "generate_nanobanana_image", nano)
    monkeypatch.setattr(presentation, "generate_huggingface_image", hf)
    assert await presentation.fetch_image("cat", "nanobanana") == b"codex"
    nano.assert_not_awaited()

    # codex 失敗 + 明確指定 huggingface → 直接走 HF
    monkeypatch.setattr(presentation, "generate_codex_image", AsyncMock(return_value=None))
    assert await presentation.fetch_image("cat", "huggingface") == b"hf"
    nano.assert_not_awaited()

    # codex 失敗 + nanobanana 成功 → 回傳 nanobanana
    assert await presentation.fetch_image("cat", "nanobanana") == b"nano"

    # codex、nanobanana 都失敗 → 最後備援 huggingface
    monkeypatch.setattr(presentation, "generate_nanobanana_image", AsyncMock(return_value=None))
    assert await presentation.fetch_image("cat", "nanobanana") == b"hf"


@pytest.mark.asyncio
async def test_generate_html_presentation_with_images_and_outline_str(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """outline_json 傳字串、include_images 配圖成功/失敗、本地 marp bin 分支。"""
    monkeypatch.setattr(presentation.settings, "ctos_mount_path", str(tmp_path / "ctos"))
    monkeypatch.setattr(presentation.settings, "nas_host", "host")
    monkeypatch.setattr(presentation.settings, "nas_user", "user")
    monkeypatch.setattr(presentation.settings, "nas_password", "pass")
    monkeypatch.setattr(presentation.settings, "nas_share", "share")

    def _fake_run(cmd, capture_output, text, timeout):  # noqa: ARG001
        # 確認走本地 marp bin（不是 npx）
        assert cmd[0].endswith("node_modules/.bin/marp")
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text("<html>ok</html>", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    orig_exists = presentation.os.path.exists

    def _fake_exists(path):
        # 假裝本地 marp bin 存在，走 480 行的本地執行分支
        if str(path).endswith("node_modules/.bin/marp"):
            return True
        return orig_exists(path)

    monkeypatch.setattr(presentation.os.path, "exists", _fake_exists)

    class _DummySMB:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def write_file(self, *_args):
            return None

    monkeypatch.setattr(presentation, "SMBService", _DummySMB)

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(presentation, "run_in_smb_pool", _run_pool)

    # 配圖：第一張成功、第二張失敗（不設 image_url）
    fetch = AsyncMock(side_effect=[b"img-bytes", None])
    monkeypatch.setattr(presentation, "fetch_image", fetch)

    outline = {
        "title": "Demo",
        "slides": [
            {"layout": "title", "title": "封面"},
            {"layout": "content", "title": "S1", "content": ["A"], "image_keyword": "cat"},
            {"layout": "content", "title": "S2", "content": ["B"], "image_keyword": "dog"},
        ],
    }
    result = await presentation.generate_html_presentation(
        outline_json=json.dumps(outline),
        include_images=True,
        image_source="pexels",
        output_format="html",
    )
    assert result["success"] is True
    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_generate_html_presentation_from_topic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """未傳 outline_json 時，走 generate_outline 產生大綱。"""
    monkeypatch.setattr(presentation.settings, "ctos_mount_path", str(tmp_path / "ctos"))
    monkeypatch.setattr(presentation.settings, "nas_host", "host")
    monkeypatch.setattr(presentation.settings, "nas_user", "user")
    monkeypatch.setattr(presentation.settings, "nas_password", "pass")
    monkeypatch.setattr(presentation.settings, "nas_share", "share")

    outline = {"title": "主題簡報", "slides": [{"layout": "title", "title": "封面"}]}
    gen_outline = AsyncMock(return_value=outline)
    monkeypatch.setattr(presentation, "generate_outline", gen_outline)

    def _fake_run(cmd, capture_output, text, timeout):  # noqa: ARG001
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text("<html>ok</html>", encoding="utf-8")
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
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def write_file(self, *_args):
            return None

    monkeypatch.setattr(presentation, "SMBService", _DummySMB)

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(presentation, "run_in_smb_pool", _run_pool)

    result = await presentation.generate_html_presentation(
        topic="我的主題",
        include_images=False,
        output_format="html",
    )
    assert result["title"] == "主題簡報"
    gen_outline.assert_awaited_once()


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
