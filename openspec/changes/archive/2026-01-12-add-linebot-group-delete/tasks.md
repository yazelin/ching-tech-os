# Tasks: add-linebot-group-delete

## 實作任務

### 1. 後端 API
**檔案**：`backend/src/ching_tech_os/api/linebot_router.py`

- [ ] 新增 `DELETE /api/linebot/groups/{group_id}` endpoint
- [ ] 刪除前查詢群組的訊息數量（用於確認訊息）
- [ ] 執行刪除（資料庫級聯處理訊息和檔案記錄）
- [ ] 返回刪除結果（含已刪除的訊息數量）

### 2. 後端 Service（可選）
**檔案**：`backend/src/ching_tech_os/services/linebot.py`

- [ ] 如需要，新增 `delete_group()` 函數封裝刪除邏輯

### 3. 前端 UI
**檔案**：`frontend/js/linebot.js`

- [ ] 在 `renderGroupDetail()` 中新增刪除按鈕
- [ ] 新增 `deleteGroup(groupId)` 函數
- [ ] 新增確認對話框，顯示將刪除的訊息數量
- [ ] 刪除成功後重新載入群組列表

## 驗證項目

- [ ] 後端 API 測試：`DELETE /api/linebot/groups/{id}` 返回成功
- [ ] 刪除後，`line_groups`、`line_messages`、`line_files` 記錄都被清除
- [ ] 前端顯示刪除按鈕
- [ ] 確認對話框正確顯示訊息數量
- [ ] 刪除成功後群組從列表消失
- [ ] NAS 檔案未被刪除（手動確認）

## 依賴關係

- 無需資料庫 migration（已有 ON DELETE CASCADE）
- 前後端可並行開發
