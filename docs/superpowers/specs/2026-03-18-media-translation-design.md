# 背景翻譯 Skill 設計（media-translation）

## 背景

AI 在 Line Bot 中收到長文翻譯需求時，錯誤使用了 claude-code-acp 的 Task 背景工具。該工具依附於 acp session，session 結束後子代理即死亡，使用者永遠收不到結果。

本設計建立一個 `media-translation` skill，沿用 media-downloader / media-transcription 的 `os.fork()` + `proactive-push` 模式，確保背景翻譯任務能獨立運行並主動通知使用者。

## 輸入來源

支援兩種輸入（二擇一）：

1. **NAS 檔案路徑**：`source_path`（ctos:// 路徑），讀取純文字檔（`.md`、`.txt`）
2. **直接文字**：`text` 欄位，直接翻譯傳入的文字

限制：僅支援純文字檔案，不支援 PDF、Word 等格式（可先用 `read_document` 擷取文字再傳入 `text`）。

### 輸入大小限制

- `source_path`：檔案大小上限 2 MB
- `text`：字元數上限 500,000 字元

## 翻譯引擎

使用 Google Gemini SDK（`google-genai`），預設模型 `gemini-2.5-flash`。

- API Key 來源：環境變數 `GEMINI_API_KEY`（與 voice TTS 共用）
- 模型可透過 input 參數 `model` 覆蓋，方便未來遷移（如 Gemini 3.0 Flash）

## 目標語言

- 預設自動偵測：英文/中英夾雜 → 繁體中文；繁體中文 → 英文
- 可透過 `target_language` 參數指定（如 `zh-TW`、`en`、`ja`）

## Skill 結構

```
backend/src/ching_tech_os/skills/media-translation/
├── SKILL.md                    # requires_app: file-manager
└── scripts/
    ├── translate.py            # 啟動翻譯（os.fork 背景執行）
    └── check-translation.py    # 查詢翻譯進度
```

## translate.py 核心流程

```
AI 呼叫 run_skill_script(skill="media-translation", script="translate", input=JSON)
  ↓
讀取 input：source_path / text / target_language / model / caller_context
  ↓
建立 job_dir（/mnt/nas/ctos/linebot/translations/YYYY-MM-DD/{job_id}/）
寫入初始 status.json
  ↓
os.fork()
  ├─ 父程序：立即回傳 { success: true, job_id, status: "started" }
  └─ 子程序：
       os.setsid()          # 脫離父程序 session
       os.chdir(job_dir)    # 防止 tmpdir 被刪
       重導向 stdin→/dev/null, stdout/stderr→worker.log
       ↓
     讀取來源內容（ctos_path → 實際檔案路徑，或直接用 text）
       ↓
     切 chunk（每 500 行一段，在空行處切分避免切斷段落）
       ↓
     逐 chunk 呼叫 Gemini 翻譯
     每完成一段更新 status.json（"translating 3/12"）
       ↓
     合併所有翻譯結果，寫入輸出檔
       ↓
     更新 status.json → completed
       ↓
     _trigger_proactive_push(job_id, "media-translation")
       ↓
     os._exit(0)
```

### Input JSON 格式

```json
{
  "source_path": "ctos://linebot/transcriptions/2026-03-18/.../transcript.md",
  "text": null,
  "target_language": null,
  "model": "gemini-2.5-flash",
  "caller_context": { "platform": "line", "platform_user_id": "Uxxxx", "is_group": true, "group_id": "Cxxxx" }
}
```

- `source_path` 和 `text` 二擇一，至少提供一個
- `target_language` 預設 null（自動偵測）
- `model` 預設 `gemini-2.5-flash`

### 輸出位置

- 來源是 NAS 檔案 → 翻譯檔存在來源旁邊，檔名加語言後綴（如 `transcript_zh-TW.md`）；若已存在則覆蓋
- 來源是純文字 → 存到 `ctos://linebot/translations/YYYY-MM-DD/{job_id}/translation.md`

### status.json 結構

```json
{
  "job_id": "a1b2c3d4",
  "status": "translating",
  "progress": "3/12",
  "source_path": "ctos://...",
  "source_filename": "transcript.md",
  "target_language": "zh-TW",
  "model": "gemini-2.5-flash",
  "output_path": null,
  "ctos_path": null,
  "error": null,
  "warnings": [],
  "caller_context": { ... },
  "created_at": "2026-03-18T10:00:00",
  "updated_at": "2026-03-18T10:01:30"
}
```

狀態值：`starting` → `reading` → `translating` → `completed` / `failed`

## Gemini 翻譯 Prompt

每個 chunk 呼叫一次：

```
你是專業翻譯。將以下內容翻譯成{target_language}。

規則：
- 保留所有時間戳格式（如 [00:00]、[01:23]）
- 保留品牌名/產品名/專有名詞的英文原文（如 NVIDIA、CUDA、Blackwell）
- 翻譯要自然流暢，不要逐字翻譯
- 保留原文的 Markdown 格式（標題、粗體、列表等）
- 不要添加任何額外說明或註解

{chunk_text}
```

若 `target_language` 為 null（自動偵測模式）：
- 使用第一個 chunk 偵測來源語言，決定翻譯方向
- 偵測結果套用到所有後續 chunk（確保一致性）

偵測 prompt（僅第一個 chunk）：
```
你是專業翻譯。偵測以下內容的主要語言：
- 若主要是英文或中英夾雜，翻譯成繁體中文
- 若主要是繁體中文，翻譯成英文
（其餘規則同上）

請在翻譯結果的第一行以 [DETECTED_LANG:xx] 格式標示偵測到的目標語言（如 [DETECTED_LANG:zh-TW]），方便後續 chunk 使用。
```
後續 chunk 使用偵測到的語言，走標準翻譯 prompt。

## Chunk 策略

- 以字元數為主：每 chunk 約 20,000 字元（約 500 行普通文字）
- 優先在空行處切分，避免切斷段落中間
- 若找不到空行，則在最近的換行處切分
- 最後不足門檻的尾巴作為最後一個 chunk

## 錯誤處理

- 單一 chunk 翻譯失敗 → 重試最多 3 次（exponential backoff）
- 3 次都失敗 → 該 chunk 保留原文，status.json 記錄 warning
- 全部 chunk 都失敗 → status 設為 `failed`

## check-translation.py

同步查詢翻譯進度：

- 輸入：`{ "job_id": "a1b2c3d4" }`
- 輸出：status.json 內容 + 完成時提供 `file_path`（絕對路徑）和 `ctos_path`
- 逾時判定：30 分鐘無更新視為 failed
- 搜尋最近 7 天的日期目錄

## 需修改的現有檔案

### 1. `backend/src/ching_tech_os/api/internal_push.py`

`_find_status_file` 加入：
```python
"media-translation": "translations",
```

`_build_message` 加入翻譯完成訊息格式：
```
✅ 翻譯完成
來源：{source_filename}
翻譯檔：{ctos_path}
⚠️ {N} 段翻譯失敗，保留原文    ← 僅 warnings 非空時顯示
（job_id: {job_id}）
```

### 2. `backend/src/ching_tech_os/services/linebot_agents.py`

在通用規則區加入：
```
禁止使用 Task 工具的 run_in_background 模式。需要背景執行的長時間任務，請使用對應的 skill script（如 media-translation、media-transcription 等）。
```

## 不需修改的檔案

- `main.py` — skill 動態載入
- `skill_script_tools.py` — `run_skill_script` 通用
- `proactive_push_service.py` — 通用推送邏輯
- `bot/agents.py` — SKILL.md body 自動注入 prompt

## SKILL.md 內容概要

```yaml
---
name: media-translation
description: 長文翻譯（Gemini，背景執行）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
---
```

Prompt body 說明：
- 翻譯功能的用法（translate / check-translation）
- Input 參數說明
- 必須附帶 caller_context
- 翻譯啟動後告知使用者 job_id，完成後系統會自動通知
