# Tasks: Configurable Restricted Mode

- [x] 1. 在 `identity_router.py` 新增 `_get_restricted_setting(agent, key, default)` helper 函式，從 agent settings JSONB 讀取文字模板，未設定時 fallback 到 default
- [x] 2. 修改 `rate_limiter.py` 的 `check_and_increment()` 新增 `custom_messages: dict[str, str] | None` 參數，支援自訂超限訊息模板（含 `{hourly_limit}` / `{daily_limit}` 變數替換）
- [x] 3. 修改 `identity_router.py` 的 `handle_restricted_mode()`：從 agent settings 讀取 `rate_limit_hourly_msg` / `rate_limit_daily_msg` 並傳入 rate_limiter；AI 回覆成功後若 `settings.disclaimer` 有值則附加到結尾；AI 失敗時使用 `settings.error_message`
- [x] 4. 修改 `identity_router.py` 的 `route_unbound()`：reject 模式時從 agent settings 讀取 `binding_prompt`（fallback 到平台特定的預設值）
- [x] 5. 修改 `command_handlers.py` 的 `get_welcome_message()` 改為 async `get_welcome_message()`，從 `bot-restricted` Agent settings 讀取 `welcome_message`（fallback 到現有預設值）；同步修改 `_handle_start()` 和 `linebot_router.py` 的 FollowEvent 處理
- [x] 6. 修改 `linebot_agents.py` 的 `DEFAULT_BOT_MODE_AGENTS` 中 `bot-restricted` 的定義，加入 `settings` 預設值（包含所有 6 個 key 的預設文字，與現有硬編碼一致）
- [x] 7. 新增 Alembic migration：更新現有 `bot-restricted` Agent 的 `settings` 欄位，用 JSONB merge 方式（不覆蓋已有的 key）寫入預設值
- [x] 8. 新增/更新測試：settings 有值時使用自訂文字、settings 為空時 fallback 到預設值、disclaimer 附加邏輯、rate limit 自訂訊息的變數替換
