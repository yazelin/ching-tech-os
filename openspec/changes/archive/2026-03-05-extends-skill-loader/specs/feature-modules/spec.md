## MODIFIED Requirements

### Requirement: Module Registry
系統 SHALL 維護一個模組 registry，描述所有可用的功能模組（內建 + Skill 擴充）。每個模組 SHALL 包含 id、source、router 資訊、MCP 工具模組、前端 App 定義、排程任務、權限 App ID 等 metadata。

#### Scenario: 內建模組定義
- **WHEN** 系統啟動
- **THEN** `BUILTIN_MODULES` dict SHALL 包含所有內建功能模組的 `ModuleInfo` 定義

#### Scenario: 合併 Registry
- **WHEN** 呼叫 `get_module_registry()`
- **THEN** SHALL 回傳內建模組 + 已安裝 Skill 模組（含 extends/）的合併 registry
- **THEN** Skill 模組 ID 與內建模組衝突時 SHALL log warning 並跳過該 Skill

#### Scenario: extends Skill 出現在 module registry
- **WHEN** extends/ 中有帶 `contributes` 的 Skill（如 ct-his）
- **THEN** 該 Skill SHALL 出現在 `get_module_registry()` 的回傳中
- **THEN** 其 `source` SHALL 為 `"skill"`（與 external skill 一致）

#### Scenario: SkillManager 不可用
- **WHEN** SkillManager 載入失敗
- **THEN** `get_module_registry()` SHALL 只回傳內建模組，不 raise exception
