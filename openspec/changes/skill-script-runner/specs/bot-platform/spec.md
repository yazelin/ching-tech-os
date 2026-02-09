# Bot Platform — Script Tool 整合

## Purpose
讓 Claude Code 的 AI 對話支援 skill script 呼叫，prompt 自動注入使用說明。

## ADDED Requirements

### Prompt 注入

WHEN 產生 AI system prompt
AND user 有權限使用帶 scripts/ 的 skill
THEN 在 prompt 中加入「Script Tools」區塊
AND 列出每個 skill 的 scripts 名稱、描述、用法範例

### Tool Call 路由

WHEN AI 回傳 tool call `run_skill_script`
THEN 路由到 ScriptRunner 執行
AND 將結果回傳給 AI 繼續對話

### 執行記錄

WHEN script 執行完成
THEN 記錄到 ai_logs 表
AND model 欄位填入 "script"
AND input_prompt 記錄 skill + script + input
AND raw_response 記錄 stdout
AND error_message 記錄 stderr（如有）
AND duration_ms 記錄執行時間
> **Note**: ai_logs 記錄為 Phase 3 功能，Phase 1 僅用 logger.info 記錄。

## Scenarios

### 完整對話流程
GIVEN user 有 weather skill 權限
WHEN user 說「台北天氣如何」
THEN AI 在 prompt 中看到 weather skill 的 get_forecast script
AND AI 決定呼叫 run_skill_script(skill="weather", script="get_forecast", input="Taipei")
AND ScriptRunner 執行 → 回傳天氣資訊
AND AI 整理後回覆 user
AND ai_logs 記錄此次 script 執行
