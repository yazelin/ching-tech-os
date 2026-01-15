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
| AI 圖片生成 | 根據文字描述生成圖片、編輯圖片 |
| 文件讀取 | 支援讀取 Word、Excel、PowerPoint、PDF 文件內容 |
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
- `read_document` - 讀取文件內容（Word/Excel/PowerPoint/PDF）

**分享功能**
- `create_share_link` - 建立公開分享連結（支援知識庫、專案、NAS 檔案）

**AI 圖片生成**（需設定 nanobanana MCP Server）
- `mcp__nanobanana__generate_image` - 根據文字描述生成圖片
- `mcp__nanobanana__edit_image` - 編輯/修改現有圖片

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

**AI 圖片生成**
```
用戶：畫一隻可愛的貓
AI：（使用 generate_image 生成圖片）
AI：（使用 prepare_file_message 準備發送）
AI：好的，我幫你畫了一隻貓 👇
AI：（顯示生成的圖片）
```

**編輯 AI 生成的圖片**
```
用戶：（回覆 Bot 發送的圖片）把背景改成藍色
AI：（查詢 line_files 取得原圖路徑）
AI：（使用 edit_image 編輯圖片）
AI：已修改背景顏色 👇
AI：（顯示編輯後的圖片）
```

**以圖生圖**
```
用戶：（回覆一張自己上傳的圖）畫類似風格的狗
AI：（取得用戶圖片路徑作為參考）
AI：（使用 generate_image 生成類似風格的圖）
AI：參考你的圖片風格畫了一隻狗 👇
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

### AI 圖片生成設定

需要設定 nanobanana MCP Server（使用 Google Gemini API）：

1. 在 `.mcp.json` 加入設定（參考 `.mcp.json.example`）：
```json
{
  "mcpServers": {
    "nanobanana": {
      "command": "npx",
      "args": ["-y", "@anthropics/create-mcp", "@willh/nano-banana-mcp"],
      "env": {
        "GOOGLE_GENERATIVE_AI_API_KEY": "your-gemini-api-key"
      }
    }
  }
}
```

2. 系統會自動建立 symlink 將生成圖片存到 NAS：
   - Symlink: `/tmp/ching-tech-os-cli/nanobanana-output`
   - 目標: `/mnt/nas/ctos/linebot/files/ai-images`

3. 生成的圖片會自動在 1 個月後清理（排程任務）

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

## 文件讀取

Line Bot 支援讀取常見文件格式的內容，讓 AI 可以進行總結、分析或查詢。

### 支援格式

| 格式 | 副檔名 | 說明 |
|------|--------|------|
| Word | .docx | 提取段落文字和表格內容 |
| Excel | .xlsx | 提取所有工作表的資料（以 \| 分隔欄位） |
| PowerPoint | .pptx | 提取所有投影片的文字內容 |
| PDF | .pdf | 提取文字層內容 |

> **舊版格式**：不支援 `.doc`、`.xls`、`.ppt` 舊版格式，上傳時會提示用戶轉存為新版格式。

### 使用方式

**用戶上傳文件到對話**
```
用戶：（上傳 report.docx）
用戶：幫我總結這份報告
AI：（自動讀取文件內容並分析）
AI：這份報告主要內容是...
```

**讀取 NAS 上的文件**
```
用戶：幫我看一下 NAS 上的那份 Excel
AI：（使用 search_nas_files 找到檔案）
AI：（使用 read_document 讀取內容）
AI：這份試算表包含 3 個工作表...
```

### 限制

- **檔案大小**：PDF/Word/PowerPoint 最大 10MB，Excel 最大 5MB
- **文字長度**：最大輸出 100,000 字元，超過會截斷
- **加密文件**：不支援有密碼保護的文件
- **純圖片 PDF**：掃描文件無法提取文字，建議截圖後上傳讓 AI 讀取

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
