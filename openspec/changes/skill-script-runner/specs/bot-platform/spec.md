# Bot Platform — Script Tool 整合

## Purpose
讓 Claude Code 的 tool calling 支援 script 類 tool，實現從 AI 對話到 script 執行的完整流程。

## ADDED Requirements

### Tool 白名單整合

WHEN SkillManager 產生使用者的 allowed_tools
AND 使用者有權限使用某個 skill
AND 該 skill 有 script tools
THEN script tools 加入 allowed_tools 列表

### Prompt 注入

WHEN 產生 AI 的 system prompt
AND 使用者的 skill 包含 script tools
THEN 在 prompt 中加入 script tools 的使用說明
AND 格式與現有 MCP tool 說明一致

### Tool Call 路由

WHEN AI 回傳一個 tool call
AND tool name 以 `skill__` 開頭
THEN 路由到 ScriptToolRunner 執行
AND 不送到 MCP server

WHEN tool name 以 `mcp__` 開頭
THEN 維持現有行為，路由到 MCP server

### 執行結果記錄

WHEN script tool 執行完成
THEN 記錄到 ai_logs 表
AND model 欄位填入 `script`
AND input_prompt 記錄 script 名稱和參數
AND raw_response 記錄 stdout
AND error_message 記錄 stderr（如有）
AND duration_ms 記錄執行時間

## Scenarios

### 使用者透過 Line Bot 呼叫 script tool
GIVEN 使用者有 weather skill 權限
AND weather skill 有 `skill__weather__get_forecast` tool
WHEN 使用者問「台北天氣如何？」
THEN AI 決定呼叫 `skill__weather__get_forecast`
AND ScriptToolRunner 執行 `scripts/get_forecast.py --city Taipei`
AND 回傳結果給 AI
AND AI 整理後回覆使用者

### MCP tool 和 Script tool 並存
GIVEN 使用者有 ai-assistant skill（MCP tools）和 weather skill（script tools）
WHEN 產生 allowed_tools
THEN 同時包含 `mcp__nanobanana__generate_image` 和 `skill__weather__get_forecast`
AND AI 可以在同一次對話中使用兩種 tool
