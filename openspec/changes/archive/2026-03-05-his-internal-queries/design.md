## 技術設計

### 架構概覽

```
LINE Bot 用戶（綁定帳號）
  → AI agent (jfmskin-full)
    → run_skill_script(skill="his-integration", script="<script_name>", input="{...}")
      → ScriptRunner (subprocess)
        → scripts/<script_name>.py
          → vision_his.py (底層查詢) / vislog_reader.py (VISLOG 讀取)
            → DBF 檔案 (CTHIS_DATA_PATH)
```

### 設計決策

#### 1. 全部使用 Skill scripts，不新增 MCP 工具
底層引擎 `vision_his.py` 已有完整的查詢函式。新增的 scripts 只負責：
- 解析 stdin 的 JSON 參數
- 呼叫底層函式
- 格式化純文字輸出

#### 2. 每個 script 直接讀 DBF（不經過快取）
與 `queue_status` 不同，內部查詢不需要 30 秒級別的即時性。每次呼叫直接讀 DBF，因為：
- 內部查詢頻率低（不像叫號那樣頻繁）
- DBF 讀取是 read-only，不影響 HIS 系統
- 避免增加快取複雜度

#### 3. VISLOG 讀取需要新增底層函式
現有 `vision_his.py` 不支援 VISLOG。需新增 `query_vislog_bookings()` 函式：
- 同時讀取即時 `VISLOG.DBF` + 歸檔 `LOG/VISLOG*.DBF`
- 篩選 `LDSP='預2[A]'`
- 從 `LSUR` 解析操作者（格式：`醫師名+TIDS`，如「廖憶如15」）
- VISLOG 路徑需要額外配置（可能在 `CTHIS_DATA_PATH` 下，也可能在不同子目錄）

#### 4. VISLOG 路徑慣例
根據測試資料觀察：
- 即時 VISLOG：`{CTHIS_DATA_PATH}/VISLOG.DBF` 或 `{CTHIS_DATA_PATH}/his_logs_tmp/VISLOG.DBF`
- 歸檔 VISLOG：`{CTHIS_DATA_PATH}/LOG/VISLOG*.DBF` 或 `{CTHIS_DATA_PATH}/after_logs/LOG/VISLOG*.DBF`

設計上採用 fallback 搜尋：先在根目錄找，找不到再掃描子目錄。

### 檔案變更

| 檔案 | 變更類型 | 說明 |
|------|---------|------|
| `extends/his/core/services/vision_his.py` | 修改 | 新增 `query_vislog_bookings()` |
| `extends/his/skills/his-integration/scripts/visit_stats.py` | 新增 | 門診統計 |
| `extends/his/skills/his-integration/scripts/drug_usage.py` | 新增 | 藥品消耗 |
| `extends/his/skills/his-integration/scripts/appointment_list.py` | 新增 | 預約總覽 |
| `extends/his/skills/his-integration/scripts/manual_booking_stats.py` | 新增 | 醫師手動預約統計 |
| `extends/his/clients/jfmskin/agents/jfmskin-full.md` | 修改 | 更新 prompt 加入 4 個新 scripts |
| `backend/tests/test_his/test_internal_scripts.py` | 新增 | 測試 |

### Script Input/Output 格式

所有 scripts 統一格式：

**Input**（stdin JSON）：
```json
{"start_date": "2026-03-01", "end_date": "2026-03-05", "doctor_name": "廖憶如"}
```
空 input 或 `{}` 使用預設參數。

**Output**（stdout 純文字）：
```
📊 門診統計（2026-03-01 ~ 2026-03-05）

廖憶如：已看 120 位
柯人玄：已看 95 位
...

合計：215 位
```

### 環境變數

| 變數 | 用途 |
|------|------|
| `CTHIS_DATA_PATH` | DBF + VISLOG 檔案根目錄（由 ScriptRunner 透過 SKILL.md env 傳入） |

注意：ScriptRunner 不會自動傳入 `CTHIS_DATA_PATH`。需要在 SKILL.md 的 `metadata.openclaw.requires.env` 中宣告，或在 script 中直接讀取 `os.environ`。目前 `queue_status.py` 未使用環境變數（從快取讀），但新 scripts 需要。解法：在每個 script 中用 `os.environ.get("CTHIS_DATA_PATH")` 取得路徑。ScriptRunner 會將 `.env` 中的環境變數透過 SKILL.md 的 env overrides 機制傳入。
