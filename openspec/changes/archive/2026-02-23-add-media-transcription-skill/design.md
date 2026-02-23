## Context

系統已有 `media-downloader` skill，採用 fork 背景程序 + status.json 的非同步模式處理耗時的下載任務。本 skill 作為其下游，需要接收下載完成的 `ctos://` 路徑，對音訊/影片做語音辨識轉逐字稿。

現有基礎設施：
- **Skill 執行框架**：`run_skill_script` MCP tool + `ScriptRunner`，腳本透過 stdin/stdout JSON 通訊
- **虛擬路徑系統**：`ctos://` 對應 `/mnt/nas/ctos/`，`shared://` 對應 NAS 共用目錄
- **ffmpeg**：系統已安裝（v6.1），可用於從影片中提取音軌
- **ASR-IME 專案**：團隊已有 `faster-whisper` + `opencc` 的使用經驗（`asr-ime-fcitx` 專案）

## Goals / Non-Goals

**Goals:**
- 提供完整的「影片/音訊 → 逐字稿」轉錄能力
- 與 media-downloader 使用相同的非同步模式（fork + status.json），使用者體驗一致
- 輸出繁體中文逐字稿（Whisper 預設輸出簡體，需轉換）
- 逐字稿暫存為 Markdown，方便後續由 AI 整理或存入知識庫/圖書館

**Non-Goals:**
- 不做即時串流轉錄（不需要麥克風輸入，只處理檔案）
- 不做說話人辨識（diarization）— 未來可擴充
- 不做字幕檔（SRT/VTT）輸出 — 未來可擴充
- 不整合到 Line Bot 語音訊息自動轉錄 — 這是另一個 change 的範疇

## Decisions

### 1. 語音辨識引擎：faster-whisper

**選擇**：`faster-whisper`（CTranslate2 優化版 Whisper）

**替代方案**：
- ~~Google Gemini API~~：付費，需 API 金鑰
- ~~OpenAI Whisper（原版）~~：速度慢，記憶體用量高
- ~~Google Cloud Speech-to-Text~~：付費，需帳號設定

**理由**：免費、本地執行、速度比原版快 4 倍、記憶體用量減半。團隊在 `asr-ime-fcitx` 已有使用經驗。

### 2. 模型大小：預設 small

**選擇**：預設 `small`，可透過 script input 參數覆蓋

| 模型 | 大小 | 速度（CPU） | 品質 |
|------|------|------------|------|
| base | 150 MB | 最快 | 普通 |
| small | 500 MB | 快 | 好 |
| medium | 1.5 GB | 中等 | 很好 |
| large-v3 | 3 GB | 慢 | 最好 |

**理由**：`small` 是品質/速度的最佳平衡點，與 ASR-IME 預設一致。使用者可根據需求指定其他模型。

### 3. 裝置偵測：自動選擇 CPU/GPU

**選擇**：參考 ASR-IME 做法
- 有 `nvidia-smi` → CUDA + float16
- 否則 → CPU + int8

目前伺服器為 CPU 環境，使用 int8 量化跑 `small` 模型即可。

### 4. 簡轉繁：opencc s2twp

**選擇**：`opencc-python-reimplemented`，使用 `s2twp`（簡體 → 繁體台灣用語）

**理由**：Whisper 對中文輸出幾乎都是簡體。ASR-IME 已驗證此方案有效。`s2twp` 相比 `s2t` 會額外轉換台灣慣用詞（如「計程車」而非「出租車」）。

### 5. 非同步架構：fork + status.json

**選擇**：與 `download-video.py` 完全相同的模式

```
transcribe script 啟動
  ├── 父程序：立即回傳 { job_id, status: "started" }
  └── 子程序（背景）：
        1. ffmpeg 提取音軌 → 暫存 .wav
        2. faster-whisper 轉錄
        3. opencc 簡轉繁
        4. 寫入 transcript.md
        5. 更新 status.json → completed
```

**理由**：
- 轉錄 10 分鐘影片可能需 2-5 分鐘（CPU），超過 script 預設 30 秒逾時
- 使用者體驗一致：transcribe 啟動 → check-transcription 查進度 → 完成取結果

### 6. 暫存路徑

```
ctos://linebot/transcriptions/{YYYY-MM-DD}/{uuid8}/
├── status.json          # 進度追蹤
├── audio.wav            # 提取的音軌（轉錄完成後刪除以節省空間）
└── transcript.md        # 逐字稿（Markdown 格式）
```

**Markdown 格式**：
```markdown
# 逐字稿：{原始檔名}

> 來源：{ctos_path}
> 轉錄時間：{timestamp}
> 模型：whisper-{model}
> 時長：{duration}

{逐字稿內容，依時間戳分段}
```

### 7. 音軌提取：ffmpeg

**選擇**：使用 `ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav`

**理由**：
- faster-whisper 需要音訊輸入（不直接處理影片）
- 16kHz mono WAV 是 Whisper 的原生取樣率
- 純音訊檔（.mp3/.m4a/.wav）可跳過此步驟，直接交給 faster-whisper

## Risks / Trade-offs

**[轉錄速度]** CPU 上 `small` 模型處理 10 分鐘音訊約需 2-5 分鐘
→ 使用非同步模式，使用者不需等待；可建議長影片改用 `base` 模型加速

**[模型首次下載]** `small` 模型約 500MB，首次執行需下載
→ status.json 顯示 "downloading_model" 狀態告知使用者；下載後自動快取

**[記憶體用量]** `small` 模型 CPU int8 約需 1GB RAM
→ 目前伺服器記憶體充足；若有問題可降級為 `base`（約 400MB）

**[簡轉繁品質]** opencc 是規則式轉換，少數詞可能轉換不完美
→ 已驗證在 ASR-IME 中效果良好；使用者後續可請 AI 校對

**[磁碟空間]** 暫存的 WAV 音訊可能很大（10 分鐘 ≈ 19MB）
→ 轉錄完成後自動刪除暫存 WAV

## Open Questions

- 是否需要提供「取消轉錄」功能？（初版暫不實作，可後續加入）
- 逐字稿是否需要包含時間戳（如 `[00:30]` 前綴）？faster-whisper 有提供 segment 時間資訊，初版先加入
