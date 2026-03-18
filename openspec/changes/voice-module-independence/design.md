## Context

目前語音模組的 TTS 是硬接線在 Bot 層：語音訊息進入後，Bot 層以 `skip_send=True` 攔截 AI 正常回覆流程，自行呼叫 `voice_tts.synthesize()` 生成語音，再合併文字+語音發送。這導致 AI 的工具呼叫（如畫圖）被跳過，且 AI 無法主動決定是否使用語音回覆。

AI 回應管線現有的「標記偵測」模式（`[FILE_MESSAGE:{...}]`）已能處理圖片等多媒體回覆，TTS 結果可循相同模式整合。

MCP 工具透過 `claude-code-acp` 的 `on_tool_end` 回調捕獲工具輸出，工具回傳的字串會被 Claude 用於後續推理。但語音檔案不適合用字串傳遞，需要 Bot 層在發送前額外處理。

## Goals / Non-Goals

**Goals:**
- AI 可主動呼叫 `text_to_speech` MCP 工具，自行決定何時、對什麼內容生成語音
- Bot 層自動偵測 TTS 工具結果，組裝為平台語音訊息（Line AudioMessage / Telegram send_voice）
- TTS 引擎可透過環境變數切換（Edge TTS / Google Cloud TTS / Gemini Native Audio）
- 語音訊息不再走特殊路徑，走正常 AI 流程（解決工具呼叫被跳過的問題）
- 前端語音 App 提供語音角色選擇、試聽功能

**Non-Goals:**
- STT 流程不改動（保持自動轉錄）
- 不實作 Google Cloud TTS / Gemini Native Audio 引擎（只預留介面）
- 不實作即時串流語音（仍為完整音檔模式）
- 不做語音角色的付費/權限管理

## Decisions

### Decision 1：TTS 結果傳遞機制 — 使用 `[VOICE_MESSAGE:{...}]` 標記

**選擇**：MCP 工具回傳成功訊息給 Claude，同時在工具輸出中嵌入結構化標記。Bot 層在 `parse_ai_response()` 階段偵測並提取。

```
[VOICE_MESSAGE:{"file_id":"uuid","duration_ms":5200}]
```

**替代方案**：
- A) 在 `ClaudeResponse.tool_calls` 中掃描 TTS 工具結果 → 需要修改 `claude_agent.py` 的回調邏輯，耦合度高
- B) TTS 工具直接發送語音 → 違反 MCP 工具的無副作用原則，耦合平台邏輯

**理由**：標記模式與現有的 `[FILE_MESSAGE:{...}]` 一致，Bot 層已有解析基礎，改動最小。MCP 工具本身只需在回傳文字中包含標記，不需要知道平台細節。

**注意**：標記不會出現在使用者看到的文字中，`parse_ai_response()` 會移除它。但 Claude 在推理時會看到工具回傳的完整字串（含標記），這不影響功能，Claude 理解這是系統標記。

### Decision 2：Bot 層語音組裝位置 — 在 `send_ai_response()` 擴充

**選擇**：擴充 `linebot_ai.py` 的 `send_ai_response()` 和 Telegram 的對應函式，新增 `voice_messages` 參數。

**流程**：
```
parse_ai_response() → 提取 text, files, voices
    ↓
send_ai_response(text, files, voices)
    ↓
Line: TextMessage + ImageMessage + AudioMessage
Telegram: send_message + send_photo + send_voice
```

**理由**：`send_ai_response()` 已負責組裝多種訊息類型，語音是自然的擴充。`parse_ai_response()` 已有正則提取邏輯，新增 `[VOICE_MESSAGE:{...}]` 模式即可。

### Decision 3：TTS 引擎抽象 — Abstract Base Class + 設定 Schema + 工廠函式

**選擇**：在 `voice_tts.py` 新增 `TTSEngine` ABC，各引擎繼承實作。透過 `TTS_ENGINE` 環境變數 + 工廠函式選擇引擎。引擎介面使用 `**params` 傳遞引擎特定參數，並透過 `get_config_schema()` 讓前端動態渲染設定 UI。

```python
@dataclass
class VoiceInfo:
    id: str          # 引擎內部識別碼
    name: str        # 人類可讀名稱
    gender: str      # male / female / neutral
    language: str    # 語言代碼

class TTSEngine(ABC):
    @abstractmethod
    async def synthesize_audio(self, text: str, **params) -> bytes:
        """回傳音訊 bytes（MP3 格式）
        params 由各引擎定義，例如：
          Edge:   voice="zh-TW-HsiaoChenNeural"
          Google: voice="cmn-TW-Standard-A", speed=1.2, pitch=0
          Gemini: style="溫柔女聲"
        """

    @abstractmethod
    async def list_voices(self, language: str = "zh-TW") -> list[VoiceInfo]:
        """回傳可用語音角色清單（Gemini 可能回傳預設風格清單）"""

    @abstractmethod
    def get_config_schema(self) -> dict:
        """回傳該引擎的設定 schema，供前端動態渲染 UI
        格式為 JSON Schema 風格的描述，例如：
          Edge:   {"voice": {"type": "select", "options": [...]}}
          Google: {"voice": {"type": "select"}, "speed": {"type": "slider", "min": 0.5, "max": 2.0, "default": 1.0}, "pitch": {"type": "slider", "min": -10, "max": 10, "default": 0}}
          Gemini: {"style": {"type": "text", "placeholder": "溫柔女聲/專業播報員/..."}}
        """

class EdgeTTSEngine(TTSEngine): ...      # 現有邏輯搬入
class GoogleCloudTTSEngine(TTSEngine): ... # raise NotImplementedError
class GeminiNativeEngine(TTSEngine): ...   # raise NotImplementedError
```

**三種引擎的設定差異**：
| 面向 | Edge TTS | Google Cloud TTS | Gemini Native Audio |
|------|----------|-----------------|-------------------|
| 語音選擇 | 固定 voice ID 清單 | 固定 voice name + 語速/音調 | 無固定清單，prompt 描述風格 |
| params | `voice` | `voice`, `speed`, `pitch` | `style` |
| UI 呈現 | 下拉選單 | 下拉選單 + 滑桿 | 文字輸入或預設風格選擇 |
| 費用 | 免費 | 按字數計費 | 按 token 計費 |

**共用邏輯保留在模組層級**：
- Markdown 清除、emoji 過濾、文字截斷 → `_clean_for_tts()`
- 存檔到 NAS、計算 duration → `synthesize()` 主函式

**理由**：引擎只負責「文字 → 音訊 bytes」的轉換，其他前處理/後處理邏輯是共用的。`get_config_schema()` 讓前端不需要硬編碼各引擎的 UI，新增引擎時只需實作介面即可自動適配。

### Decision 4：語音設定存儲 — 階層式繼承

**選擇**：語音設定採四層繼承架構，每層都以 `tts_engine` + `tts_params` JSONB 格式儲存。

**階層（由低到高）**：
```
系統預設 → Agent 覆寫 → 群組覆寫 → 使用者覆寫（僅私訊）
```

**查詢優先級**：
| 情境 | 優先級（由高到低） |
|------|-------------------|
| 私訊 | 使用者設定 > Agent 設定 > 系統預設 |
| 群組 | 群組設定 > Agent 設定 > 系統預設 |

**理由**：
- 群組場景：語音訊息所有人都聽得到，應該用群組/Agent 層級設定，保持一致性
- 私訊場景：只有使用者自己聽，應該用個人偏好
- Agent 層級介於中間，賦予 AI「角色人格」的語音特質
- 系統預設是最後 fallback

**存儲位置**：
| 層級 | 存儲位置 | 格式 |
|------|---------|------|
| 系統預設 | 環境變數 `TTS_ENGINE` + `TTS_VOICE` | 字串 |
| Agent | `bot_agents` 表 `voice_settings` JSONB 欄位 | `{"tts_engine": "edge", "tts_params": {"voice": "..."}}` |
| 群組 | `bot_groups` 表 `voice_settings` JSONB 欄位 | 同上 |
| 使用者 | `users` 表 `voice_settings` JSONB 欄位 | 同上 |

**解析函式**：
```python
async def resolve_voice_settings(
    ctos_user_id: int | None,
    group_id: str | None,
    agent_id: str | None,
) -> dict:
    """依階層優先級解析最終語音設定"""
    # 私訊：使用者 > Agent > 系統
    # 群組：群組 > Agent > 系統
```

`tts_params` 用 JSONB 存放可容納不同引擎的參數差異，切換引擎時舊參數自然失效。

### Decision 5：MCP 工具如何取得語音設定

**選擇**：`text_to_speech` 工具接收 `ctos_user_id`（由框架自動注入）。Bot 層在呼叫 AI 時將 `group_id` 和 `agent_id` 注入 system prompt 或工具 context，讓工具能呼叫 `resolve_voice_settings()` 取得正確的階層設定。

**具體實作**：工具額外接收可選的 `group_id` 和 `agent_id` 參數，由 `on_tool_input_transform` 自動注入（與 `ctos_user_id` 同理）。

**AI 不需要知道語音角色名稱**，除非使用者在對話中明確要求特定語音。工具會自動依階層優先級套用設定。

### Decision 6：移除 Bot 層硬接線的策略 — 分階段

**階段 1**（本次實作）：
- Line Bot：移除 `linebot_router.py` 中語音訊息的 `skip_send=True` 和自動 TTS 邏輯
- Telegram Bot：移除 `handler.py` 中 `_handle_voice` 的自動 TTS 邏輯
- 語音訊息改走正常 AI 流程（與文字訊息相同路徑）

**階段 2**（驗證後）：
- 清理語音相關的 fallback 程式碼

**理由**：一次性移除所有硬接線風險較高，分階段可逐步驗證。

### Decision 7：前端語音 App — 桌面應用程式模式

**選擇**：在 `desktop.js` 中註冊語音設定 App，替代現有的「開發中」佔位。

**功能**：
- 語音角色下拉選單（依引擎分組）
- 試聽按鈕：呼叫後端 API 生成短句預覽語音，前端播放
- 儲存偏好到 `user_settings`

**試聽 API**：
```
POST /api/voice/preview
Body: { "text": "你好，這是語音預覽", "engine": "edge", "params": {"voice": "zh-TW-HsiaoChenNeural"} }
Response: audio/mpeg (MP3 bytes)
```

試聽 API 接受引擎名稱和該引擎的參數包，讓使用者在切換引擎後也能正確試聽。

**理由**：試聽不需要存檔到 NAS，直接 stream 回前端播放即可，避免產生大量暫存檔。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| AI 不呼叫 TTS 工具（忘記或判斷不需要） | Prompt 引導「語音訊息優先語音回覆」；初期可監控 ai_logs 確認行為 |
| `[VOICE_MESSAGE:{...}]` 標記被 Claude 誤解或複製到回覆中 | 標記格式與 `[FILE_MESSAGE:{...}]` 一致，Claude 已能正確處理同類標記 |
| TTS 工具執行增加回應延遲 | Edge TTS 生成通常 < 2 秒，可接受；長文截斷至 500 字已控制上限 |
| 移除自動 TTS 後使用者體驗改變 | Prompt 引導確保語音訊息仍會收到語音回覆；文字訊息則不會無故附帶語音 |
| 前端試聽 API 被濫用 | Rate limiting（同使用者 10 秒內限 1 次試聽） |

### Decision 8：語音設定 API — 引擎感知 + 動態 config schema

**選擇**：由後端 API 動態提供語音角色清單和引擎設定 schema，前端依此動態渲染 UI。

**API 端點**：

`GET /api/voice/voices?engine=edge` — 語音角色列表（可選 engine 參數，預設回傳目前啟用的引擎）
```json
{
  "engine": "edge",
  "voices": [
    { "id": "zh-TW-HsiaoChenNeural", "name": "曉臻（女聲）", "gender": "female", "language": "zh-TW" }
  ],
  "config_schema": {
    "voice": { "type": "select", "label": "語音角色", "required": true }
  },
  "available_engines": ["edge", "google_cloud", "gemini"]
}
```

**前端動態渲染邏輯**：
- `type: "select"` → 下拉選單（搭配 `voices` 列表填充選項）
- `type: "slider"` → 滑桿（使用 `min`, `max`, `default`, `step` 屬性）
- `type: "text"` → 文字輸入框（使用 `placeholder` 屬性）

前端不硬編碼任何引擎的 UI 元件，完全由 `config_schema` 驅動。新增引擎時只需實作後端介面，前端自動適配。

## Open Questions

1. 群組是否需要獨立的語音設定（例如群組 A 用男聲、群組 B 用女聲）？
   - **建議**：初期只做使用者級別設定，群組設定留待後續需求
