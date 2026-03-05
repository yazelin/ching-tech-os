## ADDED Requirements

### Requirement: 民國年日期轉換
系統 SHALL 提供民國年 7 碼（1YYMMDD）與西元日期的雙向轉換。

#### Scenario: 民國年轉西元
- **WHEN** 輸入民國年字串 `"1150305"`
- **THEN** SHALL 回傳 `datetime.date(2026, 3, 5)`

#### Scenario: 西元轉民國年
- **WHEN** 輸入 `datetime.date(2026, 3, 5)`
- **THEN** SHALL 回傳字串 `"1150305"`

#### Scenario: 無效格式
- **WHEN** 輸入空字串、None、或非 7 碼字串
- **THEN** SHALL 回傳 None，不拋出例外

#### Scenario: 邊界值
- **WHEN** 輸入民國年 89 年（`"0890101"` = 2000-01-01）
- **THEN** SHALL 正確轉換

### Requirement: 讀取 DBF 檔案
系統 SHALL 使用 dbfread 函式庫讀取 Visual FoxPro DBF 檔案，處理 cp950 編碼。

#### Scenario: 讀取完整檔案
- **WHEN** 指定有效的 DBF 檔案路徑
- **THEN** SHALL 回傳 `list[dict[str, Any]]`，每筆記錄為一個 dict
- **THEN** 文字欄位 SHALL 以 cp950 解碼

#### Scenario: 編碼錯誤處理
- **WHEN** DBF 包含無法以 cp950 解碼的位元組
- **THEN** SHALL 以 replace 策略處理，不中斷讀取

#### Scenario: 檔案不存在
- **WHEN** 指定的 DBF 路徑不存在
- **THEN** SHALL 拋出 FileNotFoundError

### Requirement: 讀取 DBF Schema
系統 SHALL 提供讀取 DBF 欄位定義的功能（不讀取資料）。

#### Scenario: 取得欄位定義
- **WHEN** 指定有效的 DBF 檔案路徑
- **THEN** SHALL 回傳欄位列表，每項包含 name、type、length
