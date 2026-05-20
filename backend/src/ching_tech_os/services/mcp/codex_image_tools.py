"""Codex Image Service 的 MCP 工具包裝

提供 `codex_generate_image_tool` 與 `codex_edit_image_tool`，作為
nanobanana 的優先替代方案 — 走自架的 codex-image-service（gpt-image-2
edit + generate），消耗主機 ChatGPT 訂閱配額而非 Gemini credits。

工具回傳 `ai-images/<filename>` 相對路徑（與 nanobanana / FLUX 一致），
所以 LINE bot 抽取邏輯與 presentation 配圖流程都不用改 dispatch。
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


@mcp.tool()
async def codex_generate_image_tool(
    prompt: str,
    aspect_ratio: str = "1:1",
) -> str:
    """生成圖片（**優先使用此工具，不要用 nanobanana**）

    透過自架的 codex-image-service 走 gpt-image-2（OpenAI 內建工具，
    吃主機 ChatGPT 訂閱配額而非 Gemini credits）。失敗時回傳錯誤字串，
    呼叫端可改試 mcp__nanobanana__generate_image 作為退路。

    Args:
        prompt: 詳細的英文 / 中文生圖描述，越具體越好
        aspect_ratio: 1:1（預設）/ 4:3 / 3:4 / 16:9 / 9:16 / 21:9
            gpt-image-2 實際只支援 1024x1024、1536x1024、1024x1536 三種，
            非 1:1 / 3:4 / 9:16 都會落到最接近的橫圖（1536x1024）。

    Returns:
        成功：`圖片已生成：ai-images/codex_xxxxxxxx.png`
        失敗：人類可讀的錯誤訊息字串，**呼叫端應改試 nanobanana**
    """
    if not is_codex_image_available():
        return "Codex 未設定 — 請改用 mcp__nanobanana__generate_image"

    if aspect_ratio not in _VALID_ASPECT_RATIOS:
        logger.warning("不支援的 aspect_ratio=%r，降回 1:1", aspect_ratio)
        aspect_ratio = "1:1"

    image_path, error = await generate_image_with_codex(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
    )
    if error:
        return f"Codex 生圖失敗：{error}"
    return f"圖片已生成：{image_path}"


@mcp.tool()
async def codex_edit_image_tool(
    prompt: str,
    reference_image: str,
    aspect_ratio: str = "1:1",
) -> str:
    """編輯現有圖片（**優先使用此工具，不要用 nanobanana 的 edit_image**）

    透過 codex-image-service 走 gpt-image-2 edit 模式。把 reference 圖
    base64 encode 後 POST 給服務、由 Codex CLI 餵給內建 image_gen 工具。

    Args:
        prompt: 編輯指令（e.g.「把背景換成夜晚海邊」、「加上紅色蝴蝶結」）
        reference_image: 既存圖片本機絕對路徑或相對於 NAS 的路徑
            （例如 LINE 用戶上傳到 linebot/files/uploads/xxx.jpg）
        aspect_ratio: 同 codex_generate_image_tool

    Returns:
        成功：`圖片已編輯：ai-images/codex_xxxxxxxx.png`
        失敗：人類可讀錯誤字串
    """
    if not is_codex_image_available():
        return "Codex 未設定 — 請改用 mcp__nanobanana__edit_image"

    if aspect_ratio not in _VALID_ASPECT_RATIOS:
        logger.warning("不支援的 aspect_ratio=%r，降回 1:1", aspect_ratio)
        aspect_ratio = "1:1"

    # 嘗試本機路徑；不存在就嘗試 NAS linebot_local_path 為前綴
    ref_resolved = Path(reference_image)
    if not ref_resolved.is_file():
        nas_path = Path(settings.linebot_local_path) / reference_image.lstrip("/")
        if nas_path.is_file():
            ref_resolved = nas_path
        else:
            return f"reference 圖檔不存在：{reference_image}"

    try:
        ref_bytes = ref_resolved.read_bytes()
    except OSError as exc:
        return f"reference 圖檔讀取失敗：{exc}"

    image_path, error = await generate_image_with_codex(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        reference_bytes_list=[ref_bytes],
    )
    if error:
        return f"Codex 編輯圖失敗：{error}"
    return f"圖片已編輯：{image_path}"
