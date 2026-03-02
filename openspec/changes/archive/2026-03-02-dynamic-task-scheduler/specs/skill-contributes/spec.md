## MODIFIED Requirements

### Requirement: SKILL.md contributes 宣告格式
Skill 的 `SKILL.md` frontmatter SHALL 支援 `contributes` 區塊，宣告 Skill 擴充的系統能力。

#### Scenario: 宣告前端 App
- **WHEN** `SKILL.md` 的 `contributes.app` 包含 `id`、`name`、`icon`
- **THEN** 系統 SHALL 將該 Skill 視為一個模組，其 App 出現在桌面應用清單

#### Scenario: 宣告 App Loader
- **WHEN** `contributes.app.loader` 包含 `src` 和 `globalName`
- **THEN** 前端 SHALL 在使用者點擊該 App 時，動態載入 Skill 目錄下的 JS 檔案
- **THEN** `src` 路徑 SHALL 相對於 Skill 安裝目錄

#### Scenario: 宣告 CSS
- **WHEN** `contributes.app.css` 包含 CSS 檔案路徑
- **THEN** 前端 SHALL 在載入 App JS 前先載入該 CSS

#### Scenario: 宣告權限定義
- **WHEN** `contributes.permissions` 包含 App ID 和預設值
- **THEN** 系統 SHALL 將該權限合併進 `DEFAULT_APP_PERMISSIONS`
- **THEN** 管理員 SHALL 可在使用者權限設定中看到並控制該權限

#### Scenario: 宣告 MCP 工具模組
- **WHEN** `contributes.mcp_tools` 包含 Python 檔案路徑
- **THEN** 系統 SHALL 在 MCP Server 啟動時動態載入該檔案中的工具
- **THEN** 路徑 SHALL 相對於 Skill 安裝目錄

#### Scenario: 宣告排程任務（靜態函式）
- **WHEN** `contributes.scheduler` 包含任務定義列表，且項目含有 `fn` 欄位
- **THEN** 系統 SHALL 在啟動時註冊對應的排程任務到 APScheduler（現有行為）

#### Scenario: 宣告排程任務（動態排程）
- **WHEN** `contributes.scheduler` 包含任務定義列表，且項目含有 `executor_type` 欄位
- **THEN** 系統 SHALL 將該排程定義寫入 `scheduled_tasks` 表（若不存在同名排程）
- **THEN** 動態排程 SHALL 由排程執行引擎管理，支援 Agent 和 Skill Script 執行模式

#### Scenario: 無 contributes 的 Skill
- **WHEN** `SKILL.md` 沒有 `contributes` 區塊
- **THEN** Skill SHALL 按現有行為運作（只提供 prompt + 工具白名單 + script）
