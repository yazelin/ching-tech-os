## 1. TTS 引擎抽象層

- [x] 1.1 在 `extends/voice/voice_tts.py` 新增 `TTSEngine` ABC（含 `synthesize_audio(**params)`、`list_voices()`、`get_config_schema()`）和 `VoiceInfo` dataclass
- [x] 1.2 建立 `EdgeTTSEngine` 類別，將現有 Edge TTS 邏輯搬入 `synthesize_audio()`、`list_voices()` 和 `get_config_schema()`
- [x] 1.3 建立 `GoogleCloudTTSEngine` 和 `GeminiNativeEngine` 佔位類別（raise NotImplementedError），含各自的 `get_config_schema()` 定義
- [x] 1.4 實作 `_get_engine()` 工廠函式，依 `TTS_ENGINE` 環境變數選擇引擎
- [x] 1.5 重構 `synthesize()` 主函式：共用前處理（`_clean_for_tts()`）→ 引擎呼叫（傳入 `**tts_params`）→ 共用後處理（存檔、duration）
- [x] 1.6 確認現有 `tts_router.py` 和 `voice_startup.py` 不受影響

## 2. text_to_speech MCP 工具

- [x] 2.1 在 `services/mcp/` 新增 `voice_tools.py`，實作 `text_to_speech` 工具（透過 `voice_bridge` 呼叫）
- [x] 2.2 工具回傳包含 `[VOICE_MESSAGE:{"file_id":"...","duration_ms":...}]` 標記的成功訊息
- [x] 2.3 實作 `resolve_voice_settings(ctos_user_id, group_id, agent_id)` 階層式設定解析函式
- [x] 2.4 工具接收自動注入的 `ctos_user_id`、`group_id`、`agent_id`，呼叫 `resolve_voice_settings()` 取得最終設定
- [x] 2.5 透過 `extra_mcp_env` 注入 `CTOS_GROUP_ID` 和 `CTOS_AGENT_ID`（linebot_ai.py + identity_router.py）
- [x] 2.6 在 `services/mcp/__init__.py` 註冊 voice_tools（依 voice 模組啟用狀態條件載入）
- [x] 2.7 更新 `voice` skill 的 `SKILL.md`，在 `allowed-tools` 加入 `mcp__ching-tech-os__text_to_speech`

## 3. Bot 層回覆管線改造

- [x] 3.1 擴充 `services/bot/ai.py` 的 `parse_ai_response()`，新增 `[VOICE_MESSAGE:{...}]` 標記解析，回傳 `(text, files, voices)` 三元組
- [x] 3.2 擴充 `linebot_ai.py` 的 `send_ai_response()`，新增 `voice_messages` 參數，組裝 Line `AudioMessage`
- [x] 3.3 更新 `linebot_ai.py` 中呼叫 `parse_ai_response()` 和 `send_ai_response()` 的所有位置，傳入 voices
- [x] 3.4 擴充 Telegram `handler.py` 的回覆邏輯，偵測 voices 後呼叫 `adapter.send_voice()`

## 4. 移除 Bot 層自動 TTS 硬接線

- [x] 4.1 移除 `linebot_router.py` 中語音訊息的 `skip_send=True` 和自動 `voice_tts.synthesize()` 呼叫，讓語音訊息走正常 AI 流程
- [x] 4.2 移除 `telegram/handler.py` 中 `_handle_voice` 的自動 TTS 邏輯
- [ ] 4.3 驗證語音訊息進入後，AI 的工具呼叫（畫圖等）能正常執行

## 5. Agent Prompt 更新

- [x] 5.1 在 `services/linebot_agents.py` 和 `services/bot/agents.py` 的 prompt 中新增語音工具使用指引
- [x] 5.2 建立 Alembic migration 更新資料庫中的 prompt
- [x] 5.3 執行 migration 並驗證 prompt 內容正確

## 6. 語音設定 — 資料庫與 API

- [x] 6.1 建立 Alembic migration：`users` 表新增 `voice_settings` JSONB 欄位
- [x] 6.2 建立 Alembic migration：`bot_groups` 表新增 `voice_settings` JSONB 欄位
- [x] 6.3 建立 Alembic migration：`bot_agents` 表新增 `voice_settings` JSONB 欄位
- [x] 6.4 實作 `GET /api/voice/voices` — 回傳引擎語音角色列表 + `config_schema` + `available_engines`
- [x] 6.5 實作 `GET /api/voice/settings?scope=user|group|agent&scope_id=<id>` — 回傳指定層級設定 + 實際生效的繼承設定
- [x] 6.6 實作 `PUT /api/voice/settings` — 依 scope 儲存到對應層級（含權限檢查）
- [x] 6.7 實作 `DELETE /api/voice/settings` — 清除指定層級設定（回退到繼承）
- [x] 6.8 實作 `POST /api/voice/preview` — 接受 `engine`、`params`、`text`，生成試聽音訊直接 stream MP3
- [x] 6.9 實作試聽 API 的 rate limiting（10 秒/次/使用者）

## 7. 前端語音設定 App

- [x] 7.1 建立 `frontend/js/voice-app.js`，實作語音設定 App 模組（IIFE）
- [x] 7.2 設定範圍選擇器：支援「個人設定」/「群組設定」/「Agent 設定」切換（依使用者權限顯示）
- [x] 7.3 引擎選擇器：載入 `available_engines`，切換時重新渲染設定表單
- [x] 7.4 動態設定表單：依 `config_schema` 渲染不同控制項（select → 下拉選單、slider → 滑桿、text → 文字輸入）
- [x] 7.5 繼承指示：若當前層級未設定，顯示「繼承自 [上層名稱]」及實際生效設定
- [x] 7.6 試聽功能：以目前選擇的引擎和參數呼叫 `POST /api/voice/preview`，用 `Audio API` 播放
- [x] 7.7 儲存/清除功能：儲存設定或清除以回退到繼承
- [x] 7.8 在 `desktop.js` 中更新語音 App 註冊，替代「開發中」佔位
- [x] 7.9 建立 `frontend/css/voice-app.css` 樣式，使用 CSS 變數
- [x] 7.10 在 `index.html` 引入 CSS（login.html 不需要桌面 App CSS）

## 8. 測試與驗證

- [x] 8.1 更新 `backend/tests/` 中受影響的測試（parse_ai_response 返回值從 2 元組改為 3 元組）
- [ ] 8.2 測試：語音訊息 → STT → AI 處理 → AI 呼叫 TTS 工具 → 語音+文字回覆
- [ ] 8.3 測試：語音訊息要求畫圖 → AI 呼叫畫圖工具 + TTS 工具 → 圖片+語音+文字回覆
- [ ] 8.4 測試：文字訊息 → AI 不呼叫 TTS → 僅文字回覆
- [ ] 8.5 測試：階層式設定解析 — 私訊（使用者 > Agent > 系統）
- [ ] 8.6 測試：階層式設定解析 — 群組（群組 > Agent > 系統）
- [ ] 8.7 測試：清除設定後回退到繼承
- [ ] 8.8 測試：前端語音設定 App 的選擇、試聽、儲存、範圍切換流程
