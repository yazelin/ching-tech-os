### Requirement: Skills 管理（管理員）

Skills 管理 SHALL 支援完整的 CRUD 操作和 ClawHub marketplace 整合。

#### Scenario: 列出已安裝 Skills
- **WHEN** 管理員請求 `GET /api/skills`
- **THEN** 系統回傳所有已載入的 skills
- **AND** 每個 skill 包含 name、description、requires_app、tools_count、source、license

#### Scenario: 編輯 Skill 權限
- **WHEN** 管理員請求 `PUT /api/skills/{name}`
- **AND** 提供 requires_app、allowed_tools、mcp_servers
- **THEN** 系統更新 SKILL.md 的 frontmatter（metadata.ctos + allowed-tools）
- **AND** 觸發 SkillManager 重載
- **AND** 回傳更新後的 skill 資料

#### Scenario: 移除 Skill
- **WHEN** 管理員請求 `DELETE /api/skills/{name}`
- **AND** 該 skill 存在
- **THEN** 系統刪除 skill 目錄
- **AND** 觸發 SkillManager 重載

#### Scenario: 搜尋 ClawHub
- **WHEN** 管理員請求 `POST /api/skills/hub/search`
- **AND** 提供搜尋關鍵字
- **THEN** 系統呼叫 clawhub search
- **AND** 回傳搜尋結果（name、version、description、score）

#### Scenario: 從 ClawHub 安裝 Skill
- **WHEN** 管理員請求 `POST /api/skills/hub/install`
- **AND** 提供 skill name
- **THEN** 系統呼叫 clawhub install 下載 skill
- **AND** 呼叫 import_openclaw_skill 匯入
- **AND** 新 skill 預設 requires_app=null、allowed-tools 為空
- **AND** 觸發 SkillManager 重載

#### Scenario: 重載 Skills
- **WHEN** 管理員請求 `POST /api/skills/reload`
- **THEN** 系統清除 SkillManager 快取
- **AND** 重新掃描 skills 目錄
- **AND** 不需重啟服務

#### Scenario: 讀取 Skill 檔案
- **WHEN** 管理員請求 `GET /api/skills/{name}/files/{path}`
- **AND** path 前綴為 references/、scripts/ 或 assets/
- **THEN** 系統回傳檔案內容
- **AND** 路徑穿越檢查通過
