# AI 管理系統

AI 管理系統提供 Prompts、Agents、Logs 的管理功能，以及統一的 AI 調用介面。

## 架構概覽

```
┌─────────────────────────────────────────────────────────────┐
│                     前端應用                                  │
├─────────────────┬─────────────────┬─────────────────────────┤
│   AI 對話        │  Prompt 編輯器  │  Agent 設定   │ AI Log   │
│ (ai-assistant)  │ (prompt-editor) │(agent-settings)│(ai-log)  │
└────────┬────────┴────────┬────────┴────────┬───────┴────┬────┘
         │                 │                 │            │
         ▼                 ▼                 ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                      REST API                                │
│  /api/ai/chats    /api/ai/prompts   /api/ai/agents  /api/ai/logs
└─────────────────────────────────────────────────────────────┘
         │                 │                 │            │
         ▼                 ▼                 ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Services                                 │
│   ai_chat.py         ai_manager.py        claude_agent.py   │
└─────────────────────────────────────────────────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL                               │
│    ai_chats        ai_prompts      ai_agents      ai_logs   │
└─────────────────────────────────────────────────────────────┘
```

## 資料表結構

### ai_prompts

System prompts 的儲存表。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 主鍵 |
| name | VARCHAR(100) | 唯一識別名稱 |
| display_name | VARCHAR(200) | 顯示名稱 |
| category | VARCHAR(50) | 分類（system, task, custom） |
| content | TEXT | Prompt 內容 |
| description | TEXT | 說明 |
| variables | JSONB | 可替換變數定義 |
| created_at | TIMESTAMP | 建立時間 |
| updated_at | TIMESTAMP | 更新時間 |

### ai_agents

AI Agent 設定表，每個 Agent 綁定一個 System Prompt。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 主鍵 |
| name | VARCHAR(100) | 唯一識別名稱 |
| display_name | VARCHAR(200) | 顯示名稱 |
| description | TEXT | 說明 |
| model | VARCHAR(50) | 使用的模型（如 claude-sonnet） |
| system_prompt_id | UUID | 關聯的 Prompt（FK） |
| is_active | BOOLEAN | 是否啟用 |
| settings | JSONB | 額外設定（如 temperature） |
| created_at | TIMESTAMP | 建立時間 |
| updated_at | TIMESTAMP | 更新時間 |

### ai_logs（分區表）

AI 調用記錄，使用月份分區。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 主鍵 |
| agent_id | UUID | 使用的 Agent（FK） |
| prompt_id | UUID | 使用的 Prompt（FK） |
| context_type | VARCHAR(50) | 調用情境（web-chat, linebot, test） |
| context_id | VARCHAR(100) | 情境 ID（如 chat_id） |
| input_prompt | TEXT | 輸入訊息 |
| raw_response | TEXT | 原始回應 |
| parsed_response | JSONB | 解析後的回應 |
| model | VARCHAR(50) | 實際使用的模型 |
| success | BOOLEAN | 是否成功 |
| error_message | TEXT | 錯誤訊息 |
| duration_ms | INTEGER | 執行時間（毫秒） |
| input_tokens | INTEGER | 輸入 tokens |
| output_tokens | INTEGER | 輸出 tokens |
| created_at | TIMESTAMP | 建立時間 |

## 預設資料

### Prompts

| name | display_name | category |
|------|--------------|----------|
| web-chat-default | 預設對話助手 | system |
| web-chat-code | 程式碼助手 | system |
| linebot-group | Line 群組助手 | system |
| linebot-personal | Line 個人助理 | system |
| system-task | 系統任務 | task |

### Agents

| name | display_name | model | prompt |
|------|--------------|-------|--------|
| web-chat-default | 預設對話 | claude-sonnet | web-chat-default |
| web-chat-code | 程式碼助手 | claude-sonnet | web-chat-code |
| linebot-group | Line 群組 | claude-haiku | linebot-group |
| linebot-personal | Line 個人助理 | claude-sonnet | linebot-personal |
| system-scheduler | 系統排程 | claude-haiku | system-task |

## 服務函數

### ai_manager.py

#### 統一 AI 調用

```python
async def call_agent(
    agent_name: str,
    message: str,
    context_type: str | None = None,
    context_id: str | None = None,
    history: list[dict] | None = None,
) -> dict:
    """
    透過 Agent 調用 AI，自動記錄 Log。

    Returns:
        {
            "success": bool,
            "response": str | None,
            "error": str | None,
            "duration_ms": int | None,
            "log_id": UUID | None
        }
    """
```

使用範例：

```python
from ching_tech_os.services import ai_manager

result = await ai_manager.call_agent(
    agent_name="web-chat-default",
    message="你好，請問今天天氣如何？",
    context_type="web-chat",
    context_id="chat-123",
    history=[
        {"role": "user", "content": "之前的對話"},
        {"role": "assistant", "content": "之前的回應"}
    ]
)

if result["success"]:
    print(result["response"])
else:
    print(f"Error: {result['error']}")
```

### ai_chat.py

#### Agent 查詢函數

```python
async def get_available_agents() -> list[dict]:
    """取得可用的 Agent 列表（從資料庫，僅返回 is_active=true）"""

async def get_agent_system_prompt(agent_name: str) -> str | None:
    """取得 Agent 的 system prompt 內容

    Args:
        agent_name: Agent 名稱

    Returns:
        System prompt 內容，若 Agent 不存在或無設定 prompt 則返回 None
    """

async def get_agent_config(agent_name: str) -> dict | None:
    """取得 Agent 完整設定（model、system_prompt、settings 等）

    Returns:
        {
            "id": UUID,
            "name": str,
            "display_name": str,
            "model": str,
            "is_active": bool,
            "settings": dict | None,
            "system_prompt": str | None
        }
    """
```

## 前端應用

### Prompt 編輯器

- 檔案：`js/prompt-editor.js`, `css/prompt-editor.css`
- 功能：
  - 左側 Prompt 列表（支援分類過濾）
  - 右側編輯表單
  - 新增、儲存、刪除功能
  - Category 標籤切換

### Agent 設定

- 檔案：`js/agent-settings.js`, `css/agent-settings.css`
- 功能：
  - 左側 Agent 列表（含啟用狀態指示）
  - 右側編輯表單
  - Model 選擇（claude-sonnet, claude-haiku, claude-opus）
  - Prompt 選擇下拉選單
  - 啟用/停用開關
  - 測試功能

### AI Log

- 檔案：`js/ai-log.js`, `css/ai-log.css`
- 功能：
  - 過濾器（Agent、context_type、成功/失敗、日期範圍）
  - 統計卡片（總次數、成功率、平均耗時）
  - Log 列表（分頁）
  - Log 詳情面板

## 分區表管理

`ai_logs` 使用 PostgreSQL 原生分區，按月份分區以優化查詢效能。

### 自動分區

Migration 會建立分區管理函數 `create_ai_logs_partition()`，可自動建立當月與下月的分區。

```sql
SELECT create_ai_logs_partition();
```

### 手動建立分區

```sql
CREATE TABLE ai_logs_2025_01 PARTITION OF ai_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

## Migration

```bash
# 執行 migration（包含 AI 管理相關表）
cd backend && uv run alembic upgrade head
```

Migration 檔案：`007_create_ai_management.py`
