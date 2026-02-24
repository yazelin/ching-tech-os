# skill-management Specification

## Purpose
統一管理 CTOS 的 Skill 載入、Hub 安裝、權限控制與 Script 執行能力，確保管理流程可追蹤且安全。

## Requirements

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

### Requirement: 安裝安全與 Metadata
系統 SHALL 在 hub 安裝流程中提供完整安全檢查與 metadata 管理。

#### Scenario: ZIP 安裝安全檢查
- **WHEN** 系統下載 skill ZIP
- **THEN** 檢查壓縮檔大小與解壓總大小上限
- **AND** 阻擋 zip slip 路徑穿越

#### Scenario: SKILL.md 正規化
- **WHEN** 安裝 skill 缺少 frontmatter 或 `name/source` 不完整
- **THEN** 系統補齊/修正 frontmatter
- **AND** `name` 與安裝 slug 一致

#### Scenario: 安裝來源追蹤
- **WHEN** skill 安裝完成
- **THEN** 系統寫入 `_meta.json`
- **AND** 內容包含來源、版本、安裝時間與作者資訊（若可取得）

---

### Requirement: Script Tool 執行
系統 SHALL 提供 `run_skill_script` 通用工具執行 skill scripts，並套用權限與路徑保護。

#### Scenario: 正常執行 script
- **WHEN** AI 呼叫 `run_skill_script(skill, script, input)`
- **THEN** 系統驗證 skill 與 script 存在
- **AND** 驗證使用者具備該 skill 的 `requires_app` 權限
- **AND** 在隔離工作目錄執行 script
- **AND** 回傳 stdout/stderr 與執行時間

#### Scenario: 路徑穿越防護
- **WHEN** `skill` 或 `script` 含路徑穿越字元
- **THEN** 系統拒絕執行並回傳錯誤

#### Scenario: Script 執行記錄
- **WHEN** script 執行完成
- **THEN** 系統記錄 ai_logs
- **AND** `model` 欄位為 `"script"`

---

### Requirement: Skill 詳情與檔案瀏覽
系統 SHALL 支援查詢單一 skill 詳情與受控檔案瀏覽。

#### Scenario: 查詢 skill 詳情
- **WHEN** 管理員請求 `GET /api/skills/{name}`
- **THEN** 系統回傳 `allowed_tools`、`mcp_servers`、`references`、`scripts`、`assets`
- **AND** 回傳 `script_tools`（由 scripts 自動解析）

#### Scenario: 瀏覽 skill 檔案
- **WHEN** 管理員請求 `GET /api/skills/{name}/files/{file_path}`
- **THEN** 系統僅允許 `references/`、`scripts/`、`assets/` 前綴
- **AND** 阻擋路徑穿越

---

### Requirement: 外部 Skill 根目錄
系統 SHALL 支援外部 skill 根目錄，預設為 `~/SDD/skill`。

#### Scenario: 啟動時載入 skills
- **WHEN** 系統啟動並掃描 skills
- **THEN** 先掃描 `~/SDD/skill`
- **AND** 再掃描專案內建 skills 目錄作為 fallback

#### Scenario: 同名 skill 覆蓋
- **WHEN** 外部與內建目錄存在同名 skill
- **THEN** 以外部 skill 為準
- **AND** 記錄來源覆蓋日誌

---

### Requirement: 內建 Skill 拆分治理
系統 SHALL 以單一責任原則拆分內建 skills，降低單一 skill 負擔。

#### Scenario: 規劃拆分
- **WHEN** 盤點內建 skill 功能
- **THEN** 將多責任 skill 拆分為多個獨立 skill
- **AND** 每個 skill 僅保留單一職責與最小工具集合

---

### Requirement: Script-First 實作策略
skill 能力 SHALL 優先以 scripts（`.py`/`.sh`）實作，MCP 僅保留必要整合能力。

#### Scenario: 同功能存在 script 與 MCP
- **WHEN** 某能力同時可由 script 與 MCP 完成
- **THEN** 系統預設選擇 script 路徑
- **AND** 僅在 script 失敗且符合回退條件時改走 MCP

#### Scenario: 最小 MCP 使用原則
- **WHEN** 規劃新 skill
- **THEN** 優先設計 script 方案
- **AND** 僅在跨系統整合（如 ERPNext、印表機）保留 MCP

#### Scenario: native base/file-manager 第一批 script 化
- **WHEN** 載入 native `base` 與 `file-manager` skills
- **THEN** `allowed-tools` SHALL 以 `mcp__ching-tech-os__run_skill_script` 為主要入口
- **AND** 其主要功能 SHALL 由 `scripts/` 目錄中的工具實作

#### Scenario: fallback 邊界
- **WHEN** script 執行失敗屬於參數驗證或權限檢查錯誤
- **THEN** 系統 SHALL 回傳錯誤且不 fallback 到 MCP

---

### Requirement: 功能等價驗證
系統 SHALL 在 script 化遷移過程維持功能等價與穩定性。

#### Scenario: 切換能力實作路徑
- **WHEN** 某能力從 MCP 切換到 script
- **THEN** 必須通過功能對照驗證（輸入、輸出、錯誤行為）
- **AND** 確保使用者可觀察行為與既有流程一致

#### Scenario: external 與 native 行為對齊
- **WHEN** native `base` 或 `file-manager` 進行 script 化
- **THEN** 應以 external 同名 skill 的 scripts 行為作為對照基準
- **AND** 功能差異 SHALL 以測試或文件明確標示

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
