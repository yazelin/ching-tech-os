## 1. 資料庫與設定基礎

- [x] 1.1 建立 Alembic migration：新增 `bot_usage_tracking` 資料表（含 UNIQUE 索引和 FK）
- [x] 1.2 在 `config.py` 新增環境變數設定項：`BOT_UNBOUND_USER_POLICY`、`BOT_RESTRICTED_MODEL`、`BOT_DEBUG_MODEL`、`BOT_RATE_LIMIT_ENABLED`、`BOT_RATE_LIMIT_HOURLY`、`BOT_RATE_LIMIT_DAILY`

## 2. 斜線指令路由框架

- [x] 2.1 建立 `services/bot/commands.py`：`SlashCommand` dataclass、`CommandRouter` 類別（parse + dispatch + 權限檢查）
- [x] 2.2 將現有 `/reset` 系列指令遷移到 `CommandRouter`（保留 `trigger.py` 的 `is_reset_command()` 作為 fallback）
- [x] 2.3 在 `linebot_ai.py` 的 `handle_text_message()` 中插入指令攔截邏輯：在 `process_message_with_ai()` 之前呼叫 `CommandRouter.parse()` + `dispatch()`
- [x] 2.4 在 `bot_telegram/handler.py` 中接入相同的 `CommandRouter`（取代現有硬編碼的 `/start`、`/help`、`/reset` 判斷）
- [x] 2.5 撰寫指令路由框架的單元測試：指令解析、別名匹配、權限檢查（未綁定、非管理員、群組限制）

## 3. 身份分流路由器

- [x] 3.1 建立 `services/bot/identity_router.py`：`route_unbound()` 函式，根據 `BOT_UNBOUND_USER_POLICY` 決定 reject 或 restricted 路徑
- [x] 3.2 在 `linebot_ai.py` 的 `process_message_with_ai()` 中，查詢用戶綁定狀態後、Agent 選擇前，插入身份分流呼叫
- [x] 3.3 實作受限模式 AI 流程：選擇 `bot-restricted` Agent、組裝簡化 system prompt、對話歷史（limit=10）、call_claude、純文字回覆
- [x] 3.4 確保綁定驗證碼（6 位數字）在分流之前優先處理，不受策略影響
- [x] 3.5 撰寫身份分流的單元測試：reject 策略回覆綁定提示、restricted 策略走受限模式、已綁定用戶不受影響、群組未綁定用戶靜默忽略

## 4. Agent 預設初始化

- [ ] 4.1 在 `linebot_agents.py` 中新增 `bot-restricted` Agent 的預設 prompt 和 tools 定義
- [ ] 4.2 在 `linebot_agents.py` 中新增 `bot-debug` Agent 的預設 prompt 定義（含 debug-skill scripts 說明、輸出格式規範）
- [ ] 4.3 在 `ensure_default_agents()` 中新增 `bot-restricted` 和 `bot-debug` 的初始化邏輯（存在則不覆蓋）
- [ ] 4.4 建立 Alembic migration：在 DB 中插入 `bot-restricted` 和 `bot-debug` Agent 預設資料

## 5. Rate Limiter

- [ ] 5.1 建立 `services/bot/rate_limiter.py`：`check_rate_limit()` 查詢使用量、`record_usage()` UPSERT 計數
- [ ] 5.2 在受限模式 AI 流程入口（`identity_router.py` 的 restricted 路徑）插入 rate limit 檢查
- [ ] 5.3 撰寫 rate limiter 的單元測試：未超限通過、超過每小時限額拒絕、超過每日限額拒絕、已綁定用戶不檢查、停用 rate limit 時仍記錄使用量

## 6. debug-skill 診斷腳本

- [ ] 6.1 建立 `skills/debug-skill/` 目錄結構和 `skill.yaml` 定義檔
- [ ] 6.2 實作 `check-server-logs` 腳本：`journalctl -u ching-tech-os`，支援 `lines` 和 `keyword` 參數
- [ ] 6.3 實作 `check-ai-logs` 腳本：查詢 `ai_logs` 資料表，支援 `limit` 和 `errors_only` 參數
- [ ] 6.4 實作 `check-nginx-logs` 腳本：`docker logs ching-tech-os-nginx`，支援 `lines` 和 `type`（access/error）參數
- [ ] 6.5 實作 `check-db-status` 腳本：查詢連線數、主要資料表行數、資料庫大小
- [ ] 6.6 實作 `check-system-health` 腳本：綜合執行所有診斷項目，回傳摘要報告（健康狀態標記）

## 7. /debug 指令

- [ ] 7.1 在 `CommandRouter` 中註冊 `/debug` 指令：`require_bound=true`、`require_admin=true`、`private_only=true`
- [ ] 7.2 實作 `/debug` handler：取得 `bot-debug` Agent、使用 `BOT_DEBUG_MODEL`、呼叫 `call_claude(tools=["run_skill_script"])`、回覆診斷結果
- [ ] 7.3 測試 `/debug` 指令：管理員可執行、非管理員被拒絕、群組中靜默忽略、無問題描述時使用預設 prompt

## 8. 知識庫公開存取

- [ ] 8.1 在知識庫 `index.json` 和 Front Matter schema 中新增 `is_public` 布林欄位（預設 `false`）
- [ ] 8.2 修改 `services/knowledge.py` 的 `search_knowledge()`：新增 `public_only` 參數，為 `true` 時僅回傳 `scope=global` 且 `is_public=true` 的項目
- [ ] 8.3 修改 `services/mcp/knowledge_tools.py` 的 `search_knowledge` MCP 工具：當 `ctos_user_id` 為 NULL 時自動設定 `public_only=true`
- [ ] 8.4 在知識庫 API 和前端介面中支援設定 `is_public` 欄位（知識項目編輯表單新增「公開」勾選框）
- [ ] 8.5 圖書館資料夾公開標記：在 `list_library_folders` 中根據呼叫者身份過濾非公開資料夾

## 9. 整合測試與驗證

- [ ] 9.1 端對端測試：`BOT_UNBOUND_USER_POLICY=reject` 時行為與現有系統一致（回歸測試）
- [ ] 9.2 端對端測試：`BOT_UNBOUND_USER_POLICY=restricted` 時未綁定用戶可使用受限模式對話
- [ ] 9.3 端對端測試：受限模式的 `search_knowledge` 只回傳公開知識
- [ ] 9.4 端對端測試：`/debug` 管理員可執行診斷、非管理員被拒絕
- [ ] 9.5 端對端測試：rate limiter 超過限額時回覆使用上限提示
