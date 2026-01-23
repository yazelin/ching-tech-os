# Tasks: 租戶 NAS 隔離 - Phase 1

## 階段一：系統 NAS + 子目錄隔離

### 1.1 建立目錄結構
- [x] 1.1.1 在 NAS 上建立 `/mnt/nas/ctos/tenants/` 目錄
- [x] 1.1.2 為預設租戶建立目錄 `00000000-0000-0000-0000-000000000000/`
- [x] 1.1.3 建立子目錄：`knowledge/`, `projects/`, `linebot/`, `ai-generated/`

### 1.2 修正 knowledge.py 的 tenant_id 傳遞
- [x] 1.2.1 `delete_knowledge()` 中的 `create_knowledge_file_service()` 加入 tenant_id (`knowledge.py:689`)
- [x] 1.2.2 `upload_attachment()` 中的 `create_knowledge_file_service()` 加入 tenant_id (`knowledge.py:998`)
- [x] 1.2.3 `copy_linebot_attachment_to_knowledge()` 中的 `create_linebot_file_service()` 加入 tenant_id (`knowledge.py:1074`)
- [x] 1.2.4 `get_nas_attachment()` 新增 tenant_id 參數 (`knowledge.py:1083`)
- [x] 1.2.5 `delete_attachment()` 中的 `create_knowledge_file_service()` 加入 tenant_id (`knowledge.py:1199`)

### 1.3 修正 linebot.py 的 tenant_id 傳遞
- [x] 1.3.1 `save_to_nas()` 新增 tenant_id 參數 (`linebot.py:1080`)
- [x] 1.3.2 `download_and_save_file()` 傳遞 tenant_id 到 `save_to_nas()` (`linebot.py:939`)
- [x] 1.3.3 `read_file_from_nas()` 新增 tenant_id 參數 (`linebot.py:1770`)
- [x] 1.3.4 `delete_file()` 中的 `create_linebot_file_service()` 加入 tenant_id (`linebot.py:1821`)

### 1.4 修正 linebot_ai.py 的 tenant_id 傳遞
- [x] 1.4.1 `save_file_record()` 呼叫加入 tenant_id (`linebot_ai.py:668`)

### 1.5 修正 mcp_server.py 的安全問題
- [x] 1.5.1 `send_nas_file`: Line group 查詢加入 tenant_id 過濾 (`mcp_server.py:2652`)
- [x] 1.5.2 `search_nas_files`: 更新註解說明公司共用區不需要租戶隔離 (`mcp_server.py:2193`)
- [x] 1.5.3 `read_document`: 更新註解說明公司共用區不需要租戶隔離 (`mcp_server.py:2412`)

---

## 變更摘要

### 2026-01-21 Phase 1 完成

**services/knowledge.py 變更**：
- `delete_knowledge()`: 傳遞 tenant_id 到 `create_knowledge_file_service()`
- `upload_attachment()`: 傳遞 tenant_id 到 `create_knowledge_file_service()`
- `copy_linebot_attachment_to_knowledge()`: 傳遞 tenant_id 到 `create_linebot_file_service()`
- `get_nas_attachment()`: 新增 `tenant_id` 參數
- `delete_attachment()`: 傳遞 tenant_id 到 `create_knowledge_file_service()`

**services/linebot.py 變更**：
- `save_to_nas()`: 新增 `tenant_id` 參數，傳遞到 `create_linebot_file_service()`
- `download_and_save_file()`: 傳遞 tenant_id 到 `save_to_nas()`
- `read_file_from_nas()`: 新增 `tenant_id` 參數
- `delete_file()`: 傳遞 tenant_id 到 `create_linebot_file_service()`

**services/linebot_ai.py 變更**：
- `save_file_record()` 呼叫加入 `tenant_id=tenant_id`

**services/mcp_server.py 變更**：
- `send_nas_file`: Line group 查詢加入 `AND tenant_id = $2` 過濾
- `search_nas_files` / `read_document`: 更新註解說明公司共用區不需要租戶隔離

**目錄結構**：
- 建立 `/mnt/nas/ctos/tenants/00000000-0000-0000-0000-000000000000/`
- 建立子目錄：`knowledge/`, `projects/`, `linebot/`, `ai-generated/`

---

## 不在 Phase 1 範圍

以下項目延後到 Phase 2 或另案處理：

### 資料遷移（另案處理）
- [ ] 建立遷移腳本：將現有檔案移到租戶目錄
- [ ] 建立資料庫遷移：更新 `line_files.nas_path` 加入租戶路徑
- [ ] 備份現有資料

### Phase 2：租戶自訂 NAS（延後）
- [ ] 定義 `NASConfig` Pydantic 模型
- [ ] 建立 `TenantNASService`
- [ ] 平台管理 API
- [ ] 前端 NAS 設定介面

---

## 注意事項

### 向後相容
- `tenant_id = None` 時使用舊路徑（向後相容）
- 傳入 tenant_id 時使用新的租戶隔離路徑

### 測試重點
- 知識庫附件上傳/讀取/刪除
- Line Bot 檔案儲存/讀取/刪除
- MCP 工具正確使用租戶資訊
