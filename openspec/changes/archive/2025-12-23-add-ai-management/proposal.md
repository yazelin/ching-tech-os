# Change: 新增 AI 管理系統（4 個獨立應用）

## Why
系統需要整合多種 AI 助手場景（前端對話、Line Bot、系統服務），並提供統一的 Prompt 管理和調用日誌記錄功能。目前 AI 助手的 Prompt 採用檔案管理，不便於動態調整；且缺乏 AI 調用日誌，無法追蹤和優化 Prompt 效果。

採用 4 個獨立應用的設計，可以同時開啟並排列在螢幕上，實現「改 Prompt → 測試對話 → 看 Log」的即時反饋工作流程。

## What Changes
- **ADDED** 新增 `ai-management` 能力規格
  - AI Agent 設定管理（名稱、描述、model、system prompt 關聯）
  - AI Prompt 動態管理（資料庫 CRUD，取代檔案式管理）
  - AI Log 記錄（輸入、輸出、token 統計、執行時間）
- **MODIFIED** 現有 `AI 對話` 應用改用資料庫的 Agent/Prompt 設定
- **ADDED** 新增 `Prompt 編輯器` 應用
- **ADDED** 新增 `Agent 設定` 應用
- **ADDED** 新增 `AI Log` 應用
- **ADDED** 資料庫分區表管理（AI Log 長期保留）

## Impact
- Affected specs: `ai-management` (新增), `ai-assistant-ui` (修改)
- Affected code:
  - 後端：新增 `api/ai.py`, `services/ai_manager.py`, `models/ai.py`
  - 後端：修改 `services/ai_chat.py` 改用 Agent/Prompt 設定
  - 前端：修改 `js/apps/ai-assistant.js` 支援 Agent/Prompt
  - 前端：新增 `js/apps/prompt-editor.js`
  - 前端：新增 `js/apps/agent-settings.js`
  - 前端：新增 `js/apps/ai-log.js`
  - 資料庫：新增 migration 建立 AI 管理相關資料表
- 未來 Line Bot、系統服務等將依賴此架構

## Dependencies
- 無外部依賴
- 此提案為基礎架構，`add-line-bot` 將依賴此提案
