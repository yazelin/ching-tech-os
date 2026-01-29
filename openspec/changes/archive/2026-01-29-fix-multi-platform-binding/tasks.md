# Tasks

## 1. 修復 `verify_binding_code()` 的平台檢查邏輯
- 檔案：`backend/src/ching_tech_os/services/linebot.py`
- 在第 2192 行的 SQL 查詢加入 `AND platform_type = $3` 條件
- 傳入 `user_platform_type` 參數
- 修改錯誤訊息，明確指出是哪個平台已綁定

## 2. 修復 `unbind_line_user()` 支援指定平台解除綁定
- 檔案：`backend/src/ching_tech_os/services/linebot.py`
- 新增 `platform_type` 參數（預設 `None` 表示全部解除，保持向後相容）
- SQL 加入 `AND platform_type = $3` 條件（當指定平台時）

## 3. 修改 `DELETE /binding` API 接受 `platform_type` 參數
- 檔案：`backend/src/ching_tech_os/api/linebot_router.py`
- 新增 `platform_type` query parameter
- 傳遞給 `unbind_line_user()`
- 更新回應訊息

## 4. 修復前端 `unbindLine()` 傳入平台類型
- 檔案：`frontend/js/linebot.js`
- `unbindLine()` 接受 `platformKey` 參數
- 呼叫 `DELETE /binding?platform_type=xxx`
- 確認訊息顯示正確的平台名稱
- 按鈕 click handler 傳入 `btn.dataset.platform`

## 5. 部署到 trial 機測試
- 在 trial 機（192.168.11.21）pull 並驗證：
  - 已綁定 Line 後可以產生 Telegram 驗證碼且 Modal 不會自動關閉
  - 可以成功綁定 Telegram
  - 可以單獨解除 Line 或 Telegram 綁定
