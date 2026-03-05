## ADDED Requirements

### Requirement: 計算診間看診進度
系統 SHALL 從 CO05O 計算每個診間當日已完診的病人數，作為叫號進度。

#### Scenario: 計算已看人數
- **WHEN** 查詢今天的看診進度
- **THEN** SHALL 篩選今日日期（TBKDT）且狀態為完診（TSTS='F'）的紀錄
- **THEN** SHALL 依診別（TIDS）分組計算完診筆數
- **THEN** 每組回傳：診別代碼、醫師姓名、已看人數、總掛號人數

#### Scenario: 多診間
- **WHEN** 當日有兩個診間同時看診（如 TIDS='15' 上午診、TIDS='03' 下午診）
- **THEN** SHALL 分別回傳各診間的進度

#### Scenario: 無看診資料
- **WHEN** 當日無掛號紀錄
- **THEN** SHALL 回傳空列表

### Requirement: 排程同步看診進度
系統 SHALL 定期輪詢 DBF，將看診進度快取到記憶體。

#### Scenario: 定期輪詢
- **WHEN** 排程觸發（預設每 30 秒）
- **THEN** SHALL 讀取 CO05O 當日資料
- **THEN** SHALL 更新記憶體中的看診進度快取

#### Scenario: 非看診時段
- **WHEN** 當前時間不在看診時段（如深夜）
- **THEN** SHALL 降低輪詢頻率或暫停輪詢

#### Scenario: DBF 讀取失敗
- **WHEN** SMB 連線中斷或 DBF 讀取失敗
- **THEN** SHALL 保留最後一次成功的快取資料
- **THEN** SHALL 記錄錯誤日誌，下次輪詢時重試

### Requirement: LINE Bot 查詢看診進度
系統 SHALL 提供 LINE Bot 介面讓病人查詢各診間目前看到第幾位。

#### Scenario: 查詢叫號
- **WHEN** 病人透過 LINE Bot 查詢看診進度
- **THEN** SHALL 回傳各診間的看診進度，格式包含：診間名稱、醫師、目前看到第幾位、總掛號人數

#### Scenario: 快取回應
- **WHEN** LINE Bot 收到查詢請求
- **THEN** SHALL 從快取回傳結果，不直接讀取 DBF
- **THEN** 回應時間 SHALL 在 1 秒內
