# ching-tech-os Multi-Image Edit — Design Spec

**Status:** Design approved 2026-05-20. Ready for plan.
**Author:** yazelin + Claude
**Companion work:** Mirrors the multi-image refactor already shipped in `codex-image-service` (PR #1) and `ctos-lite` (PRs #1/#2/#3). This spec extends the same capability to ching-tech-os and harmonises the cap-policy across all three repos.

## 1. Background & Motivation

ching-tech-os routes its LINE and Telegram bots through `codex_generate_image_tool` (text-to-image) and `codex_edit_image_tool` (single-image edit). Today's reality is that internal users frequently drop **N photos in a row** and then ask "幫我合成一下" / "把這幾張的元素融在一起" — which the current single-image edit tool cannot represent.

The underlying stack is already multi-image-capable:

| Layer | Multi-image? |
|---|---|
| OpenAI `gpt-image` edit API | Yes (up to ~16 inputs per call) |
| Codex CLI `-i, --image <FILE>...` | Yes (variadic) |
| codex-image-service `/v1/images/generate` | Yes — `reference_images_base64: list[str]` shipped in PR #1 |
| ctos-lite LINE pipeline | Yes — fully wired in PRs #1/#2/#3 |
| ching-tech-os LINE / Telegram pipeline | **No** — only this spec's gap |
| nanobanana `generate_image(files=[...])` | Yes (1–14 references) |
| nanobanana `edit_image` | No (single ref only) |
| HF FLUX | No (text-to-image only) |

This spec closes the gap for ching-tech-os.

## 2. Goals

- LINE and Telegram users on ching-tech-os can drop 2+ photos and trigger a real multi-image edit (composition, outfit-swap, scene-merge, style-transfer, etc.) with one text command.
- Codex primary path AND nanobanana fallback path both carry the full reference set through.
- HF FLUX degrades gracefully (text-only, log a warning when references are dropped).
- No client-side cap on reference count — the OpenAI API (or nanobanana's own server) is the real ceiling.
- MCP surface simplifies: one unified `codex_image_tool` replaces the existing `codex_generate_image_tool` + `codex_edit_image_tool` pair, matching the ctos-lite shape.

## 3. Non-Goals

- **`services/presentation.py` is out of scope.** 30-day journal scan found zero `/api/presentation` HTTP hits and only one historical codex generation call (4/24, single image). The presentation pipeline keeps its current single-image `generate_image_with_codex` call.
- **`nanobanana.edit_image` is out of scope.** Stays single-reference; the multi-image path uses `nanobanana.generate_image(files=[...])` instead.
- **`ching_tech_os/services/bot_telegram/handler.py` non-image flows** stay untouched. We only add detection + tool wiring on top.

## 4. Design Decisions (from 2026-05-20 brainstorm)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Collapse to one MCP tool** `codex_image_tool(prompt, reference_images=None, aspect_ratio)`. Delete `codex_generate_image_tool` + `codex_edit_image_tool`. | Matches ctos-lite shape. Less surface for the model to choose between. Accept the prompt-rewrite cost to all agent definitions inside ching-tech-os. |
| D2 | **Both LINE and Telegram** get multi-image detection + wiring. | Internal users span both platforms; capability parity is the expectation. |
| D3 | **Hybrid detection rule** — explicit quoted-reply returns 1 image; otherwise (edit-keyword + recent uploads) returns N images. | Mirrors ctos-lite. Quoted-reply is a strong signal; the implicit path catches the dominant "drop N → type" UX. |
| D4 | **Codex + nanobanana** both carry the full reference list. HF FLUX silently degrades (warn + text-only). | Codex is the primary, well-thought-out path; nanobanana stays a real fallback (not best-effort). Both backends already support multi-image natively. |
| D5 | **No client-side count cap.** OpenAI / nanobanana decide the real ceiling. Per-image 10 MB cap stays (OOM defence). | "4" was an arbitrary conservative number with no evidence. Removing it costs nothing and matches user intent. |
| D6 | **Lift the cap on `ctos-lite` and `codex-image-service` too** as side-task PRs once ching-tech-os ships. | Consistency across all three repos; same one-line change in each. |

## 5. Architecture & Data Flow

```
LINE / Telegram bot webhook
  │
  ├─ type=image   → existing path → INSERT into images table (no change)
  └─ type=text    → existing path → handler picks up text + quoted_message_id
        │
        ├─ NEW: _detect_image_edit_references(user_id, line_group_id,
        │           quoted_message_id, text) → list[str]
        │         ├─ quoted_message_id is an image → [that_one]
        │         ├─ text contains edit keyword     → SQL query images table
        │         │     "WHERE user_id = $1 AND group = $2
        │         │      AND created_at > (last user text time)"
        │         │     → list[N] in chronological order (no LIMIT)
        │         └─ otherwise                        → []
        │
        ├─ build user_message:
        │     if refs > 0: prepend "[N 張參考圖: p1, p2, ...]\n"
        │
        └─ pass to ClaudeAgent with system prompt teaching the model
              to call codex_image_tool(reference_images=[...]) in this case
                │
                └─ unified MCP tool: codex_image_tool
                      │
                      └─ services/codex_image.py:
                            generate_image_with_codex(
                              prompt, aspect_ratio,
                              reference_bytes_list: list[bytes] | None,
                            )
                              │
                              └─ image_fallback.py:
                                    generate_image_with_fallback(
                                      prompt, reference_bytes_list,
                                    )
                                      ├─ try Codex → POST reference_images_base64 array
                                      ├─ fail → try nanobanana
                                      │         generate_image(files=[paths])
                                      └─ fail → HF FLUX (text-only, warn)
```

## 6. Detailed Changes

### 6.1 `services/codex_image.py`

**Current:**

```python
async def generate_image_with_codex(prompt, aspect_ratio, reference_bytes=None):
    payload = {"prompt": prompt, "aspect_ratio": aspect_ratio, "count": 1}
    if reference_bytes:
        payload["reference_image_base64"] = base64.b64encode(reference_bytes).decode("ascii")
    # POST /v1/images/generate ...

async def edit_image_with_codex(...):
    # separate function, single-image only
```

**New:**

```python
async def generate_image_with_codex(
    prompt: str,
    aspect_ratio: str = "1:1",
    reference_bytes_list: list[bytes] | None = None,
) -> tuple[str | None, str | None]:
    """Unified text-to-image AND multi-image edit entry point.
    
    reference_bytes_list:
      - None / []   → text-to-image
      - [bytes]     → single-image edit
      - [b1, b2..]  → multi-image composition (no client cap; codex-image-service
                       will pass them all through to gpt-image edit)
    """
    reference_bytes_list = reference_bytes_list or []
    payload = {"prompt": prompt, "aspect_ratio": aspect_ratio, "count": 1}
    if reference_bytes_list:
        payload["reference_images_base64"] = [
            base64.b64encode(b).decode("ascii") for b in reference_bytes_list
        ]
    # POST /v1/images/generate ... (same as before)

# edit_image_with_codex(): DELETE. Callers migrate to generate_image_with_codex
# with reference_bytes_list non-empty.
```

### 6.2 `services/image_fallback.py`

**Current:** `generate_image_with_fallback(prompt, ...)` chains Codex → nanobanana → HF FLUX. No reference image plumbing.

**New:**

```python
async def generate_image_with_fallback(
    prompt: str,
    aspect_ratio: str = "1:1",
    reference_bytes_list: list[bytes] | None = None,
) -> tuple[Path | None, str | None, str]:
    reference_bytes_list = reference_bytes_list or []
    
    # 1. Codex (primary, multi-image native)
    if is_codex_image_available():
        path, err = await generate_image_with_codex(
            prompt, aspect_ratio,
            reference_bytes_list=reference_bytes_list,
        )
        if path:
            return path, None, "codex"
        codex_err = err
    
    # 2. nanobanana (multi-image via files=[paths])
    if reference_bytes_list:
        # nanobanana wants file paths; spill bytes to a temp dir
        temp_paths = _spill_bytes_to_temp(reference_bytes_list)
        try:
            path, err = await call_nanobanana_generate_image(
                prompt=prompt, files=temp_paths, aspect_ratio=aspect_ratio,
            )
            if path:
                return path, None, "nanobanana"
        finally:
            _cleanup_temp(temp_paths)
    else:
        # text-to-image nanobanana path (existing)
        path, err = await call_nanobanana_generate_image(prompt=prompt, aspect_ratio=aspect_ratio)
        if path:
            return path, None, "nanobanana"
    
    # 3. HF FLUX (text-only; multi-image gracefully degrades)
    if reference_bytes_list:
        logger.warning(
            "FLUX fallback 不支援 reference images (%d 張)；忽略後送純 prompt",
            len(reference_bytes_list),
        )
    path, err = await generate_image_with_huggingface(prompt)
    return path, err or codex_err, "huggingface" if path else "all_failed"
```

### 6.3 `services/mcp/codex_image_tools.py`

**Current:** Two `@mcp.tool()`s — `codex_generate_image_tool(prompt, aspect_ratio)` and `codex_edit_image_tool(prompt, reference_image, aspect_ratio)`.

**New:** Single unified tool replacing both.

```python
@mcp.tool()
async def codex_image_tool(
    prompt: str,
    reference_images: list[str] | None = None,
    aspect_ratio: str = "1:1",
) -> str:
    """生成或編輯圖片。一個 tool 三種模式：

    1. 純生圖（無參考圖）
       reference_images=None
       prompt: 詳細英文描述

    2. 單張編輯（保留 identity）
       reference_images=["/path/to/image.jpg"]
       prompt: 英文 edit 指令，例「change clothing to black」

    3. 多張合成（composition / outfit-swap / scene-merge / style-transfer）
       reference_images=["/path/a.jpg", "/path/b.jpg", ...]
       prompt: 用 "image 1 / image 2 / ..." 指稱每張圖在合成裡的角色，例
              "place the subject from image 1 into the scene from image 2"

    所有路徑必須在 NAS 或本機合法位置；服務端會驗證。沒有人為的張數上限；
    超過 OpenAI / nanobanana 自己的服務上限時錯誤訊息會原樣回傳。
    """
    reference_images = reference_images or []
    
    # path validation (NAS-relative or absolute) — port from existing
    # codex_edit_image_tool logic
    resolved_paths = []
    for raw in reference_images:
        p = Path(raw)
        if not p.is_absolute():
            p = Path(settings.linebot_local_path) / raw.lstrip("/")
        if not p.exists():
            return f"reference 圖檔不存在：{raw}"
        if p.stat().st_size > 10 * 1024 * 1024:
            return f"reference 圖 {raw} 超過 10 MB"
        resolved_paths.append(p)
    
    reference_bytes_list = [p.read_bytes() for p in resolved_paths] or None
    
    path, err, _ = await generate_image_with_fallback(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        reference_bytes_list=reference_bytes_list,
    )
    if err:
        return f"生圖失敗：{err}"
    return f"圖片已生成：{path}"
```

Old `codex_generate_image_tool` and `codex_edit_image_tool` get deleted in the same commit. All agent system-prompt strings (in `linebot_ai.py`, `bot/ai.py`, `bot_telegram/handler.py`, `services/bot/agents.py`) that reference the old tool names get updated.

### 6.4 `_detect_image_edit_references` (new function in `services/message.py` or a new `services/image_edit_detection.py`)

Lives at the message-handler service layer so both LINE and Telegram handlers can call it.

```python
_IMAGE_EDIT_KEYWORDS = (
    "修", "改", "換", "加", "變", "調整", "微調", "保留", "不要改",
    "原樣", "原圖", "原本", "去掉", "刪", "拿掉",
    "顏色", "背景", "黑白", "色調",
    "再生一張", "再畫一張", "重新", "重畫",
    "合成", "組合",
)


async def _detect_image_edit_references(
    db,                                  # asyncpg connection / pool
    *,
    user_id: str,
    group_id: str | None,
    quoted_message_id: str | None,
    text: str,
) -> list[str]:
    """Return absolute temp paths of reference images to attach to this turn.

    Hybrid rule:
      1. quoted_message_id is an image (user replied to a specific photo) → [that one]
      2. text contains an edit keyword AND user has uploaded image(s) since
         their previous text message → those images, chronological
      3. otherwise → []

    No count cap. Memory/network discipline lives at the per-image byte cap.
    """
    if quoted_message_id:
        info = await get_image_info_by_line_message_id(quoted_message_id)
        if info and info.get("nas_path"):
            temp = await ensure_temp_image(quoted_message_id, info["nas_path"])
            if temp:
                return [temp]

    if not any(kw in text for kw in _IMAGE_EDIT_KEYWORDS):
        return []

    # "user 上一筆 text 之後" — get the timestamp
    last_user_text_at = await db.fetchval(
        """
        SELECT COALESCE(MAX(created_at), '1970-01-01'::timestamptz)
        FROM messages
        WHERE line_user_id = $1
          AND line_group_id IS NOT DISTINCT FROM $2
          AND role = 'user'
          AND content IS NOT NULL
          AND content <> ''
        """,
        user_id, group_id,
    )

    rows = await db.fetch(
        """
        SELECT nas_path, line_message_id
        FROM images
        WHERE line_user_id = $1
          AND line_group_id IS NOT DISTINCT FROM $2
          AND created_at > $3
        ORDER BY created_at ASC
        """,
        user_id, group_id, last_user_text_at,
    )

    paths = []
    for r in rows:
        temp = await ensure_temp_image(r["line_message_id"], r["nas_path"])
        if temp:
            paths.append(temp)
    return paths
```

**Note on `bot-generated images as reference`:** the `images` table already records LINE-uploaded user photos. When the bot REPLIES with a generated image (e.g. via `prepare_file_message`), today's code does **not** record that into the `images` table. We update the message-store layer to also insert bot-generated images so that "user replies to a bot's image and says '再加個皇冠'" works via the quoted-reply branch. This is a small additional change captured in §6.5.

### 6.5 Bot-generated images recorded in `images` table

In whatever pathway bot-generated images get sent back to the user (probably `services/bot_line/message_store.py:save_message` or the file-message-prep function), add an `INSERT INTO images` for the generated PNG with `line_message_id` = the LINE sent-message id. This makes them queryable for the quoted-reply branch of the detector.

If this requires a schema migration to mark `source = 'user' | 'bot'`, do it; otherwise just write the row with whatever marker the existing schema supports.

### 6.6 Telegram albums (`media_group_id`)

Telegram natively groups multi-image uploads via a `media_group_id`. The detection algorithm gains a small extension on the Telegram side:

```python
# in bot_telegram/handler.py text-message branch:
if message.reply_to_message and message.reply_to_message.media_group_id:
    # User replied to a Telegram album → all images in that album become refs
    refs = await get_images_by_media_group_id(message.reply_to_message.media_group_id)
    return refs
# ... else falls through to the same _detect_image_edit_references shared logic
```

LINE has no equivalent native grouping, so it falls back to the time-based "since last text" heuristic.

### 6.7 LINE / Telegram handler wiring

`linebot_ai.py` and `bot_telegram/handler.py` both:

1. Replace the existing `quoted_image_path = ...` block with a single `reference_image_paths = await _detect_image_edit_references(...)` call.
2. When `reference_image_paths`, prepend a `[N 張參考圖: <paths>]` marker to `user_message` (replaces the old `[回覆圖片: <path>]` marker; old singular case still works because list of 1 still renders).
3. Update the agent system-prompt block that lists available image tools — drop references to `codex_generate_image_tool` / `codex_edit_image_tool`, point at unified `codex_image_tool`. Include short usage guidance for the three modes.

## 7. Side Tasks (separate PRs)

After ching-tech-os ships:

**Side-PR A — `codex-image-service`:**
```python
# app/models.py
- reference_images_base64: list[str] | None = Field(default=None, max_length=4)
+ reference_images_base64: list[str] | None = Field(default=None)
```
Update test asserting "5 items rejected" to delete.

**Side-PR B — `ctos-lite`:**
```python
# services/mcp_server.py
- _MAX_REFERENCE_IMAGES = 4
- if len(reference_image_paths) > _MAX_REFERENCE_IMAGES: return "..."
+ # (cap removed; per-image 10 MB still enforced below)

# services/message_handler.py — _detect_image_edit_references
- def _detect_image_edit_references(..., max_images: int = 4) -> list[str]:
+ def _detect_image_edit_references(...) -> list[str]:
- if len(refs) >= max_images: break
+ # (no cap)
```
Update test asserting "5+ rejected" / "cap-at-4" to delete or repurpose.

Document in each PR: "OpenAI's gpt-image edit caps at ~16; that's now the real boundary."

## 8. Testing Strategy

### 8.1 New tests

`tests/test_codex_image_multi.py`:
- payload contains `reference_images_base64` array (length matches input)
- empty list / None → no `reference_images_base64` key in payload
- legacy singular kwarg → ⛔ delete (we removed `edit_image_with_codex`; old tests for it go)

`tests/test_image_fallback_multi.py`:
- Codex success path: list of bytes flows through
- Codex fail → nanobanana with `files=[temp paths]`
- All multi backends fail → HF FLUX path runs with `text-only warning`, returns text-only result
- Temp paths cleaned up regardless of success/failure

`tests/test_image_edit_detection.py`:
- `_detect_image_edit_references` quoted-reply returns `[image]`
- No-keyword text → returns `[]`
- 3 consecutive uploads → returns 3 paths chronological
- Text mid-batch breaks the run (returns only post-text uploads)
- No history → returns `[]`
- (No cap-4 test; just check large-N case works.)

`tests/test_telegram_media_group.py`:
- Reply to a media_group_id → returns all images in that group
- Reply to a single non-group image → returns 1 image
- No reply, keyword-triggered → falls back to shared detection

### 8.2 Updated tests

`tests/test_codex_image.py`:
- Remove tests for `edit_image_with_codex`. Existing payload-shape tests for `generate_image_with_codex` already match the new signature.

`tests/test_image_fallback.py`:
- Update fallback chain assertions to thread `reference_bytes_list=None` through; existing single-path tests stay green.

`tests/test_huggingface_image_service.py`:
- Unchanged (HF FLUX path is unchanged for text-only callers).

## 9. Manual Smoke (post-merge)

- [ ] LINE: drop 2 photos + type "把第一張的人放到第二張的場景, preserve face" → confirm result is a real composition with both subjects preserved.
- [ ] LINE: drop 5 photos + type "合成" → confirm all 5 reach codex-image-service (check logs); confirm OpenAI either accepts or returns a clear "too many references" error which we surface verbatim.
- [ ] Telegram: reply to a media album → confirm all images in the album become references (album path).
- [ ] LINE: quoted-reply to a single image + type "改成黑白" → confirm single-image edit still works (regression check).
- [ ] Reply to a bot-generated image + type "再加皇冠" → confirm bot's own image is found in images table and used as ref (the §6.5 behaviour).

## 10. Risks

- **`prepare_file_message` / bot reply pathway** may not currently write to the `images` table. §6.5 surfaces that — needs touching code we haven't yet inspected line-by-line. Plan task should explicitly verify before implementing.
- **`linebot_local_path` resolution** in §6.3 path-validation is copy-pasted from the existing `codex_edit_image_tool`. If the existing function had subtle behaviour we missed, it carries through.
- **Telegram media-group webhook ordering** — Telegram delivers album messages as individual events that share a `media_group_id` but may arrive out of order. The detector assumes images are already in the DB before the text message fires. If race conditions surface in real traffic, add a small delay or batch-wait. Out of scope for v1; track as a follow-up.

## 11. Acceptance

Ship-blocking criteria:
- All new + updated tests green.
- Manual smoke checklist §9 items 1, 3, 4 pass on real LINE/Telegram traffic.
- No regression on text-to-image (existing single-image and pure-prompt flows behave identically).
- Old MCP tool names (`codex_generate_image_tool` / `codex_edit_image_tool`) fully removed from agent system prompts (grep for them returns nothing under `backend/src`).

Nice-to-have (not blocking):
- Side-PRs A and B (cap removal on the other two repos) opened.
- §9 item 2 (5-photo soak) actually exercised once to characterise the OpenAI rejection threshold.
