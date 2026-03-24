## Tasks

### 1. 資料庫 Migration

- [x] 建立 `consultation_transcripts` 表（Alembic migration）
- [x] 建立索引（start_time, channel, scene_type, ai_score）
- [x] 執行 `uv run alembic upgrade head` 驗證

**檔案**: `backend/migrations/versions/0XX_consultation_transcripts.py`

---

### 2. 後處理 Pipeline

- [x] 新增 `extends/his/core/consultation_pipeline.py`
- [x] 實作 `analyze_transcript()` — Claude AI 分析（scene_type, roles, score, feedback, tags）
- [x] 實作 `save_to_database()` — 寫入 consultation_transcripts 表
- [x] 實作 `archive_to_nas()` — 歸檔 .txt + .json 到 NAS 圖書館
- [x] 實作 `process_transcript()` — 整合以上三步，任一步驟失敗不中斷
- [ ] AI 分析 prompt 調校（用已有的逐字稿測試）

**檔案**: `extends/his/core/consultation_pipeline.py`

---

### 3. 串接 consultation_monitor

- [x] 修改 `_finalize_session()` — Whisper 辨識後呼叫 `process_transcript()`
- [x] 確保 pipeline 在背景執行，不阻塞下一段音訊探測
- [x] 錯誤處理：pipeline 失敗只 log warning，不影響監控

**檔案**: `extends/his/core/consultation_monitor.py`

---

### 4. LINE Bot 查詢 Script

- [x] 新增 `query_transcripts.py` — 查詢逐字稿分析結果
- [x] 支援 action: today, date, top, low
- [x] 支援 channel 篩選
- [x] 權限檢查：需要 admin 或指定權限
- [x] 更新 `consultation-recorder/SKILL.md` 加入新 script

**檔案**: `extends/his/skills/consultation-recorder/scripts/query_transcripts.py`

---

### 5. 環境與部署

- [x] AI 呼叫改用 call_claude（OAuth，不需 ANTHROPIC_API_KEY）
- [x] 確認 `LIBRARY_MOUNT_PATH` 可寫入
- [ ] 重啟服務驗證 pipeline 完整流程
- [ ] 測試：錄製 → 辨識 → AI 分析 → 資料庫 → NAS 歸檔 → LINE Bot 查詢
