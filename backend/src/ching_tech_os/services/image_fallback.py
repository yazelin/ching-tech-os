"""圖片生成 Fallback 機制

整合三層圖片生成服務：
1. nanobanana MCP → Gemini 3 Pro（品質最好，240 秒超時）
2. 直接 API → Gemini 2.5 Flash（穩定快速，30 秒超時）
3. Hugging Face FLUX（最後備用，30 秒超時）

總等待時間最多 300 秒（5 分鐘）
"""

import asyncio
import base64
import logging
import os
import uuid
from pathlib import Path

from ..config import settings

logger = logging.getLogger("image_fallback")

# 輸出目錄（儲存到 NAS 的 ai-images 目錄）
_nas_ai_images_dir = Path(settings.linebot_local_path) / "ai-images"

# 超時設定
NANOBANANA_TIMEOUT = 240  # Pro 模型超時（秒）
GEMINI_FLASH_TIMEOUT = 30  # Flash 模型超時（秒）
HUGGINGFACE_TIMEOUT = 30  # Hugging Face 超時（秒）

# Gemini 模型設定
GEMINI_FLASH_MODEL = "gemini-2.5-flash-image"


def get_gemini_api_key() -> str | None:
    """取得 Gemini API Key（與 nanobanana 共用）"""
    return os.getenv("NANOBANANA_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")


def get_hf_token() -> str | None:
    """取得 Hugging Face API Token"""
    return os.getenv("HUGGINGFACE_API_TOKEN")


async def generate_image_with_gemini_flash(prompt: str) -> tuple[str | None, str | None]:
    """
    使用 Gemini 2.5 Flash 直接呼叫 API 生成圖片

    Args:
        prompt: 圖片描述

    Returns:
        (image_path, error_message)
        - 成功: (圖片相對路徑, None)
        - 失敗: (None, 錯誤訊息)
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return None, "未設定 GEMINI_API_KEY"

    try:
        # 延遲匯入
        import httpx

        logger.info(f"使用 Gemini Flash 生成圖片: {prompt[:50]}...")

        # Gemini API 請求
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_FLASH_MODEL}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
            },
        }

        async with httpx.AsyncClient(timeout=GEMINI_FLASH_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Gemini Flash API 錯誤: {response.status_code} - {error_text}")

                if response.status_code == 429:
                    return None, "Gemini Flash API 超過速率限制"
                elif response.status_code == 503:
                    return None, "Gemini Flash 服務暫時無法使用"
                else:
                    return None, f"Gemini Flash API 錯誤: {response.status_code}"

            result = response.json()

        # 解析回應，提取圖片
        candidates = result.get("candidates", [])
        if not candidates:
            return None, "Gemini Flash 未回傳圖片"

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        # 找到圖片 part
        image_data = None
        for part in parts:
            if "inlineData" in part:
                inline_data = part["inlineData"]
                if inline_data.get("mimeType", "").startswith("image/"):
                    image_data = inline_data.get("data")
                    break

        if not image_data:
            return None, "Gemini Flash 回應中沒有圖片"

        # 解碼 base64 並儲存
        image_bytes = base64.b64decode(image_data)

        # 確保目錄存在
        _nas_ai_images_dir.mkdir(parents=True, exist_ok=True)

        # 儲存圖片
        filename = f"gemini_flash_{uuid.uuid4().hex[:8]}.png"
        image_path = _nas_ai_images_dir / filename
        image_path.write_bytes(image_bytes)

        logger.info(f"Gemini Flash 圖片生成成功: {image_path}")
        return f"ai-images/{filename}", None

    except asyncio.TimeoutError:
        logger.warning("Gemini Flash API 超時")
        return None, "Gemini Flash API 超時"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini Flash 圖片生成失敗: {error_msg}")
        return None, f"Gemini Flash 錯誤: {error_msg}"


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
    三層 Fallback 圖片生成

    當 nanobanana (Pro) 失敗時，依序嘗試 Flash 和 Hugging Face。

    Args:
        prompt: 圖片描述
        nanobanana_error: nanobanana 的錯誤訊息（若為 None 表示尚未嘗試，但通常由 linebot_ai 處理）

    Returns:
        (image_path, service_used, error_message)
        - 成功: (圖片相對路徑, 使用的服務名稱, None)
        - 失敗: (None, None, 錯誤訊息)
    """
    errors = []

    # 第一層已由 nanobanana 處理（linebot_ai 呼叫 Claude 時）
    if nanobanana_error:
        errors.append(f"Gemini Pro: {nanobanana_error}")
        logger.info(f"Gemini Pro 失敗: {nanobanana_error}")

    # 第二層：Gemini Flash
    if get_gemini_api_key():
        logger.info("嘗試 Gemini Flash...")
        image_path, error = await generate_image_with_gemini_flash(prompt)
        if image_path:
            return image_path, "Gemini Flash", None
        errors.append(f"Gemini Flash: {error}")
        logger.warning(f"Gemini Flash 失敗: {error}")
    else:
        logger.info("Gemini Flash 未設定，跳過")

    # 第三層：Hugging Face
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

    Args:
        service_used: 使用的服務名稱

    Returns:
        通知訊息，若為主要服務則回傳 None
    """
    if service_used == "Gemini Flash":
        return "（使用備用服務生成，品質可能略有不同）"
    elif service_used == "Hugging Face FLUX":
        return "（使用備用服務生成，風格可能略有不同）"
    return None
