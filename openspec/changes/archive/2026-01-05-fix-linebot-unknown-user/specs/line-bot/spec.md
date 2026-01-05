## MODIFIED Requirements

### Requirement: Line 使用者管理 API
Line Bot SHALL 記錄並管理 Line 使用者資訊，包含綁定狀態與好友狀態。

#### Scenario: 自動建立使用者
- **WHEN** 收到訊息且發送者為新使用者
- **THEN** 系統建立 line_users 記錄
- **AND** `user_id` 初始為 NULL（未綁定）
- **AND** 取得使用者 displayName 與頭像
- **AND** 根據訊息來源設定 `is_friend` 欄位

#### Scenario: 群組訊息取得用戶資料
- **WHEN** 收到群組訊息
- **THEN** 系統使用 `get_group_member_profile(group_id, user_id)` API 取得用戶資料
- **AND** 更新用戶的 displayName 與頭像
- **AND** 新用戶的 `is_friend` 設為 `false`

#### Scenario: 個人對話取得用戶資料
- **WHEN** 收到個人對話訊息
- **THEN** 系統使用 `get_profile(user_id)` API 取得用戶資料
- **AND** 更新用戶的 displayName 與頭像
- **AND** 新用戶的 `is_friend` 設為 `true`

#### Scenario: Bot 用戶記錄
- **WHEN** 系統建立 Bot 用戶記錄（ChingTech AI）
- **THEN** `is_friend` 設為 `false`

#### Scenario: 取得使用者列表
- **WHEN** 使用者請求 `GET /api/linebot/users`
- **THEN** 系統回傳所有 Line 使用者列表
- **AND** 包含每個用戶的綁定狀態（user_id, 綁定的 CTOS 用戶名稱）
- **AND** 包含每個用戶的好友狀態（is_friend）

#### Scenario: 取得使用者對話歷史
- **WHEN** 使用者請求 `GET /api/linebot/users/{id}/messages`
- **THEN** 系統回傳該使用者的個人對話歷史
- **AND** 支援分頁與日期範圍過濾
