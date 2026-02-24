## MODIFIED Requirements

### Requirement: Hub 多來源整合
Hub 來源 SHALL 支援安裝帶有 `contributes` 宣告的 Skill，安裝後自動擴充系統功能。

#### Scenario: 列出可用來源
- **WHEN** 呼叫 `GET /api/skills/hub/sources`
- **THEN** SHALL 回傳已啟用的 Hub 來源列表（ClawHub + SkillHub if enabled）

#### Scenario: 多來源搜尋
- **WHEN** 呼叫 `GET /api/skills/hub/search?q=keyword`
- **THEN** SHALL 從所有啟用來源搜尋並合併結果

#### Scenario: 指定來源安裝
- **WHEN** 呼叫 `POST /api/skills/hub/install` 安裝帶有 `contributes` 的 Skill
- **THEN** SHALL 安裝 Skill 並將其 `contributes` 註冊為模組
- **THEN** 下次 `get_module_registry()` 呼叫 SHALL 包含該 Skill 模組

### Requirement: Skills 管理 API
Skills API SHALL 支援管理帶有 `contributes` 的 Skill 模組。

#### Scenario: 列出已安裝 skills
- **WHEN** 呼叫 `GET /api/skills`
- **THEN** SHALL 回傳所有已安裝 skills，帶有 `contributes` 的 SHALL 標記 `has_module: true`

#### Scenario: 更新 skill 權限與白名單
- **WHEN** 呼叫 `PUT /api/skills/{name}` 更新權限
- **THEN** SHALL 更新該 skill 的 app 權限和工具白名單

#### Scenario: 移除 skill
- **WHEN** 呼叫 `DELETE /api/skills/{name}` 移除帶有 `contributes` 的 Skill
- **THEN** SHALL 同時移除其模組註冊
- **THEN** 其 App SHALL 從桌面消失
- **THEN** 其 MCP 工具 SHALL 不再可用

#### Scenario: 不重啟重載
- **WHEN** 呼叫 `POST /api/skills/reload`
- **THEN** SHALL 重新掃描 Skill 目錄並更新模組 registry

## ADDED Requirements

### Requirement: Skill contributes 感知
SkillManager SHALL 在載入 Skill 時解析 `contributes` 區塊，並將相關資訊暴露給模組系統。

#### Scenario: 載入帶 contributes 的 Skill
- **WHEN** SkillManager 載入一個 Skill，其 `SKILL.md` 包含 `contributes` 區塊
- **THEN** SHALL 將 `contributes` 存入 Skill 的 metadata
- **THEN** `get_all_skills()` 回傳的 Skill 物件 SHALL 包含 `contributes` 資訊

#### Scenario: contributes 的權限合併
- **WHEN** Skill 的 `contributes.permissions` 定義了新的 App 權限
- **THEN** SHALL 合併進系統的 `DEFAULT_APP_PERMISSIONS`
- **THEN** 合併後的權限 SHALL 在 `get_effective_app_permissions()` 中生效
