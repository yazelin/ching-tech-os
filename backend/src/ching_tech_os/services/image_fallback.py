"""圖片生成 Fallback 機制

整合兩層圖片生成服務：
1. nanobanana MCP（內建 Gemini Pro → Flash 自動 fallback）
2. Hugging Face FLUX（最後備用，30 秒超時）

nanobanana 內部會自動處理 Gemini 模型間的 fallback，
本模組只負責在 nanobanana 完全失敗時（timeout/錯誤）觸發 FLUX 備用。
"""

import logging
import os
import uuid
from pathlib import Path

from ..config import settings

logger = logging.getLogger("image_fallback")

# 輸出目錄（儲存到 NAS 的 ai-images 目錄）
_nas_ai_images_dir = Path(settings.linebot_local_path) / "ai-images"

# 超時設定
HUGGINGFACE_TIMEOUT = 30  # Hugging Face 超時（秒）


def get_hf_token() -> str | None:
    """取得 Hugging Face API Token"""
    return os.getenv("HUGGINGFACE_API_TOKEN")


async def generate_image_with_huggingface(prompt: str) -> tuple[str | None, str | None]:
    """
    使用 Hugging Face FLUX.1-schnell 生成圖片

    Args:
        prompt: 圖片描述

    Returns:
        (image_path, error_message)
        - 成功: (圖片相對路徑, None)
        - 失敗: (None, 錯誤訊息)
    """
    token = get_hf_token()
    if not token:
        return None, "未設定 HUGGINGFACE_API_TOKEN"

    try:
        # 延遲匯入
        from huggingface_hub import InferenceClient

        logger.info(f"使用 Hugging Face FLUX 生成圖片: {prompt[:50]}...")

        client = InferenceClient(token=token, timeout=HUGGINGFACE_TIMEOUT)

        # 呼叫 API 生成圖片
        image = client.text_to_image(
            prompt,
            model="black-forest-labs/FLUX.1-schnell",
            guidance_scale=0.0,
            num_inference_steps=4,
        )

        # 確保目錄存在
        _nas_ai_images_dir.mkdir(parents=True, exist_ok=True)

        # 儲存圖片
        filename = f"flux_{uuid.uuid4().hex[:8]}.png"
        image_path = _nas_ai_images_dir / filename
        image.save(image_path)

        logger.info(f"Hugging Face 圖片生成成功: {image_path}")
        return f"ai-images/{filename}", None

    except ImportError:
        return None, "未安裝 huggingface_hub"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Hugging Face 圖片生成失敗: {error_msg}")

        if "401" in error_msg or "unauthorized" in error_msg.lower():
            return None, "Hugging Face API Token 無效"
        elif "429" in error_msg or "rate" in error_msg.lower():
            return None, "Hugging Face API 超過速率限制"
        elif "timeout" in error_msg.lower():
            return None, "Hugging Face API 超時"
        else:
            return None, f"Hugging Face 錯誤: {error_msg}"


async def generate_image_with_fallback(
    prompt: str,
    nanobanana_error: str | None = None,
) -> tuple[str | None, str, str | None]:
    """
    FLUX Fallback 圖片生成

    當 nanobanana MCP 完全失敗時（timeout/錯誤），使用 Hugging Face FLUX 作為備用。
    注意：Gemini 模型間的 fallback（Pro → Flash）由 nanobanana MCP 內部處理。

    Args:
        prompt: 圖片描述
        nanobanana_error: nanobanana 的錯誤訊息

    Returns:
        (image_path, service_used, error_message)
        - 成功: (圖片相對路徑, 使用的服務名稱, None)
        - 失敗: (None, "", 錯誤訊息)
    """
    errors = []

    # nanobanana 失敗原因
    if nanobanana_error:
        errors.append(f"nanobanana: {nanobanana_error}")
        logger.info(f"nanobanana 失敗: {nanobanana_error}")

    # 嘗試 Hugging Face FLUX
    if get_hf_token():
        logger.info("嘗試 Hugging Face FLUX...")
        image_path, error = await generate_image_with_huggingface(prompt)
        if image_path:
            return image_path, "Hugging Face FLUX", None
        errors.append(f"Hugging Face: {error}")
        logger.warning(f"Hugging Face 失敗: {error}")
    else:
        logger.info("Hugging Face 未設定，跳過")

    # 所有服務都失敗
    combined_error = "\n".join(errors) if errors else "沒有可用的圖片生成服務"
    return None, "", combined_error


def get_fallback_notification(service_used: str) -> str | None:
    """
    取得 fallback 通知訊息

    當使用備用服務時，回傳給使用者的說明。
    注意：Gemini 模型的 fallback 通知由 AI prompt 處理，這裡只處理 FLUX。

    Args:
        service_used: 使用的服務名稱

    Returns:
        通知訊息，若非 FLUX 則回傳 None
    """
    if service_used == "Hugging Face FLUX":
        return "（使用備用服務）"
    return None
