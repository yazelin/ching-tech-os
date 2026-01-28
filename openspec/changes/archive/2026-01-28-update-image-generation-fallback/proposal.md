# Change: 調整圖片生成 Fallback 機制與模型資訊顯示

## Why

nanobanana-py 已內建 Gemini 模型的自動 fallback 機制（gemini-3-pro → gemini-2.5-flash），但目前：
1. AI 回覆未告知用戶實際使用的模型，導致用戶在圖片品質不如預期時無法理解原因
2. ching-tech-os 的 `image_fallback.py` 中的 Gemini Flash 層與 nanobanana 內建 fallback 重複

## What Changes

1. **調整 AI Prompt**：讓 AI 根據 nanobanana 回應中的 `modelUsed` 和 `usedFallback` 欄位，在回覆中告知用戶使用了哪個模型
   - `gemini-3-pro-image-preview` → 不特別說明（預設高品質模型）
   - `gemini-2.5-flash-image` → 「（快速模式）」
   - `flux` → 「（備用服務）」

2. **簡化 Fallback 機制**：
   - 移除 `image_fallback.py` 中的 Gemini Flash 直接 API 呼叫
   - 保留 FLUX 作為 nanobanana MCP 完全失敗（timeout/錯誤）時的最後備用
   - Gemini 內部的 fallback 由 nanobanana MCP 自行處理

3. **更新資料庫 Prompt**：同步更新 `ai_prompts` 表中 `linebot-personal` 的內容

## Impact

- Affected specs: `ai-management`
- Affected code:
  - `backend/src/ching_tech_os/services/image_fallback.py` - 簡化為只保留 FLUX fallback
  - `backend/src/ching_tech_os/services/linebot_ai.py` - 調整 fallback 呼叫邏輯
  - `backend/migrations/versions/` - 新增 migration 更新 prompt
  - 資料庫 `ai_prompts` 表 - 更新 `linebot-personal` prompt 內容
