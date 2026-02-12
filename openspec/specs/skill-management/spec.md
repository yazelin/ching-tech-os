# skill-management Specification

## Purpose
統一管理 CTOS 的 Skill 載入、Hub 安裝、權限控制與 Script 執行能力，確保管理流程可追蹤且安全。

## Requirements

### Requirement: Skills 管理 API
系統 SHALL 提供僅限管理員的 Skills 管理 API，支援查詢、編輯、移除與重載。

#### Scenario: 列出已安裝 skills
- **WHEN** 管理員請求 `GET /api/skills`
- **THEN** 系統回傳 skills 清單
- **AND** 每筆資料包含 `name`、`description`、`requires_app`、`tools_count`、`scripts_count`、`source`

#### Scenario: 更新 skill 權限與白名單
- **WHEN** 管理員請求 `PUT /api/skills/{name}`
- **AND** 提供 `requires_app`、`allowed_tools`、`mcp_servers`
- **THEN** 系統更新 `SKILL.md` frontmatter
- **AND** 觸發 skill 重載

#### Scenario: 移除 skill
- **WHEN** 管理員請求 `DELETE /api/skills/{name}`
- **THEN** 系統移除對應 skill 目錄
- **AND** 觸發 skill 重載

#### Scenario: 不重啟重載
- **WHEN** 管理員請求 `POST /api/skills/reload`
- **THEN** 系統重新掃描 skills 目錄
- **AND** 不需重啟服務

---

### Requirement: Hub 多來源整合
系統 SHALL 支援 ClawHub 與 SkillHub 的多來源查詢與安裝。

#### Scenario: 列出可用來源
- **WHEN** 管理員請求 `GET /api/skills/hub/sources`
- **THEN** 系統至少回傳 ClawHub
- **AND** 僅在 `SKILLHUB_ENABLED=true` 時回傳 SkillHub

#### Scenario: 多來源搜尋
- **WHEN** 管理員請求 `POST /api/skills/hub/search` 且未指定 source
- **THEN** 系統並行搜尋可用來源並合併結果
- **AND** 每筆結果標記 `source`

#### Scenario: 指定來源安裝
- **WHEN** 管理員請求 `POST /api/skills/hub/install` 且指定 `source`
- **THEN** 系統使用對應來源下載並安裝 skill

---

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

---

### Requirement: 功能等價驗證
系統 SHALL 在 script 化遷移過程維持功能等價與穩定性。

#### Scenario: 切換能力實作路徑
- **WHEN** 某能力從 MCP 切換到 script
- **THEN** 必須通過功能對照驗證（輸入、輸出、錯誤行為）
- **AND** 確保使用者可觀察行為與既有流程一致
