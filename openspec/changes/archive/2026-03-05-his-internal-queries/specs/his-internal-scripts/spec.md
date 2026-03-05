## ADDED Requirements

### Requirement: 門診統計查詢 Script（visit_stats）
系統 SHALL 提供 Skill script 查詢指定期間的門診統計資料。

#### Scenario: 查詢今日各醫師看診量
- **WHEN** 未提供參數（或 input 為空）
- **THEN** SHALL 查詢今日所有醫師的看診量
- **THEN** SHALL 回傳每位醫師的已看人數與總掛號人數

#### Scenario: 查詢指定日期範圍
- **WHEN** input JSON 包含 `start_date` 和/或 `end_date`（YYYY-MM-DD 格式）
- **THEN** SHALL 查詢該期間的看診統計

#### Scenario: 依醫師過濾
- **WHEN** input JSON 包含 `doctor_name`
- **THEN** SHALL 只回傳該醫師的統計

#### Scenario: 輸出格式
- **THEN** SHALL 以純文字格式回傳，每位醫師一行
- **THEN** SHALL 包含合計列

### Requirement: 藥品消耗查詢 Script（drug_usage）
系統 SHALL 提供 Skill script 查詢藥品使用統計。

#### Scenario: 依藥品關鍵字查詢
- **WHEN** input JSON 包含 `keyword`
- **THEN** SHALL 從 CO02M 處方紀錄搜尋藥品名稱包含 keyword 的紀錄
- **THEN** SHALL 回傳每種匹配藥品的開方次數與總量

#### Scenario: 指定日期範圍
- **WHEN** input JSON 包含 `start_date` 和/或 `end_date`
- **THEN** SHALL 只統計該期間的處方紀錄
- **WHEN** 未提供日期
- **THEN** SHALL 預設查詢最近 30 天

#### Scenario: 輸出格式
- **THEN** SHALL 以純文字格式回傳，每種藥品一行
- **THEN** SHALL 包含藥品代碼、名稱、開方次數

### Requirement: 預約總覽查詢 Script（appointment_list）
系統 SHALL 提供 Skill script 查詢預約總覽。

#### Scenario: 查詢今日預約
- **WHEN** 未提供參數
- **THEN** SHALL 查詢今日的預約清單
- **THEN** SHALL 依醫師分組顯示

#### Scenario: 查詢未來預約
- **WHEN** input JSON 包含 `days`（天數）
- **THEN** SHALL 查詢從今天起算指定天數內的預約

#### Scenario: 依醫師過濾
- **WHEN** input JSON 包含 `doctor_name`
- **THEN** SHALL 只回傳該醫師的預約

#### Scenario: 輸出格式
- **THEN** SHALL 以純文字格式回傳
- **THEN** SHALL 依日期、醫師分組
- **THEN** SHALL 顯示預約人數，不顯示病患個資

### Requirement: 醫師手動預約統計 Script（manual_booking_stats）
系統 SHALL 提供 Skill script 統計各醫師手動預約病人的次數。

#### Scenario: 資料來源
- **THEN** SHALL 從 VISLOG 讀取操作日誌
- **THEN** SHALL 同時讀取即時 VISLOG（`VISLOG.DBF`）和歸檔 VISLOG（`LOG/VISLOG*.DBF`）
- **THEN** SHALL 篩選 `LDSP='預2[A]'` 的紀錄（手動預約操作）

#### Scenario: 解析操作醫師
- **THEN** SHALL 從 `LSUR` 欄位解析操作者名稱（格式：`醫師名+TIDS`，如「廖憶如15」）
- **THEN** SHALL 區分醫師本人預約和掛號台代為預約（`LSUR` 含「掛號台」）

#### Scenario: 查詢指定日期範圍
- **WHEN** input JSON 包含 `start_date` 和/或 `end_date`
- **THEN** SHALL 只統計該期間的預約操作（VISLOG `LDATE` 欄位，民國年 7 碼）
- **WHEN** 未提供日期
- **THEN** SHALL 預設查詢最近 30 天

#### Scenario: 輸出格式
- **THEN** SHALL 以純文字格式回傳，每位醫師一行
- **THEN** SHALL 顯示醫師姓名、手動預約次數
- **THEN** SHALL 包含合計列

### Requirement: Script 共通規範
所有內部查詢 Script SHALL 遵循統一的格式與安全規範。

#### Scenario: 輸入格式
- **WHEN** script 接收 input
- **THEN** SHALL 透過 stdin 接收 JSON 字串
- **THEN** 無 input 時 SHALL 使用預設參數

#### Scenario: 輸出格式
- **THEN** SHALL 輸出純文字（供 LINE Bot 直接回傳）
- **THEN** SHALL 不使用 Markdown 格式
- **THEN** SHALL 使用 emoji 和全形標點增加可讀性

#### Scenario: 資料路徑
- **THEN** SHALL 從環境變數 `CTHIS_DATA_PATH` 取得 DBF 檔案路徑
- **WHEN** 環境變數未設定
- **THEN** SHALL 回傳錯誤訊息「HIS 資料路徑未設定」

#### Scenario: 權限控制
- **THEN** SHALL 依賴 SKILL.md 的 `requires_app: his-integration` 控制權限
- **THEN** 未授權用戶呼叫時由 run_skill_script 框架攔截，script 本身不需處理權限
