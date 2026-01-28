# Change: 新增 Gemini 模型自動 Fallback 機制

## Why
目前圖片生成使用 `gemini-3-pro-image-preview` 模型（透過 nanobanana MCP），但該預覽版模型在 Google 風控或高負載時經常無回應（超時 5-8 分鐘）。測試顯示 `gemini-2.5-flash-image` 模型目前穩定可用（回應時間 4-6 秒），可作為備用方案。

## What Changes
- **降低 nanobanana 超時時間**：從 480 秒降至 240 秒，加快 fallback 觸發
- 新增直接呼叫 Gemini API 的功能（用於 fallback）
- 實作三層 fallback 機制：
  1. nanobanana MCP → `gemini-3-pro-image-preview`（Pro，品質最好，240 秒超時）
  2. 直接 API → `gemini-2.5-flash-image`（Flash，穩定快速，30 秒超時）
  3. Hugging Face FLUX（最後備用，30 秒超時）
- 當使用備用服務時，在 Line Bot 回覆中通知使用者
- 總等待時間從 480+ 秒降至最多 300 秒（5 分鐘）

## Impact
- Affected specs: `line-bot`
- Affected code:
  - `backend/src/ching_tech_os/services/image_fallback.py` - 新增，整合所有 fallback 邏輯
  - `backend/src/ching_tech_os/services/linebot_ai.py` - 修改，整合新的 fallback 機制、降低超時時間
  - `backend/src/ching_tech_os/services/huggingface_image.py` - 修改，移除 fallback 入口（移至新模組）
