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

# LINE / Telegram 下載圖片的固定暫存區（detector 回傳的路徑會在此）。
# 跟 services/bot/media.py 的 TEMP_IMAGE_DIR 對齊。
_BOT_TEMP_IMAGE_DIR = Path("/tmp/bot-images")


def _is_within(path: Path, root: Path) -> bool:
    """Pathlib.is_relative_to() 在 3.9+ 才有；用 try/except 兼容語意。"""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


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
        # AI 可能被 prompt-injection 騙著傳系統路徑（/etc/passwd 等），所以
        # 只允許 NAS 根目錄與 bot 暫存區兩個 root，其餘一律拒絕。
        allowed_roots = [
            Path(settings.linebot_local_path).resolve(),
            _BOT_TEMP_IMAGE_DIR.resolve(),
        ]
        resolved_paths: list[Path] = []
        for raw in reference_images:
            p = Path(raw)
            if p.is_absolute():
                p = p.resolve()
            else:
                p = (Path(settings.linebot_local_path) / raw.lstrip("/")).resolve()

            if not p.is_file() or not any(
                _is_within(p, root) for root in allowed_roots
            ):
                return f"reference 圖檔不存在或非法路徑：{raw}"

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
