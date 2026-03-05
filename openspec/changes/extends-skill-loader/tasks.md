## 1. Config 設定

- [x] 1.1 在 `config.py` 新增 `extends_dir` 設定項（預設 `{project_root}/extends`）

## 2. SkillManager 修改

- [x] 2.1 在 `SkillManager.__init__` 新增 `self._extends_skills_dir` 屬性（從 `settings.extends_dir` 讀取）
- [x] 2.2 在 `_load_skills_sync()` 中新增第三個 `_load_root()` 呼叫：extends 目錄，source="extends"，can_override_existing=False，位於 external 和 native 之間

## 3. 驗證

- [x] 3.1 啟動 CTOS，確認 ct-his 的 SKILL.md 被載入（查看日誌或 `/api/config/apps` 回傳）
- [x] 3.2 確認 ct-his 的 MCP 工具出現在 module registry（`get_module_registry()` 包含 his-management）
- [x] 3.3 確認 external skill 優先權不受影響（同名 skill external 優先）
