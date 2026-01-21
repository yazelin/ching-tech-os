# Proposal: 完整權限控制系統

## 摘要

建立完整的使用者權限控制系統，讓：
- **平台管理員** 可以控制 **租戶管理員** 的 App 權限
- **租戶管理員** 可以控制 **一般使用者** 的 App 權限
- 權限限制同時適用於 **Web UI** 和 **Line Bot AI**

## 動機

目前的權限設計有以下問題：

1. **租戶管理員權限是硬編碼的** - 除了 `platform-admin` 外全開
2. **Line Bot AI 不受權限限制** - 使用者可以透過 Line Bot 使用沒有權限的功能
3. **後端 API 沒有權限檢查** - 只要登入就能呼叫所有 API

## 設計原則

### 權限階層
```
平台管理員 ──控制──→ 租戶管理員
租戶管理員 ──控制──→ 一般使用者
```

### 權限跟著使用者
- 每個使用者有獨立的 `permissions.apps` 設定
- 不是租戶層級設定，而是使用者層級
- 預設權限依據角色不同：
  - 租戶管理員：預設大部分開啟（除了 platform-admin、terminal、code-editor）
  - 一般使用者：依據 DEFAULT_APP_PERMISSIONS

### 權限控制誰可以修改
- 平台管理員：可修改任何使用者（包括租戶管理員）
- 租戶管理員：只能修改同租戶的一般使用者
- 租戶管理員**不能**修改自己的權限

## 影響範圍

### 1. 前端 Web UI

**canAccessApp() 修改**：
```javascript
function canAccessApp(appId) {
  // 平台管理員：所有權限
  if (role === 'platform_admin') return true;

  // 租戶管理員和一般使用者：檢查 permissions.apps
  // 預設值不同，但判斷邏輯相同
  return user.permissions?.apps?.[appId] === true;
}
```

**使用者管理介面修改**：
- 平台管理員可以設定租戶管理員的 App 權限
- 使用相同的權限編輯介面

### 2. 後端 API 權限檢查

新增 API 權限檢查機制，將 App ID 對應到 API 路徑：

```python
# API 與 App 權限對應
API_APP_MAPPING = {
    "/api/project": "project-management",
    "/api/knowledge": "knowledge-base",
    "/api/nas": "file-manager",
    "/api/inventory": "inventory",
    # ...
}

# 權限檢查 middleware 或 dependency
async def require_app_permission(app_id: str):
    async def checker(session: SessionData = Depends(get_current_session)):
        if not has_app_permission(session, app_id):
            raise HTTPException(403, f"無 {app_id} 功能權限")
        return session
    return checker
```

### 3. Line Bot AI 權限控制（關鍵）

**MCP 工具與 App 權限對應**：

```python
TOOL_APP_MAPPING = {
    # 專案管理
    "query_project": "project-management",
    "create_project": "project-management",
    "update_project": "project-management",
    "add_project_member": "project-management",
    # ...

    # 知識庫
    "search_knowledge": "knowledge-base",
    "add_note": "knowledge-base",
    "get_knowledge_item": "knowledge-base",
    # ...

    # 庫存管理
    "query_inventory": "inventory",
    "add_inventory_item": "inventory",
    "record_inventory_in": "inventory",
    # ...

    # 檔案管理
    "search_nas_files": "file-manager",
    "get_nas_file_info": "file-manager",
    "send_nas_file": "file-manager",
    # ...

    # 通用工具（不需要特定權限）
    "get_message_attachments": None,  # 基礎功能
    "create_share_link": None,
}
```

**方案選擇**：採用「動態過濾工具 + Prompt 引導 + 執行時檢查」

1. **動態過濾工具列表**：
   - 在載入 MCP 工具時，根據使用者權限過濾
   - AI 只看得到有權限的工具

2. **Prompt 引導**：
   - 在 system prompt 中說明使用者可用的功能分類
   - 提供更好的使用者體驗

3. **執行時檢查**（雙重保險）：
   - MCP 工具執行時再次檢查權限
   - 防止繞過

**實作方式**：

```python
async def get_mcp_tools_for_user(
    user_permissions: dict,
    exclude_group_only: bool = False
) -> list[str]:
    """根據使用者權限取得可用的 MCP 工具"""
    all_tools = await get_mcp_tool_names(exclude_group_only)

    allowed_tools = []
    for tool in all_tools:
        tool_name = tool.replace("mcp__ching-tech-os__", "")
        required_app = TOOL_APP_MAPPING.get(tool_name)

        # 不需要特定權限的工具
        if required_app is None:
            allowed_tools.append(tool)
            continue

        # 檢查使用者是否有對應 App 權限
        if user_permissions.get("apps", {}).get(required_app, False):
            allowed_tools.append(tool)

    return allowed_tools
```

**Prompt 動態生成**：

```python
def generate_tools_prompt(user_permissions: dict) -> str:
    """根據使用者權限生成工具說明 prompt"""
    sections = []

    if user_permissions.get("apps", {}).get("project-management"):
        sections.append(PROJECT_TOOLS_PROMPT)

    if user_permissions.get("apps", {}).get("knowledge-base"):
        sections.append(KNOWLEDGE_TOOLS_PROMPT)

    if user_permissions.get("apps", {}).get("inventory"):
        sections.append(INVENTORY_TOOLS_PROMPT)

    # ...

    return "\n\n".join(sections)
```

### 4. 資料模型變更

**SessionData 擴充**：
```python
class SessionData(BaseModel):
    # ... 現有欄位 ...
    app_permissions: dict[str, bool] = {}  # 使用者的 App 權限快取
```

**使用者權限初始化**：
- 租戶管理員建立時，自動設定預設的 App 權限
- 可由平台管理員調整

## API 清單

### 現有 API 需要加入權限檢查

| API 路徑 | 需要的 App 權限 |
|---------|----------------|
| `/api/project/*` | project-management |
| `/api/knowledge/*` | knowledge-base |
| `/api/nas/*` | file-manager |
| `/api/inventory/*` | inventory |
| `/api/ai/*` | ai-assistant |
| `/api/terminal/*` | terminal |

### 權限設定 API

| 方法 | 路徑 | 說明 | 權限要求 |
|-----|-----|------|---------|
| GET | `/api/admin/users/{id}/permissions` | 取得使用者權限 | 管理員 |
| PATCH | `/api/admin/users/{id}/permissions` | 更新使用者權限 | 管理員 + 階層檢查 |

## 遷移策略

1. **現有租戶管理員**：
   - 自動初始化 permissions.apps，設定為預設開啟（維持現有行為）
   - 之後由平台管理員調整

2. **現有一般使用者**：
   - 維持現有的 DEFAULT_APP_PERMISSIONS 預設值
   - 不受影響

## 風險

1. **效能影響**：每次 API 呼叫都要檢查權限
   - 緩解：使用 session 快取權限資料

2. **Line Bot 體驗**：工具列表變動可能影響 AI 回答
   - 緩解：Prompt 引導 + 友善的無權限訊息

3. **複雜度增加**：權限檢查散布在多處
   - 緩解：統一的權限檢查函數和常數定義
