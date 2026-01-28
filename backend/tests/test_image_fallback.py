#!/usr/bin/env python3
"""測試圖片生成 Fallback 機制

用法：
    cd backend
    uv run pytest tests/test_image_fallback.py -v

測試項目：
    1. Gemini Flash 直接呼叫
    2. Hugging Face FLUX
    3. 完整 fallback 流程
"""

import asyncio

from ching_tech_os.services.image_fallback import (
    generate_image_with_gemini_flash,
    generate_image_with_huggingface,
    generate_image_with_fallback,
    get_gemini_api_key,
    get_hf_token,
)


async def test_gemini_flash():
    """測試 Gemini Flash 直接呼叫"""
    print("\n" + "=" * 50)
    print("測試 1: Gemini Flash 直接呼叫")
    print("=" * 50)

    if not get_gemini_api_key():
        print("❌ 跳過：未設定 NANOBANANA_GEMINI_API_KEY")
        return False

    prompt = "A cute orange cat sitting on a windowsill"
    print(f"Prompt: {prompt}")
    print("呼叫中...")

    path, error = await generate_image_with_gemini_flash(prompt)

    if path:
        print(f"✅ 成功！圖片路徑: {path}")
        return True
    else:
        print(f"❌ 失敗: {error}")
        return False


async def test_huggingface():
    """測試 Hugging Face FLUX"""
    print("\n" + "=" * 50)
    print("測試 2: Hugging Face FLUX")
    print("=" * 50)

    if not get_hf_token():
        print("❌ 跳過：未設定 HUGGINGFACE_API_TOKEN")
        return False

    prompt = "A cute orange cat sitting on a windowsill"
    print(f"Prompt: {prompt}")
    print("呼叫中...")

    path, error = await generate_image_with_huggingface(prompt)

    if path:
        print(f"✅ 成功！圖片路徑: {path}")
        return True
    else:
        print(f"❌ 失敗: {error}")
        return False


async def test_fallback_flow():
    """測試完整 fallback 流程（模擬 Pro 失敗）"""
    print("\n" + "=" * 50)
    print("測試 3: Fallback 流程（模擬 Gemini Pro 失敗）")
    print("=" * 50)

    prompt = "A beautiful sunset over the ocean"
    nanobanana_error = "503 Service Unavailable: The model is overloaded"

    print(f"Prompt: {prompt}")
    print(f"模擬錯誤: {nanobanana_error}")
    print("呼叫中...")

    path, service_used, error = await generate_image_with_fallback(prompt, nanobanana_error)

    if path:
        print(f"✅ 成功！")
        print(f"   使用服務: {service_used}")
        print(f"   圖片路徑: {path}")
        return True
    else:
        print(f"❌ 所有服務都失敗:")
        print(f"   {error}")
        return False


async def main():
    print("圖片生成 Fallback 測試")
    print("=" * 50)

    # 檢查環境變數
    print("\n環境變數檢查:")
    print(f"  NANOBANANA_GEMINI_API_KEY: {'✅ 已設定' if get_gemini_api_key() else '❌ 未設定'}")
    print(f"  HUGGINGFACE_API_TOKEN: {'✅ 已設定' if get_hf_token() else '❌ 未設定'}")

    results = []

    # 測試 1: Gemini Flash
    results.append(("Gemini Flash", await test_gemini_flash()))

    # 測試 2: Hugging Face
    results.append(("Hugging Face", await test_huggingface()))

    # 測試 3: Fallback 流程
    results.append(("Fallback 流程", await test_fallback_flow()))

    # 總結
    print("\n" + "=" * 50)
    print("測試結果總結")
    print("=" * 50)
    for name, success in results:
        status = "✅ 通過" if success else "❌ 失敗/跳過"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
