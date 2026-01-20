# Change: 多租戶平台化架構

## Why

目前 Ching-Tech OS 是單一公司內部自建使用的架構，無法提供給多個公司或個人工作室同時使用。為了：

1. **支援試用服務**：讓多個公司、個人工作室能夠試用系統
2. **正式訂閱轉移**：試用期間的資料能夠完整轉移到正式伺服器
3. **擴大商業應用**：從單一公司工具轉型為 SaaS 平台
4. **資料隔離安全**：確保不同租戶的資料完全隔離

## What Changes

### **BREAKING** 資料庫結構重構
- 新增 `tenants` 租戶主表
- 所有核心表格新增 `tenant_id` 欄位（users, projects, ai_logs, line_groups, knowledge_items 等）
- 建立租戶層級的複合索引

### **BREAKING** 認證與會話改造
- SessionData 新增 `tenant_id` 屬性
- 登入流程支援租戶識別（subdomain / tenant code）
- API 層自動注入租戶上下文

### **BREAKING** 檔案儲存隔離
- 知識庫路徑從 `/mnt/nas/ctos/knowledge/` 改為 `/mnt/nas/ctos/tenants/{tenant_id}/knowledge/`
- Line Bot 檔案、AI 生成檔案等同樣隔離
- PathManager 擴展支援租戶路徑

### 後端服務改造
- 所有資料庫查詢加入 `tenant_id` 過濾
- MCP 工具加入租戶驗證
- Line Bot 支援多租戶（每租戶獨立 Bot 或共享 Bot）

### 新增租戶管理功能
- 租戶建立、設定、停用
- 租戶資源配額管理
- 租戶管理員角色
- 資料匯出/匯入功能（用於試用轉正式）

### 支援兩種部署模式
- **SaaS 模式**：多租戶共享基礎設施
- **單租戶模式**：相容現有部署方式（自動建立預設租戶）

## Impact

### Affected Specs
- `backend-auth`：認證流程加入租戶識別
- `infrastructure`：資料庫、檔案儲存架構變更
- `project-management`：專案隔離
- `knowledge-base`：知識庫隔離
- `line-bot`：Line Bot 多租戶支援
- `mcp-tools`：MCP 工具加入租戶驗證
- `inventory-management`：庫存隔離
- `ai-management`：AI 對話、日誌隔離

### New Specs
- `multi-tenancy`：租戶管理相關需求

### Affected Code

**資料庫層**
- `backend/migrations/versions/` - 新增 5-10 個 migration 檔案
- `backend/src/ching_tech_os/database.py` - 連線池可能需要調整

**認證層**
- `backend/src/ching_tech_os/api/auth.py`
- `backend/src/ching_tech_os/services/auth.py`
- `backend/src/ching_tech_os/services/session.py`

**服務層（全部）**
- `backend/src/ching_tech_os/services/project.py`
- `backend/src/ching_tech_os/services/knowledge.py`
- `backend/src/ching_tech_os/services/linebot.py`
- `backend/src/ching_tech_os/services/mcp_server.py`
- `backend/src/ching_tech_os/services/inventory.py`
- `backend/src/ching_tech_os/services/vendor.py`
- `backend/src/ching_tech_os/services/user.py`
- `backend/src/ching_tech_os/services/permissions.py`

**API 層（全部）**
- `backend/src/ching_tech_os/api/*.py` - 所有 API 端點

**檔案系統**
- `backend/src/ching_tech_os/services/path_manager.py`
- `backend/src/ching_tech_os/services/local_file.py`

**前端**
- `frontend/js/login.js` - 租戶識別 UI
- `frontend/js/api-client.js` - 請求加入租戶標頭
- `frontend/js/config.js` - 租戶設定

### Migration Plan

**Phase 1: 基礎設施準備（無停機）**
- 新增 tenants 表
- 所有表格新增 nullable tenant_id 欄位
- 部署支援 NULL tenant_id 的新代碼

**Phase 2: 資料遷移**
- 建立預設租戶
- 將所有現有資料指派到預設租戶
- 驗證資料完整性

**Phase 3: 約束啟用**
- tenant_id 欄位設為 NOT NULL
- 啟用外鍵約束
- 啟用租戶過濾

**Phase 4: 功能啟用**
- 啟用租戶管理 UI
- 啟用多租戶註冊
- 監控與調優
