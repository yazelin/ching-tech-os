## MODIFIED Requirements

### Requirement: SkillManager 模組註冊
SkillManager SHALL 在載入 Skill 時，將帶有 `contributes` 的 Skill 註冊為模組。

#### Scenario: extends/ 目錄掃描
- **WHEN** SkillManager 執行 `_load_skills_sync()`
- **THEN** SHALL 依序掃描三個目錄：external → extends → native
- **THEN** extends 目錄路徑 SHALL 預設為 `{project_root}/extends/`
- **THEN** extends 目錄不存在時 SHALL 靜默跳過，不報錯

#### Scenario: extends Skill 的載入優先權
- **WHEN** extends/ 中的 Skill 與 external/ 中的同名
- **THEN** SHALL 保留 external 版本，跳過 extends 版本（external 優先權最高）
- **WHEN** extends/ 中的 Skill 與 native/ 中的同名
- **THEN** SHALL 保留 extends 版本，覆蓋 native 版本

#### Scenario: extends Skill 的 source 標記
- **WHEN** 從 extends/ 載入 Skill
- **THEN** Skill 的 `source` 欄位 SHALL 為 `"extends"`

#### Scenario: extends Skill 的 contributes 宣告
- **WHEN** extends/ 中的 Skill 含有 `contributes` 區塊
- **THEN** SHALL 經由 `_build_skill_module()` 轉換為 `ModuleInfo`
- **THEN** 其 MCP 工具、排程任務、前端 App SHALL 正常註冊

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
