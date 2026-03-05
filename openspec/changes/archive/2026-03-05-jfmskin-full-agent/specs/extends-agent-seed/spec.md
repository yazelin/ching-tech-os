## ADDED Requirements

### Requirement: extends Agent seed 機制
系統 SHALL 在啟動時掃描 `extends/*/clients/*/agents/*.md`，自動將 Agent prompt 建立到資料庫。

#### Scenario: 首次啟動建立 Agent
- **WHEN** 系統啟動且資料庫中不存在該 Agent（依 name 判斷）
- **THEN** SHALL 讀取 `.md` 檔案的 frontmatter（model、display_name、tools）和 body（prompt）
- **THEN** SHALL 在 `ai_prompts` 表建立 prompt 記錄
- **THEN** SHALL 在 `ai_agents` 表建立 Agent 記錄，關聯到該 prompt

#### Scenario: Agent 已存在時不覆蓋
- **WHEN** 系統啟動且資料庫中已存在同名 Agent
- **THEN** SHALL 跳過，不更新 prompt 或設定
- **THEN** SHALL log info 說明已跳過

#### Scenario: frontmatter 解析
- **WHEN** 讀取 Agent `.md` 檔案
- **THEN** SHALL 解析 YAML frontmatter 中的 `model`、`display_name`、`tools` 欄位
- **THEN** frontmatter 之後的內容 SHALL 作為 system prompt

#### Scenario: 檔案名稱即 Agent name
- **WHEN** 檔案為 `agents/jfmskin-full.md`
- **THEN** Agent 的 `name` SHALL 為 `jfmskin-full`（去掉 `.md` 副檔名）

#### Scenario: extends 目錄不存在
- **WHEN** `extends/` 目錄不存在或無 clients/ 子目錄
- **THEN** SHALL 靜默跳過，不報錯
