# Bot 語音訊息整合（extends/voice）

## 概述

為 Line Bot 與 Telegram Bot 加入語音訊息處理能力：
- **STT（語音轉文字）**：用戶發送語音訊息 → faster-whisper 轉錄 → 文字送入 AI 對話
- **TTS（文字轉語音）**：AI 回覆文字 → Edge TTS 生成語音 → 同時回覆文字與語音

功能以 `extends/voice/` 模組形式提供，非核心預設功能。

## 架構定位

```
extends/voice/          ← 獨立 git submodule（或目錄）
├── contributes.yaml    ← 生命週期 + router 宣告
├── voice_stt.py        ← STT 服務（同步 + 非同步策略）
├── voice_tts.py        ← TTS 服務（Edge TTS）
├── tts_router.py       ← TTS 音檔 API（FastAPI router）
├── README.md           ← 模組說明
└── skills/
    └── voice/
        └── SKILL.md    ← AI Skill 定義
```

核心系統（`linebot_router.py`、`telegram/handler.py`）需少量修改以偵測語音訊息並委派給 voice 模組處理。

---

## 需求

### Requirement: 模組載入與生命週期

#### Scenario: extends 自動發現
- **GIVEN** `extends/voice/contributes.yaml` 存在
- **WHEN** 應用程式啟動
- **THEN** `_start_extends_modules()` 掃描並執行 startup
- **AND** voice 模組目錄加入 `sys.path`

#### Scenario: contributes.yaml 格式
```yaml
lifespan:
  startup:
    callable: voice_startup.startup
  shutdown:
    callable: voice_startup.shutdown

routers:
  - module: tts_router
    attr: router
    kwargs:
      prefix: /api/voice

scheduler:
  - id: cleanup_tts_files
    func: voice_tts.cleanup_old_files
    trigger: cron
    hour: 4
    minute: 0
```

#### Scenario: _start_extends_modules() 擴充 routers 支援
- **GIVEN** 現行 `_start_extends_modules()` 只處理 `lifespan`，不處理 `routers`
- **WHEN** 本功能實作時
- **THEN** 擴充 `_start_extends_modules()` 支援 `contributes.yaml` 的 `routers` 欄位
- **AND** 將 extends 模組的 router 動態註冊到 FastAPI app
- **AND** 此擴充與現有 `_register_module_routers()` 的 builtin 機制一致
- **NOTE** `_start_extends_modules()` 接收 `app` 參數，避免 circular import

#### Scenario: 模組不存在時靜默跳過
- **GIVEN** `extends/voice/` 不存在
- **WHEN** Bot 收到語音訊息
- **THEN** 行為與現行相同（Line Bot 下載儲存但不觸發 AI；Telegram Bot 忽略）

---

### Requirement: STT — 語音轉文字

#### 基本流程
- **WHEN** Bot 收到語音訊息（Line `AudioMessageContent` / Telegram `message.voice`）
- **THEN** 下載音訊檔案到 NAS
- **AND** 根據音訊長度選擇同步或非同步轉錄
- **AND** 轉錄結果送入 AI 處理流程

#### Scenario: 短音訊同步轉錄（≤ 60 秒）
- **GIVEN** 音訊長度 ≤ 60 秒
- **WHEN** 音訊下載完成
- **THEN** 使用 `faster-whisper` `base` 模型，透過 `asyncio.to_thread()` 在 thread pool 中轉錄（避免 blocking event loop）
- **AND** 轉錄文字加上 `[語音訊息] ` 前綴
- **AND** 作為用戶文字訊息送入 AI 處理（與一般文字訊息走同一條路）
- **AND** 呼叫端透過 `origin_type="voice"` 參數傳遞語音來源資訊到 AI 回覆處理流程（觸發 TTS 回覆）

#### Scenario: 長音訊非同步轉錄（> 60 秒）
- **GIVEN** 音訊長度 > 60 秒
- **WHEN** 音訊下載完成
- **THEN** 呼叫現有 `media-transcription` skill 的 `transcribe` script（非同步 fork）
- **AND** 立即回覆用戶「語音訊息較長，轉錄中，完成後通知你」
- **AND** 轉錄完成後透過 proactive-push 通知用戶結果
- **NOTE** 長音訊不觸發 TTS 回覆（只推送逐字稿文字）

#### Scenario: 音訊長度未知
- **GIVEN** 平台未提供 duration 資訊（少數情況）
- **WHEN** 音訊下載完成
- **THEN** 使用 `ffprobe`（ffmpeg 工具）讀取檔案 header 取得實際 duration
- **AND** 若 `ffprobe` 失敗，則依檔案大小估算：Line M4A 以 1MB/60s 估算，Telegram OGG 以 120KB/60s 估算
- **AND** 根據估算結果決定同步或非同步

#### Scenario: 轉錄失敗
- **WHEN** faster-whisper 轉錄過程中發生錯誤
- **THEN** 回覆用戶「語音辨識失敗，請重新發送或改用文字」
- **AND** 記錄錯誤到 logger

---

### Requirement: STT — Line Bot 整合

#### Scenario: Line Bot 收到音訊訊息
- **GIVEN** voice 模組已載入
- **WHEN** `linebot_router.py` 的 `process_message_event()` 收到 `AudioMessageContent`
- **THEN** 照現行流程下載音訊到 NAS（`process_media_message()`）
- **AND** 取得 NAS 路徑後呼叫 `voice_stt.transcribe_for_bot()` 進行轉錄
- **AND** 轉錄文字進入 AI 處理流程（複用現有的文字訊息 AI 處理邏輯）

#### Scenario: 音訊格式
- Line 語音訊息格式為 M4A
- faster-whisper 已原生支援 M4A，無需轉檔

---

### Requirement: STT — Telegram Bot 整合

#### Scenario: Telegram Bot 訊息類型新增
- **GIVEN** voice 模組已載入
- **WHEN** `handler.py` 的 `_handle_update()` 判斷訊息類型
- **THEN** `message.voice`（語音錄音，OGG/Opus）→ `msg_type = "audio"`
- **NOTE** `message.audio`（音訊檔案附件，如 MP3 音樂）**不觸發 STT**，視為一般檔案處理。因為音訊檔案可能是音樂、podcast 等非語音內容，送入 Whisper 會浪費算力且結果無意義

#### Scenario: Telegram 語音下載
- **WHEN** 收到 Telegram voice message
- **THEN** `media.py` 新增 `download_telegram_voice()` 下載 OGG 音訊到 NAS
- **AND** 使用 `_generate_telegram_nas_path(file_type="audio", ...)` 生成路徑
- **AND** 記錄 `duration` 到 `bot_files`

#### Scenario: Telegram 音訊送入 AI
- **WHEN** 音訊下載並轉錄完成
- **THEN** 轉錄文字加上用戶名稱前綴
- **AND** 呼叫 `_handle_text_with_ai()` 走既有 AI 處理流程

#### Scenario: 音訊格式
- Telegram voice message 格式為 OGG (Opus)
- faster-whisper 已原生支援 OGG，無需轉檔

---

### Requirement: TTS — 文字轉語音

#### Scenario: Edge TTS 生成語音
- **WHEN** 需要將 AI 回覆文字轉為語音
- **THEN** 使用 `edge-tts` 套件生成 MP3 音檔
- **AND** 預設語音角色 `zh-TW-HsiaoChenNeural`（台灣女聲）
- **AND** 音檔儲存到 NAS：`voice/tts/{date}/{uuid}.mp3`

#### Scenario: 文字前處理
- **WHEN** AI 回覆文字包含 Markdown 格式（`**粗體**`、`- 列表`、`` `程式碼` `` 等）
- **THEN** 先清除 Markdown 標記再送入 TTS
- **AND** 若文字超過 500 字，截斷至 500 字（Edge TTS 效能考量）
- **AND** 截斷時在末尾加上「...後續請參考文字訊息」

#### Scenario: TTS 失敗
- **WHEN** Edge TTS 生成失敗（網路問題等）
- **THEN** 僅回覆文字訊息（不影響用戶體驗）
- **AND** 記錄警告到 logger

---

### Requirement: TTS — Line Bot 回覆

#### Scenario: Line Bot 語音回覆
- **GIVEN** 用戶的原始訊息為語音
- **WHEN** AI 回覆文字已生成
- **THEN** 使用 Edge TTS 生成 MP3
- **AND** 儲存到 NAS，取得 TTS API URL
- **AND** 使用 `AudioMessage(original_content_url=url, duration=ms)` 回覆
- **AND** 同時回覆 `TextMessage`（文字版本）
- **NOTE** Line AudioMessage 需要 `original_content_url`（HTTPS 公開 URL）和 `duration`（毫秒）

#### Scenario: Line Bot 使用 push 回覆
- **GIVEN** reply_token 可能已過期（AI 處理 + TTS 生成耗時）
- **WHEN** reply_token 不可用
- **THEN** 使用 `push_messages()` 主動推送文字 + 音訊

---

### Requirement: TTS — Telegram Bot 回覆

#### Scenario: Telegram Bot 語音回覆
- **GIVEN** 用戶的原始訊息為語音
- **WHEN** AI 回覆文字已生成
- **THEN** 使用 Edge TTS 生成 MP3
- **AND** 使用 `bot.send_voice()` 直接上傳音檔（Telegram 支援直接上傳，不需公開 URL）
- **AND** 同時發送文字訊息

#### Scenario: Telegram adapter 新增方法
- `TelegramBotAdapter` 新增 `send_voice(target, audio_bytes, duration, reply_to)` 方法
- 使用 `bot.send_voice()` 上傳 OGG/MP3 音檔

---

### Requirement: TTS 音檔 API

#### Scenario: TTS 檔案下載端點
- **GIVEN** `extends/voice/tts_router.py` 提供 FastAPI router
- **WHEN** Line 伺服器請求 `GET /api/voice/tts/{file_id}.mp3`
- **THEN** 從 NAS 讀取對應的 MP3 檔案
- **AND** 回傳 `audio/mpeg` Content-Type
- **AND** 設定 `Cache-Control: public, max-age=86400`

#### Scenario: file_id 安全性
- `file_id` 使用 UUID4 格式（如 `a1b2c3d4-e5f6-7890-abcd-ef1234567890`），不可預測
- 端點不需認證（Line 伺服器需直接存取），但 UUID4 本身提供足夠的不可列舉性
- 音檔 24 小時後自動清理，進一步限制暴露窗口
- 路徑穿越防護：`file_id` 必須符合 UUID4 格式，否則回傳 400

#### Scenario: 檔案不存在
- **WHEN** 請求的 file_id 對應的檔案不存在
- **THEN** 回傳 404

#### Scenario: 音檔自動清理
- **GIVEN** TTS 音檔為暫存性質
- **WHEN** 音檔存放超過 24 小時
- **THEN** 排程清理任務 `voice_tts.cleanup_old_files()` 刪除過期音檔
- **AND** 清理任務透過 `contributes.yaml` 的 `scheduler` 欄位註冊（每日 04:00 執行）

---

### Requirement: voice_stt.py 介面

```python
# extends/voice/voice_stt.py

from dataclasses import dataclass

@dataclass
class TranscribeResult:
    mode: str            # "sync" | "async"
    text: str | None     # 轉錄文字（sync 模式下有值，async 模式為 None）
    job_id: str | None   # 非同步 job ID（async 模式下有值，sync 模式為 None）
    error: str | None    # 錯誤訊息（失敗時有值，成功為 None）

async def transcribe_for_bot(
    nas_path: str,
    duration_ms: int | None = None,
    file_size: int | None = None,
    platform: str = "line",
) -> TranscribeResult:
    """Bot 語音訊息轉錄入口

    Args:
        nas_path: 音訊檔在 NAS 上的路徑
        duration_ms: 音訊長度（毫秒），由平台提供
        file_size: 檔案大小（bytes），作為 duration 的備選判斷
        platform: 來源平台（"line" | "telegram"），用於 duration 估算

    Returns:
        TranscribeResult
    """

async def warmup() -> None:
    """啟動時預載 whisper base 模型到記憶體（在 thread pool 中執行，不阻塞 event loop）。"""

def cleanup() -> None:
    """關閉時釋放模型資源。"""
```

#### 並行存取
- faster-whisper (CTranslate2) 推論不是 thread-safe
- 使用 `asyncio.Semaphore(1)` 序列化並行的轉錄請求
- 多個語音訊息同時到達時排隊處理，第二個以後的會稍微延遲

---

### Requirement: voice_tts.py 介面

```python
# extends/voice/voice_tts.py

from dataclasses import dataclass

@dataclass
class TTSResult:
    nas_path: str | None      # 音檔 NAS 路徑（成功時有值）
    file_id: str | None       # UUID4 音檔 ID（用於 API URL）
    duration_ms: int | None   # 音檔長度（毫秒）
    audio_bytes: bytes | None # 音檔二進位（供 Telegram 直接上傳）
    error: str | None         # 錯誤訊息（失敗時有值，成功為 None）

async def synthesize(
    text: str,
    voice: str = "zh-TW-HsiaoChenNeural",
) -> TTSResult:
    """將文字轉為語音

    Args:
        text: 要轉語音的文字（會自動清除 Markdown、截斷至 500 字）
        voice: Edge TTS 語音角色

    Returns:
        TTSResult
    """

def cleanup_old_files() -> None:
    """清理超過 24 小時的 TTS 暫存音檔。由排程任務呼叫。"""
```

#### 已知限制（v1）
- TTS 語音角色固定為繁體中文，不會根據 STT 偵測到的語言自動切換
- Edge TTS 依賴 Microsoft 線上服務，離線時 TTS 不可用（但不影響 STT 和文字回覆）

---

### Requirement: SKILL.md 定義

```yaml
---
name: voice
description: Bot 語音訊息處理（STT + TTS）
allowed-tools: ""
metadata:
  ctos:
    requires_app: voice
    mcp_servers: ""
  contributes:
    app:
      id: voice
      name: 語音訊息
      icon: mdi-microphone
    permissions:
      voice:
        default: true
        display_name: 語音訊息
---
```

---

### Requirement: 核心系統修改（最小化）

核心系統需要少量修改以支援語音模組的條件載入。

#### voice 模組發現工具函式
- 新增 `services/bot/voice_bridge.py`
- 提供 `get_voice_module()` → 回傳 voice 模組或 `None`
- 透過 `sys.modules` 或 `importlib` 檢查 voice 模組是否已載入
- 所有核心程式碼透過此 bridge 存取 voice 功能

```python
# services/bot/voice_bridge.py

def get_voice_stt():
    """取得 voice STT 模組，未安裝時回傳 None"""
    try:
        import voice_stt
        return voice_stt
    except ImportError:
        return None

def get_voice_tts():
    """取得 voice TTS 模組，未安裝時回傳 None"""
    try:
        import voice_tts
        return voice_tts
    except ImportError:
        return None
```

#### origin_type 語音來源資訊傳遞
Bot 回覆需要知道「用戶原始訊息是語音」才能觸發 TTS。傳遞機制如下：

**Line Bot**：
- `linebot_router.py` 在音訊轉錄完成後，呼叫 AI 處理時傳入 `origin_type="voice"` 參數
- AI 回覆後，檢查 `origin_type`，若為 `"voice"` 則呼叫 TTS 生成語音並附帶回覆

**Telegram Bot**：
- `handler.py` 新增 `_handle_voice()` 函式（類似 `_handle_text()`）
- 內部流程：下載 → STT → 組裝 AI prompt → 呼叫 `_handle_text_with_ai()`
- AI 回覆後，由 `_handle_voice()` 負責額外發送語音訊息

兩邊的 TTS 回覆邏輯都在各自的 handler 中完成，不需修改 AI 核心處理流程（`call_claude` / `linebot_ai`）。

#### linebot_router.py 修改
- 在 `process_message_event()` 的 `message_type == "audio"` 分支後
- 新增：如果 voice 模組可用，呼叫 `transcribe_for_bot()` 後走文字 AI 流程
- AI 回覆後呼叫 TTS 生成語音，同時回覆文字 + 音訊
- 約 30 行新增程式碼

#### telegram/handler.py 修改
- 訊息類型判斷新增 `message.voice` → `"audio"`
- 新增 `_handle_voice()` 函式：下載 → STT → AI → TTS 回覆
- 約 40 行新增程式碼

#### telegram/media.py 修改
- 新增 `download_telegram_voice()` 函式
- 參考現有 `download_telegram_photo()` 的模式
- 約 40 行新增程式碼

#### telegram/adapter.py 修改
- 新增 `send_voice(target, audio_bytes, duration, reply_to)` 方法
- 使用 `bot.send_voice()` 直接上傳音檔
- 約 20 行新增程式碼

#### bot_line/messaging.py 修改
- 新增 `AudioMessage` import（從 `linebot.v3.messaging`）
- 更新 `reply_messages()` 和 `push_messages()` 的 type hint 包含 `AudioMessage`
- 新增 `push_audio()` 輔助函式（類似 `push_image()`）
- 約 25 行新增程式碼

#### main.py 修改
- `_start_extends_modules()` 新增 `app` 參數，支援 `routers` 欄位
- 約 15 行新增程式碼

#### contributes.yaml 的 router 註冊
- **需要擴充** `_start_extends_modules()` 支援 `routers` 欄位
- 擴充方式：`_start_extends_modules(app)` 接收 FastAPI app 參數
- 讀取 `contributes.yaml` 的 `routers` 欄位後，動態 `app.include_router()`
- 此機制與現有 `_register_module_routers()` 一致，不引入 circular import

#### main.py 擴充
```python
# main.py lifespan() 中
extends_shutdown_fns = await _start_extends_modules(app)  # 傳入 app
```

```python
# _start_extends_modules(app) 中新增
routers_cfg = config.get("routers")
if isinstance(routers_cfg, list):
    for router_spec in routers_cfg:
        mod = importlib.import_module(router_spec["module"])
        router = getattr(mod, router_spec.get("attr", "router"))
        kwargs = router_spec.get("kwargs", {})
        app.include_router(router, **kwargs)
```

#### voice_startup.py
```python
# extends/voice/voice_startup.py

async def startup():
    """模組啟動：預載 whisper 模型"""
    from voice_stt import warmup
    await warmup()

async def shutdown():
    """模組關閉：釋放資源"""
    from voice_stt import cleanup
    cleanup()
```

---

### Requirement: 套件依賴

#### extends/voice 內部依賴
- `edge-tts`：TTS 引擎（需安裝到後端環境）
- `faster-whisper`：已在後端 `pyproject.toml` 中安裝

#### 安裝方式
- `edge-tts` 加入後端 `pyproject.toml` 的 optional dependencies
- 或由 extends/voice 的 `requirements.txt` 聲明，安裝時手動 `pip install`

建議方案：加入 `pyproject.toml` 的 optional dependencies group `voice`：
```toml
[project.optional-dependencies]
voice = ["edge-tts>=6.1.0"]
```

---

## 檔案變更總覽

### 新增（extends/voice/）
| 檔案 | 用途 |
|------|------|
| `contributes.yaml` | 生命週期宣告 |
| `voice_stt.py` | STT 服務（同步/非同步轉錄） |
| `voice_tts.py` | TTS 服務（Edge TTS） |
| `voice_startup.py` | 模組啟動/關閉（預載模型、註冊 router） |
| `tts_router.py` | TTS 音檔下載 API |
| `skills/voice/SKILL.md` | AI Skill 定義 |
| `README.md` | 模組說明 |

### 新增（核心）
| 檔案 | 用途 |
|------|------|
| `services/bot/voice_bridge.py` | voice 模組條件載入橋接 |

### 修改（核心，最小化）
| 檔案 | 變更內容 | 預估行數 |
|------|---------|---------|
| `main.py` | `_start_extends_modules(app)` 支援 routers | +15 行 |
| `api/linebot_router.py` | 音訊 → STT → AI → TTS 回覆 | +30 行 |
| `services/bot_telegram/handler.py` | 新增 voice 類型 + `_handle_voice()` | +40 行 |
| `services/bot_telegram/media.py` | 新增 `download_telegram_voice()` | +40 行 |
| `services/bot_telegram/adapter.py` | 新增 `send_voice()` | +20 行 |
| `services/bot_line/messaging.py` | `AudioMessage` + `push_audio()` | +25 行 |
| `pyproject.toml` | 新增 `voice` optional dependency | +3 行 |

---

## 流程圖

### 短音訊（≤ 60 秒）完整流程
```
用戶發語音 → [Line/Telegram] Webhook 接收
  → 判斷 message_type = "audio"
  → 下載音訊到 NAS
  → voice_bridge.get_voice_stt() 檢查模組是否可用
    → 不可用：僅儲存，不處理（現行行為）
    → 可用：
      → voice_stt.transcribe_for_bot(nas_path, duration)
      → mode = "sync"（duration ≤ 60s）
      → faster-whisper base 模型同步轉錄
      → 回傳 text = "[語音訊息] 轉錄文字..."
      → 送入 AI 處理（複用文字訊息流程）
      → AI 回覆 text
      → voice_bridge.get_voice_tts() 檢查 TTS 模組
        → 可用：voice_tts.synthesize(ai_reply_text)
          → Edge TTS 生成 MP3
          → Line: 回覆 TextMessage + AudioMessage
          → Telegram: send_text + send_voice
        → 不可用：僅回覆文字
```

### 長音訊（> 60 秒）流程
```
用戶發語音 → 下載音訊到 NAS
  → voice_stt.transcribe_for_bot(nas_path, duration)
  → mode = "async"（duration > 60s）
  → 呼叫 media-transcription skill 背景轉錄
  → 立即回覆「語音訊息較長，轉錄中...」
  → [背景] 轉錄完成 → proactive-push 通知用戶逐字稿
```
