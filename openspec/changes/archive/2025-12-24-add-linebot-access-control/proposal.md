# Change: Line Bot 存取控制

## Why
目前 Line Bot 沒有任何存取控制，任何人加入群組或私訊 Bot 都能獲得回應。這導致：
1. 非公司人員可能意外或故意使用 Bot
2. 無法追蹤誰在使用 Bot
3. 可能洩漏敏感的專案/知識庫資訊

需要限制只有 ching-tech-os 的合法用戶才能使用 Line Bot。

## What Changes
- **Line 用戶與 CTOS 用戶綁定**：透過驗證碼流程，將 Line 帳號與 CTOS 帳號關聯
- **解除綁定**：用戶可解除綁定，方便更換 Line 帳號
- **群組白名單**：新增群組的 `allow_ai_response` 欄位，控制是否回應
- **存取控制邏輯**：
  - 個人對話：必須綁定 CTOS 帳號才會回應
  - 群組對話：群組必須設為允許回應且發送者必須已綁定帳號
- **綁定管理 UI**：Line Bot 管理介面新增用戶綁定狀態查看與管理

## Impact
- Affected specs: `line-bot`, `backend-auth`
- Affected code:
  - `backend/services/linebot.py` - 新增存取控制邏輯
  - `backend/services/linebot_ai.py` - 加入綁定檢查
  - `backend/api/linebot_router.py` - 新增綁定/解綁 API
  - `backend/migrations/` - 新增資料表欄位
  - `frontend/js/linebot.js` - 綁定管理 UI

## Design Decisions

### 綁定流程
1. 用戶在 CTOS 的 Line Bot 管理頁面點擊「綁定 Line 帳號」
2. 系統產生 6 碼驗證碼（5 分鐘有效）
3. 用戶用 Line 私訊 Bot 傳送驗證碼
4. Bot 驗證成功後，綁定 Line 帳號與 CTOS 帳號
5. 完成後用戶可正常使用 Bot

### 解除綁定流程
- 用戶在 CTOS 中可解除自己的 Line 綁定
- 管理員可解除任何用戶的綁定
- 解除後 `line_users.user_id` 設為 NULL
- 該 Line 帳號將無法再使用 Bot（直到重新綁定）

### 群組控制
- 預設新群組 `allow_ai_response = false`
- 管理員可在 CTOS 中開啟群組的 AI 回應
- 群組中發言者仍需為已綁定用戶

### 未綁定用戶的處理
- 個人對話：回覆提示訊息「請先在 CTOS 綁定 Line 帳號」
- 群組對話：靜默不回應（避免干擾）

## Migration
- 現有 `line_users.user_id` 欄位已存在但未使用，將開始使用
- 新增 `line_groups.allow_ai_response` 欄位，預設 `false`
- 新增 `line_binding_codes` 表存放驗證碼
- 現有綁定的群組（已有 project_id）可選擇自動設為 `allow_ai_response = true`
