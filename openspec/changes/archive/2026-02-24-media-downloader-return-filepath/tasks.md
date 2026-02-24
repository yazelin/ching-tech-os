## 1. check-download.py 新增 file_path

- [x] 1.1 在 `check-download.py` 的完成分支（`status == "completed"`）新增 `file_path` 欄位：用 `path_manager.to_filesystem(ctos_path)` 轉換，try-except 包裹，失敗時靜默跳過
- [x] 1.2 驗證：手動觸發一次下載，確認 check-download 回傳包含 `file_path` 且路徑正確

## 2. SKILL.md 更新 AI 行為指引

- [x] 2.1 更新 check-download 說明：完成時回傳 `ctos_path`（用於歸檔、傳給 transcribe）+ `file_path`（絕對路徑）
- [x] 2.2 新增指引：後續操作要轉逐字稿時，用 check-download 回傳的 `ctos_path` 作為 transcribe 的 `source_path`，**禁止自行猜測或拼湊路徑**
- [x] 2.3 新增指引：AI 回報下載完成時，須在回覆中包含 `ctos_path`，確保對話歷史中保留完整路徑供後續引用

## 3. Spec 同步

- [x] 3.1 執行 `openspec sync-specs` 將 delta spec 合併回 `openspec/specs/media-downloader/spec.md`
