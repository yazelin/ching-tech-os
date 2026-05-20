# Multi-Image Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-image edit support (composition / outfit-swap / scene-merge / style-transfer) to ching-tech-os LINE + Telegram bots, mirroring the capability already shipped in ctos-lite. Also lift the artificial 4-image cap on `codex-image-service` and `ctos-lite` for consistency.

**Architecture:** Unify `codex_generate_image_tool` + `codex_edit_image_tool` MCP into one `codex_image_tool(prompt, reference_images: list[str] | None)`. `generate_image_with_codex` accepts `reference_bytes_list: list[bytes]` and POSTs `reference_images_base64` array to codex-image-service. LINE and Telegram handlers gain a shared `_detect_image_edit_references` that returns 0-N reference paths via SQL queries (hybrid rule: quoted-reply → 1 image; else edit-keyword + post-last-text-message images → N images). Telegram adds a special `media_group_id` branch for native albums. Bot-generated images become quotable references by adding them to `bot_files`. No client-side count cap — OpenAI / nanobanana decide the real ceiling.

**Tech Stack:** Python 3.11+, FastAPI, asyncpg, FastMCP, pytest + pytest-asyncio, httpx (test mocking via respx/MonkeyPatch).

**Companion spec:** `docs/superpowers/specs/2026-05-20-multi-image-edit-design.md`

---

## File Structure (decomposition decisions)

**Modify:**
- `backend/src/ching_tech_os/services/codex_image.py` — `generate_image_with_codex` accepts `reference_bytes_list: list[bytes] | None`; delete `edit_image_with_codex` (thin wrapper, no longer needed since the unified tool resolves paths upstream).
- `backend/src/ching_tech_os/services/mcp/codex_image_tools.py` — replace the two `@mcp.tool()` functions with one unified `codex_image_tool`.
- `backend/src/ching_tech_os/services/linebot_ai.py` — swap `quoted_image_path = ...` block with shared detector call; update system-prompt injection (lines ~822-838) to name only the unified tool; change `[回覆圖片: ...]` marker to `[N 張參考圖: ...]` for the multi-image case.
- `backend/src/ching_tech_os/services/bot_telegram/handler.py` — equivalent wiring for the text-message branch; add Telegram album (`media_group_id`) special branch in the detector helper.
- `backend/src/ching_tech_os/services/bot_line/message_store.py` (or whichever module replies with generated images) — insert a `bot_files` row when the bot sends a generated image, so future quoted-reply-to-bot-image becomes valid.

**Create:**
- `backend/src/ching_tech_os/services/image_edit_detection.py` — shared `_detect_image_edit_references(...)` + `_IMAGE_EDIT_KEYWORDS`. Both LINE and Telegram handlers import it.

**Test:**
- `backend/tests/test_codex_image.py` — update `TestEdit::test_edit_passes_base64_reference_in_body` for new signature; delete `TestEdit::test_edit_helper_*` tests; add multi-image payload tests.
- `backend/tests/test_image_edit_detection.py` (new) — unit tests for the detector against an asyncpg connection (using existing test DB fixture).
- `backend/tests/test_codex_image_tools.py` (new) — unit tests for the unified MCP tool wrapper.
- `backend/tests/test_telegram_media_group.py` (new) — Telegram album branch test.

**Out of scope (per spec §3):**
- `services/presentation.py` (zero traffic in 30 days)
- nanobanana `edit_image` MCP tool (stays single-reference)
- `services/image_fallback.py` (FLUX is text-only; existing signature already drops references naturally)

---

## Setup (do once before Task 1)

- [ ] **Confirm worktree + venv**

```bash
cd /home/ct/SDD/ching-tech-os
git status --short   # main has WIP on transcribe.py + untracked fishtool screenshots — leave alone
git worktree add .worktrees/multi-image-edit -b feat/multi-image-edit main
cd .worktrees/multi-image-edit
ls backend/.venv/bin/python   # confirm venv exists via main checkout's path
```

The worktree shares the main checkout's `backend/.venv` (editable install reads source from the worktree). Run all tests with:

```bash
cd /home/ct/SDD/ching-tech-os/.worktrees/multi-image-edit/backend
./.venv/bin/python -m pytest ...
```

Baseline: `./.venv/bin/python -m pytest tests/test_codex_image.py tests/test_image_fallback.py tests/test_huggingface_image_service.py -q` should be all green before any edits.

---

## Task 1: `generate_image_with_codex` accepts a list of reference bytes

**Files:**
- Modify: `backend/src/ching_tech_os/services/codex_image.py` (the `generate_image_with_codex` function, lines 44-138; delete `edit_image_with_codex` lines 141-164)
- Test: `backend/tests/test_codex_image.py`

- [ ] **Step 1: Write the failing tests**

Replace the `TestEdit` class in `backend/tests/test_codex_image.py` with:

```python
class TestEdit:
    """Multi-image reference plumbing in generate_image_with_codex."""

    @pytest.mark.asyncio
    async def test_single_reference_sent_as_one_element_array(self):
        ref_bytes = b"\x89PNG\r\n\x1a\nA"
        with patch_codex_post(_ok_response()) as captured:
            await generate_image_with_codex(
                "make it black and white",
                reference_bytes_list=[ref_bytes],
            )
        body = captured["json"]
        assert "reference_images_base64" in body
        assert len(body["reference_images_base64"]) == 1
        assert base64.b64decode(body["reference_images_base64"][0]) == ref_bytes
        # Legacy singular field must not be set
        assert "reference_image_base64" not in body

    @pytest.mark.asyncio
    async def test_three_references_sent_as_array(self):
        refs = [b"\x89PNG\r\n\x1a\nA", b"\x89PNG\r\n\x1a\nB", b"\x89PNG\r\n\x1a\nC"]
        with patch_codex_post(_ok_response()) as captured:
            await generate_image_with_codex(
                "composite these",
                reference_bytes_list=refs,
            )
        body = captured["json"]
        assert "reference_images_base64" in body
        assert len(body["reference_images_base64"]) == 3
        for i, raw in enumerate(refs):
            assert base64.b64decode(body["reference_images_base64"][i]) == raw

    @pytest.mark.asyncio
    async def test_empty_or_none_omits_field_entirely(self):
        for case in (None, []):
            with patch_codex_post(_ok_response()) as captured:
                await generate_image_with_codex(
                    "pure text-to-image",
                    reference_bytes_list=case,
                )
            body = captured["json"]
            assert "reference_images_base64" not in body
            assert "reference_image_base64" not in body
```

Add these two helpers near the top of the test file (above the test classes), after the existing fixtures:

```python
from contextlib import contextmanager
from unittest.mock import patch, AsyncMock


def _ok_response():
    """Build a fake httpx response shape codex-image-service returns on success."""
    fake_resp = AsyncMock()
    fake_resp.status_code = 200
    fake_resp.json = lambda: {
        "images": [{"url": "http://fake/img.png"}],
    }
    fake_resp.text = ""
    return fake_resp


def _ok_download():
    fake_dl = AsyncMock()
    fake_dl.status_code = 200
    fake_dl.content = b"\x89PNG\r\n\x1a\nFAKE"
    return fake_dl


@contextmanager
def patch_codex_post(post_resp):
    """Patch both httpx.AsyncClient.post (the generate call) and .get (PNG download).

    Captured payload exposed as captured['json']."""
    captured = {}

    async def _post(self, url, json=None, headers=None):
        captured["json"] = json
        captured["url"] = url
        return post_resp

    async def _get(self, url):
        return _ok_download()

    with patch("httpx.AsyncClient.post", new=_post), \
         patch("httpx.AsyncClient.get", new=_get):
        yield captured
```

Also delete the obsolete tests in the same file (lines around 197–221):

```python
# DELETE:
#   TestEdit.test_edit_helper_reads_file_off_disk
#   TestEdit.test_edit_helper_missing_file_returns_error
# Reason: edit_image_with_codex is removed in this task; path resolution
# moves into the MCP tool layer (Task 2).
```

And update the existing `TestEdit.test_edit_passes_base64_reference_in_body` (line 182) — fold its assertion into `test_single_reference_sent_as_one_element_array` above.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/ct/SDD/ching-tech-os/.worktrees/multi-image-edit/backend
./.venv/bin/python -m pytest tests/test_codex_image.py::TestEdit -v
```

Expected: `TypeError: generate_image_with_codex() got an unexpected keyword argument 'reference_bytes_list'`.

- [ ] **Step 3: Update `generate_image_with_codex`**

In `backend/src/ching_tech_os/services/codex_image.py`, replace the function signature and the payload-build block:

```python
async def generate_image_with_codex(
    prompt: str,
    aspect_ratio: str = "1:1",
    reference_bytes_list: list[bytes] | None = None,
) -> tuple[str | None, str | None]:
    """呼叫 codex-image-service 產圖；給 reference_bytes_list 時走 edit mode。

    Args:
        prompt: 生圖 / 編輯指令
        aspect_ratio: 1:1 / 4:3 / 3:4 / 16:9 / 9:16 / 21:9
        reference_bytes_list: 1+ 張參考圖 bytes（None / [] = 純文字生圖）
            無張數上限；codex-image-service / OpenAI 自己拒絕超量。
            單張 10 MB 的限制在 MCP tool 層做（這層不檢查 size）。

    Returns:
        (image_path, error_message)
          - 成功: ("ai-images/codex_xxxxxxxx.png", None)
          - 失敗: (None, "人類可讀錯誤")
    """
    if not is_codex_image_available():
        return None, "未設定 CODEX_IMAGE_BASE_URL / CODEX_IMAGE_API_KEY"

    base_url = settings.codex_image_base_url.rstrip("/")
    api_key = settings.codex_image_api_key
    size = _CODEX_SIZE_BY_ASPECT.get(aspect_ratio, "1024x1024")

    reference_bytes_list = reference_bytes_list or []

    payload: dict = {
        "prompt": prompt,
        "size": size,
        "quality": settings.codex_image_quality or "medium",
        "count": 1,
    }
    if reference_bytes_list:
        payload["reference_images_base64"] = [
            base64.b64encode(b).decode("ascii") for b in reference_bytes_list
        ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info(
        "Codex 生圖 (mode=%s, refs=%d, aspect=%s, prompt=%s...)",
        "edit" if reference_bytes_list else "generate",
        len(reference_bytes_list),
        aspect_ratio,
        prompt[:60],
    )

    # ... rest of the function body (try/except httpx.post, 401/403/200 handling,
    # download PNG, write to NAS) stays IDENTICAL to current code from line 89 onwards.
```

Then **delete** the entire `edit_image_with_codex` function (lines 141-164). It is no longer used; path resolution moves into the MCP tool wrapper in Task 2.

- [ ] **Step 4: Run tests to verify they pass**

```bash
./.venv/bin/python -m pytest tests/test_codex_image.py -v
```

Expected: 3 new `TestEdit` tests pass; the existing `TestGenerateText` tests (text-to-image flow) still pass.

- [ ] **Step 5: Commit**

```bash
cd /home/ct/SDD/ching-tech-os/.worktrees/multi-image-edit
git add backend/src/ching_tech_os/services/codex_image.py backend/tests/test_codex_image.py
git commit -m "feat(codex_image): accept reference_bytes_list and send array payload

Replace singular reference_bytes with reference_bytes_list, sending
reference_images_base64 as a base64 array to codex-image-service
(which supports 1..N references in edit mode since its PR #1).

No client-side count cap — the OpenAI API is the real ceiling.

Delete edit_image_with_codex (thin path-to-bytes wrapper). Path
resolution moves into the unified MCP tool in the next commit; this
removes a redundant code path."
```

---

## Task 2: Unified `codex_image_tool` MCP

**Files:**
- Modify: `backend/src/ching_tech_os/services/mcp/codex_image_tools.py` (replace both `@mcp.tool()`)
- Test: `backend/tests/test_codex_image_tools.py` (new file)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_codex_image_tools.py`:

```python
"""Unit tests for the unified codex_image_tool MCP wrapper."""

from __future__ import annotations

import base64
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock


@pytest.fixture
def reference_files(tmp_path, monkeypatch):
    """Make two real PNG files in a fake NAS root."""
    from ching_tech_os.config import settings
    monkeypatch.setattr(settings, "linebot_local_path", str(tmp_path))
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
    monkeypatch.setattr(settings, "linebot_local_path", str(tmp_path))
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./.venv/bin/python -m pytest tests/test_codex_image_tools.py -v
```

Expected: `ImportError: cannot import name 'codex_image_tool'` (function doesn't exist yet) for most; the last test passes already-by-accident (the old names still exist) — that's fine, it will pass after refactor anyway.

- [ ] **Step 3: Rewrite `codex_image_tools.py`**

Replace the entire body of `backend/src/ching_tech_os/services/mcp/codex_image_tools.py` with:

```python
"""Codex Image Service 的 MCP 工具包裝（unified text-to-image + 多圖編輯）

一個 `codex_image_tool` 取代過去的 `codex_generate_image_tool` +
`codex_edit_image_tool` — 統一介面、簡化 AI 決策。

工具回傳 `ai-images/<filename>` 相對路徑（與 nanobanana / FLUX 一致），
所以下游分發 / presentation 配圖流程都不用改 dispatch。
"""

from __future__ import annotations

from pathlib import Path

from .server import mcp, logger
from ..codex_image import (
    generate_image_with_codex,
    is_codex_image_available,
)
from ...config import settings


_VALID_ASPECT_RATIOS = {"1:1", "4:3", "3:4", "16:9", "9:16", "21:9"}
_PER_IMAGE_BYTE_LIMIT = 10 * 1024 * 1024   # 10 MB / image (OOM defence)


@mcp.tool()
async def codex_image_tool(
    prompt: str,
    reference_images: list[str] | None = None,
    aspect_ratio: str = "1:1",
) -> str:
    """生成或編輯圖片（一個 tool 三種模式）

    透過自架的 codex-image-service 走 gpt-image-2（OpenAI 內建工具，
    吃主機 ChatGPT 訂閱配額而非 Gemini credits）。失敗時回傳開頭為
    「Codex」的錯誤字串，呼叫端可改試 mcp__nanobanana__* 作為退路。

    Args:
        prompt: 詳細生圖 / 編輯指令
            - 純生圖：自然語言英文 / 中文，越具體越好
            - 編輯 / 合成：用 "image 1 / image 2 / ..." 指稱每張圖在
              合成裡的角色，例 "place the person from image 1 into
              the kitchen scene from image 2, preserve face and outfit"
        reference_images: 0..N 張參考圖的本機絕對路徑或相對於 NAS
            (settings.linebot_local_path) 的路徑
            - None / [] → 純文字生圖
            - 1 張 → 單張編輯（保留 identity）
            - 2+ 張 → 多張合成 / 換裝 / 風格融合
            無張數上限；超過 OpenAI / nanobanana 自己的服務上限時
            錯誤訊息會原樣回傳。
            每張 ≤ 10 MB（OOM 防護）。
        aspect_ratio: 1:1（預設）/ 4:3 / 3:4 / 16:9 / 9:16 / 21:9
            gpt-image-2 實際只支援 1024x1024、1536x1024、1024x1536 三種。

    Returns:
        成功：`圖片已生成：ai-images/codex_xxxxxxxx.png`
        失敗：人類可讀錯誤字串
    """
    if not is_codex_image_available():
        return "Codex 未設定 — 請改用 mcp__nanobanana__generate_image"

    if aspect_ratio not in _VALID_ASPECT_RATIOS:
        logger.warning("不支援的 aspect_ratio=%r，降回 1:1", aspect_ratio)
        aspect_ratio = "1:1"

    reference_bytes_list: list[bytes] | None = None
    if reference_images:
        resolved_paths: list[Path] = []
        for raw in reference_images:
            p = Path(raw)
            if not p.is_file():
                nas_path = Path(settings.linebot_local_path) / raw.lstrip("/")
                if nas_path.is_file():
                    p = nas_path
                else:
                    return f"reference 圖檔不存在：{raw}"
            if p.stat().st_size > _PER_IMAGE_BYTE_LIMIT:
                return f"reference 圖 {raw} 超過 10 MB"
            resolved_paths.append(p)
        reference_bytes_list = [p.read_bytes() for p in resolved_paths]

    image_path, error = await generate_image_with_codex(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        reference_bytes_list=reference_bytes_list,
    )
    if error:
        return f"Codex 生圖失敗：{error}"
    return f"圖片已生成：{image_path}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./.venv/bin/python -m pytest tests/test_codex_image_tools.py -v
```

Expected: 8 tests pass.

- [ ] **Step 5: Run full test subset to confirm no upstream test broke**

```bash
./.venv/bin/python -m pytest tests/test_codex_image.py tests/test_codex_image_tools.py tests/test_image_fallback.py tests/test_huggingface_image_service.py -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/src/ching_tech_os/services/mcp/codex_image_tools.py backend/tests/test_codex_image_tools.py
git commit -m "feat(mcp): unified codex_image_tool replaces generate/edit pair

The legacy split between codex_generate_image_tool and
codex_edit_image_tool added cognitive cost (which one for what?)
without buying anything — both eventually called the same underlying
function. One tool with optional reference_images=list[str] is
cleaner and matches the ctos-lite shape.

Path resolution (NAS-relative → absolute, file existence, 10 MB
per-image cap) lives here in the MCP wrapper; the codex_image.py
service layer stays focused on the HTTP call shape.

Old tool names removed. Agent system prompts updated in the next
commit."
```

---

## Task 3: Shared detection module

**Files:**
- Create: `backend/src/ching_tech_os/services/image_edit_detection.py`
- Test: `backend/tests/test_image_edit_detection.py` (new)

- [ ] **Step 1: Inspect existing test DB fixtures**

```bash
cd /home/ct/SDD/ching-tech-os/.worktrees/multi-image-edit/backend
grep -rln "conftest\|pytest_asyncio\|fixture.*conn\|fixture.*db" tests/ | head -10
cat tests/conftest.py 2>/dev/null | head -50
```

Confirm whether there's an existing async DB fixture. If yes, reuse. If no, mock the connection in the detector tests.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_image_edit_detection.py`:

```python
"""Unit tests for _detect_image_edit_references — the shared multi-image
reference collector for both LINE and Telegram bots.

The detector is platform-agnostic: it takes an asyncpg connection,
user / group identifiers, the optional quoted_message_id, and the
current text — and returns 0..N reference temp paths.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from ching_tech_os.services.image_edit_detection import (
    _detect_image_edit_references,
    _IMAGE_EDIT_KEYWORDS,
)


@pytest.fixture
def mock_conn():
    """A fake asyncpg connection with fetchval + fetch we can prime."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    return conn


@pytest.fixture
def patch_ensure_temp_image():
    """Replace ensure_temp_image with an identity-like passthrough that
    returns a fake temp path for any non-empty nas_path."""
    async def fake(line_message_id: str, nas_path: str) -> str | None:
        return f"/tmp/test/{line_message_id}.jpg" if nas_path else None

    with patch(
        "ching_tech_os.services.image_edit_detection.ensure_temp_image",
        new=fake,
    ):
        yield


@pytest.fixture
def patch_image_info_lookup():
    """Replace get_image_info_by_line_message_id with a fake lookup."""
    lookups = {}

    async def fake(line_message_id: str) -> dict | None:
        return lookups.get(line_message_id)

    with patch(
        "ching_tech_os.services.image_edit_detection.get_image_info_by_line_message_id",
        new=fake,
    ):
        yield lookups


@pytest.mark.asyncio
class TestDetectImageEditReferences:

    async def test_quoted_reply_to_image_returns_single(
        self, mock_conn, patch_ensure_temp_image, patch_image_info_lookup,
    ):
        patch_image_info_lookup["MSG_QUOTED"] = {"nas_path": "/nas/a.jpg"}
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id="MSG_QUOTED",
            text="改成黑白",
        )
        assert result == ["/tmp/test/MSG_QUOTED.jpg"]
        mock_conn.fetch.assert_not_awaited()   # quoted-reply short-circuits

    async def test_quoted_reply_to_text_falls_through(
        self, mock_conn, patch_ensure_temp_image, patch_image_info_lookup,
    ):
        # quoted_message_id present but not an image → fall through to text branch
        # text has no edit keyword → return []
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id="MSG_TEXT",
            text="今天天氣不錯",
        )
        assert result == []

    async def test_no_keyword_returns_empty(
        self, mock_conn, patch_ensure_temp_image,
    ):
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="今天天氣不錯",
        )
        assert result == []
        mock_conn.fetch.assert_not_awaited()

    async def test_keyword_with_no_recent_uploads_returns_empty(
        self, mock_conn, patch_ensure_temp_image,
    ):
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 1, tzinfo=timezone.utc)
        )
        mock_conn.fetch = AsyncMock(return_value=[])
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="幫我改一下",
        )
        assert result == []

    async def test_keyword_with_three_recent_uploads_returns_all_chronological(
        self, mock_conn, patch_ensure_temp_image,
    ):
        # Mock returns rows in chronological order (DB query uses ORDER BY ASC)
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 20, tzinfo=timezone.utc)
        )
        mock_conn.fetch = AsyncMock(return_value=[
            {"line_message_id": "MSG_A", "nas_path": "/nas/a.jpg"},
            {"line_message_id": "MSG_B", "nas_path": "/nas/b.jpg"},
            {"line_message_id": "MSG_C", "nas_path": "/nas/c.jpg"},
        ])
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="幫我合成這幾張",
        )
        assert result == [
            "/tmp/test/MSG_A.jpg",
            "/tmp/test/MSG_B.jpg",
            "/tmp/test/MSG_C.jpg",
        ]

    async def test_keyword_set_contains_合成_and_組合(self):
        # Sanity: keywords for the dominant "merge / compose" intent must exist
        assert "合成" in _IMAGE_EDIT_KEYWORDS
        assert "組合" in _IMAGE_EDIT_KEYWORDS

    async def test_no_count_cap(
        self, mock_conn, patch_ensure_temp_image,
    ):
        # Detector must not silently truncate. 20 rows → 20 results.
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 20, tzinfo=timezone.utc)
        )
        rows = [
            {"line_message_id": f"MSG_{i}", "nas_path": f"/nas/{i}.jpg"}
            for i in range(20)
        ]
        mock_conn.fetch = AsyncMock(return_value=rows)
        result = await _detect_image_edit_references(
            mock_conn,
            user_id="USR_X",
            group_id=None,
            quoted_message_id=None,
            text="合成",
        )
        assert len(result) == 20

    async def test_ensure_temp_image_failure_drops_that_path(
        self, mock_conn,
    ):
        """If ensure_temp_image returns None for some path, that row is skipped
        and others continue."""
        mock_conn.fetchval = AsyncMock(
            return_value=datetime(2026, 5, 20, tzinfo=timezone.utc)
        )
        mock_conn.fetch = AsyncMock(return_value=[
            {"line_message_id": "MSG_OK", "nas_path": "/nas/a.jpg"},
            {"line_message_id": "MSG_BAD", "nas_path": ""},   # ensure returns None
            {"line_message_id": "MSG_OK2", "nas_path": "/nas/c.jpg"},
        ])

        async def fake_ensure(mid, nas_path):
            return f"/tmp/test/{mid}.jpg" if nas_path else None

        with patch(
            "ching_tech_os.services.image_edit_detection.ensure_temp_image",
            new=fake_ensure,
        ):
            result = await _detect_image_edit_references(
                mock_conn,
                user_id="USR_X",
                group_id=None,
                quoted_message_id=None,
                text="改一下",
            )
        assert result == ["/tmp/test/MSG_OK.jpg", "/tmp/test/MSG_OK2.jpg"]
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
./.venv/bin/python -m pytest tests/test_image_edit_detection.py -v
```

Expected: `ImportError: No module named 'ching_tech_os.services.image_edit_detection'`.

- [ ] **Step 4: Create the detection module**

Create `backend/src/ching_tech_os/services/image_edit_detection.py`:

```python
"""Shared multi-image reference collector for LINE / Telegram bot handlers.

Hybrid rule:
  1. quoted_message_id points to an image → return [that image]
     (Strong explicit signal — user replied to a specific photo.)
  2. text contains an edit keyword AND the user has uploaded image(s)
     since their previous text message → return those images chronologically
     (LINE / Telegram natural pattern: drop N photos, then type "合成")
  3. otherwise → return []

No count cap — the OpenAI API (~16 for gpt-image edit) is the real
ceiling. Per-image 10 MB cap lives at the MCP tool layer.

The detector is platform-agnostic; both `linebot_ai.py` and the
Telegram handler call it the same way. Telegram's `media_group_id`
branch lives in its own handler — see telegram_album_images() below.
"""

from __future__ import annotations

import logging
from typing import Protocol

from .bot_line.file_handler import (
    ensure_temp_image,
    get_image_info_by_line_message_id,
)

logger = logging.getLogger(__name__)


class _AsyncpgLike(Protocol):
    async def fetchval(self, query: str, *args): ...
    async def fetch(self, query: str, *args): ...


_IMAGE_EDIT_KEYWORDS = (
    # Direct edit verbs
    "修", "改", "換", "加", "變", "調整", "微調",
    # Preservation / framing
    "保留", "不要改", "原樣", "原圖", "原本",
    # Removal
    "去掉", "刪", "拿掉",
    # Style / colour / background tweaks
    "顏色", "背景", "黑白", "色調",
    # Re-render variants
    "再生一張", "再畫一張", "重新", "重畫",
    # The dominant multi-image composition verbs (added 2026-05 for
    # ctos-lite; ching-tech-os benefits from the same coverage)
    "合成", "組合",
)


async def _detect_image_edit_references(
    conn: _AsyncpgLike,
    *,
    user_id: str,
    group_id: str | None,
    quoted_message_id: str | None,
    text: str,
) -> list[str]:
    """Return absolute temp paths of reference images to attach to this turn.

    Args:
        conn:                  asyncpg connection / pool member
        user_id:               platform_user_id from bot_users (LINE userId or
                               Telegram user id stringified)
        group_id:              bot_groups.id UUID or None for personal chat
        quoted_message_id:     LINE quotedMessageId or Telegram reply-to message
                               id (string); None when the user didn't reply
        text:                  the user's text message content (pre-cleanup)

    Returns:
        List of temp paths in chronological order (oldest first). Empty list
        when the turn shouldn't trigger multi-image edit mode.
    """
    # Branch 1: explicit quoted reply — single image, strong signal
    if quoted_message_id:
        info = await get_image_info_by_line_message_id(quoted_message_id)
        if info and info.get("nas_path"):
            temp = await ensure_temp_image(quoted_message_id, info["nas_path"])
            if temp:
                logger.info(
                    "image edit detect: quoted reply → 1 image (%s)", temp,
                )
                return [temp]
        # quoted message wasn't an image — fall through to keyword branch

    # Branch 2: keyword + recent uploads
    if not any(kw in text for kw in _IMAGE_EDIT_KEYWORDS):
        return []

    # Find the user's previous text-message timestamp (anchor for the batch)
    if group_id is not None:
        last_text_at = await conn.fetchval(
            """
            SELECT COALESCE(MAX(m.created_at), '1970-01-01'::timestamptz)
            FROM bot_messages m
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id = $1
              AND u.platform_user_id = $2
              AND m.is_from_bot = false
              AND m.message_type = 'text'
              AND m.content IS NOT NULL
              AND m.content <> ''
            """,
            group_id, user_id,
        )
        rows = await conn.fetch(
            """
            SELECT m.message_id as line_message_id, f.nas_path
            FROM bot_messages m
            JOIN bot_files f ON f.message_id = m.id
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id = $1
              AND u.platform_user_id = $2
              AND m.is_from_bot = false
              AND m.message_type = 'image'
              AND f.file_type = 'image'
              AND m.created_at > $3
            ORDER BY m.created_at ASC
            """,
            group_id, user_id, last_text_at,
        )
    else:
        last_text_at = await conn.fetchval(
            """
            SELECT COALESCE(MAX(m.created_at), '1970-01-01'::timestamptz)
            FROM bot_messages m
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id IS NULL
              AND u.platform_user_id = $1
              AND m.is_from_bot = false
              AND m.message_type = 'text'
              AND m.content IS NOT NULL
              AND m.content <> ''
            """,
            user_id,
        )
        rows = await conn.fetch(
            """
            SELECT m.message_id as line_message_id, f.nas_path
            FROM bot_messages m
            JOIN bot_files f ON f.message_id = m.id
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id IS NULL
              AND u.platform_user_id = $1
              AND m.is_from_bot = false
              AND m.message_type = 'image'
              AND f.file_type = 'image'
              AND m.created_at > $2
            ORDER BY m.created_at ASC
            """,
            user_id, last_text_at,
        )

    if not rows:
        return []

    paths: list[str] = []
    for row in rows:
        temp = await ensure_temp_image(row["line_message_id"], row["nas_path"])
        if temp:
            paths.append(temp)
    if paths:
        logger.info(
            "image edit detect: keyword %r + %d uploads since %s",
            text[:30], len(paths), last_text_at,
        )
    return paths
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
./.venv/bin/python -m pytest tests/test_image_edit_detection.py -v
```

Expected: 8 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/ching_tech_os/services/image_edit_detection.py backend/tests/test_image_edit_detection.py
git commit -m "feat(detection): platform-agnostic _detect_image_edit_references

Hybrid rule: quoted-reply → 1 image (strong signal); else edit-keyword
+ images uploaded since user's previous text → N images chronological.
No count cap — OpenAI API decides the real ceiling.

Reused by linebot_ai.py (next commit) and bot_telegram/handler.py
(after that). Designed to take any asyncpg-shape conn so the existing
test infra (mocks) works without a real DB."
```

---

## Task 4: Wire detection into LINE handler + update system prompt

**Files:**
- Modify: `backend/src/ching_tech_os/services/linebot_ai.py` (the `quoted_image_path = None ...` block around lines 846-887; the system-prompt injection around lines 822-838; the user_message marker around lines 897-899)

- [ ] **Step 1: Update system-prompt injection (lines ~822-838)**

Find this block in `backend/src/ching_tech_os/services/linebot_ai.py`:

```python
        from .codex_image import is_codex_image_available
        if is_codex_image_available():
            codex_bias = (
                "\n\n## 圖片生成 / 編輯工具優先序（系統強制）\n"
                "當用戶要求生成、修改、編輯圖片時，**必須**先試以下工具：\n"
                "- 純文字生圖 → `mcp__ching-tech-os__codex_generate_image_tool`\n"
                "- 編輯既有圖（含 reply 圖片） → `mcp__ching-tech-os__codex_edit_image_tool`\n"
                "\n"
                "只有當上述 codex 工具回傳開頭為「Codex」的錯誤字串時，"
                "才能改試 `mcp__nanobanana__generate_image` 或 `mcp__nanobanana__edit_image` 作為退路。\n"
                "原因：codex 跑在我們自架的 codex-image-service、消耗的是 "
                "ChatGPT 訂閱配額而非額外 Gemini credits。"
            )
            system_prompt = (system_prompt or "") + codex_bias
```

Replace with:

```python
        from .codex_image import is_codex_image_available
        if is_codex_image_available():
            codex_bias = (
                "\n\n## 圖片生成 / 編輯工具優先序（系統強制）\n"
                "當用戶要求生成、修改、編輯、合成圖片時，**必須**先試："
                "`mcp__ching-tech-os__codex_image_tool`\n"
                "\n"
                "三種使用模式：\n"
                "- **純生圖**：`codex_image_tool(prompt=英文描述)`\n"
                "- **單張編輯**：`codex_image_tool(prompt=英文edit指令, "
                "reference_images=[圖片路徑])`\n"
                "- **多圖合成 / 換裝 / 場景融合**："
                "`codex_image_tool(prompt=英文合成指令含 'image 1 / image 2 / ...', "
                "reference_images=[圖1路徑, 圖2路徑, ...])`\n"
                "\n"
                "用戶訊息開頭如有 `[N 張參考圖: <path1>, <path2>, ...]` 標註，"
                "**就是已偵測到的多圖合成場景**，把那些路徑原樣帶進 "
                "`reference_images` 即可；不要用 Read 工具讀圖（會浪費 token）。\n"
                "\n"
                "只有當 codex_image_tool 回傳開頭為「Codex」的錯誤字串時，"
                "才能改試 `mcp__nanobanana__generate_image` 作為退路 "
                "（nanobanana 也吃 `files=[路徑列表]` 做多圖）。\n"
                "原因：codex 跑在自架的 codex-image-service、消耗 ChatGPT "
                "訂閱配額而非 Gemini credits。"
            )
            system_prompt = (system_prompt or "") + codex_bias
```

- [ ] **Step 2: Replace the `quoted_image_path = None ...` block (lines ~846-887)**

Find the block starting at `# 處理回覆舊訊息（quotedMessageId）`. Replace the **image** branch (the `if quoted_message_id:` opening through the `quoted_image_path = temp_path` assignment) with a single detector call that uses the new module. Keep the **file** and **text** branches unchanged.

The new shape:

```python
        # 處理回覆舊訊息（quotedMessageId）- 圖片走多圖偵測器、檔案 / 文字保持原樣
        from .image_edit_detection import _detect_image_edit_references
        reference_image_paths: list[str] = []
        quoted_file_path = None
        quoted_text_content = None

        # Multi-image / single-image reference detection (covers quoted-reply
        # AND the implicit "drop N photos then 合成" pattern).
        async with get_connection() as _det_conn:
            reference_image_paths = await _detect_image_edit_references(
                _det_conn,
                user_id=line_user_id or "",
                group_id=str(line_group_id) if line_group_id else None,
                quoted_message_id=quoted_message_id,
                text=content,
            )
        if reference_image_paths:
            logger.info(
                f"用戶 image edit 場景: {len(reference_image_paths)} 張 reference 圖",
            )

        # Only fall through to file / text quoted branches when the detector
        # didn't pick this up as an image edit
        if not reference_image_paths and quoted_message_id:
            file_info = await get_file_info_by_line_message_id(quoted_message_id)
            if file_info and file_info.get("nas_path") and file_info.get("file_name"):
                file_name = file_info["file_name"]
                file_size = file_info.get("file_size")
                if is_readable_file(file_name):
                    if file_size and file_size > MAX_READABLE_FILE_SIZE:
                        logger.info(f"用戶回覆檔案過大: {quoted_message_id} -> {file_name}")
                    else:
                        temp_path = await ensure_temp_file(
                            quoted_message_id, file_info["nas_path"], file_name, file_size
                        )
                        if temp_path:
                            quoted_file_path = temp_path
                            logger.info(f"用戶回覆檔案: {quoted_message_id} -> {temp_path}")
                else:
                    logger.info(f"用戶回覆檔案類型不支援: {quoted_message_id} -> {file_name}")
            else:
                msg_info = await get_message_content_by_line_message_id(quoted_message_id)
                if msg_info and msg_info.get("content"):
                    quoted_text_content = {
                        "content": msg_info["content"],
                        "display_name": msg_info.get("display_name", ""),
                        "is_from_bot": msg_info.get("is_from_bot", False),
                    }
                    logger.info(f"用戶回覆文字: {quoted_message_id} -> {msg_info['content'][:50]}...")
```

(The variables `quoted_image_path` is gone — its single-image case is now subsumed by `reference_image_paths` with len 1.)

- [ ] **Step 3: Replace the user_message marker (lines ~897-899)**

Find:

```python
        # 如果是回覆圖片、檔案或文字，在訊息開頭標註
        if quoted_image_path:
            user_message = f"[回覆圖片: {quoted_image_path}]\n{user_message}"
        elif quoted_file_path:
```

Replace with:

```python
        # 如果有偵測到參考圖、檔案或回覆文字，在訊息開頭標註
        if reference_image_paths:
            paths_str = ", ".join(reference_image_paths)
            user_message = f"[{len(reference_image_paths)} 張參考圖: {paths_str}]\n{user_message}"
        elif quoted_file_path:
```

(Keep the rest of the elif chain — file / text / pdf branches — unchanged.)

- [ ] **Step 4: Smoke import test**

```bash
cd /home/ct/SDD/ching-tech-os/.worktrees/multi-image-edit/backend
./.venv/bin/python -c "from ching_tech_os.services import linebot_ai; print('import ok')"
```

Expected: `import ok`.

- [ ] **Step 5: Run the existing LINE-handler tests if any**

```bash
./.venv/bin/python -m pytest tests/ -q -k "linebot or line_handler or test_codex_image" 2>&1 | tail -10
```

Expected: green (or only fail on tests we haven't touched yet — note those failures and confirm they don't involve our edits).

- [ ] **Step 6: Commit**

```bash
git add backend/src/ching_tech_os/services/linebot_ai.py
git commit -m "feat(linebot): wire multi-image detection + unified codex_image_tool

Replace quoted_image_path single-shot lookup with a call to the shared
_detect_image_edit_references helper. The detector also catches the
implicit 'drop N photos then 合成' pattern that the old code missed.

System-prompt injection now names the unified codex_image_tool only
(old codex_generate_image_tool / codex_edit_image_tool names removed)
and teaches the model the three modes (pure generation, single edit,
multi-image composition).

User message marker changes from [回覆圖片: <path>] to
[N 張參考圖: <p1>, <p2>, ...]; single-image case still renders cleanly
as [1 張參考圖: ...]."
```

---

## Task 5: Wire detection into Telegram handler

**Files:**
- Modify: `backend/src/ching_tech_os/services/bot_telegram/handler.py` (text-message handling block)

- [ ] **Step 1: Locate the text-message handler in Telegram**

```bash
grep -nE "async def.*text|message.text|async def handle_message|MessageHandler" \
  backend/src/ching_tech_os/services/bot_telegram/handler.py | head -10
```

Find the function (likely `async def handle_text_message(...)` or similar) that consumes a Telegram text message and dispatches to AI. Note its signature for the next step.

- [ ] **Step 2: Add the detector call**

Find the section in that function where Telegram's equivalent of "quoted image" is handled. Insert the equivalent of the LINE wiring from Task 4. Concrete pseudo-shape (adapt to actual function names that exist in the file):

```python
from ..image_edit_detection import _detect_image_edit_references
from ..bot_line.file_handler import get_connection

reference_image_paths: list[str] = []
async with get_connection() as _det_conn:
    quoted_id = None
    if message.reply_to_message:
        quoted_id = str(message.reply_to_message.message_id)
    reference_image_paths = await _detect_image_edit_references(
        _det_conn,
        user_id=str(message.from_user.id),
        group_id=str(chat_uuid) if chat_uuid else None,
        quoted_message_id=quoted_id,
        text=message.text or "",
    )
if reference_image_paths:
    paths_str = ", ".join(reference_image_paths)
    user_message = f"[{len(reference_image_paths)} 張參考圖: {paths_str}]\n{user_message}"
```

(`chat_uuid` is whatever variable in the Telegram handler corresponds to `line_group_id` for personal-vs-group routing. Use the file's existing naming.)

- [ ] **Step 3: Smoke import test**

```bash
./.venv/bin/python -c "from ching_tech_os.services.bot_telegram import handler; print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/ching_tech_os/services/bot_telegram/handler.py
git commit -m "feat(telegram): wire multi-image detection into text-message handler

Telegram handler now calls the shared _detect_image_edit_references and
prepends the same [N 張參考圖: ...] marker that LINE does, so the agent
prompt teaching applies uniformly across both platforms.

The reply_to_message_id maps to quoted_message_id; the underlying
bot_messages.message_id lookup works the same for both bots because
the schema is platform-agnostic at this layer."
```

---

## Task 6: Telegram media-group (album) special branch

**Files:**
- Modify: `backend/src/ching_tech_os/services/image_edit_detection.py` (add `telegram_album_images` helper)
- Modify: `backend/src/ching_tech_os/services/bot_telegram/handler.py` (call the helper BEFORE the generic detector when the reply target is a media-group)
- Test: `backend/tests/test_telegram_media_group.py` (new)

- [ ] **Step 1: Inspect how Telegram media-group ID is stored in bot_messages**

```bash
grep -nE "media_group_id|media_group" \
  backend/src/ching_tech_os/services/bot_telegram/*.py | head -10
grep -rln "media_group_id" backend/migrations/ 2>/dev/null
```

If `media_group_id` is already a column on `bot_messages` (or `bot_files`), perfect. If not, this task gains a small alembic migration:

```python
# in a new alembic revision:
op.add_column('bot_files', sa.Column('telegram_media_group_id', sa.String(64), nullable=True))
op.create_index('ix_bot_files_telegram_media_group', 'bot_files',
                ['telegram_media_group_id'])
```

And the Telegram image-save code path needs updating to populate it. **Decide based on what the grep shows.** If the column already exists, just query it.

- [ ] **Step 2: Add the helper to `image_edit_detection.py`**

Append to `backend/src/ching_tech_os/services/image_edit_detection.py`:

```python
async def telegram_album_images(
    conn: _AsyncpgLike,
    media_group_id: str,
) -> list[str]:
    """Return reference temp paths for every image in a Telegram album.

    Telegram delivers album uploads as separate messages that share a
    media_group_id; this short-circuits the generic time-based heuristic
    when the user explicitly replies to a member of an album.
    """
    rows = await conn.fetch(
        """
        SELECT m.message_id as line_message_id, f.nas_path
        FROM bot_messages m
        JOIN bot_files f ON f.message_id = m.id
        WHERE f.telegram_media_group_id = $1
          AND f.file_type = 'image'
        ORDER BY m.created_at ASC
        """,
        media_group_id,
    )
    paths = []
    for row in rows:
        temp = await ensure_temp_image(row["line_message_id"], row["nas_path"])
        if temp:
            paths.append(temp)
    logger.info(
        "telegram album detect: media_group_id=%s → %d images",
        media_group_id, len(paths),
    )
    return paths
```

- [ ] **Step 3: Add tests**

Create `backend/tests/test_telegram_media_group.py`:

```python
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
```

- [ ] **Step 4: Wire into the Telegram handler**

In `backend/src/ching_tech_os/services/bot_telegram/handler.py`, before the generic `_detect_image_edit_references` call from Task 5, add:

```python
from ..image_edit_detection import telegram_album_images, _detect_image_edit_references

reference_image_paths: list[str] = []
async with get_connection() as _det_conn:
    # Album branch first — Telegram albums share a media_group_id which
    # is a stronger signal than the time-based heuristic.
    if message.reply_to_message and getattr(
        message.reply_to_message, "media_group_id", None,
    ):
        reference_image_paths = await telegram_album_images(
            _det_conn,
            media_group_id=message.reply_to_message.media_group_id,
        )
    if not reference_image_paths:
        quoted_id = None
        if message.reply_to_message:
            quoted_id = str(message.reply_to_message.message_id)
        reference_image_paths = await _detect_image_edit_references(
            _det_conn,
            user_id=str(message.from_user.id),
            group_id=str(chat_uuid) if chat_uuid else None,
            quoted_message_id=quoted_id,
            text=message.text or "",
        )
```

- [ ] **Step 5: Run the new test**

```bash
./.venv/bin/python -m pytest tests/test_telegram_media_group.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/ching_tech_os/services/image_edit_detection.py backend/tests/test_telegram_media_group.py backend/src/ching_tech_os/services/bot_telegram/handler.py
git commit -m "feat(telegram): album (media_group_id) short-circuits time heuristic

When a Telegram user replies to a message inside a media-group album,
every image in that album becomes a reference — a stronger signal
than the generic 'images since previous text' heuristic.

If the media_group_id column doesn't yet exist on bot_files, a small
alembic migration is included alongside this commit. If it does, this
commit is pure read-side change.

LINE has no equivalent native grouping, so this is Telegram-only."
```

---

## Task 7: Save bot-generated images to `bot_files` for quoted-reply edit

**Files:**
- Modify: `backend/src/ching_tech_os/services/bot_line/message_store.py` (`save_bot_response` or whichever function the LINE bot calls after sending an `ImageMessage` reply)
- Test: `backend/tests/test_message_store_bot_image.py` (new, small)

- [ ] **Step 1: Discover the bot-image send pathway**

```bash
grep -rnE "ImageMessage|originalContentUrl|previewImageUrl" \
  backend/src/ching_tech_os/services/ backend/src/ching_tech_os/api/ \
  --include="*.py" | head -10
grep -rn "save_bot_response\b" backend/src/ching_tech_os/ --include="*.py" | head -10
```

Identify the call site that sends LINE `ImageMessage` back to the user. That is where we hook the `bot_files` insertion.

- [ ] **Step 2: Write the test**

Create `backend/tests/test_message_store_bot_image.py`:

```python
"""Bot-generated images must be recorded in bot_files so that the user
can later reply to them and trigger multi-image edit."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_save_bot_image_response_inserts_bot_files_row():
    """When the bot replies with a generated image, a bot_files row gets
    written so quoted-reply-to-bot-image works."""
    # Implementation skeleton — the actual fixture wiring depends on what
    # function we found in Step 1. The test asserts that, after calling
    # the bot-image-save function, an INSERT on bot_files with file_type
    # = 'image' and the expected nas_path was executed.
    pass   # fill in after Step 1 reveals the right entry point
```

(This task's test is intentionally a scaffold — Step 1's investigation determines the concrete shape. Update both the test and the implementation together in Steps 3-4.)

- [ ] **Step 3: Add the `bot_files` insert in the bot-image-send pathway**

In the function discovered in Step 1, after the bot successfully sends the LINE ImageMessage and obtains the sent-message id, add:

```python
# Record bot-generated image so quoted-reply edit works later
if image_local_path:   # the NAS path of the generated PNG we just sent
    async with get_connection() as _conn:
        await _conn.execute(
            """
            INSERT INTO bot_files (message_id, nas_path, file_type, file_name)
            VALUES ($1, $2, 'image', $3)
            """,
            bot_message_uuid,        # the bot_messages row UUID we just inserted
            image_local_path,        # NAS-relative path
            Path(image_local_path).name,
        )
```

(Field set adapted to whatever `bot_files` actually requires — check column nullability from the schema. If `file_size` is NOT NULL, add it.)

- [ ] **Step 4: Run the test + smoke import**

```bash
./.venv/bin/python -m pytest tests/test_message_store_bot_image.py -v
./.venv/bin/python -c "from ching_tech_os.services.bot_line import message_store; print('ok')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/ching_tech_os/services/bot_line/message_store.py backend/tests/test_message_store_bot_image.py
git commit -m "feat(bot_line): record bot-generated images in bot_files

Without this row, get_image_info_by_line_message_id returns None for
bot reply images, and the multi-image detector's quoted-reply branch
silently misses them. With this row, the user can reply to a generated
image and say '再加皇冠' to trigger single-image edit on the bot's
own output."
```

---

## Task 8: Side-PR — codex-image-service cap removal

Separate repo: `/home/ct/codex/codex-image-service`.

**Files:**
- Modify: `/home/ct/codex/codex-image-service/app/models.py` (line 14)
- Modify: `/home/ct/codex/codex-image-service/tests/test_models_multi_image.py` (delete the cap-at-4 test)

- [ ] **Step 1: Branch + worktree**

```bash
cd /home/ct/codex/codex-image-service
git worktree add .worktrees/lift-cap -b chore/lift-reference-images-cap main
cd .worktrees/lift-cap
./.venv/bin/python -m pytest tests/ -q   # baseline must be green
```

(The repo has its own venv — likely at `.venv` or shared with main checkout; use the working invocation from prior PR #1 work.)

- [ ] **Step 2: Modify the model**

In `app/models.py`, change:

```python
    reference_images_base64: list[str] | None = Field(
        default=None,
        max_length=4,
    )
```

to:

```python
    reference_images_base64: list[str] | None = Field(default=None)
    # Note: no client-side count cap. OpenAI's gpt-image edit API
    # accepts ~16 images and will reject anything beyond that with a
    # clear error which we surface verbatim. The 4-cap from PR #1 was
    # arbitrary; lifting it for consistency across ctos-lite and
    # ching-tech-os, which deliberately set no cap either.
```

- [ ] **Step 3: Delete the cap-at-4 test**

In `tests/test_models_multi_image.py`, delete the `test_plural_max_4_images` test (about 8 lines).

- [ ] **Step 4: Run tests + commit + PR**

```bash
./.venv/bin/python -m pytest tests/ -q
git add app/models.py tests/test_models_multi_image.py
git commit -m "chore: remove arbitrary 4-image cap on reference_images_base64

The cap was a conservative starter set in PR #1 with no evidence.
Lifted for consistency with ctos-lite and ching-tech-os, which
explicitly chose no client-side cap (let the OpenAI API decide).
The per-image 20 MB string cap stays."
git push -u origin chore/lift-reference-images-cap
gh pr create --title "chore: lift the 4-image cap on reference_images_base64" \
  --body "Companion to ching-tech-os multi-image PR. ctos-lite and ching-tech-os already pass arbitrary-N reference lists; the 4-cap here is the last artificial limit. OpenAI's ~16-image edit limit is the real ceiling and surfaces clearly when exceeded."
```

---

## Task 9: Side-PR — ctos-lite cap removal

Separate repo: `/home/ct/SDD/ctos-lite`.

**Files:**
- Modify: `backend/src/ctos_lite/services/mcp_server.py` (`_MAX_REFERENCE_IMAGES` constant + the rejection check)
- Modify: `backend/src/ctos_lite/services/message_handler.py` (`_detect_image_edit_references` `max_images` param)
- Modify: corresponding tests

- [ ] **Step 1: Branch + worktree**

```bash
cd /home/ct/SDD/ctos-lite
git worktree add .worktrees/lift-cap -b chore/lift-reference-images-cap origin/main
cd .worktrees/lift-cap
PYTHONPATH=backend/src /home/ct/SDD/ctos-lite/backend/.venv/bin/python \
  -m pytest backend/tests/ -q
```

- [ ] **Step 2: Lift cap in mcp_server.py**

Find:

```python
_MAX_REFERENCE_IMAGES = 4
...
if len(reference_image_paths) > _MAX_REFERENCE_IMAGES:
    return f"參考圖最多 {_MAX_REFERENCE_IMAGES} 張，收到 {len(reference_image_paths)} 張"
```

Delete both the constant and the check. (The per-image 10 MB cap stays.)

- [ ] **Step 3: Lift cap in message_handler.py detector**

Find the signature:

```python
def _detect_image_edit_references(
    text: str,
    quoted_content: str | None,
    history: list[dict],
    max_images: int = 4,
) -> list[str]:
```

Remove the `max_images: int = 4` parameter. Find inside the function:

```python
if path:
    refs.append(path)
    if len(refs) >= max_images:
        break
```

Replace with:

```python
if path:
    refs.append(path)
```

(Remove the `if len(refs) >= max_images: break` line.)

- [ ] **Step 4: Update tests**

In `backend/tests/test_message_handler.py`, find `TestDetectImageEditReferences::test_cap_at_4_images` and either:
- Delete it entirely, OR
- Repurpose it as `test_no_cap_returns_all` asserting 6+ uploads all come back.

Recommended: repurpose to keep evidence:

```python
def test_no_cap_returns_all_uploads(self):
    history = [self._upload_msg(f"/tmp/{i}.jpg") for i in range(6)]
    refs = _detect_image_edit_references(
        text="合成", quoted_content=None, history=history,
    )
    assert refs == [f"/tmp/{i}.jpg" for i in range(6)]
```

- [ ] **Step 5: Run tests + commit + PR**

```bash
PYTHONPATH=backend/src /home/ct/SDD/ctos-lite/backend/.venv/bin/python \
  -m pytest backend/tests/ -q
git add backend/src/ctos_lite/services/mcp_server.py \
        backend/src/ctos_lite/services/message_handler.py \
        backend/tests/test_message_handler.py
git commit -m "chore: lift the 4-image cap (both MCP layer and detector)

Companion to ching-tech-os multi-image PR. The cap was a conservative
default with no evidence; OpenAI's ~16-image gpt-image edit limit is
the real ceiling and surfaces clearly when exceeded. The per-image
10 MB cap stays."
git push -u origin chore/lift-reference-images-cap
gh pr create --title "chore: lift the 4-image cap on multi-image detector + MCP" \
  --body "Companion to ching-tech-os multi-image PR. Mirrors the codex-image-service cap-removal PR."
```

---

## Manual smoke test (post all PRs merged + ching-tech-os redeployed)

Per spec §9:

- [ ] LINE: drop 2 photos + type "把第一張的人放到第二張的場景, preserve face" → confirm composition result with both subjects preserved.
- [ ] LINE: drop 5 photos + type "合成" → confirm all 5 reach codex-image-service (workdir shows `reference_1.jpg` through `reference_5.jpg`); confirm OpenAI either accepts or returns a clear "too many references" error.
- [ ] Telegram: reply to a media album → all album images become references.
- [ ] LINE: quoted-reply to a single image + type "改成黑白" → single-image edit regression check.
- [ ] Reply to a bot-generated image + type "再加皇冠" → Task 7 behaviour.

---

## Plan Self-Review

**Spec coverage:**
- §2 Goals: D1 (Task 2), D2 (Tasks 4+5), D3 (Task 3 + Task 4 wire), D4 (Task 4 prompt teaches nanobanana fallback), D5 (Tasks 1+2 no cap), D6 (Tasks 8+9) — all covered.
- §6.1 codex_image.py — Task 1.
- §6.2 image_fallback.py — confirmed NO CHANGE needed (text-only FLUX doesn't see references); plan correctly omits.
- §6.3 MCP tool — Task 2.
- §6.4 detection — Task 3.
- §6.5 bot-generated images — Task 7.
- §6.6 Telegram albums — Task 6.
- §6.7 LINE/Telegram wiring — Tasks 4+5.
- §7 side tasks — Tasks 8+9.
- §8 testing — distributed across tasks with concrete test code in each.
- §9 manual smoke — explicit checklist at the end.

**Placeholder scan:**
- Task 5 Step 2's pseudo-shape uses `chat_uuid` as a variable name placeholder because the actual Telegram handler variable wasn't read line-by-line; the step instruction explicitly tells the executor to adapt to the file's existing naming. This is a known unknown surfaced honestly, not a hidden placeholder. Acceptable.
- Task 6 Step 1 hedges on whether the `media_group_id` column exists or needs a migration — the executor must investigate first. Acceptable given the schema-state unknown.
- Task 7 Step 2's test is intentionally a scaffold (`pass`) with a comment requiring fill-in after Step 1's investigation. **This is a placeholder by design** — the entry-point function isn't known yet. Decision: leave as-is and rely on the executor following the order; the alternative (full speculative test) would be wrong if the actual function shape differs.

**Type consistency:**
- `reference_bytes_list: list[bytes] | None` used consistently in `codex_image.py` (Task 1), MCP tool (Task 2), and detection consumers (Tasks 4/5).
- `reference_image_paths: list[str]` used consistently in LINE/Telegram handlers.
- `_detect_image_edit_references` signature consistent across Task 3 definition and Tasks 4/5 call sites.

**Scope check:**
- 9 tasks. Main feature work is Tasks 1-7 (single repo, single PR). Tasks 8-9 are tiny side-PRs in other repos, separated by repo boundary. Each task ships independent commits; no task depends on a future task's commit (Task 7 is independent of Task 6; Tasks 8/9 don't touch the main PR).

---

## Plan complete

Save location: `/home/ct/SDD/ching-tech-os/docs/superpowers/plans/2026-05-21-multi-image-edit.md`

Execution: invoke superpowers:subagent-driven-development next.
