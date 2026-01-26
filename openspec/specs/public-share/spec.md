# public-share Specification

## Purpose
TBD - created by archiving change add-linebot-md-converter-agents. Update Purpose after archive.
## Requirements
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

