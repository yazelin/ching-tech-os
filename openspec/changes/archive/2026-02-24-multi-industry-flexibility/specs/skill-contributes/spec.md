## ADDED Requirements

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

#### Scenario: 宣告排程任務
- **WHEN** `contributes.scheduler` 包含任務定義列表
- **THEN** 系統 SHALL 在啟動時註冊對應的排程任務到 APScheduler

#### Scenario: 無 contributes 的 Skill
- **WHEN** `SKILL.md` 沒有 `contributes` 區塊
- **THEN** Skill SHALL 按現有行為運作（只提供 prompt + 工具白名單 + script）

### Requirement: hub_meta.py 解析 contributes
`hub_meta.py` SHALL 支援解析 `SKILL.md` frontmatter 中的 `contributes` 區塊。

#### Scenario: 解析完整 contributes
- **WHEN** `SKILL.md` frontmatter 包含 `contributes` 區塊
- **THEN** `parse_skill_md()` SHALL 將 `contributes` 內容存入 Skill metadata

#### Scenario: contributes 欄位驗證
- **WHEN** `contributes.app` 缺少必要欄位（`id`、`name`、`icon`）
- **THEN** SHALL log warning 並忽略 `app` 宣告，Skill 其餘功能正常運作

### Requirement: SkillManager 模組註冊
SkillManager SHALL 在載入 Skill 時，將帶有 `contributes` 的 Skill 註冊為模組。

#### Scenario: 安裝 Skill 觸發模組註冊
- **WHEN** 從 Hub 安裝一個帶有 `contributes` 的 Skill
- **THEN** 該 Skill SHALL 出現在 `get_module_registry()` 的回傳中
- **THEN** 其 App SHALL 出現在 `/api/config/apps` 回傳中

#### Scenario: 卸載 Skill 移除模組
- **WHEN** 卸載一個帶有 `contributes` 的 Skill
- **THEN** 該 Skill SHALL 從模組 registry 中移除
- **THEN** 其 App SHALL 不再出現在桌面

#### Scenario: 模組 ID 衝突
- **WHEN** Skill 的 `contributes.app.id` 與內建模組 ID 相同
- **THEN** SHALL log warning 並跳過該 Skill 的模組註冊
- **THEN** Skill 的 prompt 和工具白名單功能 SHALL 不受影響

### Requirement: Skill 前端資源 Serve
系統 SHALL 提供 API 端點供前端存取 Skill 提供的 JS/CSS 靜態檔案。

#### Scenario: 存取 Skill 前端檔案
- **WHEN** GET `/api/skills/{skill_name}/frontend/{file_path}`
- **THEN** SHALL 從 Skill 安裝目錄的 `frontend/` 子目錄回傳對應的靜態檔案

#### Scenario: 路徑穿越防護
- **WHEN** `file_path` 包含 `..` 或絕對路徑
- **THEN** SHALL 回傳 400 Bad Request

#### Scenario: Skill 不存在
- **WHEN** 指定的 `skill_name` 未安裝
- **THEN** SHALL 回傳 404
