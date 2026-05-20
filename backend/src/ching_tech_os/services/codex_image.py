"""自架 codex-image-service HTTP client（吃 ChatGPT 訂閱配額）

文字生圖 + 圖片編輯都支援。失敗時回傳錯誤字串，呼叫者可決定是否退到
nanobanana / HF FLUX 等備援。輸出路徑回傳格式與 huggingface_image /
nanobanana 一致（`ai-images/<filename>` 相對路徑）。
"""

from __future__ import annotations

import base64
import logging
import uuid
from pathlib import Path

import httpx

from ..config import settings

logger = logging.getLogger("codex_image")

# 與 nanobanana / FLUX 共用同一個輸出目錄結構，下游不用區分 provider
_nas_ai_images_dir = Path(settings.linebot_local_path) / "ai-images"

# codex-image-service request timeout — 對齊 nginx proxy_read_timeout
_CODEX_HTTP_TIMEOUT = 650
_CODEX_DOWNLOAD_TIMEOUT = 60

# gpt-image-2 只支援這三種尺寸；其他 aspect_ratio 對應到最近的
_CODEX_SIZE_BY_ASPECT: dict[str, str] = {
    "1:1": "1024x1024",
    "4:3": "1536x1024",
    "16:9": "1536x1024",
    "21:9": "1536x1024",
    "3:4": "1024x1536",
    "9:16": "1024x1536",
}


def is_codex_image_available() -> bool:
    """是否設定了 codex-image-service 的 base URL + api key。"""
    return bool(settings.codex_image_base_url and settings.codex_image_api_key)


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

    try:
        async with httpx.AsyncClient(timeout=_CODEX_HTTP_TIMEOUT) as client:
            resp = await client.post(
                f"{base_url}/v1/images/generate",
                json=payload,
                headers=headers,
            )
    except httpx.ConnectError:
        return None, "Codex 服務無法連線"
    except httpx.TimeoutException:
        return None, f"Codex 等待逾時（>{_CODEX_HTTP_TIMEOUT}s）"
    except Exception as exc:
        logger.exception("Codex 請求失敗")
        return None, f"Codex 請求失敗：{exc}"

    if resp.status_code == 401:
        return None, "Codex API key 無效（401，看起來不是 cimg_ 開頭的 bearer key）"
    if resp.status_code == 403:
        return None, "Codex API key 已停用（403）"
    if resp.status_code != 200:
        body = resp.text[:200] if resp.text else ""
        return None, f"Codex HTTP {resp.status_code}：{body}"

    try:
        data = resp.json()
    except Exception as exc:
        return None, f"Codex 回應不是合法 JSON：{exc}"

    images = data.get("images") or []
    if not images:
        return None, f"Codex 沒回傳圖片：{data}"
    image_url = images[0].get("url", "")
    if not image_url:
        return None, "Codex 回應缺少 image url"

    # 把產出的 PNG 抓下來、存到 NAS ai-images/ 底下
    try:
        async with httpx.AsyncClient(timeout=_CODEX_DOWNLOAD_TIMEOUT) as client:
            png_resp = await client.get(image_url)
    except Exception as exc:
        return None, f"Codex 圖檔下載失敗：{exc}"
    if png_resp.status_code != 200:
        return None, f"Codex 圖檔下載 HTTP {png_resp.status_code}"

    _nas_ai_images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"codex_{uuid.uuid4().hex[:8]}.png"
    image_path = _nas_ai_images_dir / filename
    image_path.write_bytes(png_resp.content)
    logger.info("Codex 圖檔已存：%s（%d bytes）", image_path, len(png_resp.content))
    return f"ai-images/{filename}", None

