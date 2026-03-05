## ADDED Requirements

### Requirement: config.yaml 客戶設定檔格式
每個客戶目錄 SHALL 包含 `config.yaml`，定義該客戶的部署設定。設定檔 SHALL 採用以下區塊結構。

#### Scenario: client 基本資訊區塊
- **WHEN** 解析 `config.yaml` 的 `client` 區塊
- **THEN** SHALL 包含 `name`（診所名稱）、`code`（kebab-case 代碼）、`type`（科別）

#### Scenario: his 系統設定區塊
- **WHEN** 解析 `config.yaml` 的 `his` 區塊
- **THEN** SHALL 包含 `system`（HIS 系統類型，如 `vision`）、`data_format`（資料格式，如 `dbf`）
- **THEN** SHALL 包含 `encoding`（文字編碼，如 `cp950`）、`date_format`（日期格式，如 `roc7`）

#### Scenario: connection 連線設定區塊
- **WHEN** 解析 `config.yaml` 的 `connection` 區塊
- **THEN** SHALL 包含 `method`（連線方式：`tailscale`、`smb`、`local`）
- **THEN** SHALL 包含 `his_server_ip`（HIS 伺服器 IP）和 `dbf_base_path`（DBF 檔案根路徑）
- **THEN** 敏感資訊（密碼、VPN token）SHALL 不存放在 config.yaml 中，改由環境變數提供

#### Scenario: agents Agent 指定區塊
- **WHEN** 解析 `config.yaml` 的 `agents` 區塊
- **THEN** SHALL 包含 `restricted`（未綁定用戶 Agent 名稱）和 `full`（已綁定用戶 Agent 名稱）
- **THEN** Agent 名稱 SHALL 對應到 `agents/` 目錄下的 `.md` 檔案（去掉副檔名）

#### Scenario: features 功能開關區塊
- **WHEN** 解析 `config.yaml` 的 `features` 區塊
- **THEN** SHALL 以 boolean 值控制各項功能的啟停
- **THEN** SHALL 至少支援以下開關：`edu_bot`（衛教 Bot）、`appointment_query`（預約查詢）、`revisit_analysis`（回診率分析）、`drug_analysis`（藥品消耗分析）、`push_reminder`（推播提醒）

#### Scenario: rate_limit 頻率限制區塊
- **WHEN** 解析 `config.yaml` 的 `rate_limit` 區塊
- **THEN** SHALL 包含 `hourly`（每小時上限）、`daily`（每日上限）、`model`（受限模式使用的 AI 模型）
- **THEN** `hourly` SHALL 小於或等於 `daily`

### Requirement: Agent Prompt 檔案格式
`agents/` 目錄下的 `.md` 檔案 SHALL 包含 Agent 的 system prompt 定義。

#### Scenario: Agent prompt 檔案結構
- **WHEN** 讀取 `agents/{agent-name}.md`
- **THEN** 檔案內容 SHALL 為純文字的 system prompt
- **THEN** MAY 包含 YAML frontmatter 定義 Agent 的 metadata（model、tools、display_name）

#### Scenario: jfmskin-edu prompt 與 DB 一致
- **WHEN** 比對 `agents/jfmskin-edu.md` 與資料庫中 `jfmskin-edu` Agent 的 system_prompt
- **THEN** 檔案版本 SHALL 作為版控的 source of truth
- **THEN** 部署時 SHALL 透過 seed 機制將檔案內容同步至資料庫

#### Scenario: jfmskin-full prompt 定義
- **WHEN** 讀取 `agents/jfmskin-full.md`
- **THEN** SHALL 定義杰膚美完整模式 Agent 的 system prompt
- **THEN** prompt SHALL 包含 HIS 相關工具的使用說明（查預約、查病患等）

### Requirement: 客戶範本完整性
`clients/_template/` SHALL 提供完整的新客戶部署範本，所有欄位帶註解說明。

#### Scenario: 範本 config.yaml 所有欄位有註解
- **WHEN** 讀取 `clients/_template/config.yaml`
- **THEN** 每個設定欄位 SHALL 附帶 YAML 註解說明用途、可選值、預設值

#### Scenario: 範本 README 包含部署檢查清單
- **WHEN** 讀取 `clients/_template/README.md`
- **THEN** SHALL 包含新客戶部署的步驟檢查清單
- **THEN** 檢查清單 SHALL 涵蓋：連線設定、Agent 建立、知識庫初始化、環境變數設定、測試驗證

### Requirement: 環境變數範本
每個客戶的 `deploy/` 目錄 MAY 包含 `.env.example`，列出該客戶部署所需的環境變數。

#### Scenario: .env.example 包含必要變數
- **WHEN** 讀取 `clients/{client_code}/deploy/.env.example`
- **THEN** SHALL 列出所有必要的環境變數及說明
- **THEN** SHALL 包含 HIS 連線相關變數（如 `HIS_CLIENT`、VPN 設定）
- **THEN** SHALL 包含 Bot 相關變數（如 `BOT_UNBOUND_USER_POLICY`、`BOT_DEFAULT_RESTRICTED_AGENT`）
- **THEN** 敏感值 SHALL 使用佔位符（如 `your-password-here`），不包含真實密碼
