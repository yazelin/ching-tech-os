## Architecture

### 整體流程

```
consultation_monitor.py
  │ _finalize_session() 完成 Whisper 辨識
  │ 回傳 {channel, start_time, duration, transcript, segments}
  │
  ▼
consultation_pipeline.py (新增)
  │
  ├── 1. AI 分析（Claude）
  │     └── 一次呼叫，回傳結構化 JSON
  │
  ├── 2. 存入資料庫
  │     └── INSERT INTO consultation_transcripts
  │
  └── 3. 歸檔到 NAS
        └── 寫 .txt + .json 到 /mnt/nas/library/看診逐字稿/
```

### Pipeline 呼叫方式

`consultation_monitor.py` 的 `_finalize_session` 辨識完成後，在背景 thread 呼叫 pipeline：

```python
# consultation_monitor.py（修改）
async def _finalize_session(session):
    full_audio = session.get_full_audio()
    result = await asyncio.to_thread(_transcribe, full_audio)
    session.save_transcript(result)  # 保留原本的 /tmp 存檔（debug 用）

    # 新增：呼叫後處理 pipeline
    if result and result.get("text", "").strip():
        await asyncio.to_thread(
            process_transcript,
            channel=f"CH{session.channel:02d}",
            start_time=session.start_time,
            duration_seconds=session.buffer_seconds,
            transcript=result["text"],
            segments=result["segments"],
        )
```

## Technical Decisions

### AI 分析 Prompt 設計

單次呼叫 Claude，回傳結構化 JSON：

```
系統 Prompt:
你是皮膚科診所的看診對話分析助手。
分析以下從診間錄音轉錄的逐字稿，回傳 JSON 格式分析結果。

注意：
- 逐字稿來自語音辨識，可能有錯字或漏字
- 如果無法判斷是看診對話（可能是閒聊、討論行政事務），scene_type 設為對應類型
- 從對話內容推定誰是醫師、誰是病患（醫師通常在解釋病情/治療、病患在描述症狀/提問）
- 評分只在 scene_type 為 consultation 時給出

回傳格式（嚴格 JSON）：
{
  "scene_type": "consultation" | "chat" | "admin" | "unclassified",
  "summary": "簡述這段對話的主要內容（50字內）",
  "roles": [
    {"role": "doctor", "name": null, "evidence": "解釋了注射療程的注意事項"},
    {"role": "patient", "name": null, "evidence": "詢問術後保養問題"},
    {"role": "nurse", "name": null, "evidence": "協助操作電腦"}
  ],
  "score": 8,          // 1-10，僅 consultation 時給出，否則 null
  "score_breakdown": {  // 僅 consultation 時給出，否則 null
    "explanation_clarity": 8,  // 解釋清晰度
    "empathy": 7,              // 同理心
    "patient_engagement": 9,   // 病患參與度
    "professionalism": 8       // 專業度
  },
  "feedback": "醫師解釋療程很清楚，但可以多確認病患是否理解",
  "tags": ["注射", "肉毒", "術後衛教"]
}
```

### AI 呼叫方式

使用系統的 `call_claude`（claude-code-acp，OAuth 認證），不需要 API key：

```python
from ching_tech_os.services.claude_agent import call_claude

response = await call_claude(
    prompt=f"分析以下逐字稿：\n\n{transcript}",
    model="haiku",
    system_prompt=ANALYSIS_SYSTEM_PROMPT,
    timeout=60,
    tools=[],
)
```

**模型選擇**：Haiku — 每天可能有數十段逐字稿，Haiku 成本低且速度快，分析品質足夠。

### 資料庫 Schema

```sql
CREATE TABLE consultation_transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(10) NOT NULL,           -- 'CH08', 'CH10', 'CH11'
    start_time TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER NOT NULL,
    transcript TEXT NOT NULL,
    segments JSONB,                          -- [{start, end, text}, ...]
    scene_type VARCHAR(20) DEFAULT 'unclassified',
    ai_summary TEXT,
    ai_score SMALLINT,                       -- 1-10, NULL if not consultation
    ai_score_breakdown JSONB,                -- {explanation_clarity, empathy, ...}
    ai_feedback TEXT,
    ai_roles JSONB,                          -- [{role, name, evidence}, ...]
    ai_tags JSONB DEFAULT '[]'::jsonb,       -- ["注射", "水光針"]
    ai_raw_response JSONB,                   -- 完整 AI 回應（debug 用）
    nas_path VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ct_start_time ON consultation_transcripts(start_time DESC);
CREATE INDEX idx_ct_channel ON consultation_transcripts(channel);
CREATE INDEX idx_ct_scene_type ON consultation_transcripts(scene_type);
CREATE INDEX idx_ct_ai_score ON consultation_transcripts(ai_score) WHERE ai_score IS NOT NULL;
```

不使用分區表（資料量不大，一天數十筆）。

### NAS 歸檔格式

**路徑**：`{LIBRARY_MOUNT_PATH}/看診逐字稿/{YYYY-MM}/{YYYY-MM-DD}_{channel}_{HHMMSS}.txt`

**txt 檔**（人可讀）：
```
# CH08 看診逐字稿
# 時間: 2026-03-24 10:35:00
# 時長: 480 秒
# 場景: consultation
# 摘要: 討論肉毒注射療程，說明術後注意事項
# 評分: 8/10

[0:00~0:05] 今天是來打肉毒對嗎
[0:05~0:08] 對 上次有先諮詢過
...
```

**json 檔**（結構化，供後續系統讀取）：
```json
{
  "channel": "CH08",
  "start_time": "2026-03-24T10:35:00",
  "duration_seconds": 480,
  "transcript": "...",
  "segments": [...],
  "analysis": { ... AI 完整回應 ... }
}
```

### LINE Bot 查詢

新增 skill script `query_transcripts.py`，支援：

```json
// 查今天的看診分析
{"action": "today"}

// 查特定頻道
{"action": "today", "channel": "CH08"}

// 查特定日期
{"action": "date", "date": "2026-03-24"}

// 查高分/低分
{"action": "top", "limit": 5}
{"action": "low", "limit": 5}
```

回傳格式（文字）：
```
📊 今日看診分析（2026-03-24）

CH08 10:35 看診（8分）
  肉毒注射療程說明，術後注意事項衛教
CH11 10:48 看診（7分）
  酒糟問診，蠕形蟎蟲檢查建議
CH08 11:15 閒聊
  護理師討論排班

共 3 段 | 平均分數 7.5
```

### 權限控制

查詢 API 需要 admin 權限。在 `query_transcripts.py` 中：
- skill 的 `requires_app` 設為需要特定權限
- 或直接在 script 內檢查 `ctos_user_id` 是否為 admin

### 錯誤處理

Pipeline 任一步驟失敗不應影響 consultation_monitor 的持續運作：

```python
async def process_transcript(...):
    # AI 分析失敗 → 仍然存入資料庫（ai_ 欄位為 null）
    # 資料庫失敗 → 仍然歸檔到 NAS
    # NAS 失敗 → 至少逐字稿在 /tmp 有一份
    # 全部失敗 → 只 log warning，不中斷監控
```

## Dependencies

- `anthropic` — 已在 pyproject.toml
- `asyncpg` — 已有，用於資料庫寫入
- `LIBRARY_MOUNT_PATH` — NAS 掛載路徑
- `ANTHROPIC_API_KEY` — 環境變數（systemd service 需設定）
