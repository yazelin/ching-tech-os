## Tasks

### 底層引擎擴充

- [x] 1. 新增 `query_vislog_bookings()` 到 `vision_his.py`
  - 讀取即時 VISLOG + 歸檔 VISLOG
  - 篩選 `LDSP='預2[A]'`
  - 從 `LSUR` 解析操作者名稱
  - 支援日期範圍過濾
- [x] 2. 新增 VISLOG 相關測試到 `test_vision_his.py`

### Skill Scripts 實作

- [x] 3. 實作 `scripts/visit_stats.py`（門診統計）
  - 呼叫 `query_visits()` + `get_doctor_name()`
  - 支援日期範圍、醫師過濾
  - 純文字輸出含合計列
- [x] 4. 實作 `scripts/drug_usage.py`（藥品消耗）
  - 呼叫 `query_prescriptions()`
  - 支援藥品關鍵字、日期範圍
  - 純文字輸出含開方次數
- [x] 5. 實作 `scripts/appointment_list.py`（預約總覽）
  - 呼叫 `query_appointments()` + `get_doctor_name()`
  - 依日期、醫師分組
  - 顯示預約人數，不顯示病患個資
- [x] 6. 實作 `scripts/manual_booking_stats.py`（醫師手動預約統計）
  - 呼叫 `query_vislog_bookings()`
  - 區分醫師本人預約 vs 掛號台代為預約
  - 純文字輸出含合計列

### 環境變數與路徑

- [x] 7. 確認 SKILL.md env overrides 設定，讓 ScriptRunner 傳入 `CTHIS_DATA_PATH`
- [x] 8. 每個 script 加入 `CTHIS_DATA_PATH` 環境變數讀取與缺失錯誤處理

### Agent 整合

- [x] 9. 更新 `jfmskin-full.md` agent prompt，加入 4 個新 scripts 的使用說明

### 測試

- [x] 10. 新增 `test_internal_scripts.py`，測試 4 個 scripts 的 input 解析與輸出格式
