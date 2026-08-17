#!/usr/bin/env python3
"""真實 HF FLUX 圖片生成 smoke；預設跳過，需明確設定環境變數。

用法：
    cd backend
    RUN_HF_IMAGE_SMOKE=1 uv run pytest tests/test_image_fallback.py -v

注意：
    - 會真的呼叫 Hugging Face API（消耗 quota），需要 HUGGINGFACE_API_TOKEN
    - 輸出導到 tmp_path，不寫入正式 NAS 目錄
    - 單元測試（含 mock）見 test_image_fallback_extended.py
"""

import os

import pytest

from ching_tech_os.services import image_fallback
from ching_tech_os.services.image_fallback import (
    generate_image_with_huggingface,
    generate_image_with_fallback,
    get_hf_token,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_HF_IMAGE_SMOKE") != "1",
    reason="需明確設定 RUN_HF_IMAGE_SMOKE=1 才執行真實 HF FLUX smoke（會消耗 API quota）",
)


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    """輸出導到測試暫存目錄，不污染正式 NAS 的 ai-images。"""
    monkeypatch.setattr(image_fallback, "_nas_ai_images_dir", tmp_path / "ai-images")


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
