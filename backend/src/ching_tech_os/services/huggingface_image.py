"""Hugging Face 圖片生成服務

作為 nanobanana (Gemini) 的備用圖片生成服務，
使用 FLUX.1-schnell 模型。
"""

import logging
import os
import uuid
from pathlib import Path

from ..config import settings

logger = logging.getLogger("huggingface_image")

# 輸出目錄（直接儲存到 NAS 的 ai-images 目錄，與 nanobanana 相同）
_nas_ai_images_dir = Path(settings.linebot_local_path) / "ai-images"

# Hugging Face 設定
HF_MODEL = "black-forest-labs/FLUX.1-schnell"


def get_hf_token() -> str | None:
    """取得 Hugging Face API Token"""
    return os.getenv("HUGGINGFACE_API_TOKEN")


def is_fallback_available() -> bool:
    """檢查備用服務是否可用"""
    return get_hf_token() is not None


async def generate_image_with_flux(prompt: str) -> tuple[str | None, str | None]:
    """
    使用 Hugging Face FLUX.1-schnell 生成圖片

    Args:
        prompt: 圖片描述

    Returns:
        (image_path, error_message)
        - 成功: (圖片路徑, None)
        - 失敗: (None, 錯誤訊息)
    """
    token = get_hf_token()
    if not token:
        return None, "未設定 HUGGINGFACE_API_TOKEN"

    try:
        # 延遲匯入，避免未安裝時報錯
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=token)

        logger.info(f"使用 Hugging Face FLUX 生成圖片: {prompt[:50]}...")

        # 呼叫 API 生成圖片
        # FLUX.1-schnell 建議 guidance_scale=0, num_inference_steps=4
        image = client.text_to_image(
            prompt,
            model=HF_MODEL,
            guidance_scale=0.0,
            num_inference_steps=4,
        )

        # 確保 NAS 目錄存在
        _nas_ai_images_dir.mkdir(parents=True, exist_ok=True)

        # 儲存圖片到 NAS（與 nanobanana 相同位置）
        filename = f"flux_{uuid.uuid4().hex[:8]}.png"
        image_path = _nas_ai_images_dir / filename
        image.save(image_path)

        logger.info(f"Hugging Face 圖片生成成功: {image_path}")
        # 回傳 ai-images/ 相對路徑，方便後續處理
        return f"ai-images/{filename}", None

    except ImportError:
        error = "未安裝 huggingface_hub，請執行 uv add huggingface_hub"
        logger.error(error)
        return None, error

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Hugging Face 圖片生成失敗: {error_msg}")

        # 解析常見錯誤
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            return None, "Hugging Face API Token 無效"
        elif "429" in error_msg or "rate" in error_msg.lower():
            return None, "Hugging Face API 超過速率限制，請稍後再試"
        elif "503" in error_msg or "unavailable" in error_msg.lower():
            return None, "Hugging Face 服務暫時無法使用"
        else:
            return None, f"Hugging Face 錯誤: {error_msg}"


async def generate_image_fallback(
    prompt: str,
    original_error: str,
) -> tuple[str | None, bool, str | None]:
    """
    備用圖片生成服務入口

    Args:
        prompt: 圖片描述
        original_error: 原始服務（nanobanana）的錯誤訊息

    Returns:
        (image_path, used_fallback, error_message)
        - 成功: (圖片路徑, True, None)
        - 失敗: (None, True, 錯誤訊息)
        - 未啟用: (None, False, None)
    """
    if not is_fallback_available():
        logger.info("備用服務未設定，跳過")
        return None, False, None

    # 檢查是否應該觸發備用
    should_fallback = any(
        keyword in original_error.lower()
        for keyword in ["overloaded", "quota", "limit", "503", "429", "timeout"]
    )

    if not should_fallback:
        logger.info(f"錯誤類型不觸發備用: {original_error[:50]}")
        return None, False, None

    logger.info(f"觸發備用服務，原始錯誤: {original_error[:50]}")

    image_path, error = await generate_image_with_flux(prompt)

    if image_path:
        return image_path, True, None
    else:
        return None, True, error
