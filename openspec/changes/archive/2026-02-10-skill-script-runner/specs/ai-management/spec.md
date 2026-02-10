# AI Management — Script Runner 擴充

## Purpose
透過一個通用 `run_skill_script` MCP tool，讓 AI 能執行 skill 的 scripts/，實現 ClawHub skill 安裝即可用。

## ADDED Requirements

### Requirement: Script 掃描

SkillManager SHALL 在載入 skill 時自動掃描 scripts/ 目錄，記錄可用的 script 檔案及其描述。

#### Scenario: Skill 有 scripts 目錄
GIVEN SkillManager 載入一個 skill
WHEN 該 skill 的目錄下有 `scripts/` 子目錄
THEN 記錄該 skill 有哪些 script（.py, .sh）
AND 提取每個 script 的描述（docstring 或 `# Description:` 註解）

### Requirement: run_skill_script MCP Tool

系統 SHALL 提供通用的 `run_skill_script(skill, script, input)` MCP tool，執行 skill 的 script 並回傳結果。

#### Scenario: 正常執行
WHEN AI 呼叫 `run_skill_script(skill, script, input)`
THEN 先驗證 user 有此 skill 的權限（requires_app 檢查）
AND 驗證 skill 存在且有 scripts/ 目錄
AND 驗證 script 存在於該 skill 的 scripts/ 下
AND 以 subprocess 執行 script
AND 回傳 stdout 作為結果

#### Scenario: 路徑穿越防護
WHEN skill name 或 script name 包含路徑穿越字元
THEN 拒絕執行，回傳錯誤

#### Scenario: 權限不足
WHEN user 沒有此 skill 的 requires_app 權限
THEN 拒絕執行，回傳「無權限使用此 skill」

### Requirement: Script 執行

ScriptRunner SHALL 根據 script 類型選擇執行方式，支援 timeout 和錯誤處理。

#### Scenario: Python script 有 uv
WHEN 執行 .py script
AND 系統有 uv
THEN 使用 `uv run {script_path}` 執行（自動處理 dependencies）

#### Scenario: Python script 無 uv
WHEN 執行 .py script
AND 系統沒有 uv
THEN 使用 `python3 {script_path}` 執行

#### Scenario: Shell script
WHEN 執行 .sh script
THEN 使用 `bash {script_path}` 執行

#### Scenario: 有 input
WHEN input 不為空
THEN 透過 stdin 傳入 script

#### Scenario: 執行逾時
WHEN script 執行超過 timeout（預設 30 秒）
THEN 終止 subprocess
AND 回傳「Script 執行逾時」

#### Scenario: 執行失敗
WHEN script 回傳非零 exit code
THEN 回傳 stderr 內容作為錯誤訊息

### Requirement: 環境變數

系統 SHALL 在執行 script 時注入必要的環境變數，包括 skill 資訊和 SKILL.md 宣告的外部 API key。

#### Scenario: 注入環境變數
WHEN 執行 script
THEN 注入 SKILL_NAME, SKILL_DIR, SKILL_ASSETS_DIR
AND 從 SKILL.md metadata.openclaw.requires.env 繼承宣告的變數

### Requirement: 白名單整合

系統 SHALL 根據使用者權限動態決定是否加入 run_skill_script tool。

#### Scenario: 有 script skill 的使用者
WHEN 產生 user 的 allowed_tools
AND user 有權限使用至少一個帶 scripts/ 的 skill
THEN 將 `run_skill_script` 加入 allowed_tools

#### Scenario: 無 script skill 的使用者
WHEN user 沒有任何帶 scripts/ 的 skill
THEN 不加入 `run_skill_script`

## Scenarios

### Scenario: ClawHub skill 安裝後可用
GIVEN 管理員從 ClawHub 安裝了 weather skill（有 scripts/get_forecast.py）
AND 管理員設定 weather skill 的 requires_app = null（所有人可用）
WHEN 使用者問「台北天氣」
THEN AI 呼叫 run_skill_script(skill="weather", script="get_forecast", input="Taipei")
AND ScriptRunner 執行 scripts/get_forecast.py
AND 結果回傳給 AI 整理後回覆

### Scenario: 權限限制
GIVEN weather skill 的 requires_app = "weather-app"
AND 使用者沒有 "weather-app" 權限
WHEN AI 呼叫 run_skill_script(skill="weather", ...)
THEN 回傳「無權限使用此 skill」

### Scenario: 路徑穿越防護
WHEN AI 呼叫 run_skill_script(skill="../etc", script="passwd", ...)
THEN 拒絕執行
