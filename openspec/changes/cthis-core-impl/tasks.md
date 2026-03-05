## 1. 測試基礎建設

- [x] 1.1 建立 `backend/tests/test_his/` 目錄與 `conftest.py`，定義 `dbf_data_path` fixture（從 `CTHIS_DATA_PATH` 環境變數讀取，不存在時 skip）
- [x] 1.2 確認 `pytest` 能跑且 `dbfread` 可用

## 2. DBF 讀取引擎（TDD）

- [x] 2.1 寫 `test_dbf_reader.py`：民國年轉換測試（正常、邊界、無效值）
- [x] 2.2 實作 `dbf_reader.py` 的 `roc_to_date()` 和 `date_to_roc()`
- [x] 2.3 寫 `test_dbf_reader.py`：DBF 讀取測試（讀 CO01M 前 5 筆、schema 查詢、檔案不存在）
- [x] 2.4 實作 `dbf_reader.py` 的 `read_dbf()` 和 `read_dbf_schema()`

## 3. HIS 查詢層（TDD）

- [x] 3.1 寫 `test_vision_his.py`：病患查詢測試（依病歷號查、不存在的病歷號）
- [x] 3.2 實作 `vision_his.py` 的 `query_patient()`
- [x] 3.3 寫 `test_vision_his.py`：就診紀錄查詢測試（依病歷號、日期範圍、醫師、狀態過濾）
- [x] 3.4 實作 `vision_his.py` 的 `query_visits()`
- [x] 3.5 寫 `test_vision_his.py`：預約查詢測試
- [x] 3.6 實作 `vision_his.py` 的 `query_appointments()`
- [x] 3.7 寫 `test_vision_his.py`：處方查詢測試（更新 CO02P → CO02M）
- [x] 3.8 實作 `vision_his.py` 的 `query_prescriptions()`
- [x] 3.9 寫 `test_vision_his.py`：醫師姓名查詢測試（從 VIS00）
- [x] 3.10 實作 `vision_his.py` 的 `get_doctor_name()`

## 4. 診間叫號進度

- [x] 4.1 寫 `test_clinic_queue.py`：計算看診進度測試（依 TIDS 分組、算已完診人數和總掛號人數）
- [x] 4.2 在 `vision_his.py` 新增 `get_queue_status()` 函式（計算各診間看診進度）
- [x] 4.3 建立叫號快取模組（記憶體快取 dict + 更新/讀取函式）
- [x] 4.4 建立排程任務（每 30 秒輪詢 CO05O、更新快取，非看診時段降頻）
- [x] 4.5 建立 Skill script `queue_status.py`（讀快取、格式化回應給 LINE Bot）

## 5. 整合驗證

- [x] 5.1 跑全部測試確認通過
- [x] 5.2 手動呼叫 `get_queue_status()` 確認用測試資料能正確計算進度
