## Why

診所院長需要了解各醫師的看診溝通品質，作為教育訓練教材。目前已完成 NVR RTSP 串流抓取、VAD 聲音偵測自動錄製、Whisper 語音辨識等基礎設施（`consultation_monitor.py`），但辨識後的逐字稿只存在 `/tmp`，沒有歸檔、沒有結構化儲存、沒有 AI 分析，也沒有查詢介面。

需要將逐字稿串接完整的後處理流程：歸檔、AI 分析、資料庫儲存、查詢介面，讓院長可以檢視、篩選、分析各診間的看診對話。

## What Changes

### 1. 逐字稿後處理 Pipeline

`consultation_monitor.py` 辨識完成後，觸發後處理流程：

```
Whisper 辨識完成
  → AI 分析（Claude）
    → 判斷場景類型（看診 / 閒聊 / 無法分類）
    → 推定角色（醫師 / 病患 / 護理師）
    → 看診摘要
    → 溝通品質評分（1-10）
    → 改善建議
    → 療程標籤
  → 存入資料庫
  → 歸檔到 NAS 圖書館
  → 音訊 buffer 丟棄（不保留音檔）
```

### 2. 資料庫（新增 `consultation_transcripts` 表）

| 欄位 | 說明 |
|------|------|
| id | UUID |
| channel | 頻道（CH08, CH10, CH11） |
| start_time | 錄製開始時間 |
| duration_seconds | 音訊長度 |
| transcript | 完整逐字稿 |
| segments | 分段逐字稿（JSON，含時間戳） |
| scene_type | 場景類型（consultation / chat / unclassified） |
| ai_summary | AI 摘要 |
| ai_score | 溝通品質評分 1-10（null = 非看診） |
| ai_feedback | 改善建議 |
| ai_roles | AI 推定的角色分配（JSON） |
| ai_tags | 療程標籤（JSON array，如 ["注射", "水光針"]） |
| nas_path | NAS 歸檔路徑 |
| created_at | 建立時間 |

### 3. NAS 歸檔

```
/mnt/nas/library/看診逐字稿/
  └── 2026-03/
      ├── 2026-03-24_CH08_103500.txt
      ├── 2026-03-24_CH08_103500.json  （含 AI 分析結果）
      └── ...
```

### 4. 查詢介面

- **LINE Bot**：院長可查詢「今天的看診分析」「CH08 的逐字稿」
- **Web 前端**（後續）：看診分析頁面，按日期/頻道/評分篩選

## Capabilities

### New Capabilities

- `consultation-transcript-storage`: 逐字稿資料庫儲存與 NAS 歸檔
- `consultation-ai-analysis`: AI 自動分析逐字稿（角色推定、摘要、評分、標籤）
- `consultation-query`: LINE Bot 查詢看診分析結果

### Modified Capabilities

- `consultation-monitor`（`extends/his/core/consultation_monitor.py`）: 辨識完成後呼叫後處理 pipeline

## Impact

- **新增檔案**：
  - `extends/his/core/consultation_pipeline.py` — 後處理 pipeline（AI 分析 + 存檔 + 歸檔）
  - `backend/migrations/versions/0XX_consultation_transcripts.py` — 資料庫 migration
  - `extends/his/skills/consultation-recorder/scripts/query_transcripts.py` — LINE Bot 查詢
- **修改檔案**：
  - `extends/his/core/consultation_monitor.py` — `_finalize_session` 串接 pipeline
- **依賴**：`anthropic`（已有）
- **環境需求**：`ANTHROPIC_API_KEY` 或系統現有的 AI 呼叫機制
- **不影響**：前端（本階段不做 Web UI）、其他 HIS 功能

## Constraints

- 音訊不保留，辨識完即丟棄
- AI 分析不出場景類型時標為 `unclassified`，不強制分類
- 逐字稿含病患隱私，查詢需要 admin 權限
- 同一位醫師可能在不同診間走動，不綁定醫師與頻道的對應
- Whisper 辨識可能有誤，AI 分析應容忍辨識錯誤

## Out of Scope

- Web 前端看診分析頁面（後續獨立 change）
- 歷史錄影回放（NVR 不支援 RTSP 回放）
- 醫師身份自動識別（目前由 AI 從對話內容推定）
- 音訊保存/回放
