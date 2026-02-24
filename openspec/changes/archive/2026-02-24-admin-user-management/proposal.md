## Why

目前系統登入只支援 SMB/NAS 認證，雖然後端已有密碼認證邏輯，但管理員無法從 UI 建立純 CTOS 本地帳號。這導致所有使用者都必須有 NAS 帳號才能登入。此外，當使用者從 NAS 認證轉為密碼認證後（設定了 password_hash），沒有任何機制可以切回 NAS 認證。需要提供完整的使用者帳號管理能力，讓管理員可以獨立於 NAS 建立和管理本地帳號。

## What Changes

- 新增管理員 API 端點：建立使用者、編輯使用者資訊、重設密碼、停用/啟用帳號、清除密碼（恢復 NAS 認證）
- 在「系統設定」App 的使用者管理 Tab 中新增 UI：
  - 「新增使用者」按鈕與對話框（帳號、密碼、顯示名稱、角色）
  - 使用者列表加入操作選單：編輯、重設密碼、停用/啟用、清除密碼
- 使用者列表顯示認證方式標籤（密碼認證 / NAS 認證）
- 新增後端服務函數：清除使用者密碼（將 password_hash 設為 NULL，恢復 NAS 認證）

## Capabilities

### New Capabilities
- `admin-user-crud`: 管理員帳號 CRUD 管理功能，涵蓋建立使用者、編輯資訊、重設密碼、停用/啟用、清除密碼的 API 端點與前端 UI

### Modified Capabilities
- `backend-auth`: 新增「清除密碼」的服務函數（`clear_user_password`），允許將使用者從密碼認證切回 NAS 認證

## Impact

- **後端 API**：`api/user.py` 新增 5~6 個管理員端點
- **後端服務**：`services/user.py` 新增 `clear_user_password()` 函數
- **後端模型**：`models/user.py` 新增請求/回應 Pydantic 模型
- **前端 JS**：`settings.js` 新增使用者管理 UI（新增、編輯、操作選單）
- **前端 CSS**：`settings.css` 新增對話框與操作按鈕樣式
- **現有 NAS 使用者不受影響**：登入判斷邏輯（有 password_hash → 密碼認證，無 → NAS 認證）維持不變
