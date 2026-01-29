# fix-multi-platform-binding

## Summary

修復多平台綁定邏輯，允許同一 CTOS 帳號同時綁定 Line 和 Telegram。

## Problem

目前系統在已綁定 Line 的情況下，無法再綁定 Telegram，原因是多處程式碼缺少 `platform_type` 條件：

### 後端問題

1. **`verify_binding_code()` 第 2192-2201 行**：檢查 CTOS 用戶是否已綁定時，SQL 查詢沒有加 `platform_type` 條件，導致已綁定 Line 就擋掉 Telegram 綁定。
   ```sql
   -- 目前（錯誤）：找到任何平台的綁定就報錯
   SELECT id FROM bot_users WHERE user_id = $1 AND tenant_id = $2
   -- 應該：只檢查同平台
   SELECT id FROM bot_users WHERE user_id = $1 AND tenant_id = $2 AND platform_type = $3
   ```

2. **`unbind_line_user()` 第 2249-2257 行**：解除綁定時沒有 `platform_type` 條件，會一次解除所有平台綁定。

3. **API `DELETE /binding`**：沒有接受 `platform_type` 參數，無法指定解除哪個平台的綁定。

### 前端問題（已部分修復）

4. **`showBindingCodeModal()` polling**：已修復（commit 47914ef），改為檢查對應平台的 `is_bound`。

5. **`unbindLine()` 函式**：解除綁定沒有傳 `platform_type`，且確認訊息寫死為「Line」。

## Scope

- `backend/src/ching_tech_os/services/linebot.py` — `verify_binding_code()`、`unbind_line_user()`
- `backend/src/ching_tech_os/api/linebot_router.py` — `DELETE /binding` API
- `frontend/js/linebot.js` — `unbindLine()` 函式

## Risks

- 低風險：修改為加入 `platform_type` 條件，是收緊查詢範圍，不會影響已有的綁定記錄
