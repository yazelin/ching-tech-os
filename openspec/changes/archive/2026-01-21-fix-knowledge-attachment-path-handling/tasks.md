# Tasks: 修正知識庫附件路徑處理

## 1. 修正公開分享 API

- [x] 1.1 修正 `share.py` 的 `get_public_attachment` 函數 ✓
- [x] 1.2 支援 NAS 附件的 `ctos://knowledge/` 格式 ✓
- [x] 1.3 測試公開分享頁面的附件下載 ✓

## 2. 修正 MCP 工具

- [x] 2.1 新增 `read_knowledge_attachment` MCP 工具 ✓
- [x] 2.2 修正 `prepare_file_message` 支援知識庫附件路徑 ✓

## 3. 資料遷移

- [x] 3.1 保持向後兼容，兩種格式都支援（無需遷移）✓

## 4. 驗證

- [x] 4.1 確認公開分享頁面可以正確顯示和下載附件 ✓
- [x] 4.2 確認 Line Bot 可以發送知識庫附件圖片 ✓
