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
| name | VARCHAR(128) | 唯一識別名稱 |
| display_name | VARCHAR(256) | 顯示名稱 |
| category | VARCHAR(64) | 分類（system, task, template） |
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
| name | VARCHAR(64) | 唯一識別名稱 |
| display_name | VARCHAR(128) | 顯示名稱 |
| description | TEXT | 說明 |
| model | VARCHAR(32) | 使用的模型（如 claude-sonnet） |
| system_prompt_id | UUID | 關聯的 Prompt（FK） |
| is_active | BOOLEAN | 是否啟用 |
| tools | JSONB | 允許使用的工具列表（如 `["WebSearch", "WebFetch"]`） |
| settings | JSONB | 額外設定（見下方） |
| voice_settings | JSON | 語音設定（TTS 相關） |
| created_at | TIMESTAMP | 建立時間 |
| updated_at | TIMESTAMP | 更新時間 |

#### settings 欄位說明

`settings` JSONB 欄位依 Agent 類型有不同的用途：

**通用設定**：

| Key | 類型 | 說明 |
|-----|------|------|
| `user_selectable` | string | 設為 `"true"` 時，此 Agent 可透過 `/agent` 指令切換 |

**bot-restricted Agent 專用設定**：

| Key | 類型 | 說明 |
|-----|------|------|
| `welcome_message` | string | 未綁定用戶的歡迎訊息 |
| `binding_prompt` | string | 帳號綁定提示 |
| `rate_limit_hourly_msg` | string | 每小時限額提示 |
| `rate_limit_daily_msg` | string | 每日限額提示 |
| `disclaimer` | string | 免責聲明 |
| `error_message` | string | 錯誤回應訊息 |

### ai_logs（分區表）

AI 調用記錄，使用月份分區。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 主鍵 |
| agent_id | UUID | 使用的 Agent（FK） |
| prompt_id | UUID | 使用的 Prompt（FK） |
| context_type | VARCHAR(32) | 調用情境（見下方） |
| context_id | VARCHAR(64) | 情境 ID（如 chat_id） |
| input_prompt | TEXT | 輸入訊息 |
| system_prompt | TEXT | 實際使用的 system prompt 內容 |
| allowed_tools | JSON | 允許使用的工具列表 |
| raw_response | TEXT | 原始回應 |
| parsed_response | JSONB | 解析後的回應 |
| model | VARCHAR(32) | 實際使用的模型 |
| success | BOOLEAN | 是否成功 |
| error_message | TEXT | 錯誤訊息 |
| duration_ms | INTEGER | 執行時間（毫秒） |
| input_tokens | INTEGER | 輸入 tokens |
| output_tokens | INTEGER | 輸出 tokens |
| created_at | TIMESTAMP | 建立時間 |

#### context_type 值一覽

| context_type | 說明 |
|--------------|------|
| `web-chat` | Web 前端對話 |
| `linebot-group` | Line 群組對話 |
| `linebot-personal` | Line 個人對話 |
| `telegram-group` | Telegram 群組對話 |
| `telegram-personal` | Telegram 個人對話 |
| `scheduler` | 系統排程任務 |
| `script` | Skill Script 執行 |
| `compress` | 對話壓縮 |
| `bot-debug` | Bot Debug 模式 |
| `test` | Agent 測試 |

### bot_users / bot_groups Agent 偏好欄位

Bot 用戶和群組表透過以下欄位支援 Agent 偏好持久化：

| 欄位 | 類型 | 說明 |
|------|------|------|
| active_agent_id | UUID (FK → ai_agents) | 已綁定用戶的 Agent 偏好（`/agent` 指令設定） |
| restricted_agent_id | UUID (FK → ai_agents) | 未綁定用戶（受限模式）的 Agent 偏好（`/agent restricted` 指令設定） |

兩個欄位都設有 `ON DELETE SET NULL`，Agent 被刪除時自動清除偏好。

### bot_usage_tracking

追蹤未綁定用戶的訊息使用量，支援 rate limiting。

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | UUID | 主鍵 |
| bot_user_id | UUID (FK → bot_users) | Bot 用戶 ID |
| period_type | VARCHAR(10) | 時段類型（如 hourly, daily） |
| period_key | VARCHAR(20) | 時段鍵值 |
| message_count | INT | 訊息數量 |
| created_at | TIMESTAMPTZ | 建立時間 |
| updated_at | TIMESTAMPTZ | 更新時間 |

## Agent 偏好與路由機制

### 已綁定用戶 Agent 路由

Bot 對話時，已綁定用戶的 Agent 選擇遵循以下優先級：

1. **群組對話**：`bot_groups.active_agent_id` → 預設 `linebot-group`
2. **個人對話**：`bot_users.active_agent_id` → 預設 `linebot-personal`

如果偏好的 Agent 不存在或已停用，自動 fallback 到預設 Agent。

### 受限模式（未綁定用戶）Agent 路由

未綁定用戶使用受限模式，Agent 選擇遵循 fallback 鏈：

1. `bot_groups.restricted_agent_id`（群組設定）
2. 環境變數 `BOT_DEFAULT_RESTRICTED_AGENT`
3. 預設 `bot-restricted`

### `/agent` 指令

透過 Bot 的 `/agent` 指令管理 Agent 偏好：

| 指令 | 說明 |
|------|------|
| `/agent` | 顯示目前 Agent 和可切換清單 |
| `/agent <name>` | 用名稱切換 Agent |
| `/agent <number>` | 用編號切換 Agent |
| `/agent reset` | 恢復預設 Agent |
| `/agent restricted` | 顯示受限模式 Agent 和可切換清單（群組限定） |
| `/agent restricted <name/number>` | 切換受限模式 Agent（群組限定） |
| `/agent restricted reset` | 重置受限模式 Agent 為預設（群組限定） |

**可切換條件**：Agent 必須同時滿足 `is_active = true` 且 `settings->>'user_selectable' = 'true'`。

## 預設 Agents

### Bot 對話 Agents

| name | display_name | model | 說明 |
|------|--------------|-------|------|
| linebot-personal | Line 個人助理 | claude-sonnet | Line/Telegram 個人對話預設 Agent |
| linebot-group | Line 群組助理 | claude-haiku | Line/Telegram 群組對話預設 Agent |
| bot-restricted | 受限模式 | — | 未綁定用戶使用的 Agent |
| bot-debug | Debug 模式 | — | `/debug` 指令用的 Agent |

### Web 對話 Agents

| name | display_name | model | 說明 |
|------|--------------|-------|------|
| web-chat-default | 預設對話 | claude-sonnet | 前端對話預設 Agent |
| web-chat-code | 程式碼助手 | claude-sonnet | 程式碼相關問題 Agent |
| web-search | 網路搜尋 | claude-sonnet | 帶 WebSearch 工具的 Agent |

### 系統 Agents

| name | display_name | model | 說明 |
|------|--------------|-------|------|
| system-scheduler | 系統排程 | claude-haiku | 排程任務用 Agent |

### Extends 模組 Agents

Extends 子模組可透過 `contributes.yaml` 定義自己的 Agent，啟動時自動 seed。例如：

| name | display_name | 說明 |
|------|--------------|------|
| jfmskin-full | 杰膚美內部助理（CTHIS） | 含 HIS 系統查詢的內部 Agent |
| jfmskin-edu | 杰膚美衛教助理 | 對外衛教諮詢 Agent |

## 預設 Prompts

| name | display_name | category |
|------|--------------|----------|
| web-chat-default | 預設對話助手 | system |
| web-chat-code | 程式碼助手 | system |
| linebot-group | Line 群組助手 | system |
| linebot-personal | Line 個人助理 | system |
| system-task | 系統任務 | task |

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

#### 可切換 Agent 查詢

```python
async def get_selectable_agents() -> list[dict]:
    """取得可供 /agent 指令切換的 Agent 清單

    查詢 is_active=true 且 settings.user_selectable='true' 的 Agent，按 name 排序。
    """
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

### linebot_agents.py

#### Agent 偏好管理函數

```python
async def set_user_active_agent(bot_user_id: str, agent_id: str | None) -> None:
    """設定用戶的個人對話 Agent 偏好"""

async def set_group_active_agent(bot_group_id: str, agent_id: str | None) -> None:
    """設定群組的 Agent 偏好"""

async def get_user_active_agent_id(bot_user_id: str) -> str | None:
    """查詢用戶的 active_agent_id"""

async def get_group_active_agent_id(bot_group_id: str) -> str | None:
    """查詢群組的 active_agent_id"""

async def set_group_restricted_agent(bot_group_id: str, agent_id: str | None) -> None:
    """設定群組的受限模式 Agent 偏好"""

async def get_group_restricted_agent_id(bot_group_id: str) -> str | None:
    """查詢群組的 restricted_agent_id"""

async def get_restricted_agent(bot_group_id: str | None = None) -> dict | None:
    """取得受限模式使用的 Agent
    Fallback 鏈：群組 restricted_agent_id → 環境變數 → bot-restricted
    """

async def get_linebot_agent(
    is_group: bool,
    *,
    bot_user_id: str | None = None,
    bot_group_id: str | None = None,
) -> dict | None:
    """取得 Bot Agent 設定，支援偏好覆蓋
    路由：active_agent_id > 預設 linebot-group/linebot-personal
    """

async def ensure_default_linebot_agents() -> None:
    """確保預設的 Bot Agent 存在（啟動時呼叫）"""
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
  - 工具（Tools）選擇：WebSearch, WebFetch, Read, Write, Edit, Bash, Glob, Grep
  - 啟用/停用開關
  - 測試功能
  - Skills 管理分頁（已安裝 / Skills Hub）

### AI Log

- 檔案：`js/ai-log.js`, `css/ai-log.css`
- 功能：
  - 過濾器（Agent、context_type、成功/失敗、日期範圍）
  - context_type 過濾選項：Web 對話、Line 群組/個人、Telegram 群組/個人、系統、Script 執行、測試
  - 統計卡片（總次數、成功率、平均耗時）
  - Log 列表（分頁，可顯示 script 標籤和使用的工具）
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

相關 Migration 檔案：

| Migration | 說明 |
|-----------|------|
| `001_initial_schema.py` | 建立 ai_agents、ai_prompts、ai_logs 表 |
| `002_seed_data.py` | 載入預設 Prompt 和 Agent 種子資料 |
| `009_add_bot_usage_tracking.py` | 新增 bot_usage_tracking 表（rate limiting） |
| `010_add_bot_restricted_settings.py` | 設定 bot-restricted Agent 的 settings 預設值 |
| `011_add_active_agent_id.py` | bot_users/bot_groups 新增 active_agent_id 欄位 |
| `012_add_restricted_agent_id.py` | bot_users/bot_groups 新增 restricted_agent_id 欄位 |
| `017_voice_module_independence.py` | ai_agents 新增 voice_settings 欄位 |
