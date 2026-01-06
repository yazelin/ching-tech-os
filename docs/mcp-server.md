# MCP Server 說明

擎添工業 OS 的 MCP (Model Context Protocol) Server，使用 FastMCP 實作。

## 概述

MCP Server 提供一組 AI 工具，可供：
- Claude Code CLI（透過 stdio 模式）
- Line Bot AI 助理（直接呼叫）
- 其他 MCP 客戶端

## 設定

### Claude Code CLI

在專案根目錄的 `.mcp.json` 設定：

```json
{
  "mcpServers": {
    "ching-tech-os": {
      "command": "/home/ct/SDD/ching-tech-os/backend/.venv/bin/python",
      "args": ["-m", "ching_tech_os.mcp_cli"]
    }
  }
}
```

### 手動執行

```bash
cd backend
uv run python -m ching_tech_os.mcp_cli
```

## 可用工具

### 專案管理

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `query_project` | 查詢專案資訊 | `project_id`（UUID）, `keyword`（搜尋） |
| `create_project` | 建立新專案 | `name`（必填）, `description`, `start_date`, `end_date` |
| `add_project_member` | 新增專案成員 | `project_id`（必填）, `name`（必填）, `role`, `company`, `email`, `phone`, `notes`, `is_internal`（預設 True） |
| `add_project_milestone` | 新增專案里程碑 | `project_id`（必填）, `name`（必填）, `milestone_type`, `planned_date`, `actual_date`, `status`, `notes` |
| `get_project_milestones` | 取得專案里程碑 | `project_id`（必填）, `status`（過濾）, `limit` |
| `get_project_meetings` | 取得專案會議記錄 | `project_id`（必填）, `limit` |
| `get_project_members` | 取得專案成員 | `project_id`（必填）, `is_internal`（過濾） |

### 知識庫

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `search_knowledge` | 搜尋知識庫 | `query`（必填）, `project`, `category`, `limit` |
| `get_knowledge_item` | 取得知識庫文件完整內容 | `kb_id`（必填，如 kb-001） |
| `update_knowledge_item` | 更新知識庫文件 | `kb_id`（必填）, `title`, `content`, `category`, `topics`, `projects`, `roles`, `level`, `type` |
| `delete_knowledge_item` | 刪除知識庫文件 | `kb_id`（必填） |
| `add_note` | 新增筆記到知識庫 | `title`（必填）, `content`（必填）, `category`, `topics`, `project` |
| `add_note_with_attachments` | 新增筆記並加入附件 | `title`（必填）, `content`（必填）, `attachments`（必填，NAS 路徑列表）, `category`, `topics`, `project` |

### 知識庫附件

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_attachments_to_knowledge` | 為現有知識新增附件 | `kb_id`（必填）, `attachments`（必填，NAS 路徑列表）, `descriptions`（附件描述列表） |
| `get_knowledge_attachments` | 取得知識庫附件列表 | `kb_id`（必填） |
| `update_knowledge_attachment` | 更新附件說明 | `kb_id`（必填）, `attachment_index`（必填）, `description` |

### Line Bot

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `summarize_chat` | 取得群組聊天記錄 | `line_group_id`（必填）, `hours`, `max_messages` |
| `get_message_attachments` | 查詢對話中的附件 | `line_user_id`, `line_group_id`, `days`, `file_type`, `limit` |

### 分享功能

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `create_share_link` | 建立公開分享連結 | `resource_type`（必填，knowledge 或 project）, `resource_id`（必填）, `expires_in`（1h/24h/7d/null） |

## 使用範例

### 透過 Claude Code CLI

```bash
# 確保 .mcp.json 已設定
claude "查詢最近的專案"
claude "建立一個新專案叫做「測試專案」"
claude "幫我搜尋知識庫中關於水切爐的資料"
```

Claude 會自動使用對應的 MCP 工具執行操作。

### 透過程式碼呼叫

```python
from ching_tech_os.services.mcp_server import get_mcp_tools, execute_tool

# 取得工具列表（符合 Claude API 格式）
tools = await get_mcp_tools()

# 執行工具
result = await execute_tool("query_project", {"keyword": "測試"})
print(result)

# 建立專案
result = await execute_tool("create_project", {
    "name": "新專案",
    "description": "專案描述",
    "start_date": "2026-01-01"
})

# 新增成員
result = await execute_tool("add_project_member", {
    "project_id": "uuid-here",
    "name": "張三",
    "role": "專案經理",
    "is_internal": True
})
```

## 架構說明

### 檔案結構

```
backend/src/ching_tech_os/
├── mcp_cli.py              # CLI 入口點
└── services/
    └── mcp_server.py       # MCP Server 實作
```

### 工具定義方式

使用 FastMCP 的 decorator 定義工具：

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ching-tech-os")

@mcp.tool()
async def my_tool(param1: str, param2: int = 10) -> str:
    """
    工具說明

    Args:
        param1: 參數1說明
        param2: 參數2說明，預設 10
    """
    return f"結果: {param1}, {param2}"
```

Schema 會自動從 type hints 和 docstring 生成。

### 工具存取介面

`mcp_server.py` 提供以下函數供其他服務使用：

- `get_mcp_tools()` - 取得工具定義列表（符合 Claude API 格式）
- `get_mcp_tool_names(exclude_group_only)` - 取得工具名稱列表
- `execute_tool(tool_name, arguments)` - 執行工具

這讓 Line Bot AI 和其他服務可以直接呼叫工具，無需透過 MCP 協議。

## 新增工具

1. 在 `mcp_server.py` 中使用 `@mcp.tool()` 裝飾器定義函數
2. 使用 type hints 定義參數類型
3. 在 docstring 中描述工具和參數
4. 如果需要資料庫連線，使用 `await ensure_db_connection()`
5. 更新 `linebot_agents.py` 中的 prompt（讓 Line Bot AI 知道新工具）
6. 更新 `013_update_linebot_prompts.py` migration
7. 執行 SQL 更新資料庫中的 prompt

範例：

```python
@mcp.tool()
async def my_new_tool(
    required_param: str,
    optional_param: int = 5,
) -> str:
    """
    工具功能說明

    Args:
        required_param: 必填參數說明
        optional_param: 選填參數說明，預設 5
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        # 執行資料庫查詢
        ...
    return "結果"
```
