# Line Bot Specification - Multi-Tenant Changes

## MODIFIED Requirements

### Requirement: Line Group Management
系統 SHALL 管理 Line 群組與租戶的關聯：
- line_group_id: Line 群組 ID
- **tenant_id: 租戶識別（必填）**
- project_id: 關聯專案（可選）
- name: 群組名稱
- created_at: 建立時間

#### Scenario: 群組首次互動
- **WHEN** Line 群組首次與 Bot 互動
- **THEN** 系統要求綁定租戶代碼
- **AND** 綁定成功後記錄 tenant_id

#### Scenario: 已綁定群組訊息
- **WHEN** 已綁定租戶的群組發送訊息
- **THEN** 訊息歸屬於該租戶
- **AND** AI 回應使用該租戶的知識庫

### Requirement: Line User Binding
系統 SHALL 管理 Line 用戶與系統用戶的綁定：
- line_user_id: Line 用戶 ID
- **tenant_id: 租戶識別（必填）**
- user_id: 系統用戶 ID（可選）
- display_name: Line 顯示名稱

#### Scenario: 用戶綁定帳號
- **WHEN** Line 用戶綁定 CTOS 帳號
- **THEN** 記錄 tenant_id 和 user_id
- **AND** 後續訊息可識別用戶身份

#### Scenario: 用戶跨租戶
- **WHEN** 同一 Line 用戶在不同租戶的群組
- **THEN** 系統為每個租戶建立獨立的 line_users 記錄
- **AND** 分別綁定不同的 CTOS 帳號

### Requirement: Line Message Storage
系統 SHALL 儲存 Line 訊息於租戶隔離的空間：
- message_id: 訊息 ID
- **tenant_id: 租戶識別（必填）**
- line_group_id / line_user_id: 來源
- content: 訊息內容
- attachments: 附件路徑

#### Scenario: 訊息附件儲存
- **WHEN** 用戶發送圖片或檔案
- **THEN** 附件儲存於 /mnt/nas/ctos/tenants/{tenant_id}/linebot/
- **AND** 依群組或用戶分類

### Requirement: Line Bot Webhook
系統 SHALL 處理 Line Bot Webhook 並識別租戶：
- 從群組 ID 或用戶 ID 查詢對應的 tenant_id
- 未綁定租戶時提示進行綁定
- 已綁定租戶時正常處理訊息

#### Scenario: 未綁定群組的訊息
- **WHEN** 收到未綁定租戶的群組訊息
- **THEN** Bot 回覆「請先綁定公司帳號」
- **AND** 提供綁定指令說明

## ADDED Requirements

### Requirement: Tenant Binding Command
系統 SHALL 提供租戶綁定指令：
- 指令格式：`/bind {tenant_code}`
- 驗證租戶代碼有效性
- 綁定成功後儲存關聯

#### Scenario: 綁定成功
- **WHEN** 用戶在群組發送 `/bind acme`
- **AND** acme 租戶存在且狀態為 active
- **THEN** 群組綁定到 acme 租戶
- **AND** Bot 回覆「綁定成功」

#### Scenario: 綁定失敗 - 租戶不存在
- **WHEN** 用戶發送 `/bind invalid_code`
- **THEN** Bot 回覆「租戶代碼無效」
- **AND** 群組維持未綁定狀態

### Requirement: Tenant Unbinding
系統 SHALL 支援解除租戶綁定：
- 指令格式：`/unbind`
- 需要群組管理員權限
- 解除後可重新綁定其他租戶

#### Scenario: 解除綁定
- **WHEN** 群組管理員發送 `/unbind`
- **THEN** 清除群組的 tenant_id
- **AND** Bot 回覆「已解除綁定」

### Requirement: Line Bot AI Context
系統 SHALL 在 AI 回應時傳遞租戶上下文：
- AI Agent Prompt 包含 ctos_tenant_id 參數
- MCP 工具使用租戶 ID 過濾資料
- 知識庫搜尋限定於該租戶

#### Scenario: AI 回應使用租戶資料
- **WHEN** 用戶詢問專案進度
- **THEN** AI 僅搜尋該租戶的專案資料
- **AND** 不會回傳其他租戶的資訊
