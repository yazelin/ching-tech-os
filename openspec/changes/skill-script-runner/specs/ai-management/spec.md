# AI Management — Script Runner 擴充

## Purpose
讓 SkillManager 能自動將 skill 的 scripts/ 目錄中的腳本註冊為 AI 可呼叫的 tool，實現 ClawHub skill 安裝即可用。

## ADDED Requirements

### Script 掃描與註冊

WHEN SkillManager 載入一個 skill
AND 該 skill 的目錄下有 `scripts/` 子目錄
THEN 掃描所有 `.py` 和 `.sh` 檔案
AND 為每個 script 產生一個 tool，命名為 `skill__{skill_name}__{script_stem}`
AND 將 tool 加入該 skill 的 allowed_tools 列表

### Script 描述解析

WHEN SKILL.md frontmatter 包含 `scripts` 區塊
THEN 從中提取每個 script 的 description、args、timeout
AND 用這些資訊產生 tool 的 JSON schema

WHEN SKILL.md 沒有 `scripts` 區塊
AND script 檔案開頭有 docstring 或 `# Description:` 註解
THEN 自動提取作為 tool description

WHEN 都沒有描述
THEN 使用預設 description：`Execute {script_name} from {skill_name}`

### Script 執行

WHEN AI 呼叫一個 script tool
THEN 以 subprocess 方式執行對應的 script
AND 注入環境變數：SKILL_NAME, SKILL_DIR, SKILL_ASSETS_DIR
AND 透過 CLI args 傳入參數（`--arg_name value` 格式）
AND 設定 timeout（預設 30 秒，可由 SKILL.md 覆蓋）
AND capture stdout 作為 tool 回傳結果
AND capture stderr 作為錯誤訊息

WHEN script 執行超時
THEN 終止 subprocess
AND 回傳錯誤訊息「Script execution timed out after {N} seconds」

WHEN script 回傳非零 exit code
THEN 回傳 stderr 內容作為錯誤訊息

### 環境變數注入

WHEN 執行 script tool
THEN 注入以下環境變數：
  - `SKILL_NAME`: skill 名稱
  - `SKILL_DIR`: skill 目錄的絕對路徑
  - `SKILL_ASSETS_DIR`: assets 目錄的絕對路徑
AND 從 SKILL.md `metadata.openclaw.requires.env` 列出的 key，從 `.env` 繼承

WHEN 必要的環境變數未設定
AND SKILL.md 中標記為 `primaryEnv`
THEN 載入時發出警告：「Skill {name} 缺少環境變數 {key}，script tools 可能無法正常運作」

### 安全隔離

WHEN 執行 script tool
THEN 在獨立的工作目錄中執行（`/tmp/skill-runner/{session_id}/`）
AND 不繼承主進程的完整環境（只注入明確宣告的變數）
AND script 無法存取 skill 目錄以外的檔案（透過 cwd 限制）

## Scenarios

### 安裝 ClawHub skill 後自動可用
GIVEN 從 ClawHub 安裝了 `weather` skill
AND 該 skill 有 `scripts/get_forecast.py`
WHEN SkillManager 重載
THEN 自動產生 tool `skill__weather__get_forecast`
AND 該 tool 出現在 skill 的 allowed_tools 中
AND AI 可以呼叫此 tool

### 手動覆蓋 tool 列表
GIVEN skill `weather` 有 3 個 scripts
AND 管理員透過 UI 移除其中 1 個 tool
WHEN SkillManager 重載
THEN 保留管理員的覆蓋設定
AND 只有 2 個 tool 可用

### Script 需要 API key
GIVEN skill `ai-ppt-generator` 的 SKILL.md 宣告 `primaryEnv: BAIDU_API_KEY`
AND `.env` 中沒有 `BAIDU_API_KEY`
WHEN SkillManager 載入此 skill
THEN 發出警告 log
AND script tools 仍然註冊（但執行時可能失敗）
