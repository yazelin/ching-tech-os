## ADDED Requirements

### Requirement: 清除使用者密碼服務
系統 SHALL 提供 `clear_user_password()` 服務函數，將使用者的 `password_hash` 設為 NULL，使其認證方式恢復為 NAS SMB 認證。

#### Scenario: 清除密碼後登入走 NAS 認證
- **WHEN** 使用者的 `password_hash` 被清除為 NULL
- **AND** 使用者嘗試登入
- **THEN** 登入邏輯跳過密碼認證（因 `password_hash` 為 NULL）
- **AND** fallback 到 SMB 認證流程

#### Scenario: 清除密碼同時重設 must_change_password
- **WHEN** 呼叫 `clear_user_password(user_id)`
- **THEN** `password_hash` 設為 NULL
- **AND** `must_change_password` 設為 `False`
- **AND** `password_changed_at` 設為 NULL
