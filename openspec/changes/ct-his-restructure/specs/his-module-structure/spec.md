## ADDED Requirements

### Requirement: ct-his 頂層目錄結構
ct-his 子模組 SHALL 採用以下頂層目錄結構組織程式碼與設定：

- `core/` — 通用 HIS 引擎（與客戶無關的共用程式碼）
- `clients/` — 客戶部署設定（每個客戶一個子目錄）
- `skills/` — CTOS Skill 整合定義
- `archive/` — 過渡期保留（遷移完成後移除）

#### Scenario: 子模組根目錄包含必要結構
- **WHEN** 檢查 ct-his 子模組根目錄
- **THEN** SHALL 存在 `core/`、`clients/`、`skills/` 目錄
- **THEN** SHALL 存在 `README.md` 說明子模組用途與結構

#### Scenario: 不包含客戶的 runtime 資料
- **WHEN** 檢查 ct-his repository 內容
- **THEN** SHALL 不包含任何病患資料、DBF 資料檔、或 HIS 資料庫副本
- **THEN** 客戶的 runtime 資料 SHALL 由各部署實例的 CTOS 資料庫管理

### Requirement: core/ 通用 HIS 引擎結構
`core/` 目錄 SHALL 包含與特定客戶無關的通用 HIS 服務程式碼。

- `core/services/` — 業務邏輯（DBF 讀取、展望 API 抽象、預約管理等）
- `core/models.py` — 共用 Pydantic 資料模型
- `core/mcp_tools.py` — HIS MCP 工具定義

#### Scenario: core/ 目錄包含服務骨架
- **WHEN** 檢查 `core/` 目錄
- **THEN** SHALL 存在 `__init__.py`
- **THEN** SHALL 存在 `services/` 目錄，包含至少 `dbf_reader.py`（DBF 讀取引擎）和 `vision_his.py`（展望 HIS API 抽象層）
- **THEN** SHALL 存在 `mcp_tools.py`，定義 HIS MCP 工具介面

#### Scenario: DBF 讀取引擎基本介面
- **WHEN** 檢查 `core/services/dbf_reader.py`
- **THEN** SHALL 提供讀取 Visual FoxPro DBF 檔案的函式
- **THEN** SHALL 支援 cp950（Big5）編碼
- **THEN** SHALL 支援民國年 7 碼日期格式（1YYMMDD）轉換

#### Scenario: 展望 HIS API 抽象層基本介面
- **WHEN** 檢查 `core/services/vision_his.py`
- **THEN** SHALL 提供病患查詢、掛號紀錄查詢、處方查詢、預約查詢的函式骨架
- **THEN** 每個函式 SHALL 接受客戶設定（連線資訊、路徑）作為參數，不硬編碼任何客戶特定值

#### Scenario: MCP 工具定義
- **WHEN** 檢查 `core/mcp_tools.py`
- **THEN** SHALL 定義以下 MCP 工具的函式簽名：查詢預約、查詢病患、查詢處方
- **THEN** 工具實作 SHALL 呼叫 `core/services/` 中的服務函式

### Requirement: clients/ 客戶目錄結構
`clients/` 目錄 SHALL 以子目錄方式管理每個客戶的部署設定，每個客戶使用獨立的 kebab-case 目錄名稱。

#### Scenario: 客戶目錄包含必要檔案
- **WHEN** 檢查 `clients/{client_code}/` 目錄
- **THEN** SHALL 存在 `config.yaml`（部署設定）
- **THEN** SHALL 存在 `agents/` 目錄（Agent prompt 定義）
- **THEN** MAY 存在 `knowledge/`（知識庫種子資料）、`deploy/`（部署筆記）、`analysis/`（分析腳本）

#### Scenario: 杰膚美客戶目錄
- **WHEN** 檢查 `clients/jfmskin/` 目錄
- **THEN** SHALL 存在 `config.yaml`、`agents/jfmskin-edu.md`、`agents/jfmskin-full.md`
- **THEN** SHALL 存在 `analysis/` 目錄，包含從 `archive/` 遷移的分析腳本

#### Scenario: 新客戶範本
- **WHEN** 檢查 `clients/_template/` 目錄
- **THEN** SHALL 存在 `config.yaml`（範本設定檔，所有欄位帶註解說明）
- **THEN** SHALL 存在 `agents/` 目錄（空的 Agent prompt 範本）
- **THEN** SHALL 存在 `README.md`（部署檢查清單）

### Requirement: SKILL.md 模組宣告
ct-his 根目錄 SHALL 包含 `SKILL.md`，遵循 CTOS Skill contributes 規範宣告模組能力。

#### Scenario: SKILL.md frontmatter 宣告 contributes
- **WHEN** 解析 ct-his 的 `SKILL.md` frontmatter
- **THEN** SHALL 包含 `contributes.mcp_tools` 指向 `core/mcp_tools.py`
- **THEN** MAY 包含 `contributes.scheduler` 定義排程任務
- **THEN** MAY 包含 `contributes.app` 定義前端應用（HIS 管理介面）

#### Scenario: SKILL.md 符合 CTOS Skill 規範
- **WHEN** CTOS SkillManager 掃描到 ct-his 的 `SKILL.md`
- **THEN** SHALL 能被 `parse_skill_md()` 正確解析
- **THEN** SHALL 能透過 `_build_skill_module()` 轉換為 `ModuleInfo`

### Requirement: 現有腳本遷移
`archive/` 目錄下的分析腳本 SHALL 遷移至對應客戶的 `clients/{client_code}/analysis/` 目錄。

#### Scenario: 杰膚美分析腳本遷移
- **WHEN** 遷移完成
- **THEN** `archive/analysis/analyze-revisit-rate.py` SHALL 搬移至 `clients/jfmskin/analysis/`
- **THEN** `archive/analysis/analyze-drug-consumption.py` SHALL 搬移至 `clients/jfmskin/analysis/`
- **THEN** `archive/analysis/analyze-followup-booking.py` SHALL 搬移至 `clients/jfmskin/analysis/`
- **THEN** 腳本內容 SHALL 不做修改，僅搬移位置

#### Scenario: PowerShell 診所腳本遷移
- **WHEN** 遷移完成
- **THEN** `archive/` 中的 PowerShell 腳本（collect-his-info.ps1、scan-his-server.ps1 等）SHALL 搬移至 `clients/jfmskin/deploy/scripts/`
