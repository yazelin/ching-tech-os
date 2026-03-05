## ADDED Requirements

### Requirement: 查詢病患資料
系統 SHALL 從 CO01M（病患主檔）查詢病患基本資料。

#### Scenario: 依病歷號查詢
- **WHEN** 提供病歷號（KCSTMR，7 碼）
- **THEN** SHALL 回傳病患姓名、生日、性別、電話、身分證號
- **THEN** 生日 SHALL 從民國年轉換為西元日期

#### Scenario: 病歷號不存在
- **WHEN** 提供的病歷號在 CO01M 中不存在
- **THEN** SHALL 回傳 None

### Requirement: 查詢就診紀錄
系統 SHALL 從 CO05O（掛號紀錄）查詢就診紀錄，支援多條件過濾。

#### Scenario: 依病歷號查詢
- **WHEN** 提供病歷號
- **THEN** SHALL 回傳該病患的就診紀錄列表（依日期降序）

#### Scenario: 依日期範圍過濾
- **WHEN** 提供 start_date 和/或 end_date
- **THEN** SHALL 只回傳該日期範圍內的紀錄（TBKDT 轉換後比對）

#### Scenario: 依醫師過濾
- **WHEN** 提供 doctor_id（對應 TIDS）
- **THEN** SHALL 只回傳該醫師的紀錄

#### Scenario: 依狀態過濾
- **WHEN** 提供 status（預設 "F"）
- **THEN** SHALL 只回傳匹配 TSTS 的紀錄

#### Scenario: 回傳筆數限制
- **WHEN** 提供 limit 參數（預設 50）
- **THEN** SHALL 最多回傳指定筆數

### Requirement: 查詢預約紀錄
系統 SHALL 從 co05b（預約主檔）查詢預約紀錄。

#### Scenario: 查詢未來預約
- **WHEN** 提供 start_date 為今天
- **THEN** SHALL 回傳今天（含）之後的預約紀錄

#### Scenario: 依醫師過濾
- **WHEN** 提供 doctor_id
- **THEN** SHALL 只回傳該醫師的預約

### Requirement: 查詢處方明細
系統 SHALL 從 CO02M（處方明細）查詢用藥紀錄。

#### Scenario: 依病歷號查詢
- **WHEN** 提供病歷號
- **THEN** SHALL 回傳該病患的處方列表，包含藥品代碼、名稱、劑量、給藥途徑、天數

#### Scenario: 依藥品代碼過濾
- **WHEN** 提供 drug_code
- **THEN** SHALL 只回傳使用該藥品的處方紀錄

### Requirement: 查詢醫師姓名
系統 SHALL 提供醫師 ID 到姓名的對應查詢。

#### Scenario: 從 VIS00 查詢
- **WHEN** 提供醫師 ID（TIDS / VIDS）
- **THEN** SHALL 從 VIS00（使用者帳號表）回傳醫師姓名（VNAME）

#### Scenario: 醫師不存在
- **WHEN** 提供的 ID 不存在
- **THEN** SHALL 回傳 None
