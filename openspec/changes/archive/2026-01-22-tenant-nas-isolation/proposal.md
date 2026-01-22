# Change: 租戶 NAS 隔離 - Phase 1

## Why

目前系統中的檔案儲存（知識庫附件、Line Bot 檔案）沒有租戶隔離。程式碼中已有租戶路徑支援（`path_manager.py`、`local_file.py`），但 `tenant_id` 沒有被正確傳遞到 file service，導致所有租戶的檔案混在一起。

## What Changes

### Phase 1（本次變更）：系統 NAS + 子目錄隔離

1. **修正 knowledge.py 的 tenant_id 傳遞**
   - `delete_knowledge()` 中的 `create_knowledge_file_service()` 加入 tenant_id
   - `upload_attachment()` 中的 `create_knowledge_file_service()` 加入 tenant_id
   - `copy_linebot_attachment_to_knowledge()` 加入 tenant_id
   - `get_nas_attachment()` 新增 tenant_id 參數
   - `delete_attachment()` 中的 `create_knowledge_file_service()` 加入 tenant_id

2. **修正 linebot.py 的 tenant_id 傳遞**
   - `save_to_nas()` 新增 tenant_id 參數
   - `download_and_save_file()` 傳遞 tenant_id 到 `save_to_nas()`
   - `read_file_from_nas()` 新增 tenant_id 參數
   - `delete_file()` 中的 `create_linebot_file_service()` 加入 tenant_id

3. **修正 linebot_ai.py 的 tenant_id 傳遞**
   - `save_file_record()` 呼叫加入 tenant_id

4. **修正 mcp_server.py 的安全問題**（高優先）
   - `search_nas_files`: 使用已轉換的 tid 做路徑驗證
   - `read_document`: 使用已轉換的 tid 做路徑驗證
   - `send_nas_file`: Line group 查詢加入 tenant_id 過濾
   - `prepare_file_message`: 同上

### 不在本次範圍

- Phase 2（租戶自訂 NAS）：當有租戶需要自訂 NAS 時再實作
- 資料遷移腳本：需要停機時間，另案處理

## Impact

- **Affected specs**: 無（這是基礎架構修正，不影響使用者可見功能）
- **Affected code**:
  - `services/knowledge.py`: 5 處修改
  - `services/linebot.py`: 5 處修改
  - `services/linebot_ai.py`: 1 處修改
  - `services/mcp_server.py`: 4 處修改（安全修正）
- **向後相容**: 是。`tenant_id = None` 時使用預設租戶路徑
- **需要測試**: 知識庫附件上傳/讀取、Line Bot 檔案儲存/讀取
