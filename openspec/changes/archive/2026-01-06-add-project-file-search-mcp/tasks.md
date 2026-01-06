# Tasks: NAS 共享檔案搜尋 MCP 工具

## 1. MCP 工具實作
- [x] 1.1 在 `mcp_server.py` 新增 `search_nas_files` 工具
- [x] 1.2 實作檔案列表功能（使用 Python `pathlib`）
- [x] 1.3 實作關鍵字過濾（大小寫不敏感，多關鍵字 AND 匹配）
- [x] 1.4 實作檔案類型過濾（支援多種類型）
- [x] 1.5 限制回傳數量（預設 100 筆）
- [x] 1.6 新增 `get_nas_file_info` 工具取得檔案詳細資訊

## 2. 擴充分享連結服務
- [x] 2.1 修改 `services/share.py` 支援 `nas_file` resource_type
- [x] 2.2 實作 `get_resource_title` 處理 NAS 檔案（回傳檔名）
- [x] 2.3 實作路徑驗證（確保在 `/mnt/nas/projects` 下）
- [x] 2.4 新增檔案下載 API 端點

## 3. Line Bot 整合
- [x] 3.1 更新 `linebot_agents.py` 的 prompt，加入新工具說明
- [x] 3.2 更新資料庫中的 prompt（migration 017, 018）
- [x] 3.3 實作 `send_nas_file` MCP 工具（直接發送檔案）
  - 圖片（jpg/png/gif/webp）< 10MB → ImageMessage（直接顯示）
  - 其他檔案 → 發送下載連結（含 24 小時有效期提示）
  - Line API 不支援 FileMessage，PDF/XLSX 只能發連結

## 4. 檔案管理器整合
- [x] 4.1 實作路徑對應邏輯（檔案管理器路徑 → 系統掛載點路徑）
  - `/擎添共用區/在案資料分享/...` → `/mnt/nas/projects/...`
- [x] 4.2 右鍵選單新增「產生分享連結」選項（僅可分享路徑顯示）
- [x] 4.3 呼叫 ShareDialogModule 產生連結（resourceType: 'nas_file'）
- [x] 4.4 不可分享路徑不顯示選項

## 5. 定期清理過期連結
- [x] 5.1 在 `scheduler.py` 設定背景任務
- [x] 5.2 每小時執行清理（刪除 `expires_at < now` 的記錄）
- [x] 5.3 保留 `expires_at = NULL` 的永久連結

## 6. 測試
- [x] 6.1 手動測試：搜尋「亦達 layout pdf」
- [x] 6.2 手動測試：搜尋「亦達時程規劃」驗證語意匹配
- [x] 6.3 手動測試：大小寫不敏感（layout → Layout）
- [x] 6.4 手動測試：小圖片 → ImageMessage 直接顯示
- [x] 6.5 手動測試：小 PDF/XLSX → 連結可下載
- [x] 6.6 手動測試：檔案管理器產生分享連結
- [x] 6.7 過期連結清理（排程任務已設定，每小時執行）
