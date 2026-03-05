## Why

ct-his 模組目前只有骨架（所有函式 `raise NotImplementedError`），無法實際查詢展望 HIS 資料。杰膚美診所需要透過 LINE Bot 查詢診間看診進度（叫號），讓候診病人知道何時該回來。這需要 DBF 讀取引擎和 HIS 查詢層真正可用。

## What Changes

- 實作 `dbf_reader.py`：民國年日期轉換、DBF 檔案讀取與 schema 查詢
- 實作 `vision_his.py`：病患查詢、掛號/就診紀錄查詢、預約查詢、處方查詢、醫師姓名查詢
- 新增叫號進度查詢：從 CO05O 計算每個診間已完診人數，提供 LINE Bot 查詢介面
- 新增排程輪詢機制：定期同步看診進度到快取，避免每次查詢都讀 DBF
- 採用 TDD 開發：先建立測試（使用 NAS 上的測試 DBF 資料），再逐步實作

### DBF 表格對應

| 表格 | 用途 | 關鍵欄位 |
|------|------|----------|
| CO01M | 病患主檔 | KCSTMR（病歷號）、MNAME（姓名）、MBIRTHDT（生日） |
| CO05O | 掛號紀錄 | TREGNO（掛號序號）、TSTS（狀態 F=完診 H=候診）、TIDS（診別）、TROOM（診間）、TBEGTIME/TENDTIME |
| co05b | 預約主檔 | TBKDATE（預約日期）、TIDS（診別）、TSTS（狀態） |
| CO02M | 處方明細 | KCSTMR、IDATE、DNO（藥品代碼）、WICTM（藥品名稱） |
| CO28E | EMR 紀錄 | 醫師姓名來源 |
| DRUG | 藥品資料庫 | 藥品代碼與名稱對照 |
| VIS00 | 使用者/醫師帳號 | VUSER、VNAME、VIDS |

### 叫號查詢邏輯

叫號機與病人號碼沒有直接綁定 — 病人自己知道他是第幾個掛號的，叫號機只顯示「目前看到第幾位」。因此：

- **目前看到第幾位** = 該診間/時段 `TSTS='F'`（已完診）的筆數
- 每 30 秒～1 分鐘輪詢 CO05O，算出各診間進度，快取到記憶體
- LINE Bot 查詢時直接回傳快取結果，回應速度快

## Capabilities

### New Capabilities
- `dbf-reader`: DBF 檔案讀取引擎，處理 cp950 編碼和民國年日期格式
- `his-query`: 展望 HIS 資料查詢層（病患、就診、預約、處方）
- `clinic-queue`: 診間叫號進度查詢（排程同步 + LINE Bot 查詢）

### Modified Capabilities
（無）

## Impact

- **extends/his/core/**：`dbf_reader.py`、`vision_his.py`、`models.py` 從骨架變為實作
- **後端**：新增排程任務（輪詢看診進度）、可能新增 Skill script 供 LINE Bot 查詢
- **依賴**：新增 `dbfread` 套件（已安裝）
- **測試**：新增 `backend/tests/test_his/` 測試目錄，使用 NAS 上的測試 DBF 資料
- **現有功能**：不影響，MCP 工具骨架保持不變（待實作連接後自然可用）
