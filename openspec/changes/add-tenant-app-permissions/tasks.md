# Tasks: 完整權限控制系統

## Phase 1: 權限資料結構與常數

### 1.1 定義工具與 App 權限對應
- [ ] 1.1.1 在 `services/permissions.py` 新增 `TOOL_APP_MAPPING` 常數
  - 列出所有 MCP 工具對應的 App 權限
  - `None` 表示不需要特定權限

- [ ] 1.1.2 新增 `API_APP_MAPPING` 常數
  - 列出 API 路徑前綴對應的 App 權限

- [ ] 1.1.3 新增租戶管理員預設權限常數
  ```python
  DEFAULT_TENANT_ADMIN_PERMISSIONS = {
      "apps": {
          "platform-admin": False,  # 禁止
          "terminal": False,        # 高風險
          "code-editor": False,     # 高風險
          # 其他預設開啟
      }
  }
  ```

### 1.2 權限檢查函數
- [ ] 1.2.1 新增 `has_app_permission(session, app_id)` 函數
- [ ] 1.2.2 新增 `get_user_app_permissions(user_id)` async 函數
- [ ] 1.2.3 新增 `require_app_permission(app_id)` FastAPI dependency

## Phase 2: 後端 Session 與 API

### 2.1 Session 擴充
- [ ] 2.1.1 在 `SessionData` 加入 `app_permissions` 欄位
- [ ] 2.1.2 修改 session 建立邏輯，載入使用者權限

### 2.2 API 權限檢查
- [ ] 2.2.1 修改 `/api/project/*` 路由加入權限檢查
- [ ] 2.2.2 修改 `/api/knowledge/*` 路由加入權限檢查
- [ ] 2.2.3 修改 `/api/nas/*` 路由加入權限檢查
- [ ] 2.2.4 修改 `/api/inventory/*` 路由加入權限檢查
- [ ] 2.2.5 修改 `/api/ai/*` 路由加入權限檢查（排除基本功能）

### 2.3 權限設定 API
- [ ] 2.3.1 修改 `PATCH /api/admin/users/{id}/permissions`
  - 平台管理員可修改租戶管理員
  - 租戶管理員只能修改一般使用者
  - 不能修改自己的權限

## Phase 3: Line Bot AI 權限控制

### 3.1 工具過濾
- [ ] 3.1.1 新增 `get_mcp_tools_for_user(user_permissions, ...)` 函數
  - 根據使用者權限過濾可用工具
- [ ] 3.1.2 修改 `linebot_ai.py` 的工具載入邏輯
  - 傳入使用者權限，取得過濾後的工具列表

### 3.2 Prompt 動態生成
- [ ] 3.2.1 將現有的工具說明 prompt 拆分成多個區塊
  - PROJECT_TOOLS_PROMPT
  - KNOWLEDGE_TOOLS_PROMPT
  - INVENTORY_TOOLS_PROMPT
  - FILE_TOOLS_PROMPT
  - 等等

- [ ] 3.2.2 新增 `generate_tools_prompt(user_permissions)` 函數
  - 根據使用者權限組合 prompt

- [ ] 3.2.3 修改 `linebot_ai.py` 使用動態 prompt

### 3.3 執行時權限檢查
- [ ] 3.3.1 在 MCP 工具執行層加入權限檢查
  - 從 context 取得使用者資訊
  - 檢查是否有對應權限
  - 無權限時回傳友善訊息

### 3.4 使用者資訊傳遞
- [ ] 3.4.1 修改 Line Bot 處理流程，傳遞使用者權限到 AI 呼叫
- [ ] 3.4.2 確保群組和個人對話都能正確取得使用者權限

## Phase 4: 前端修改

### 4.1 權限判斷邏輯
- [ ] 4.1.1 修改 `permissions.js` 的 `canAccessApp()`
  - 租戶管理員也要檢查 `permissions.apps`
  - 只有平台管理員是全開

### 4.2 使用者管理介面
- [ ] 4.2.1 修改使用者列表，顯示租戶管理員的權限狀態
- [ ] 4.2.2 平台管理員可以編輯租戶管理員的 App 權限
- [ ] 4.2.3 顯示「無法修改自己的權限」提示

## Phase 5: 遷移與初始化

### 5.1 現有資料遷移
- [ ] 5.1.1 建立 migration：為現有租戶管理員初始化 permissions.apps
  - 設定為預設全開（除了受限的 App）

### 5.2 使用者建立流程
- [ ] 5.2.1 修改建立租戶管理員的邏輯
  - 自動設定預設的 App 權限

## Phase 6: 測試

### 6.1 權限控制測試
- [ ] 6.1.1 測試平台管理員可修改租戶管理員權限
- [ ] 6.1.2 測試租戶管理員只能修改一般使用者
- [ ] 6.1.3 測試租戶管理員不能修改自己的權限

### 6.2 前端測試
- [ ] 6.2.1 測試租戶管理員只能看到有權限的 App
- [ ] 6.2.2 測試無權限時桌面不顯示該 App

### 6.3 API 權限測試
- [ ] 6.3.1 測試無權限時 API 回傳 403
- [ ] 6.3.2 測試有權限時 API 正常運作

### 6.4 Line Bot 測試
- [ ] 6.4.1 測試無專案管理權限的使用者不能使用專案工具
- [ ] 6.4.2 測試無知識庫權限的使用者不能使用知識庫工具
- [ ] 6.4.3 測試 AI 回答正確引導使用者（無權限時的友善訊息）
