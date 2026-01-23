# Tasks: 完整權限控制系統

## Phase 1: 權限資料結構與常數

### 1.1 定義工具與 App 權限對應
- [x] 1.1.1 在 `services/permissions.py` 新增 `TOOL_APP_MAPPING` 常數
  - 列出所有 MCP 工具對應的 App 權限
  - `None` 表示不需要特定權限

- [x] 1.1.2 新增 `API_APP_MAPPING` 常數
  - 列出 API 路徑前綴對應的 App 權限

- [x] 1.1.3 新增租戶管理員預設權限常數
  - `DEFAULT_TENANT_ADMIN_APP_PERMISSIONS`
  - `DEFAULT_TENANT_ADMIN_PERMISSIONS`

### 1.2 權限檢查函數
- [x] 1.2.1 新增 `has_app_permission(role, permissions, app_id)` 函數
- [x] 1.2.2 新增 `get_user_app_permissions(user_id)` async 函數
- [x] 1.2.3 新增 `get_mcp_tools_for_user(role, permissions, all_tool_names)` 函數
- [x] 1.2.4 新增 `check_tool_permission(tool_name, role, permissions)` 函數
- [x] 1.2.5 新增 `require_app_permission(app_id)` FastAPI dependency

## Phase 2: 後端 Session 與 API

### 2.1 Session 擴充
- [x] 2.1.1 在 `SessionData` 加入 `app_permissions` 欄位
- [x] 2.1.2 修改 session 建立邏輯，載入使用者權限

### 2.2 API 權限檢查
- [x] 2.2.1 修改 `/api/project/*` 路由加入權限檢查
- [x] 2.2.2 修改 `/api/knowledge/*` 路由加入權限檢查
- [x] 2.2.3 修改 `/api/nas/*` 路由加入權限檢查
- [x] 2.2.4 修改 `/api/inventory/*` 路由加入權限檢查
- [x] 2.2.5 修改 `/api/ai/*` 路由加入權限檢查（排除基本功能）

### 2.3 權限設定 API
- [x] 2.3.1 修改 `PATCH /api/admin/users/{id}/permissions`
  - 平台管理員可修改租戶管理員
  - 租戶管理員只能修改一般使用者
  - 不能修改自己的權限

## Phase 3: Line Bot AI 權限控制

### 3.1 工具過濾
- [x] 3.1.1 新增 `get_mcp_tools_for_user(user_permissions, ...)` 函數
  - 根據使用者權限過濾可用工具
- [x] 3.1.2 修改 `linebot_ai.py` 的工具載入邏輯
  - 傳入使用者權限，取得過濾後的工具列表
  - 新增 `get_user_role_and_permissions()` 函數取得使用者資訊

### 3.2 Prompt 動態生成
- [x] 3.2.1 將現有的工具說明 prompt 拆分成多個區塊
  - PROJECT_TOOLS_PROMPT
  - KNOWLEDGE_TOOLS_PROMPT
  - INVENTORY_TOOLS_PROMPT
  - FILE_TOOLS_PROMPT
  - 等等

- [x] 3.2.2 新增 `generate_tools_prompt(user_permissions)` 函數
  - 根據使用者權限組合 prompt

- [x] 3.2.3 修改 `linebot_ai.py` 使用動態 prompt

### 3.3 執行時權限檢查
- [x] 3.3.1 在 MCP 工具執行層加入權限檢查
  - 從 context 取得使用者資訊
  - 檢查是否有對應權限
  - 無權限時回傳友善訊息

### 3.4 使用者資訊傳遞
- [x] 3.4.1 修改 Line Bot 處理流程，傳遞使用者權限到 AI 呼叫
- [x] 3.4.2 確保群組和個人對話都能正確取得使用者權限

## Phase 4: 前端修改

### 4.1 權限判斷邏輯
- [x] 4.1.1 修改 `permissions.js` 的 `canAccessApp()`
  - 租戶管理員也要檢查 `permissions.apps`
  - 只有平台管理員是全開

### 4.2 使用者管理介面
- [x] 4.2.1 修改使用者列表，顯示租戶管理員的權限狀態
- [x] 4.2.2 平台管理員可以編輯租戶管理員的 App 權限
- [x] 4.2.3 顯示「無法修改自己的權限」提示

## Phase 5: 遷移與初始化

### 5.1 現有資料遷移
- [x] 5.1.1 建立 migration：為現有租戶管理員初始化 permissions.apps
  - 設定為預設全開（除了受限的 App）

### 5.2 使用者建立流程
- [x] 5.2.1 修改建立租戶管理員的邏輯
  - 自動設定預設的 App 權限

## Phase 6: 測試

### 6.1 權限控制測試
- [x] 6.1.1 測試平台管理員可修改租戶管理員權限
- [x] 6.1.2 測試租戶管理員只能修改一般使用者
- [x] 6.1.3 測試租戶管理員不能修改自己的權限

### 6.2 前端測試
- [x] 6.2.1 測試租戶管理員只能看到有權限的 App
- [x] 6.2.2 測試無權限時桌面不顯示該 App

### 6.3 API 權限測試
- [x] 6.3.1 測試無權限時 API 回傳 403
- [x] 6.3.2 測試有權限時 API 正常運作

### 6.4 Line Bot 測試
- [x] 6.4.1 測試無專案管理權限的使用者不能使用專案工具
- [x] 6.4.2 測試無知識庫權限的使用者不能使用知識庫工具
- [x] 6.4.3 測試 AI 回答正確引導使用者（無權限時的友善訊息）

---

## 變更摘要

### 2026-01-21 Phase 1 & Phase 3 部分實作

**services/permissions.py 變更**：
- 新增 `TOOL_APP_MAPPING` 常數：所有 MCP 工具對應的 App 權限
- 新增 `API_APP_MAPPING` 常數：API 路徑前綴對應的 App 權限
- 新增 `DEFAULT_TENANT_ADMIN_APP_PERMISSIONS` 常數
- 新增 `DEFAULT_TENANT_ADMIN_PERMISSIONS` 常數
- 新增 `APP_DISPLAY_NAMES` 中的 `inventory` 和 `platform-admin` 項目
- 新增 `has_app_permission()` 函數：基於角色和權限設定檢查 App 權限
- 新增 `get_user_app_permissions()` async 函數：從資料庫取得使用者 App 權限
- 新增 `get_mcp_tools_for_user()` 函數：根據權限過濾可用 MCP 工具
- 新增 `check_tool_permission()` 函數：檢查特定工具的權限

**services/user.py 變更**：
- 新增 `get_user_role_and_permissions()` async 函數：取得使用者角色和權限

**services/linebot_ai.py 變更**：
- 修改 `process_message_with_ai()` 函數
- 在取得 MCP 工具列表後，根據使用者權限過濾工具
- 透過 `line_user_id` 查詢 `ctos_user_id`，再取得角色和權限

### 2026-01-21 Phase 2-6 完成實作

**api/auth.py 變更**：
- 新增 `require_tenant_admin_or_above()` FastAPI dependency
- 新增 `require_can_manage_target()` 權限階層檢查函數
- 新增 `can_manage_user()` 輔助函數

**api/user.py 變更**：
- 修改 `PATCH /api/admin/users/{id}/permissions` 加入權限階層檢查
  - 平台管理員可修改任何人（除了自己）
  - 租戶管理員只能修改同租戶的一般使用者
  - 不能修改自己的權限

**services/linebot_agents.py 變更**：
- 將工具說明 prompt 拆分成多個區塊（PROJECT_TOOLS_PROMPT、KNOWLEDGE_TOOLS_PROMPT 等）
- 新增 `generate_tools_prompt(app_permissions)` 函數
- 根據使用者權限動態組合 prompt

**前端變更**：
- `permissions.js`: 修改 `canAccessApp()` 函數，租戶管理員也需檢查 `permissions.apps`
- `platform-admin.js`: 新增租戶管理員 App 權限編輯對話框
- `platform-admin.css`: 新增權限對話框樣式
- `tenant-admin.js`: 新增使用者 App 權限編輯對話框
- `tenant-admin.css`: 新增權限對話框樣式

**資料庫遷移**：
- `059_init_tenant_admin_permissions.py`: 為現有租戶管理員初始化 `permissions.apps`
