## 1. 測試保護（重構前必須完成）
- [ ] 1.1 建立 pytest 測試環境（conftest.py、mock database、mock Line SDK）
- [ ] 1.2 測試 AI 回應解析（parse_ai_response、FILE_MESSAGE 提取）
- [ ] 1.3 測試 system prompt 建構（build_system_prompt、記憶整合）
- [ ] 1.4 測試存取控制邏輯（check_line_access、綁定檢查）
- [ ] 1.5 測試訊息發送邏輯（reply_messages、push_messages、fallback）
- [ ] 1.6 測試 Agent 初始化邏輯（ensure_default_agents）
- [ ] 1.7 測試對話歷史組合（get_conversation_context）
- [ ] 1.8 測試圖片生成自動處理（auto_prepare_generated_images）

## 2. 核心抽象層建立
- [ ] 2.1 建立 `services/bot/__init__.py`
- [ ] 2.2 建立 `services/bot/adapter.py` — BotAdapter Protocol + 可選 Protocol（EditableMessageAdapter, ProgressNotifier）
- [ ] 2.3 建立 `services/bot/message.py` — BotMessage, BotContext, SentMessage dataclass
- [ ] 2.4 建立 `services/bot/media.py` — 平台無關的媒體處理（暫存管理、NAS 存取）

## 3. AI 處理核心抽離
- [ ] 3.1 將 `parse_ai_response()` 搬到 `services/bot/ai.py`
- [ ] 3.2 將 `build_system_prompt()` 搬到 `services/bot/ai.py`
- [ ] 3.3 將 `get_conversation_context()` 搬到 `services/bot/ai.py`
- [ ] 3.4 將 `process_message_with_ai()` 核心邏輯搬到 `services/bot/ai.py`，發送邏輯留在平台 handler
- [ ] 3.5 將 `auto_prepare_generated_images()` 搬到 `services/bot/ai.py`
- [ ] 3.6 將 nanobanana 錯誤處理函式搬到 `services/bot/ai.py`
- [ ] 3.7 確認所有測試通過

## 4. Agent 管理遷移
- [ ] 4.1 將 `linebot_agents.py` 核心邏輯搬到 `services/bot/agents.py`
- [ ] 4.2 更新 Agent name 從 `linebot-personal`/`linebot-group` 為更通用的命名（保留向後相容映射）
- [ ] 4.3 確認所有測試通過

## 5. Line 平台 Adapter 建立
- [ ] 5.1 建立 `services/bot_line/__init__.py`
- [ ] 5.2 建立 `services/bot_line/adapter.py` — LineBotAdapter 實作 BotAdapter Protocol
- [ ] 5.3 建立 `services/bot_line/webhook.py` — webhook 驗證、事件解析
- [ ] 5.4 建立 `services/bot_line/handler.py` — Line 事件處理（join/leave/follow/unfollow）
- [ ] 5.5 建立 `services/bot_line/service.py` — Line 專屬邏輯（綁定、群組管理、NAS 路徑等）
- [ ] 5.6 更新 `linebot_ai.py` 的發送邏輯改用 LineBotAdapter
- [ ] 5.7 確認所有測試通過

## 6. 資料庫 Migration
- [ ] 6.1 建立 Alembic migration：`line_groups` → `bot_groups`（加 `platform_type` 欄位，預設 'line'）
- [ ] 6.2 建立 Alembic migration：`line_users` → `bot_users`
- [ ] 6.3 建立 Alembic migration：`line_messages` → `bot_messages`
- [ ] 6.4 建立 Alembic migration：`line_files` → `bot_files`
- [ ] 6.5 建立 Alembic migration：`line_binding_codes` → `bot_binding_codes`
- [ ] 6.6 建立 Alembic migration：`line_group_memories` → `bot_group_memories`、`line_user_memories` → `bot_user_memories`
- [ ] 6.7 更新所有 SQL 查詢中的表名引用（143 處）
- [ ] 6.8 更新 `models/linebot.py` → `models/bot.py`
- [ ] 6.9 確認所有測試通過

## 7. API Router 重構
- [ ] 7.1 建立 `api/bot_router.py`（從 `linebot_router.py` 遷移）
- [ ] 7.2 更新 `main.py` 路由註冊
- [ ] 7.3 保留 `/api/linebot/` 向後相容 redirect（或直接修改前端）
- [ ] 7.4 更新前端 `linebot.js` 的 API 路徑
- [ ] 7.5 確認所有測試通過

## 8. 清理與驗證
- [ ] 8.1 移除舊檔案（linebot.py、linebot_ai.py、linebot_agents.py、linebot_router.py）
- [ ] 8.2 更新 `mcp_server.py` 中的表名引用
- [ ] 8.3 更新 `config.py` 中的相關設定
- [ ] 8.4 完整回歸測試
- [ ] 8.5 更新 openspec line-bot spec 為 bot-platform spec
- [ ] 8.6 更新 CLAUDE.md 中的 linebot 相關說明
