# public-share spec delta

## MODIFIED Requirements

### Requirement: Share Link with Password
系統 SHALL 支援建立帶密碼保護的分享連結。

#### Scenario: 建立帶密碼的分享連結
- **GIVEN** 用戶要分享資源
- **WHEN** 呼叫 `POST /api/share` 並提供 `password` 參數
- **THEN** 系統產生分享連結
- **AND** 將密碼 hash 後儲存
- **AND** 回應中包含原始密碼（僅此次回傳）

#### Scenario: 建立無密碼分享連結
- **GIVEN** 用戶要分享資源
- **WHEN** 呼叫 `POST /api/share` 不提供 `password` 參數
- **THEN** 系統產生分享連結（維持原有行為）
- **AND** 不需要密碼即可存取

### Requirement: Password Protected Access
系統 SHALL 對有密碼的分享連結進行密碼驗證。

#### Scenario: 正確密碼存取
- **GIVEN** 分享連結有設定密碼
- **WHEN** 呼叫 `GET /api/public/{token}?password=xxx` 且密碼正確
- **THEN** 系統回傳分享內容
- **AND** 重設錯誤嘗試次數

#### Scenario: 錯誤密碼存取
- **GIVEN** 分享連結有設定密碼
- **WHEN** 呼叫 `GET /api/public/{token}?password=wrong`
- **THEN** 系統回傳 401 錯誤
- **AND** 增加錯誤嘗試次數

#### Scenario: 未提供密碼
- **GIVEN** 分享連結有設定密碼
- **WHEN** 呼叫 `GET /api/public/{token}` 不提供 password
- **THEN** 系統回傳 401 錯誤並提示需要密碼

#### Scenario: 錯誤次數鎖定
- **GIVEN** 分享連結錯誤嘗試次數達到 5 次
- **WHEN** 再次嘗試存取
- **THEN** 系統回傳 423 Locked 錯誤

## ADDED Requirements

### Requirement: Content Resource Type
系統 SHALL 支援 `content` 資源類型，直接儲存內容而非引用其他資源。

#### Scenario: 建立內容分享
- **GIVEN** 用戶有一段文字內容要分享
- **WHEN** 呼叫 `POST /api/share` 並設定 resource_type='content'
- **AND** 提供 content, content_type, filename 參數
- **THEN** 系統將內容直接儲存在分享記錄中
- **AND** 回傳分享連結

#### Scenario: 存取內容分享
- **GIVEN** 存在 resource_type='content' 的分享連結
- **WHEN** 呼叫 `GET /api/public/{token}`
- **THEN** 系統回傳儲存的內容
- **AND** 包含 content_type 和 filename

### Requirement: CORS Support
系統 SHALL 對公開分享 API 支援 CORS 跨域存取。

#### Scenario: 跨域存取
- **GIVEN** MD2PPT 網站要存取分享內容
- **WHEN** 從 https://md-2-ppt-evolution.vercel.app 發送請求
- **THEN** 回應包含正確的 CORS headers
- **AND** 允許該來源存取
