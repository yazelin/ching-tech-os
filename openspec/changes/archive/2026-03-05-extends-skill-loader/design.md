## Context

CTOS 的 SkillManager 目前掃描兩個目錄載入 Skill：
1. `external_skills_dir`（`~/SDD/external-skills/`）— 優先權最高，可覆蓋同名 native
2. `native_skills_dir`（`backend/src/ching_tech_os/skills/`）— 內建 skill

ct-his 子模組位於 `extends/his/`，已建立 SKILL.md（contributes: mcp_tools, app, permissions），但 SkillManager 不會掃描 `extends/` 目錄。

## Goals / Non-Goals

**Goals:**
- 讓 SkillManager 掃描 `extends/` 目錄下的子目錄
- extends Skill 的優先權介於 external 和 native 之間
- 新增 config.py 設定項，讓 extends 路徑可配置

**Non-Goals:**
- 不修改 extends/ 內部結構（已在 ct-his-restructure 完成）
- 不新增 API 端點（extends Skill 透過現有 module registry 自動暴露）
- 不處理 extends Skill 的安裝/卸載（submodule 手動管理）

## Decisions

### D1: 掃描順序 external → extends → native

```python
# _load_skills_sync() 修改後
_load_root(self._external_skills_dir, source="external", can_override_existing=True)
_load_root(self._extends_skills_dir, source="extends", can_override_existing=False)
_load_root(self._native_skills_dir, source="native", can_override_existing=False)
```

**理由**：external 始終最高優先權（使用者自訂），extends 次之（子模組提供），native 最低（內建預設）。extends 用 `can_override_existing=False` 代表不會覆蓋 external 中的同名 skill，但因為它比 native 先掃描，所以會覆蓋 native 中的同名 skill。

### D2: extends 路徑用 config.py 設定

在 `config.py` 新增：
```python
extends_dir: str = _get_env("EXTENDS_DIR", str(_project_root / "extends"))
```

**理由**：預設值指向專案根目錄的 `extends/`，大多數情況不需要改。特殊部署場景可透過環境變數覆蓋。

### D3: extends 目錄不存在時靜默跳過

**理由**：`_load_root()` 已有 `if not root.exists(): return` 邏輯，不需要額外處理。不是每個 CTOS 實例都有 extends/ 目錄。

## Risks / Trade-offs

**[extends Skill 不自動 seed]** → 與 external 不同，extends/ 目錄不會自動建立或初始化。這是預期行為，因為 extends 是 git submodule 管理的。

**[mcp_tools_file 路徑解析]** → `_build_skill_module()` 用 `_resolve_skill_file()` 解析 MCP 工具路徑，需確認它能正確處理 extends/ 下的相對路徑。根據程式碼分析，`skill.skill_dir` 會被設為 extends/ 下的實際目錄，路徑解析應正常運作。
