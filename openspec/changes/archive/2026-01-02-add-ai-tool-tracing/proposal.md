# Proposal: add-ai-tool-tracing

## Summary
增強 AI Log 系統，記錄並視覺化 Claude CLI 的工具調用過程，讓使用者能夠清楚了解 AI 處理請求時的執行流程。

## Problem Statement
目前 AI Log 只記錄最終的輸入和輸出文字，無法得知：
- AI 調用了哪些工具（MCP tools）
- 每個工具的輸入參數和輸出結果
- 工具調用的順序
- Token 使用量（Claude CLI 純文字模式不提供）

這導致在除錯或分析 AI 行為時，缺乏足夠的資訊來理解 AI 的決策過程。

## Proposed Solution
1. **後端**：修改 Claude CLI 調用方式，使用 `--output-format stream-json --verbose` 獲取完整的執行流程
2. **後端**：解析 stream-json 輸出，提取工具調用記錄並存入 `parsed_response` 欄位
3. **前端**：在 AI Log 詳情面板新增「執行流程」區塊，視覺化顯示工具調用順序（含輸入輸出）

## Scope
- **修改**：`ai-management` spec 的 AI Log 相關 requirements
- **不影響**：Line Bot 和 Web Chat 的調用方式（仍使用 `response.message` 取得最終回應）

## Success Criteria
- AI Log 詳情頁面能顯示工具調用流程
- 每個工具調用顯示名稱、輸入參數、輸出結果
- 輸入輸出支援收合/展開
- Log 中記錄正確的 token 使用量
- 現有功能（Line Bot、Web Chat）不受影響
