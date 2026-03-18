## ADDED Requirements

### Requirement: 建立案件
系統 SHALL 提供 `create_case` MCP 工具，接收案件基本資訊後建立案件記錄並自動建立資料夾結構。

#### Scenario: 成功建立案件
- **WHEN** AI 呼叫 `create_case(case_name="王小明損害賠償", case_type="civil", court="臺灣臺北地方法院", role="plaintiff")`
- **THEN** 系統在 `law_cases` 表格新增一筆記錄，並在設定的 `base_path` 下建立案件資料夾（含 8 個子資料夾：00_案件總覽、10_書狀、20_證據、30_對造、40_裁判、50_法規、80_AI產出、90_操作紀錄），回傳案件 ID 和資料夾路徑

#### Scenario: 案件名稱重複
- **WHEN** AI 呼叫 `create_case` 且 `case_name` 與現有案件完全相同
- **THEN** 系統仍 SHALL 建立案件（允許同名），但在回傳訊息中提示已有同名案件存在

#### Scenario: 資料夾根路徑未設定
- **WHEN** `config.yaml` 的 `storage.base_path` 為空或環境變數 `LAW_DATA_PATH` 未設定
- **THEN** 系統 SHALL 回傳錯誤訊息，指引使用者設定資料夾路徑

### Requirement: 查詢案件
系統 SHALL 提供 `get_case` 和 `list_cases` MCP 工具，支援以案件 ID、案號或篩選條件查詢案件。

#### Scenario: 以案件 ID 查詢
- **WHEN** AI 呼叫 `get_case(case_id=1)`
- **THEN** 系統回傳案件完整資訊，包含關聯的當事人清單（含角色）

#### Scenario: 以案號查詢
- **WHEN** AI 呼叫 `get_case(case_number="113年度訴字第1234號")`
- **THEN** 系統回傳該案號對應的案件完整資訊

#### Scenario: 篩選案件列表
- **WHEN** AI 呼叫 `list_cases(status="active", case_type="civil")`
- **THEN** 系統回傳符合條件的案件列表，依 `updated_at` 降冪排列

#### Scenario: 無符合條件的案件
- **WHEN** 查詢條件無任何匹配結果
- **THEN** 系統回傳空列表和提示訊息

### Requirement: 更新案件
系統 SHALL 提供 `update_case` MCP 工具，可更新案件的任何欄位。

#### Scenario: 更新案件狀態
- **WHEN** AI 呼叫 `update_case(case_id=1, status="closed")`
- **THEN** 系統更新 `law_cases` 對應記錄的 `status` 欄位，並更新 `updated_at` 時間戳

#### Scenario: 更新下次開庭日
- **WHEN** AI 呼叫 `update_case(case_id=1, next_court_date="2026-04-15")`
- **THEN** 系統更新 `next_court_date` 欄位

#### Scenario: 案件不存在
- **WHEN** AI 呼叫 `update_case` 且 `case_id` 不存在
- **THEN** 系統回傳錯誤訊息「案件不存在」

### Requirement: 案件資料夾結構
系統 SHALL 在建立案件時自動建立標準化的 8 層資料夾結構，路徑格式由 `config.yaml` 的 `storage.folder_template` 決定。

#### Scenario: 預設資料夾命名
- **WHEN** `folder_template` 為 `"{case_id}_{case_name}"`，案件 ID 為 1，案件名稱為「王小明損害賠償」
- **THEN** 資料夾名稱為 `1_王小明損害賠償/`，內含 8 個子資料夾

#### Scenario: 資料夾已存在
- **WHEN** 目標路徑已存在同名資料夾
- **THEN** 系統 SHALL 不覆蓋現有資料夾，回傳警告訊息並將案件記錄指向現有資料夾

### Requirement: 案件 DB 表格
系統 SHALL 透過 Alembic migration 建立 `law_cases` 表格，包含案號、名稱、類型、法院、角色、狀態、承辦律師、資料夾路徑、下次開庭日、備註、時間戳等欄位。

#### Scenario: Migration 執行
- **WHEN** 執行 `uv run alembic upgrade head`
- **THEN** 資料庫中建立 `law_cases` 表格，包含所有定義的欄位和預設值
