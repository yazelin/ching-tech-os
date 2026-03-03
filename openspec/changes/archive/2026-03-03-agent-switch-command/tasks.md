## 1. 資料庫 Migration

- [x] 1.1 建立 Alembic migration：`bot_users` 新增 `active_agent_id UUID` nullable 欄位，FK 指向 `ai_agents.id`（`ON DELETE SET NULL`）
- [x] 1.2 同一 migration：`bot_groups` 新增 `active_agent_id UUID` nullable 欄位，FK 指向 `ai_agents.id`（`ON DELETE SET NULL`）

## 2. AI Manager 擴充

- [x] 2.1 在 `ai_manager.py` 新增 `get_selectable_agents()` 方法，查詢 `is_active = true` 且 `settings->>'user_selectable' = 'true'` 的 Agent，按 name 排序回傳
- [x] 2.2 在 `ai_manager.py` 新增 `get_agent_by_id(agent_id)` 方法（若不存在），供路由覆蓋時用 UUID 查詢 Agent（已存在 `get_agent(agent_id)` 可直接使用）

## 3. Agent 偏好持久化

- [x] 3.1 新增函式 `set_user_active_agent(bot_user_id, agent_id)` 更新 `bot_users.active_agent_id`
- [x] 3.2 新增函式 `set_group_active_agent(bot_group_id, agent_id)` 更新 `bot_groups.active_agent_id`
- [x] 3.3 新增函式 `get_user_active_agent_id(bot_user_id)` 查詢用戶的 `active_agent_id`
- [x] 3.4 新增函式 `get_group_active_agent_id(bot_group_id)` 查詢群組的 `active_agent_id`

## 4. Agent 路由覆蓋

- [x] 4.1 修改 `linebot_agents.py` 的 `get_linebot_agent()` 簽名，增加 `bot_user_id=None` 和 `bot_group_id=None` 參數
- [x] 4.2 實作路由覆蓋邏輯：群組有 `active_agent_id` 時優先使用，個人對話同理，NULL 時 fallback 到預設
- [x] 4.3 修改 `linebot_ai.py` 的 `process_message_with_ai()` 呼叫處，傳入 `bot_user_id` 和 `bot_group_id`
- [x] 4.4 修改 `bot_telegram/handler.py` 的 `_handle_text_with_ai()` 呼叫處，傳入 `bot_user_id` 和 `bot_group_id`

## 5. /agent 指令實作

- [x] 5.1 在 `command_handlers.py` 新增 `_handle_agent(ctx)` handler
- [x] 5.2 實作無參數邏輯：查詢目前使用的 Agent，列出帶序號的可切換清單
- [x] 5.3 實作名稱切換邏輯：驗證 Agent 存在且 `user_selectable`，呼叫偏好持久化函式
- [x] 5.4 實作編號切換邏輯：解析數字參數，對應到排序後清單的序號
- [x] 5.5 實作 `/agent reset` 邏輯：清除 `active_agent_id` 為 NULL
- [x] 5.6 在 `register_builtin_commands()` 中註冊 `/agent` 指令（`require_bound=True, require_admin=True, private_only=False`）

## 6. 測試

- [x] 6.1 撰寫 `/agent` handler 單元測試：無參數列表、名稱切換、編號切換、reset、權限檢查、無效輸入
- [x] 6.2 撰寫 `get_linebot_agent()` 路由覆蓋測試：有偏好時使用偏好 Agent、無偏好時使用預設
- [x] 6.3 執行 `uv run pytest` 確認所有測試通過（766 passed）

## 7. 文件更新

- [x] 7.1 更新 `docs/linebot.md` 新增 `/agent` 指令說明
- [x] 7.2 更新 `docs/telegram-bot.md` 新增 `/agent` 指令交叉引用
