## ADDED Requirements

### Requirement: 使用者資訊 API
系統 SHALL 提供 API 讓登入後的使用者查看和更新個人資訊。

#### Scenario: 取得目前使用者資訊
- Given 使用者已登入
- When 呼叫 GET /api/user/me
- Then 系統回傳該使用者的資訊
- And 包含 username、display_name、created_at、last_login_at

#### Scenario: 更新顯示名稱
- Given 使用者已登入
- When 呼叫 PATCH /api/user/me 並提供新的 display_name
- Then 系統更新資料庫中的 display_name
- And 回傳更新後的使用者資訊

#### Scenario: 未登入時存取使用者資訊
- Given 使用者未登入或 token 無效
- When 呼叫使用者資訊 API
- Then 系統回傳 401 未授權錯誤
