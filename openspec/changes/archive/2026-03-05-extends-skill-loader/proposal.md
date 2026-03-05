## Why

ct-his 子模組已重構為標準 SKILL.md 格式（含 contributes 宣告），但 CTOS 的 SkillManager 目前只掃描兩個目錄（external-skills/ 和 native skills/），無法載入 `extends/` 下的子模組。需要讓 SkillManager 支援第三個掃描路徑，使 extends/ 下的 submodule 能自動註冊為 CTOS 模組。

## What Changes

- SkillManager 新增 `extends/` 目錄掃描路徑，載入順序：external → extends → native
- 新增 `EXTENDS_DIR` 設定（預設為 `{project_root}/extends/`）
- extends 中的 Skill 不可覆蓋 external（external 優先權最高），但可覆蓋 native

## Capabilities

### New Capabilities
（無新 capability — 變更範圍小，以 modified 為主）

### Modified Capabilities
- `skill-contributes`: SkillManager 的掃描路徑新增 extends/ 目錄
- `feature-modules`: extends/ 中帶有 contributes 的 Skill 能被 get_module_registry() 識別為模組

## Impact

- **後端**：`skills/__init__.py`（SkillManager._load_skills_sync）、`config.py`（新增 extends 路徑設定）
- **模組系統**：extends/ 中的 SKILL.md 會自動出現在 module registry
- **現有功能**：不受影響，external 和 native 的掃描行為不變
