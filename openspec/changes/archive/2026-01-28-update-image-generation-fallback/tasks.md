# Tasks: 調整圖片生成 Fallback 機制

## 1. 更新 AI Prompt

- [x] 1.1 在 `linebot-personal` prompt 的【AI 圖片生成】區塊新增模型資訊說明
  - 說明 nanobanana 回應中的 `modelUsed`、`usedFallback` 欄位含義
  - 指示 AI 在回覆中告知用戶使用的模型
- [x] 1.2 建立 Alembic migration 更新資料庫中的 prompt
  - `004_update_image_generation_prompt.py`

## 2. 簡化 Fallback 機制

- [x] 2.1 修改 `image_fallback.py`
  - 移除 `generate_image_with_gemini_flash()` 函式
  - 移除 `generate_image_with_fallback()` 中的 Gemini Flash 層
  - 只保留 FLUX 作為最後備用
- [x] 2.2 修改 `linebot_ai.py`
  - 調整 fallback 呼叫邏輯，只在 nanobanana 完全失敗時才觸發 FLUX
  - 更新相關註解說明

## 3. 更新通知訊息

- [x] 3.1 修改 `get_fallback_notification()` 函式
  - 移除 "Gemini Flash" 相關通知（已由 prompt 處理）
  - 保留 "Hugging Face FLUX" 通知

## 4. 測試驗證

- [x] 4.1 測試 nanobanana 成功（Pro 模型）情境
- [x] 4.2 測試 nanobanana fallback（Flash 模型）情境 - 確認 AI 有告知用戶
- [x] 4.3 測試 nanobanana 完全失敗 → FLUX fallback 情境
- [x] 4.4 執行 migration 並驗證 prompt 更新成功
