## Context

目前 Bot 的 Agent 選擇邏輯是硬編碼的：`get_linebot_agent(is_group)` 根據 `is_group` 回傳 `linebot-group` 或 `linebot-personal`。沒有機制讓用戶在對話中切換 Agent。

系統中有 4 個預設 Agent（`linebot-personal`、`linebot-group`、`bot-restricted`、`bot-debug`），未來會為客戶建立更多 Agent（如杰膚美衛教助理）。需要一個方式讓管理員在聊天中快速切換和測試不同 Agent。

現有的指令框架（`CommandRouter` + `SlashCommand`）已經成熟，新增指令的模式明確。

## Goals / Non-Goals

**Goals:**
- 已綁定的管理員可以在個人或群組對話中用 `/agent` 切換當前使用的 Agent
- 切換後的偏好持久化，直到手動 reset 或切換為止
- 只有標記為 `user_selectable` 的 Agent 會出現在可切換清單
- 群組切換影響該群組所有對話，個人切換只影響自己
- Line 和 Telegram 平台行為一致

**Non-Goals:**
- 非管理員用戶切換 Agent（安全考量，僅管理員可用）
- 在 Web UI 中切換 Agent（此功能僅限 Bot 指令介面）
- 自動切換 Agent（例如根據訊息內容自動選擇）
- 未綁定用戶的 Agent 切換（受限模式不受影響）

## Decisions

### D1: Agent 偏好的儲存位置

**選擇**：在 `bot_users` 和 `bot_groups` 表各新增 `active_agent_id UUID` nullable FK 欄位。

**替代方案**：
- `bot_users.settings` JSONB 欄位：需新增欄位且查詢不如 FK 直覺
- 新建 `bot_agent_preferences` 表：過度工程，關聯太多查詢複雜

**理由**：
- 直接的 FK 關聯，查詢簡單且有外鍵保護
- `NULL` 表示使用預設（`linebot-personal` / `linebot-group`），不需要額外邏輯判斷
- 一個欄位解決，migration 簡單

### D2: 群組 vs 個人的切換語義

**選擇**：
- **個人對話**：偏好存在 `bot_users.active_agent_id`，僅影響該用戶的個人對話
- **群組對話**：偏好存在 `bot_groups.active_agent_id`，僅影響該特定群組

每個群組各自獨立：在 A 群組執行 `/agent jfmskin` 只有 A 群組改用杰膚美 Agent，B 群組和個人對話完全不受影響。

**理由**：
- 群組場景是主要使用案例（讓客戶在擎添的某個群組中體驗特定 Agent）
- 群組級別切換最直覺——「這個群組現在用杰膚美的 Agent」
- 不同群組可以同時測試不同 Agent，互不干擾

### D3: 可選 Agent 的標記方式

**選擇**：在 `ai_agents.settings` JSONB 中新增 `user_selectable: true` 旗標。

**替代方案**：
- 新增 `user_selectable boolean` 欄位：需要 migration 加欄位
- 用 naming convention 過濾：不夠彈性

**理由**：
- `settings` JSONB 已經用於存放 Agent 級別的配置（如 `bot-restricted` 的訊息模板）
- 不需要 schema 變更，只需在 migration 中 `UPDATE settings`
- 預設所有 Agent 都不可選（`user_selectable` 不存在或 `false`），需手動開啟

### D4: 指令權限設定

**選擇**：`require_bound=True, require_admin=True, private_only=False`

**理由**：
- 需要管理員身份：防止一般用戶亂切換群組的 Agent
- 不限個人對話：群組切換是核心場景
- 已綁定帳號是必要前提：需要 `bot_user_id` 來存偏好

### D5: Agent 路由的覆蓋邏輯

**選擇**：修改 `get_linebot_agent()` 簽名，增加可選的 `bot_user_id` 和 `bot_group_id` 參數。

```
get_linebot_agent(is_group, bot_user_id=None, bot_group_id=None)
```

路由優先級：
1. 群組對話：`bot_groups.active_agent_id` > 預設 `linebot-group`
2. 個人對話：`bot_users.active_agent_id` > 預設 `linebot-personal`

**理由**：
- 向後相容，原有呼叫不受影響
- 查詢邏輯集中在一個函式中

### D6: `/agent reset` 行為

**選擇**：將 `active_agent_id` 設回 `NULL`，恢復預設 Agent。

在群組中執行 `/agent reset` 清除群組偏好，在個人對話中清除個人偏好。

## Risks / Trade-offs

- **[工具權限擴散]** 切換到其他 Agent 時，工具組會隨 Agent 的 `tools` 欄位改變。管理員可能不小心啟用不適當的工具。→ 緩解：僅限管理員操作，且 `user_selectable` 需手動開啟。

- **[Agent 刪除後的懸空引用]** 如果被選中的 Agent 被刪除，FK 會阻擋刪除操作。→ 緩解：使用 `ON DELETE SET NULL`，Agent 刪除時自動恢復預設。

- **[受限模式不受影響]** 未綁定用戶始終走 `identity_router` 的受限模式路徑，不經過 `get_linebot_agent()`，因此 `/agent` 切換不影響未綁定用戶。這是預期行為。

- **[Prompt 長度差異]** 不同 Agent 的 prompt 長度差異很大（personal 約 8000 字，restricted 約 500 字），切換後 token 消耗可能大幅變化。→ 緩解：這是管理員的測試行為，token 消耗可接受。
