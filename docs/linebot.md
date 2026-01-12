# Line Bot 整合

Line Bot 整合功能，實現 Line 訊息儲存、AI 助理回應、知識庫管理與公開分享。

## 架構

```
Line Platform
     │
     ▼ Webhook
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI                                                         │
│  ┌─────────────┐    ┌─────────────────────────────────────────┐ │
│  │ linebot_    │    │ linebot_ai.py                           │ │
│  │ router.py   │───▶│ - process_message_with_ai               │ │
│  │ - webhook   │    │ - call_claude_with_tools                │ │
│  └─────────────┘    └──────────────┬──────────────────────────┘ │
│         │                          │                             │
│         ▼                          ▼                             │
│  ┌─────────────┐    ┌─────────────────────────────────────────┐ │
│  │ linebot.py  │    │ mcp_server.py                           │ │
│  │ - 儲存訊息  │    │ - 專案：query/create/add_member/...     │ │
│  │ - 用戶管理  │    │ - 知識庫：search/get/update/add_note/...│ │
│  │ - 群組管理  │    │ - 附件：add/get/update_attachment       │ │
│  │ - 檔案儲存  │    │ - NAS：search_nas_files/prepare_file    │ │
│  │ - 回覆訊息  │    │ - 分享：create_share_link               │ │
│  └─────────────┘    └─────────────────────────────────────────┘ │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐    ┌─────────────┐                             │
│  │ PostgreSQL  │    │ NAS 檔案    │                             │
│  │ line_*      │    │ 附件儲存    │                             │
│  └─────────────┘    └─────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

## 功能總覽

| 功能 | 說明 |
|------|------|
| 訊息儲存 | 自動儲存所有群組/個人訊息到資料庫 |
| 檔案儲存 | 圖片、檔案自動下載到 NAS |
| AI 對話 | 個人/群組對話支援 AI 助理 |
| 專案管理 | 透過對話建立專案、新增成員和里程碑 |
| 知識庫 | 透過對話新增筆記、搜尋知識、管理附件 |
| NAS 檔案搜尋 | 搜尋並發送 NAS 共享檔案（圖片直接發送） |
| 公開分享 | 建立知識庫/專案/檔案的公開連結分享給外部人員 |

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
| file_type | VARCHAR(32) | 檔案類型（image/file/video/audio） |
| file_name | VARCHAR(256) | 原始檔名 |
| file_size | BIGINT | 檔案大小 |
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
DELETE /api/linebot/groups/{group_id}
```

> **刪除群組**：刪除群組會級聯刪除相關訊息（`line_messages`）和檔案記錄（`line_files`），但 NAS 實體檔案不會被刪除。

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
- **群組對話**：Bot 被 @ 提及、或回覆 Bot 訊息時觸發

### Agent 設定

系統預設兩個 Line Bot Agent（儲存在 `ai_agents` 表）：

| Agent | 模型 | 用途 |
|-------|------|------|
| `linebot-personal` | claude-sonnet | 個人對話，完整 prompt |
| `linebot-group` | claude-haiku | 群組對話，精簡 prompt |

Prompt 內容可透過「AI 管理」應用程式修改。

### 對話歷史

- 每個用戶/群組維護獨立的對話歷史
- 對話歷史儲存在 `ai_conversations` 和 `ai_conversation_messages` 表
- 用戶可發送 `/新對話` 或 `/reset` 清除歷史

### MCP 工具

AI 助理可使用的工具（完整列表見 [docs/mcp-server.md](mcp-server.md)）：

**專案管理**
- `query_project` - 查詢專案
- `create_project` - 建立專案
- `add_project_member` - 新增成員（is_internal 預設 True，外部人員設 False）
- `add_project_milestone` - 新增里程碑
- `get_project_milestones` / `get_project_meetings` / `get_project_members` - 查詢

**知識庫**
- `search_knowledge` - 搜尋知識庫
- `get_knowledge_item` - 取得完整內容
- `update_knowledge_item` - 更新知識（可更新標題、內容、標籤、類型、層級等）
- `delete_knowledge_item` - 刪除知識
- `add_note` - 新增純文字筆記（自動判定 scope）
- `add_note_with_attachments` - 新增筆記並加入附件（自動判定 scope）

> **知識庫 Scope 自動判定**：透過 Line Bot 建立的知識會根據對話來源自動設定 scope：
> - **個人對話 + 已綁定 CTOS 帳號** → `personal`（僅建立者可編輯）
> - **群組對話 + 群組已綁定專案** → `project`（專案成員可編輯）
> - **其他情況** → `global`（全域，僅 global_write 權限可編輯）

**知識庫附件**
- `get_message_attachments` - 查詢對話中的附件（圖片、檔案）
- `add_attachments_to_knowledge` - 為現有知識新增附件
- `get_knowledge_attachments` - 查詢知識庫附件列表
- `update_knowledge_attachment` - 更新附件說明

**群組專用**
- `summarize_chat` - 取得群組聊天記錄摘要

**NAS 檔案搜尋**
- `search_nas_files` - 搜尋 NAS 共享檔案
- `get_nas_file_info` - 取得檔案詳細資訊
- `prepare_file_message` - 準備檔案訊息供回覆

**分享功能**
- `create_share_link` - 建立公開分享連結（支援知識庫、專案、NAS 檔案）

### 使用情境範例

**建立專案並新增成員**
```
用戶：幫我建立一個「水切爐改善」專案，成員有張三和李四
AI：（使用 create_project 建立專案）
AI：（使用 add_project_member 新增張三）
AI：（使用 add_project_member 新增李四）
AI：已建立專案「水切爐改善」，並新增成員張三、李四
```

**將對話中的圖片加入知識庫**
```
用戶：把剛剛那張圖加到知識庫，標題叫「水切爐改善方案」
AI：（使用 get_message_attachments 查詢最近的圖片）
AI：（使用 add_note_with_attachments 建立筆記並加入圖片）
AI：已建立知識「水切爐改善方案」並加入 1 張圖片
```

**建立分享連結**
```
用戶：幫我分享 kb-015 給客戶看
AI：（使用 create_share_link 建立連結）
AI：分享連結已建立！
    連結：https://xxx/share/abc123
    有效至 2026-01-07 19:00
```

**搜尋並發送 NAS 檔案**
```
用戶：給我亦達的 layout 圖
AI：（使用 search_nas_files 搜尋）
AI：（找到多個檔案，列出供用戶選擇）
用戶：第二個
AI：（使用 prepare_file_message 準備檔案）
AI：（直接發送圖片到 Line）
```

**發送多張圖片**
```
用戶：給我那個資料夾的圖
AI：（搜尋找到 10 張圖片）
AI：這個資料夾有 10 張圖，我先傳 4 張給你看，其他的附上連結：
AI：（發送 4 張 ImageMessage + 文字訊息含 6 個連結）
```

## 設定

### 環境變數

```bash
# Line Bot 設定
CHING_TECH_LINE_CHANNEL_SECRET=your_channel_secret
CHING_TECH_LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token

# NAS 設定（附件儲存）
CHING_TECH_LINEBOT_NAS_HOST=192.168.1.xxx
CHING_TECH_LINEBOT_NAS_USER=username
CHING_TECH_LINEBOT_NAS_PASSWORD=password
CHING_TECH_LINEBOT_NAS_SHARE=share_name
CHING_TECH_LINEBOT_NAS_PATH=linebot/files
```

### Line Developers Console 設定

1. 建立 Messaging API Channel
2. 設定 Webhook URL: `https://your-domain/api/linebot/webhook`
3. 啟用 Webhook
4. 取得 Channel Secret 和 Channel Access Token

## 前端介面

桌面應用程式「Line Bot」提供：

- **群組標籤頁**：群組列表、專案綁定、最近訊息
- **用戶標籤頁**：用戶列表、系統帳號綁定
- **訊息標籤頁**：訊息瀏覽、群組篩選、附件預覽

## 檔案儲存

Line Bot 收到的檔案會自動下載並儲存到 NAS：

```
NAS/{linebot_path}/
├── {year}/
│   └── {month}/
│       ├── {uuid}_image.jpg
│       ├── {uuid}_document.pdf
│       └── ...
```

檔案路徑記錄在 `line_files.nas_path`，可透過 `get_message_attachments` 工具查詢。

## 執行 Migration

```bash
cd backend
uv run alembic upgrade head
```

## Claude Code CLI 整合

MCP Server 使用 FastMCP 實作，支援 Claude Code CLI 使用。詳見 [docs/mcp-server.md](mcp-server.md)。

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
