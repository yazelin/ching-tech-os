"""Hugging Face 圖片生成服務

此模組已被 image_fallback.py 取代。
保留此檔案以確保向後相容，但所有邏輯已移至 image_fallback.py。

請使用 image_fallback.py 的 generate_image_with_fallback() 函數。
"""

import logging

logger = logging.getLogger("huggingface_image")

# 向後相容：重新匯出 image_fallback 的函數
from .image_fallback import (
    generate_image_with_huggingface as generate_image_with_flux,
    get_hf_token,
)


def is_fallback_available() -> bool:
    """檢查備用服務是否可用（向後相容）"""
    return get_hf_token() is not None


async def generate_image_fallback(
    prompt: str,
    original_error: str,
) -> tuple[str | None, bool, str | None]:
    """
    備用圖片生成服務入口（向後相容）

    此函數已被 image_fallback.py 的 generate_image_with_fallback() 取代。
    保留此函數以確保舊程式碼不會出錯。

    Args:
        prompt: 圖片描述
        original_error: 原始服務的錯誤訊息

    Returns:
        (image_path, used_fallback, error_message)
    """
    logger.warning(
        "generate_image_fallback() 已棄用，請使用 image_fallback.generate_image_with_fallback()"
    )

    from .image_fallback import generate_image_with_fallback

    image_path, service_used, error = await generate_image_with_fallback(prompt, original_error)

    if image_path:
        return image_path, True, None
    elif error:
        return None, True, error
    else:
        return None, False, None
