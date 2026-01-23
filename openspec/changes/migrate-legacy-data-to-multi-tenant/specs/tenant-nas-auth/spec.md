# Spec: tenant-nas-auth

租戶 NAS SMB 登入驗證功能規格。

## ADDED Requirements

### Requirement: 租戶可設定啟用 NAS 登入驗證

系統 **MUST** 允許租戶管理員或平台管理員在租戶設定中啟用 NAS SMB 登入驗證。
啟用後，使用者可以用 NAS 帳號密碼登入此租戶。

#### Scenario: 平台管理員啟用租戶的 NAS 登入

```
Given 平台管理員已登入
And 存在租戶 "chingtech"
When 管理員開啟租戶設定頁面
And 勾選「允許使用 NAS 帳號登入」
And 填入 NAS 主機位址 "192.168.11.50"
And 填入驗證共享名稱 "擎添開發"
And 點擊儲存
Then 租戶設定儲存成功
And enable_nas_auth 設為 true
And nas_auth_host 設為 "192.168.11.50"
And nas_auth_share 設為 "擎添開發"
```

#### Scenario: 使用預設 NAS 設定

```
Given 平台管理員已登入
And 存在租戶 "demo"
When 管理員開啟租戶設定頁面
And 勾選「允許使用 NAS 帳號登入」
And 不填入自訂 NAS 設定
And 點擊儲存
Then 租戶設定儲存成功
And enable_nas_auth 設為 true
And nas_auth_host 保持為 null（使用系統預設）
```

### Requirement: 使用 NAS 帳號登入啟用 NAS 驗證的租戶

系統 **MUST** 允許使用者用 NAS 帳號密碼登入已啟用 NAS 驗證的租戶。
若使用者尚未在系統中建立記錄，首次登入時 **SHALL** 自動建立。

#### Scenario: 首次使用 NAS 帳號登入

```
Given 租戶 "chingtech" 已啟用 NAS 登入驗證
And NAS 上存在帳號 "newuser" 密碼 "password123"
And 系統中不存在使用者 "newuser"
When 使用者輸入帳號 "newuser" 密碼 "password123"
And 選擇租戶 "chingtech"
And 點擊登入
Then SMB 驗證成功
And 系統自動建立使用者 "newuser" 屬於 "chingtech" 租戶
And 使用者成功登入
And 取得有效的 session token
```

#### Scenario: 既有使用者使用 NAS 帳號登入

```
Given 租戶 "chingtech" 已啟用 NAS 登入驗證
And 系統中存在使用者 "yazelin" 屬於 "chingtech" 租戶
And 該使用者尚未設定密碼
When 使用者輸入帳號 "yazelin" 密碼 "nas_password"
And 選擇租戶 "chingtech"
And 點擊登入
Then SMB 驗證成功
And 使用者成功登入
And 更新 last_login_at 時間
```

#### Scenario: NAS 驗證失敗

```
Given 租戶 "chingtech" 已啟用 NAS 登入驗證
When 使用者輸入帳號 "wronguser" 密碼 "wrongpass"
And 選擇租戶 "chingtech"
And 點擊登入
Then SMB 驗證失敗
And 回傳錯誤訊息「帳號或密碼錯誤」
And 記錄登入失敗事件
```

### Requirement: 已設定密碼的使用者優先使用密碼驗證

系統 **MUST** 優先使用密碼驗證（若使用者已設定密碼），
即使租戶啟用 NAS 驗證，也不會嘗試 SMB 驗證。

#### Scenario: 已設定密碼的使用者登入

```
Given 租戶 "chingtech" 已啟用 NAS 登入驗證
And 使用者 "admin" 已設定密碼 "secure123"
When 使用者輸入帳號 "admin" 密碼 "secure123"
And 選擇租戶 "chingtech"
And 點擊登入
Then 使用密碼驗證（不嘗試 SMB）
And 密碼驗證成功
And 使用者成功登入
```

### Requirement: 未啟用 NAS 驗證的租戶無法用 NAS 帳號登入

系統 **MUST** 拒絕未啟用 NAS 驗證租戶的 NAS 帳號登入請求。
若使用者不存在且無法用其他方式驗證，登入 **SHALL** 失敗。

#### Scenario: 租戶未啟用 NAS 驗證

```
Given 租戶 "demo" 未啟用 NAS 登入驗證
And 使用者 "newuser" 不存在於系統中
When 使用者輸入帳號 "newuser" 密碼 "password"
And 選擇租戶 "demo"
And 點擊登入
Then 查詢使用者不存在
And 租戶未啟用 NAS 驗證
And 回傳錯誤訊息「帳號不存在」
```

### Requirement: 測試 NAS 連線功能

系統 **MUST** 提供測試 NAS 連線功能，
讓管理員可以在儲存設定前驗證連線是否正常。

#### Scenario: 測試 NAS 連線成功

```
Given 平台管理員已登入
And 正在編輯租戶 "chingtech" 的設定
And 已填入 NAS 主機 "192.168.11.50" 共享 "擎添開發"
When 點擊「測試連線」按鈕
Then 使用系統服務帳號嘗試連線
And 連線成功
And 顯示「連線成功」訊息
```

#### Scenario: 測試 NAS 連線失敗

```
Given 平台管理員已登入
And 正在編輯租戶 "test" 的設定
And 已填入 NAS 主機 "192.168.11.99" 共享 "不存在"
When 點擊「測試連線」按鈕
Then 連線失敗
And 顯示錯誤訊息「無法連線至指定的 NAS 主機」
```

## Cross References

- backend-auth: 認證服務
- user-settings: 使用者設定（租戶管理）
