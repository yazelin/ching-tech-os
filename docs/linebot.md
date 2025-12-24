# Line Bot 整合

Line Bot 整合功能，實現 Line 訊息儲存與 AI 助理回應。

## 架構

```
Line Platform
     │
     ▼ Webhook
┌─────────────────────────────────────────────────────┐
│  FastAPI                                            │
│  ┌─────────────┐    ┌─────────────────────────────┐│
│  │ linebot_    │    │ linebot_ai.py               ││
│  │ router.py   │───▶│ - process_message_with_ai   ││
│  │ - webhook   │    │ - call_claude_with_tools    ││
│  └─────────────┘    └──────────────┬──────────────┘│
│         │                          │               │
│         ▼                          ▼               │
│  ┌─────────────┐    ┌─────────────────────────────┐│
│  │ linebot.py  │    │ mcp_server.py               ││
│  │ - 儲存訊息  │    │ - query_project             ││
│  │ - 用戶管理  │    │ - get_project_milestones    ││
│  │ - 群組管理  │    │ - get_project_meetings      ││
│  └─────────────┘    │ - summarize_chat            ││
│         │           └─────────────────────────────┘│
│         ▼                                          │
│  ┌─────────────┐                                   │
│  │ PostgreSQL  │                                   │
│  │ line_*      │                                   │
│  └─────────────┘                                   │
└─────────────────────────────────────────────────────┘
```

## 資料表

### line_groups
群組資訊，可綁定專案。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 內部 ID |
| line_group_id | VARCHAR(64) | Line 群組 ID |
| name | VARCHAR(256) | 群組名稱 |
| project_id | UUID | 綁定的專案 |
| is_active | BOOLEAN | 是否使用中 |

### line_users
用戶資訊。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 內部 ID |
| line_user_id | VARCHAR(64) | Line 用戶 ID |
| display_name | VARCHAR(256) | 顯示名稱 |
| user_id | INTEGER | 對應的系統用戶 |

### line_messages
所有訊息記錄。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 內部 ID |
| message_id | VARCHAR(64) | Line 訊息 ID |
| line_user_id | UUID | 發送者 |
| line_group_id | UUID | 群組（NULL=個人） |
| message_type | VARCHAR(32) | 訊息類型 |
| content | TEXT | 訊息內容 |
| ai_processed | BOOLEAN | 是否已 AI 處理 |

### line_files
檔案記錄。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 內部 ID |
| message_id | UUID | 關聯訊息 |
| file_type | VARCHAR(32) | 檔案類型 |
| nas_path | TEXT | NAS 儲存路徑 |

## API 端點

### Webhook

```
POST /api/linebot/webhook
```

Line 平台的 Webhook 端點，需在 Line Developers Console 設定。

### 群組管理

```
GET /api/linebot/groups
GET /api/linebot/groups/{group_id}
POST /api/linebot/groups/{group_id}/bind-project
DELETE /api/linebot/groups/{group_id}/bind-project
```

### 用戶管理

```
GET /api/linebot/users
GET /api/linebot/users/{user_id}
```

### 訊息查詢

```
GET /api/linebot/messages?group_id=xxx&page=1&page_size=50
```

## AI 處理邏輯

### 觸發條件

- **個人對話**：所有訊息都觸發 AI 處理
- **群組對話**：僅當 Bot 被 @ 提及時觸發

### MCP 工具

AI 助理可使用的工具：

1. **query_project** - 查詢專案資訊
2. **get_project_milestones** - 取得專案里程碑
3. **get_project_meetings** - 取得會議記錄
4. **get_project_members** - 取得專案成員
5. **summarize_chat** - 取得聊天記錄

## 設定

### 環境變數

```bash
# Line Bot 設定
CHING_TECH_LINE_CHANNEL_SECRET=your_channel_secret
CHING_TECH_LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
```

### Line Developers Console 設定

1. 建立 Messaging API Channel
2. 設定 Webhook URL: `https://your-domain/api/linebot/webhook`
3. 啟用 Webhook
4. 取得 Channel Secret 和 Channel Access Token

## 前端介面

桌面應用程式「Line Bot」提供：

- **群組標籤頁**：群組列表、專案綁定、最近訊息
- **用戶標籤頁**：用戶列表
- **訊息標籤頁**：訊息瀏覽、群組篩選

## 執行 Migration

```bash
cd backend
uv run alembic upgrade head
```

## Claude Code CLI 整合

MCP Server 使用 FastMCP 實作，支援 Claude Code CLI 使用。

### 設定方式

在專案根目錄的 `.mcp.json` 加入（已設定完成）：

```json
{
  "mcpServers": {
    "ching-tech-os": {
      "command": "uv",
      "args": ["run", "python", "-m", "ching_tech_os.mcp_cli"],
      "cwd": "/home/ct/SDD/ching-tech-os/backend"
    }
  }
}
```

啟動 Claude Code CLI 時會自動載入專案的 MCP Server。

### 可用工具

| 工具 | 說明 |
|------|------|
| `query_project` | 查詢專案資訊 |
| `get_project_milestones` | 取得專案里程碑 |
| `get_project_meetings` | 取得會議記錄 |
| `get_project_members` | 取得專案成員 |
| `summarize_chat` | 取得 Line 群組聊天記錄 |

### 架構優勢

使用 FastMCP 的好處：

1. **定義一次**：工具用 `@mcp.tool()` 裝飾器定義，Schema 自動生成
2. **多處使用**：
   - Claude Code CLI：stdio 模式
   - Line Bot：直接呼叫 `execute_tool()`
   - 其他 MCP 客戶端：標準 MCP 協議
3. **型別安全**：參數型別自動驗證
4. **文件自動生成**：從 docstring 提取描述
