## ADDED Requirements

### Requirement: SkillManager 動態管理

SkillManager SHALL 支援運行時動態管理 skills，不需重啟服務。

#### Scenario: 動態重載
- **GIVEN** 管理員修改了 skills 目錄內容
- **WHEN** 呼叫 `reload_skills()`
- **THEN** SkillManager 清除快取並重新掃描
- **AND** 新增/修改/刪除的 skill 立即生效
- **AND** 不影響正在進行的 AI 對話

#### Scenario: 更新 SKILL.md
- **GIVEN** 一個已存在的 skill
- **WHEN** 呼叫 `update_skill_metadata(name, ...)`
- **THEN** 只更新 SKILL.md 的 YAML frontmatter
- **AND** 保留 Markdown body 內容不變
- **AND** 自動觸發重載

#### Scenario: 匯入外部 Skill 安全性
- **GIVEN** 從 ClawHub 安裝了一個新 skill
- **THEN** 該 skill 預設 requires_app=null（所有人可見 prompt）
- **AND** 該 skill 預設 allowed-tools 為空（AI 不會呼叫任何工具）
- **AND** 管理員必須手動設定 allowed-tools 和 mcp_servers 才會生效
