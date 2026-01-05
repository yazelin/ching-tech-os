# Proposal: AI Log 完整輸入記錄

## Summary
AI Log 需要完整記錄發送給 AI 的所有內容，以便除錯和在其他環境重現測試。

## Problem Statement

### 現況
```
ai_logs 表目前欄位：
- system_prompt  → System Prompt（已有）
- input_prompt   → 只記錄「當前使用者訊息」（已修正為完整對話）
- raw_response   → AI 回應
- parsed_response → 解析後回應（含 tool_calls）
```

### 問題
1. `input_prompt` 只記錄當前訊息，遺失歷史對話 → **已修正**
2. `allowed_tools`（允許使用的工具）未記錄 → **需新增**
3. UI 沒有「複製完整請求」功能 → **需新增**

## Solution

### 資料庫變更
新增 `allowed_tools JSONB` 欄位：
```sql
ALTER TABLE ai_logs ADD COLUMN allowed_tools JSONB;
```

### 後端變更
- `ai_manager.py:call_agent()` 記錄 `allowed_tools`

### 前端變更

#### Log 列表新增 Tools 欄位
在「類型」後、「耗時」前新增 Tools 欄位：
- **可用且有使用**：實心背景 + 白字
- **可用但未使用**：色框 + 色字

#### 詳情頁調整
- Tool Calls 區塊預設全部折疊
- 新增「複製完整請求」按鈕，組合：
  ```
  === System Prompt ===
  {system_prompt}

  === Allowed Tools ===
  {allowed_tools}

  === Messages ===
  {input_prompt}
  ```

## Scope

### In Scope
- Migration 新增 `allowed_tools` 欄位
- 後端記錄 `allowed_tools`
- Log 列表新增 Tools 顯示
- 詳情頁 tool_calls 預設折疊
- 新增「複製完整請求」功能

### Out of Scope
- 歷史資料回填

## Acceptance Criteria

- [ ] `ai_logs` 新增 `allowed_tools` 欄位
- [ ] `call_agent()` 記錄 `allowed_tools`
- [ ] Log 列表顯示 Tools（區分有用/未用）
- [ ] 詳情頁 tool_calls 預設折疊
- [ ] 可複製完整請求（system_prompt + allowed_tools + input_prompt）
