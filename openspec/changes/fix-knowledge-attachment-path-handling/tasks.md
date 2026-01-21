# Tasks: 修正知識庫附件路徑處理

## 1. 修正公開分享 API

- [ ] 1.1 修正 `share.py` 的 `get_public_attachment` 函數
  - 支援 `local://knowledge/assets/images/...` 格式
  - 支援 `local://knowledge/images/...` 格式（舊）
  - 將這些格式轉換為正確的檔案系統路徑

- [ ] 1.2 支援 NAS 附件的 `ctos://knowledge/` 格式
  - 將 `ctos://knowledge/attachments/...` 轉換為正確的 NAS 路徑

- [ ] 1.3 測試公開分享頁面的附件下載
  - 測試新格式附件下載
  - 測試舊格式附件下載
  - 測試預覽功能

## 2. 修正 MCP 工具（可選）

- [ ] 2.1 評估是否需要新增 MCP 工具讀取知識庫附件
- [ ] 2.2 或修正 `prepare_file_message` 支援知識庫附件路徑

## 3. 資料遷移（可選）

- [ ] 3.1 評估是否需要遷移舊資料的路徑格式
- [ ] 3.2 若需要，建立遷移腳本更新 `data/knowledge/entries/*.md`

## 4. 驗證

- [ ] 4.1 確認公開分享頁面可以正確顯示和下載附件
- [ ] 4.2 確認 Line Bot 個人對話可以發送知識庫附件圖片
