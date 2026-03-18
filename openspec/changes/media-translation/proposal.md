## Why

AI 在 Line Bot 中收到長文翻譯需求時，錯誤使用了 claude-code-acp 的 Task 背景工具（`run_in_background: true`）。該工具依附於 acp session，session 結束後子代理即死亡，使用者永遠收不到翻譯結果。需要一個正式的背景翻譯 skill，沿用 media-downloader / media-transcription 的 `os.fork()` + `proactive-push` 模式。

## What Changes

- 新增 `media-translation` skill：使用 Google Gemini SDK 進行長文翻譯，背景執行
- 支援 NAS 檔案路徑或直接文字輸入
- 自動偵測語言方向（英文→繁中、繁中→英文），可指定目標語言
- 分 chunk 翻譯（每 20,000 字元一段），有進度追蹤
- 完成後透過 proactive-push 主動通知使用者
- 在 prompt 中禁止 AI 使用 Task 工具的 `run_in_background` 模式

## Capabilities

### New Capabilities
- `media-translation`：背景長文翻譯 skill，含 translate（啟動）和 check-translation（查進度）兩個 script

### Modified Capabilities
- `bot-platform`：prompt 新增禁止 Task run_in_background 規則
- `bot-proactive-push`：internal_push.py 新增 media-translation 的完成通知

## Impact

- **後端**：
  - `skills/media-translation/`：新增 SKILL.md、translate.py、check-translation.py
  - `api/internal_push.py`：新增翻譯完成訊息格式
  - `services/linebot_agents.py`：新增禁止 background Task 規則
