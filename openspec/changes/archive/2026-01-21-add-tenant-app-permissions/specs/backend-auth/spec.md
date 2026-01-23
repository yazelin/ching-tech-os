# backend-auth Delta

## ADDED Requirements

### Requirement: 使用者 App 權限控制
系統 SHALL 支援為每個使用者設定獨立的 App 權限，權限限制適用於 Web UI、後端 API 和 Line Bot AI。

#### Scenario: 平台管理員設定租戶管理員權限
- Given 平台管理員已登入
- When 修改某租戶管理員的 permissions.apps 設定
- Then 系統儲存該設定到 users 表
- And 該租戶管理員的可用功能立即受限

#### Scenario: 租戶管理員只能看到有權限的 App
- Given 租戶管理員已登入
- And 其 permissions.apps 中 "inventory" 為 false
- When 租戶管理員查看桌面
- Then 不顯示「庫存管理」App
- And 直接存取該 App URL 時顯示無權限錯誤

#### Scenario: 租戶管理員無法修改自己的權限
- Given 租戶管理員已登入
- When 嘗試修改自己的 permissions.apps
- Then 系統回傳 403 權限錯誤
- And 顯示「無法修改自己的權限」訊息

#### Scenario: 租戶管理員只能修改一般使用者權限
- Given 租戶管理員已登入
- When 嘗試修改另一個租戶管理員的權限
- Then 系統回傳 403 權限錯誤

#### Scenario: 新建租戶管理員自動初始化權限
- Given 平台管理員建立新的租戶管理員
- When 使用者建立成功
- Then 系統自動設定預設的 App 權限
- And 預設開啟大部分功能（除了 platform-admin、terminal、code-editor）

---

### Requirement: 後端 API App 權限檢查
系統 SHALL 在後端 API 層檢查使用者是否有對應的 App 權限，無權限時回傳 403 錯誤。

#### Scenario: 無專案管理權限時存取專案 API
- Given 使用者已登入
- And 其 permissions.apps 中 "project-management" 為 false
- When 呼叫 GET /api/project/list
- Then 系統回傳 403 權限錯誤
- And 回傳訊息說明需要「專案管理」權限

#### Scenario: 有權限時正常存取 API
- Given 使用者已登入
- And 其 permissions.apps 中 "project-management" 為 true
- When 呼叫 GET /api/project/list
- Then API 正常回應專案列表

#### Scenario: 平台管理員不受 API 權限限制
- Given 平台管理員已登入
- When 呼叫任何 API
- Then API 正常回應
- Note 平台管理員擁有所有權限

---

### Requirement: Line Bot AI App 權限控制
系統 SHALL 根據使用者的 App 權限，動態調整 Line Bot AI 可用的工具和 Prompt。

#### Scenario: 無專案管理權限的使用者使用 Line Bot
- Given 使用者透過 Line 與 Bot 對話
- And 其 permissions.apps 中 "project-management" 為 false
- When 使用者詢問專案相關問題
- Then AI 回應說明使用者沒有專案管理權限
- And AI 不會嘗試呼叫專案相關工具

#### Scenario: AI 只看到有權限的工具
- Given 使用者透過 Line 與 Bot 對話
- And 其 permissions.apps 只有 "knowledge-base" 為 true
- When AI 處理使用者訊息
- Then AI 的可用工具列表只包含知識庫相關工具
- And Prompt 只說明知識庫功能

#### Scenario: 執行時權限檢查（雙重保險）
- Given 使用者透過 Line 與 Bot 對話
- And 其 permissions.apps 中 "inventory" 為 false
- When AI 嘗試呼叫庫存相關工具（繞過前置過濾）
- Then 系統在執行工具時檢查權限
- And 回傳「您沒有庫存管理權限」訊息

#### Scenario: 群組對話中的權限檢查
- Given 使用者在群組中與 Bot 對話
- And 該使用者的 permissions.apps 有限制
- When AI 處理該使用者的訊息
- Then 權限檢查基於發訊息的使用者
- And 不是基於群組設定
