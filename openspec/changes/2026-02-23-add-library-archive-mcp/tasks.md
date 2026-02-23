# Tasks: add-library-archive-mcp

## 實作任務

- [ ] 1. **新增 `list_library_folders` MCP 工具**（`services/mcp/nas_tools.py`）
   - 權限檢查（`file-manager` + `shared_sources.library`）
   - `os.walk` 遍歷 `library_mount_path`，限制 `max_depth`
   - 回傳樹狀結構（資料夾名稱 + 檔案數量）

- [ ] 2. **新增 `archive_to_library` MCP 工具**（`services/mcp/nas_tools.py`）
   - 權限檢查（同上）
   - 驗證 `source_path` 為 CTOS zone 且檔案存在
   - 驗證 `category` 在 `LIBRARY_CATEGORIES` 白名單中
   - `_sanitize_path_segment` 清理 folder / filename
   - 目標目錄不存在時 `mkdir -p`
   - 檔名重複時加數字後綴（`-2`, `-3`）
   - `shutil.copy2` 複製檔案
   - 回傳歸檔結果路徑（`shared://library/...`）

- [ ] 3. **更新權限設定**（`services/permissions.py`）
   - `TOOL_APP_MAPPING` 新增 `list_library_folders` 和 `archive_to_library` → `file-manager`

- [ ] 4. **更新 AI Agent prompt**
   - 更新 `bot/agents.py` 中的 prompt，加入圖書館歸檔指引
   - 建立 migration 更新資料庫中的 prompt

- [ ] 5. **新增單元測試**（`tests/test_library_archive.py`）
   - `_sanitize_path_segment` 路徑清理測試
   - `archive_to_library` 正常歸檔、category 錯誤、source 非 CTOS、檔案不存在、檔名重複
   - `list_library_folders` 正常列出、空目錄

## 驗證

- [ ] 6. **執行測試**：`uv run pytest tests/test_library_archive.py -v`
- [ ] 7. **手動整合測試**：掛載 library 後，透過 Line Bot 上傳檔案並要求 AI 歸檔
