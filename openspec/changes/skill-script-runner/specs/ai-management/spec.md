# AI Management — Script Runner 擴充

## Purpose
透過一個通用 `run_skill_script` MCP tool，讓 AI 能執行 skill 的 scripts/，實現 ClawHub skill 安裝即可用。

## ADDED Requirements

### Script 掃描

WHEN SkillManager 載入一個 skill
AND 該 skill 的目錄下有 `scripts/` 子目錄
THEN 記錄該 skill 有哪些 script（.py, .sh）
AND 提取每個 script 的描述（docstring 或 `# Description:` 註解）

### run_skill_script MCP Tool

WHEN AI 呼叫 `run_skill_script(skill, script, input)`
THEN 先驗證 user 有此 skill 的權限（requires_app 檢查）
AND 驗證 skill 存在且有 scripts/ 目錄
AND 驗證 script 存在於該 skill 的 scripts/ 下
AND 以 subprocess 執行 script
AND 回傳 stdout 作為結果

WHEN skill name 或 script name 包含路徑穿越字元
THEN 拒絕執行，回傳錯誤

WHEN user 沒有此 skill 的 requires_app 權限
THEN 拒絕執行，回傳「無權限使用此 skill」

### Script 執行

WHEN 執行 .py script
AND 系統有 uv
THEN 使用 `uv run {script_path}` 執行（自動處理 dependencies）

WHEN 執行 .py script
AND 系統沒有 uv
THEN 使用 `python3 {script_path}` 執行

WHEN 執行 .sh script
THEN 使用 `bash {script_path}` 執行

WHEN input 不為空
THEN 透過 stdin 傳入 script

WHEN script 執行超過 timeout（預設 30 秒）
THEN 終止 subprocess
AND 回傳「Script 執行逾時」

WHEN script 回傳非零 exit code
THEN 回傳 stderr 內容作為錯誤訊息

### 環境變數

WHEN 執行 script
THEN 注入 SKILL_NAME, SKILL_DIR, SKILL_ASSETS_DIR
AND 從 .env 繼承 SKILL.md metadata.openclaw.requires.env 宣告的變數

### 白名單整合

WHEN 產生 user 的 allowed_tools
AND user 有權限使用至少一個帶 scripts/ 的 skill
THEN 將 `run_skill_script` 加入 allowed_tools

WHEN user 沒有任何帶 scripts/ 的 skill
THEN 不加入 `run_skill_script`

## Scenarios

### ClawHub skill 安裝後可用
GIVEN 管理員從 ClawHub 安裝了 weather skill（有 scripts/get_forecast.py）
AND 管理員設定 weather skill 的 requires_app = null（所有人可用）
WHEN 使用者問「台北天氣」
THEN AI 呼叫 run_skill_script(skill="weather", script="get_forecast", input="Taipei")
AND ScriptRunner 執行 scripts/get_forecast.py
AND 結果回傳給 AI 整理後回覆

### 權限限制
GIVEN weather skill 的 requires_app = "weather-app"
AND 使用者沒有 "weather-app" 權限
WHEN AI 呼叫 run_skill_script(skill="weather", ...)
THEN 回傳「無權限使用此 skill」

### 路徑穿越防護
WHEN AI 呼叫 run_skill_script(skill="../etc", script="passwd", ...)
THEN 拒絕執行
