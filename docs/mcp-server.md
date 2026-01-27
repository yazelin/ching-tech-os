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
| `update_project` ⚠️ | 更新專案資訊 | `project_id`（必填）, `ctos_user_id`（必填）, `name`, `description`, `status`, `start_date`, `end_date` |
| `add_project_member` | 新增專案成員 | `project_id`（必填）, `name`（必填）, `role`, `company`, `email`, `phone`, `notes`, `is_internal`（預設 True）, `ctos_user_id`（自動綁定） |
| `update_project_member` ⚠️ | 更新成員資訊 | `member_id`（必填）, `ctos_user_id`（必填）, `project_id`, `name`, `role`, `company`, `email`, `phone`, `notes`, `is_internal`, `bind_to_caller` |
| `add_project_milestone` | 新增專案里程碑 | `project_id`（必填）, `name`（必填）, `milestone_type`, `planned_date`, `actual_date`, `status`, `notes` |
| `update_milestone` ⚠️ | 更新里程碑 | `milestone_id`（必填）, `ctos_user_id`（必填）, `project_id`, `name`, `milestone_type`, `planned_date`, `actual_date`, `status`, `notes` |
| `get_project_milestones` | 取得專案里程碑 | `project_id`（必填）, `status`（過濾）, `limit` |
| `add_project_meeting` ⚠️ | 新增會議記錄 | `project_id`（必填）, `title`（必填）, `ctos_user_id`（必填）, `meeting_date`, `location`, `attendees`, `content` |
| `update_project_meeting` ⚠️ | 更新會議記錄 | `meeting_id`（必填）, `ctos_user_id`（必填）, `project_id`, `title`, `meeting_date`, `location`, `attendees`, `content` |
| `get_project_meetings` | 取得專案會議記錄 | `project_id`（必填）, `limit` |
| `get_project_members` | 取得專案成員 | `project_id`（必填）, `is_internal`（過濾） |

> ⚠️ 標記的工具需要權限控制，必須傳入 `ctos_user_id` 參數，且只有專案成員才能操作。

### 專案連結

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_project_link` | 新增專案連結 | `project_id`（必填）, `title`（必填）, `url`（必填）, `description` |
| `get_project_links` | 取得專案連結列表 | `project_id`（必填）, `limit` |
| `update_project_link` | 更新專案連結 | `link_id`（必填）, `project_id`, `title`, `url`, `description` |
| `delete_project_link` | 刪除專案連結 | `link_id`（必填）, `project_id` |

### 專案附件

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_project_attachment` | 從 NAS 路徑添加附件到專案 | `project_id`（必填）, `nas_path`（必填，從 get_message_attachments 或 search_nas_files 取得）, `description` |
| `get_project_attachments` | 取得專案附件列表 | `project_id`（必填）, `limit` |
| `update_project_attachment` | 更新專案附件描述 | `attachment_id`（必填）, `project_id`, `description` |
| `delete_project_attachment` | 刪除專案附件 | `attachment_id`（必填）, `project_id` |

### 發包期程

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_delivery_schedule` | 新增發包記錄 | `project_id`（必填）, `vendor`（必填，廠商名稱）, `item`（必填，料件名稱）, `quantity`, `order_date`, `expected_delivery_date`, `status`（pending/ordered/delivered/completed）, `notes` |
| `update_delivery_schedule` | 更新發包記錄 | `delivery_id` 或 `project_id` + `vendor` + `item`（模糊匹配）, `status`, `actual_delivery_date`, `expected_delivery_date`, `quantity`, `notes` |
| `get_delivery_schedules` | 查詢發包列表 | `project_id`（必填）, `status`（過濾）, `vendor`（過濾）, `limit` |

### 物料/庫存管理

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `query_inventory` | 查詢物料/庫存 | `keyword`（搜尋名稱、型號或規格）, `item_id`（查詢特定物料詳情）, `category`（類別過濾）, `vendor`（廠商過濾）, `low_stock`（只顯示庫存不足）, `limit` |
| `add_inventory_item` | 新增物料 | `name`（必填）, `model`（型號）, `specification`（規格）, `unit`（單位）, `category`（類別）, `default_vendor`（預設廠商）, `storage_location`（存放庫位，如 A-1-3）, `min_stock`（最低庫存量）, `notes` |
| `update_inventory_item` | 更新物料資訊 | `item_id` 或 `item_name`（擇一）, `name`, `model`, `specification`, `unit`, `category`, `default_vendor`, `storage_location`, `min_stock`, `notes` |
| `record_inventory_in` | 記錄進貨 | `quantity`（必填）, `item_id` 或 `item_name`（擇一）, `vendor`（廠商）, `project_id` 或 `project_name`（關聯專案）, `transaction_date`, `notes` |
| `record_inventory_out` | 記錄出貨/領料 | `quantity`（必填）, `item_id` 或 `item_name`（擇一）, `project_id` 或 `project_name`（關聯專案）, `transaction_date`, `notes` |
| `adjust_inventory` | 庫存調整（盤點校正） | `new_quantity`（必填）, `reason`（必填，如「盤點調整」）, `item_id` 或 `item_name`（擇一） |

> **庫存低量警示**：當物料設定了 `min_stock` 且目前庫存低於此值，`query_inventory` 會顯示 ⚠️ 警示。使用 `low_stock=true` 可只查詢庫存不足的物料。

### 訂購記錄

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_inventory_order` | 新增訂購記錄 | `order_quantity`（必填）, `item_id` 或 `item_name`（擇一）, `order_date`, `expected_delivery_date`, `vendor`, `project_id` 或 `project_name`, `notes` |
| `update_inventory_order` | 更新訂購記錄 | `order_id`（必填）, `order_quantity`, `order_date`, `expected_delivery_date`, `actual_delivery_date`, `status`（pending/ordered/delivered/cancelled）, `vendor`, `project_id`, `notes` |
| `get_inventory_orders` | 查詢訂購記錄 | `item_id` 或 `item_name`（擇一）, `status`（過濾）, `limit` |

### 知識庫

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `search_knowledge` | 搜尋知識庫 | `query`（必填）, `project`, `category`, `limit`, `ctos_user_id`（傳入可搜尋個人知識） |
| `get_knowledge_item` | 取得知識庫文件完整內容 | `kb_id`（必填，如 kb-001） |
| `update_knowledge_item` | 更新知識庫文件 | `kb_id`（必填）, `title`, `content`, `category`, `scope`（global/personal）, `topics`, `projects`, `roles`, `level`, `type`, `ctos_user_id`（改為 personal 時必填） |
| `delete_knowledge_item` | 刪除知識庫文件 | `kb_id`（必填） |
| `add_note` | 新增筆記到知識庫 | `title`（必填）, `content`（必填）, `category`, `topics`, `project`, `line_group_id`, `line_user_id`, `ctos_user_id` |
| `add_note_with_attachments` | 新增筆記並加入附件 | `title`（必填）, `content`（必填）, `attachments`（必填，NAS 路徑列表）, `category`, `topics`, `project`, `line_group_id`, `line_user_id`, `ctos_user_id` |

> **知識庫 Scope 自動判定**：`add_note` 和 `add_note_with_attachments` 會根據對話來源參數自動設定 scope：
> - `line_user_id` + `ctos_user_id`（已綁定）→ `personal`（個人知識）
> - `line_group_id` + 群組已綁定專案 → `project`（專案知識）
> - 其他情況 → `global`（全域知識）

### 知識庫附件

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_attachments_to_knowledge` | 為現有知識新增附件 | `kb_id`（必填）, `attachments`（必填，NAS 路徑列表）, `descriptions`（附件描述列表） |
| `get_knowledge_attachments` | 取得知識庫附件列表 | `kb_id`（必填） |
| `update_knowledge_attachment` | 更新附件說明 | `kb_id`（必填）, `attachment_index`（必填）, `description` |
| `read_knowledge_attachment` | 讀取知識庫附件的文字內容 | `kb_id`（必填）, `attachment_index`（預設 0）, `max_chars`（預設 15000） |

> **附件內容讀取**：`read_knowledge_attachment` 可讀取 Word/Excel/PowerPoint/PDF 等文件格式的附件內容，方便 AI 分析或回答問題。

### Line Bot

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `summarize_chat` | 取得群組聊天記錄 | `line_group_id`（必填）, `hours`, `max_messages` |
| `get_message_attachments` | 查詢對話中的附件 | `line_user_id`, `line_group_id`, `days`, `file_type`, `limit` |

### 自訂記憶

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_memory` | 新增自訂記憶 | `content`（必填）, `title`（選填，會自動產生）, `line_group_id`, `line_user_id` |
| `get_memories` | 查詢記憶列表 | `line_group_id`, `line_user_id` |
| `update_memory` | 更新記憶 | `memory_id`（必填）, `title`, `content`, `is_active`（啟用/停用） |
| `delete_memory` | 刪除記憶 | `memory_id`（必填） |

> **自訂記憶**：用戶可以設定自訂記憶讓 AI 記住特定指示（如回覆風格、稱呼方式等）。每個群組/用戶的記憶獨立管理，可隨時啟用或停用。

### NAS 檔案

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `search_nas_files` | 搜尋 NAS 共享檔案 | `keywords`（必填，逗號分隔）, `file_types`（副檔名，如 pdf,xlsx）, `limit` |
| `get_nas_file_info` | 取得 NAS 檔案詳細資訊 | `file_path`（必填，/mnt/nas/projects/... 路徑） |
| `read_document` | 讀取文件內容（Word/Excel/PowerPoint/PDF） | `file_path`（必填）, `max_chars`（預設 50000） |
| `prepare_file_message` | 準備檔案訊息供 Line Bot 回覆 | `file_path`（必填） |

> **文件讀取支援格式**：`read_document` 可讀取 `.docx`、`.xlsx`、`.pptx`、`.pdf` 檔案，將內容轉為純文字供 AI 分析。不支援舊版格式（`.doc`、`.xls`、`.ppt`）和加密文件。

### 分享功能

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `create_share_link` | 建立公開分享連結 | `resource_type`（必填，knowledge/project/nas_file/project_attachment/content）, `resource_id`（必填）, `expires_in`（1h/24h/7d/null）, `password`（選填，4 位數密碼） |
| `share_knowledge_attachment` | 分享知識庫附件（.md2ppt/.md2doc） | `kb_id`（必填，如 kb-001）, `attachment_idx`（必填，附件索引從 0 開始）, `expires_in`（1h/24h/7d/null） |

> **密碼保護**：分享連結可設定 4 位數密碼保護，5 次輸入錯誤後將鎖定 30 分鐘。

### 簡報生成

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `generate_presentation` | 生成 PowerPoint 簡報 | `topic`, `num_slides`, `style`, `include_images`, `image_source`, `outline_json`, `design_json` |

#### 基本用法（指定主題）

```python
result = await execute_tool("generate_presentation", {
    "topic": "AI 在製造業的應用",
    "num_slides": 5,
    "style": "tech",          # professional/casual/creative/minimal/dark/tech/nature/warm/elegant
    "include_images": True,
    "image_source": "pexels"  # pexels/huggingface/nanobanana
})
```

#### 進階用法（自訂設計）

使用 `design_json` 參數可完全自訂簡報的視覺設計：

```python
design_json = {
    "design": {
        "colors": {
            "background": "#0D1117",      # 深空藍背景
            "title": "#58A6FF",           # 亮藍標題
            "subtitle": "#A371F7",        # 電紫副標題
            "text": "#C9D1D9",            # 淺藍白內文
            "bullet": "#A371F7",          # 項目符號顏色
            "accent": "#A371F7"           # 強調色
        },
        "typography": {
            "title_font": "Noto Sans TC",
            "title_size": 44,
            "title_bold": True,
            "body_font": "Noto Sans TC",
            "body_size": 20
        },
        "layout": {
            "title_align": "left",        # left/center
            "image_position": "right",    # left/right/bottom
            "image_size": "medium"        # small/medium/large
        },
        "decorations": {
            "title_underline": True,
            "title_underline_color": "#A371F7",
            "accent_bar_left": False,
            "page_number": True,
            "page_number_position": "bottom-right"
        }
    },
    "slides": [
        {"type": "title", "title": "主標題", "subtitle": "副標題"},
        {"type": "content", "title": "章節標題", "content": ["重點1", "重點2"], "image_keyword": "technology"}
    ]
}

result = await execute_tool("generate_presentation", {
    "design_json": json.dumps(design_json),
    "include_images": True
})
```

#### 預設風格

| 風格 | 說明 | 適用場景 |
|------|------|----------|
| `professional` | 淺藍灰背景、深海軍藍標題 | 客戶提案、正式報告 |
| `casual` | 花白背景、森林綠標題 | 內部分享、教育訓練 |
| `creative` | 淡紫背景、紫羅蘭標題 | 創意提案、品牌展示 |
| `minimal` | 純白背景、近黑標題 | 技術文件、學術報告 |
| `dark` | 深藍黑背景、淺灰白標題 | 投影展示、晚間活動 |
| `tech` | 深空藍背景、青色標題 | 科技新創、產品發布 |
| `nature` | 薄荷白背景、深森林綠標題 | 環保、健康主題 |
| `warm` | 奶油白背景、磚紅標題 | 激勵演講、活動推廣 |
| `elegant` | 象牙白背景、深金棕標題 | 奢華品牌、高端提案 |

### MD2PPT/MD2DOC 文件轉換

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `generate_md2ppt` | 產生 MD2PPT 格式簡報 | `content`（必填，要轉換的內容或主題）, `style`（選填，風格需求如「科技藍」「簡約深色」） |
| `generate_md2doc` | 產生 MD2DOC 格式文件 | `content`（必填，要轉換的內容） |

> **與 generate_presentation 的差異**：
> - `generate_presentation`：直接生成 PowerPoint 檔案（使用 Marp）
> - `generate_md2ppt`：產生可線上編輯的 MD2PPT 格式內容，透過分享連結在 MD2PPT 網站編輯後匯出 PPTX
>
> MD2PPT/MD2DOC 的優勢：
> - 可線上即時編輯內容
> - 支援更豐富的排版功能（圖表、雙欄、動畫等）
> - 可匯出為多種格式（PPTX、Word、PDF）

#### 使用範例

```python
# 產生簡報
result = await execute_tool("generate_md2ppt", {
    "content": "介紹我們公司的 AI 解決方案，包含產品特色和應用案例",
    "style": "科技藍"
})
# 回傳：分享連結 + 4 位數密碼

# 產生文件
result = await execute_tool("generate_md2doc", {
    "content": "撰寫設備操作 SOP，包含開機、操作流程、關機步驟"
})
# 回傳：分享連結 + 4 位數密碼
```

### AI 圖片生成（外部 MCP Server）

透過 nanobanana MCP Server（使用 Google Gemini API）提供 AI 圖片生成功能：

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `mcp__nanobanana__generate_image` | 根據文字描述生成圖片 | `prompt`（必填，英文描述效果較好）, `files`（參考圖片路徑）, `resolution`（固定 "1K"） |
| `mcp__nanobanana__edit_image` | 編輯/修改現有圖片 | `file`（必填，圖片路徑）, `prompt`（必填，編輯指示）, `resolution`（固定 "1K"） |

> 設定方式請參考 [docs/linebot.md](linebot.md#ai-圖片生成設定)

## 使用範例

### 透過 Claude Code CLI

```bash
# 確保 .mcp.json 已設定
claude "查詢最近的專案"
claude "建立一個新專案叫做「測試專案」"
claude "幫我搜尋知識庫中關於水切爐的資料"
claude "找一下亦達 layout 的 pdf"
claude "畫一隻可愛的貓"  # AI 圖片生成（需設定 nanobanana）
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

## 權限控制

標記 ⚠️ 的工具需要權限控制：

### 機制說明

1. **用戶關聯**：Line 用戶透過 `line_users.user_id` 關聯到 CTOS 用戶
2. **成員關聯**：專案成員透過 `project_members.user_id` 關聯到 CTOS 用戶
3. **權限檢查**：呼叫工具時傳入 `ctos_user_id`，系統檢查該用戶是否為專案成員

### 錯誤訊息

- 未關聯 CTOS 帳號：「請聯繫管理員關聯帳號」
- 非專案成員：「您不是此專案的成員，無法進行此操作」

### 自動綁定

`add_project_member` 支援自動綁定功能：

```python
# 新增成員並自動綁定到呼叫者的 CTOS 帳號
result = await execute_tool("add_project_member", {
    "project_id": "uuid-here",
    "name": "張三",
    "is_internal": True,
    "ctos_user_id": 1  # 傳入 ctos_user_id 自動綁定
})
```

- 若已存在同名成員但未綁定，會自動完成綁定
- 綁定後該成員即可使用需要權限的工具

## 新增工具

1. 在 `mcp_server.py` 中使用 `@mcp.tool()` 裝飾器定義函數
2. 使用 type hints 定義參數類型
3. 在 docstring 中描述工具和參數
4. 如果需要資料庫連線，使用 `await ensure_db_connection()`
5. 如果需要權限控制，加入 `ctos_user_id` 參數並呼叫 `check_project_member_permission()`
6. 更新 `linebot_agents.py` 中的 prompt（讓 Line Bot AI 知道新工具）
7. 建立新的 migration 更新資料庫中的 prompt
8. 執行 `alembic upgrade head` 套用變更

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
