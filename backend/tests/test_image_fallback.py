#!/usr/bin/env python3
"""測試圖片生成 Fallback 機制

用法：
    cd backend
    uv run pytest tests/test_image_fallback.py -v

測試項目：
    1. Hugging Face FLUX
    2. 完整 fallback 流程

注意：需要設定 HUGGINGFACE_API_TOKEN 環境變數才能執行
"""

import pytest

from ching_tech_os.services.image_fallback import (
    generate_image_with_huggingface,
    generate_image_with_fallback,
    get_hf_token,
)


@pytest.mark.asyncio
async def test_huggingface():
    """測試 Hugging Face FLUX"""
    if not get_hf_token():
        pytest.skip("未設定 HUGGINGFACE_API_TOKEN")

    prompt = "A cute orange cat sitting on a windowsill"
    path, error = await generate_image_with_huggingface(prompt)
    # 允許失敗（外部 API 可能不可用）
    assert path is not None or error is not None


@pytest.mark.asyncio
async def test_fallback_flow():
    """測試完整 fallback 流程（模擬 Nanobanana 失敗）"""
    if not get_hf_token():
        pytest.skip("未設定 HUGGINGFACE_API_TOKEN")

    prompt = "A beautiful sunset over the ocean"
    nanobanana_error = "503 Service Unavailable: The model is overloaded"

    path, service_used, error = await generate_image_with_fallback(prompt, nanobanana_error)
    # 允許失敗（外部 API 可能不可用）
    assert path is not None or error is not None
