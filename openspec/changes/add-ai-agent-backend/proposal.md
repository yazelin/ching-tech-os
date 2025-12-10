# Change: 新增 AI Agent 後端整合

## Status
**PENDING** - 等待 `add-ai-assistant-ui` 完成後再處理

## Why
AI 助手前端 UI 完成後，需要整合 Claude API 後端以提供實際的 AI 對話功能。此 proposal 記錄後端整合的規劃，待前端 UI 完成後再進行實作。

## What Changes
- 新增 FastAPI 後端服務
- 整合 Claude API（支援多種模型）
- 實作對話 session 管理（利用 Claude 的 session 功能）
- 實作 WebSocket 或 SSE 即時通訊
- 前端連接後端 API

## Impact
- Affected specs: 新增 `ai-agent-backend`
- Affected code:
  - `backend/` - 新增 FastAPI 應用
  - `frontend/js/ai-assistant.js` - 修改以連接後端 API

## Technical Notes

### Claude Session 管理
- Claude API 支援 session 功能，可讓使用者切換模型時維持對話上下文
- 每個對話框對應一個獨立的 session
- Session ID 需要持久化於資料庫

### 模型支援
預計支援以下 Claude 模型：
- Claude 3 Opus
- Claude 3 Sonnet
- Claude 3 Haiku

### 架構規劃
```
Frontend (AI Assistant UI)
    ↓ WebSocket / SSE
Backend (FastAPI)
    ↓ httpx
Claude API
```

## Dependencies
- 需先完成 `add-ai-assistant-ui`
- 需先完成 `add-backend-nas-auth`（使用者驗證）

## Out of Scope
- 前端 UI（由 `add-ai-assistant-ui` 處理）
- 其他 AI 服務整合（OpenAI 等）
