# Change: 修正 Line Bot 用戶顯示為「未知用戶」及好友狀態問題

## Why

目前 Line Bot 在群組中收到訊息時，如果發送者沒有加 Bot 為好友，系統無法取得用戶的 displayName，導致：

1. **訊息記錄中顯示「未知用戶」**：AI 處理歷史訊息時無法分辨不同的「未知用戶」是否為同一人
2. **用戶列表頁面無法辨識用戶**：管理員在用戶頁面中看到的所有非好友用戶都顯示「未知用戶」，完全無法分辨誰是誰
3. **MCP 工具摘要不清**：`summarize_chat` 產生的聊天摘要中無法識別發言者

根本原因：目前程式碼使用 `get_profile(user_id)` API，這只能取得**與 Bot 有好友關係**的用戶資料。對於群組中沒有加 Bot 為好友的成員，應改用 `get_group_member_profile(group_id, user_id)` API。

此外，用戶列表頁面的「好友」狀態也有問題：

4. **所有用戶都顯示「好友」**：`is_friend` 欄位預設為 `true`，且沒有程式碼維護此欄位
5. **連 Bot 自己（ChingTech AI）也顯示「好友」**：這明顯不合理

## What Changes

- **新增 `get_group_member_profile` 函數**：使用 Line API 取得群組成員的 profile
- **修改 `save_message` 函數**：在群組訊息場景中優先使用 `get_group_member_profile` 取得用戶資料
- **確保用戶資料持續更新**：每次收到群組訊息時更新用戶的 displayName（用戶可能會更改名稱）
- **正確維護 `is_friend` 欄位**：
  - 從群組訊息建立的用戶：`is_friend = false`
  - 從個人對話（FollowEvent）建立的用戶：`is_friend = true`
  - Bot 自己：`is_friend = false`（或不顯示此欄位）
- **更新規格說明**：明確記錄群組成員 profile 的取得方式及好友狀態判斷邏輯

## Impact

- 受影響的規格：`line-bot`
- 受影響的程式碼：
  - `backend/src/ching_tech_os/services/linebot.py`
    - 新增 `get_group_member_profile()` 函數
    - 修改 `save_message()` 函數，依據訊息來源使用不同的 profile API
    - 修改 `get_or_create_user()` 函數，正確設定 `is_friend` 欄位
    - 修改 `get_or_create_bot_user()` 函數，設定 Bot 的 `is_friend = false`

## Technical Notes

根據 [Line Messaging API 文件](https://developers.line.biz/en/docs/messaging-api/group-chats/)：

| API | 適用場景 | 限制 |
|-----|----------|------|
| `get_profile(user_id)` | 個人對話 | 只能取得與 Bot 有好友關係的用戶 |
| `get_group_member_profile(group_id, user_id)` | 群組對話 | 可取得群組內任何成員，不需好友關係 |

實作策略：
- 群組訊息：使用 `get_group_member_profile(group_id, user_id)`
- 個人對話：維持使用 `get_profile(user_id)`（這類用戶必定與 Bot 有好友關係）
