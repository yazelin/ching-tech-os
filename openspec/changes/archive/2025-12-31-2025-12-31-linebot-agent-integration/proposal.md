# Proposal: linebot-agent-integration

## Summary
Line Bot 整合 AI Agent 系統，使用資料庫中的 Agent/Prompt 設定而非硬編碼，實現原始設計中的 Agent 整合目標。

## Motivation
原始設計文件（add-line-bot/design.md）明確指出：
> 使用 `linebot-personal` AI Agent 處理訊息（來自 ai-management）

但目前實作偏離了設計：
- System Prompt 硬編碼在 `linebot_ai.py` 中
- Model 設定硬編碼為 `"sonnet"`
- AI Log 記錄時 Agent 顯示為 `-`（因為找不到名為 `"linebot"` 的 Agent）

這導致：
1. 無法透過 UI 修改 Line Bot 的 Prompt
2. 個人對話和群組對話使用相同的 Prompt
3. AI Log 無法正確關聯到 Agent

## Scope
- 修改 `linebot_ai.py` 使用資料庫中的 Agent 設定
- 區分 `linebot-personal` 和 `linebot-group` 兩種 Agent
- 在應用程式啟動時確保預設 Agent 存在
- 更新 Prompt 內容包含 MCP 工具說明
- 支援從 Agent 設定讀取內建工具（如 WebSearch）
- 增強個人對話歷史功能（修正查詢、增加長度）
- 實作對話重置功能（`/新對話` 指令）

## Out of Scope
- 不修改 Line Bot 前端介面
- 不修改 AI 管理的 API
- 不新增 Agent 動態切換功能
- 群組對話不支援重置（多人共享歷史，靜默忽略）

## Dependencies
- `ai-management` spec（已實作）
- `line-bot` spec（已實作）
