## Context

實作 ct-his 模組的核心功能：DBF 讀取引擎、HIS 查詢層、診間叫號進度。所有程式碼在 `extends/his/core/` 內，骨架已存在（`NotImplementedError`），本次填入實作。測試資料位於 NAS：`/mnt/nas/ctos/external-data/cthis-jfmskin/data`（33 個 DBF，由環境變數 `CTHIS_DATA_PATH` 指定）。

## Decisions

### D1: DBF 讀取用 dbfread，同步 API 包裝為 async

`dbfread` 是純 Python 同步函式庫。`vision_his.py` 宣告為 `async def`，但 DBF 讀取是 CPU-bound + file I/O。

做法：`dbf_reader.py` 保持同步（`def`），`vision_his.py` 用 `asyncio.to_thread()` 包裝呼叫，避免阻塞 event loop。

**理由**：DBF 讀取不適合 async IO（不是 socket），`to_thread` 是最簡單的非阻塞方案。

### D2: CO05O 全量讀取 + 記憶體過濾

CO05O 有 10 萬筆紀錄（~49MB），全量讀取約需 2-3 秒。兩種策略：

1. **全量讀取 + Python 過濾**（簡單，但慢）
2. **只讀今天的資料**（需要 CDX 索引或逐筆掃描）

做法：採用策略 1，但加快取。叫號排程每 30 秒讀一次，結果快取到記憶體。HIS 查詢（病患、處方等）按需讀取，因為查詢頻率低。

**理由**：`dbfread` 不支援索引查詢，只能全量掃描。排程快取攤平了讀取成本。

### D3: 叫號進度用記憶體快取，不寫 DB

看診進度是短暫資料（只關心當天、且 30 秒就更新一次），不需要持久化。

做法：用模組層級的 dict 快取，結構為 `{date: {period_id: QueueStatus}}`。排程更新時整批替換。

**理由**：簡單、快速、無 DB 依賴。服務重啟時 30 秒內就會重新填充。

### D4: 叫號查詢用 Skill Script，不用 MCP

LINE Bot 查詢叫號進度不需要 AI 推理，是固定格式的查詢回應。

做法：建立 Skill script（`extends/his/skills/his-integration/scripts/queue_status.py`），透過 `run_skill_script` 工具被 Agent 呼叫。Script 直接讀快取、格式化回應。

**理由**：
- Skill script 執行快（不經 MCP 協議）
- 回應格式固定，不需要 AI 組裝
- 已有 `run_skill_script` 工具基礎設施

### D5: TDD 開發，測試放在 backend/tests/

測試使用 NAS 上的真實 DBF 測試資料，不做 mock。

做法：
- 測試目錄：`backend/tests/test_his/`
- `test_dbf_reader.py`：日期轉換 + DBF 讀取（純 unit test）
- `test_vision_his.py`：HIS 查詢（需要 DBF 測試資料）
- `test_clinic_queue.py`：叫號計算邏輯
- 需要 DBF 資料的測試加 `@pytest.mark.skipif` 跳過（CI 沒有 NAS）

**理由**：真實資料測試能驗證編碼、欄位名稱、資料格式等細節，mock 反而容易漏洞。

### D6: 看診進度的分組鍵

從 CO05O 資料觀察：
- `TID` = 醫師代碼（如 `"1"`）
- `TIDS` = 診別代碼（如 `"15"` 上午、`"03"` 下午）
- 同一時段只有一位醫師

做法：以 `(TIDS)` 作為分組鍵（即「診別」），每個診別代表一個診間的一個時段。再從 VIS00 查醫師姓名對應 TIDS。

### D7: 處方表是 CO02M 不是 CO02P

從實際 DBF schema 確認：CO02M 包含處方明細欄位（DNO 藥品代碼、WICTM 藥品名稱、PFQ 頻次、PPS 途徑等）。更新 `vision_his.py` 的註解與實作。

## Risks / Trade-offs

**[CO05O 全量讀取效能]** → 10 萬筆 49MB，每 30 秒讀一次可能對 NAS 造成負擔。可觀察實際耗時，必要時改為只讀最近 N 天或用 file mtime 判斷是否需要重讀。

**[SMB 連線穩定性]** → 透過 Tailscale VPN 的 SMB 連線可能中斷。排程已設計為失敗時保留最後快取、下次重試。

**[測試資料時效性]** → NAS 上的 DBF 是靜態副本，最新日期為 1150228（2026-02-28）。測試中的「今天」需用測試資料中的日期，不能用 `date.today()`。

**[dbfread 記憶體使用]** → 全量讀 CO05O 會將 10 萬筆載入記憶體。單次約 100-200MB，在排程間隔外會被 GC。可接受。
