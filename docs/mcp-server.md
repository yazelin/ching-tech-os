# MCP Server 說明

擎添工業 OS 的 MCP (Model Context Protocol) Server，使用 FastMCP 實作。

## 概述

MCP Server 提供一組 AI 工具，可供：
- Claude Code CLI（透過 stdio 模式）
- Line Bot AI 助理（直接呼叫）
- 其他 MCP 客戶端

## 近期重點（2026-03）

- MCP 工具已完成**模組化重構**：從單一 `mcp_server.py` 拆分為 `services/mcp/` 子模組，依功能分類為獨立檔案。
- 工具改為**條件載入**：`core` 工具（memory、message）永遠載入，其餘依 `ENABLED_MODULES` 判斷是否註冊。
- Skill 可透過 `contributes.mcp_tools` 動態掛入工具模組，不需改核心 static import。
- Extends 模組（如 `law`）也可透過 `contributes.yaml` 的 `mcp_tools` 欄位提供 in-process MCP 工具。
- Skills 路由策略預設為 `script-first`：優先執行 `run_skill_script`，必要時才走 MCP fallback。

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

## 架構說明

### 檔案結構

```
backend/src/ching_tech_os/
├── mcp_cli.py                  # CLI 入口點（stdio 模式）
└── services/
    ├── mcp_server.py           # 向後相容模組（re-export，過渡期保留）
    └── mcp/                    # MCP 工具模組（模組化架構）
        ├── __init__.py               # 模組入口：載入 core 工具、條件載入其他模組
        ├── server.py                 # FastMCP 實例、共用輔助函數、工具存取介面
        ├── knowledge_tools.py        # 知識庫工具（搜尋、新增、附件等）
        ├── media_tools.py            # 媒體工具（下載網路圖片/檔案、PDF 轉圖片）
        ├── memory_tools.py           # 自訂記憶工具（core，永遠載入）
        ├── message_tools.py          # 訊息相關工具（core，永遠載入）
        ├── nas_tools.py              # NAS 檔案工具（搜尋、讀取、發送、圖書館）
        ├── presentation_tools.py     # 簡報/文件生成、列印工具
        ├── scheduler_tools.py        # 排程管理工具
        ├── share_tools.py            # 分享連結工具
        ├── skill_script_tools.py     # AI Skills 腳本執行
        ├── voice_tools.py            # 語音合成工具（text_to_speech）
        └── web_tools.py              # 網頁擷取工具（browse_webpage）
```

### 模組載入機制

`__init__.py` 控制工具的載入流程：

1. **Core 工具**（永遠載入）：`memory_tools`、`message_tools`
2. **條件載入**（依 `ENABLED_MODULES`）：透過 `modules.py` 的 `mcp_module` 欄位指定，如 `knowledge_tools`、`nas_tools` 等
3. **無條件載入**：`voice_tools`、`web_tools`（獨立於模組系統，載入失敗不影響其他工具）
4. **Skill MCP 工具**：Skill 透過 `contributes.yaml` 的 `mcp_tools` 欄位提供工具模組，動態載入
5. **Extends MCP 工具**：Extends 模組（如 `law`）透過 `contributes.yaml` 的 `mcp_tools` 欄位提供 in-process 工具，由 `load_extends_mcp_tools()` 載入

### 向後相容

`services/mcp_server.py` 為過渡期保留的相容模組，所有 API 都 re-export 自 `services/mcp/`。新程式碼應直接 `from services.mcp import ...`。

### 工具定義方式

各工具檔案 import `server.py` 的共用 `mcp` 實例，使用 FastMCP decorator 註冊工具：

```python
from .server import mcp, ensure_db_connection, check_mcp_tool_permission

@mcp.tool()
async def my_tool(param1: str, param2: int = 10) -> str:
    """
    工具說明

    Args:
        param1: 參數1說明
        param2: 參數2說明，預設 10
    """
    await ensure_db_connection()
    # ...
    return "結果"
```

Schema 會自動從 type hints 和 docstring 生成。

### 共用輔助函數（server.py）

| 函數 | 用途 |
|------|------|
| `ensure_db_connection()` | 確保資料庫連線池已初始化（懶初始化） |
| `resolve_ctos_user_id(ctos_user_id)` | 解析使用者 ID，fallback 讀取 `CTOS_USER_ID` 環境變數 |
| `resolve_agent_allowed_shared_sources()` | 從環境變數讀取 Agent 允許的 NAS shared 來源限制 |
| `resolve_agent_allowed_library_paths()` | 從環境變數讀取 Agent 允許的 library 子路徑限制 |
| `check_mcp_tool_permission(tool_name, ctos_user_id)` | 檢查使用者的工具權限 |
| `check_project_member_permission(project_id, user_id)` | 檢查使用者是否為專案成員 |
| `to_taipei_time(dt)` | 將 datetime 轉換為台北時區 (UTC+8) |

### 工具存取介面

`server.py` 提供以下函數供其他服務使用（如 Line Bot AI、Telegram Bot）：

- `get_mcp_tools()` - 取得工具定義列表（符合 Claude API 格式）
- `get_mcp_tool_names(exclude_group_only)` - 取得工具名稱列表
- `execute_tool(tool_name, arguments)` - 執行工具

這讓 Bot AI 和其他服務可以直接呼叫工具，無需透過 MCP 協議。

## 可用工具

### 知識庫（knowledge_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `search_knowledge` | 搜尋知識庫 | `query`（必填）, `project`, `category`, `limit`, `line_user_id`, `ctos_user_id` |
| `get_knowledge_item` | 取得知識庫文件完整內容 | `kb_id`（必填）, `ctos_user_id` |
| `update_knowledge_item` | 更新知識庫文件 | `kb_id`（必填）, `title`, `content`, `category`, `scope`, `topics`, `projects`, `roles`, `level`, `type`, `ctos_user_id` |
| `delete_knowledge_item` | 刪除知識庫文件 | `kb_id`（必填） |
| `add_note` | 新增筆記到知識庫 | `title`（必填）, `content`（必填）, `category`, `topics`, `project`, `line_group_id`, `line_user_id`, `ctos_user_id` |
| `add_note_with_attachments` | 新增筆記並加入附件 | `title`（必填）, `content`（必填）, `attachments`（必填，NAS 路徑列表）, `category`, `topics`, `project`, `line_group_id`, `line_user_id`, `ctos_user_id` |

> **知識庫 Scope 自動判定**：`add_note` 和 `add_note_with_attachments` 會根據對話來源參數自動設定 scope：
> - `line_user_id` + `ctos_user_id`（已綁定）→ `personal`（個人知識）
> - `line_group_id` + 群組已綁定專案 → `project`（專案知識）
> - 其他情況 → `global`（全域知識）

### 知識庫附件（knowledge_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_attachments_to_knowledge` | 為現有知識新增附件 | `kb_id`（必填）, `attachments`（必填，NAS 路徑列表）, `descriptions`, `ctos_user_id` |
| `get_knowledge_attachments` | 取得知識庫附件列表 | `kb_id`（必填）, `ctos_user_id` |
| `update_knowledge_attachment` | 更新附件說明 | `kb_id`（必填）, `attachment_index`（必填）, `description`, `ctos_user_id` |
| `read_knowledge_attachment` | 讀取知識庫附件的文字內容 | `kb_id`（必填）, `attachment_index`（預設 0）, `max_chars`（預設 15000）, `ctos_user_id` |

> **附件內容讀取**：`read_knowledge_attachment` 可讀取 Word/Excel/PowerPoint/PDF 等文件格式的附件內容，方便 AI 分析或回答問題。

### 自訂記憶（memory_tools.py）— Core

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `add_memory` | 新增自訂記憶 | `content`（必填）, `title`（選填，會自動產生）, `line_group_id`, `line_user_id` |
| `get_memories` | 查詢記憶列表 | `line_group_id`, `line_user_id` |
| `update_memory` | 更新記憶 | `memory_id`（必填）, `title`, `content`, `is_active`（啟用/停用） |
| `delete_memory` | 刪除記憶 | `memory_id`（必填） |

> **自訂記憶**：用戶可以設定自訂記憶讓 AI 記住特定指示（如回覆風格、稱呼方式等）。每個群組/用戶的記憶獨立管理，可隨時啟用或停用。

### Line Bot / 訊息（message_tools.py）— Core

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `summarize_chat` | 取得群組聊天記錄 | `line_group_id`（必填）, `hours`, `max_messages` |
| `get_message_attachments` | 查詢對話中的附件 | `line_user_id`, `line_group_id`, `days`, `file_type`, `limit` |

### NAS 檔案（nas_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `search_nas_files` | 搜尋 NAS 共享檔案 | `keywords`（必填，逗號分隔）, `file_types`（副檔名，如 pdf,xlsx）, `limit`, `ctos_user_id` |
| `get_nas_file_info` | 取得 NAS 檔案詳細資訊 | `file_path`（必填）, `ctos_user_id` |
| `read_document` | 讀取文件內容（Word/Excel/PowerPoint/PDF） | `file_path`（必填）, `max_chars`（預設 50000）, `ctos_user_id` |
| `prepare_file_message` | 準備檔案訊息供 Line Bot 回覆 | `file_path`（必填）, `ctos_user_id` |
| `send_nas_file` | 透過 Bot 發送 NAS 檔案給使用者 | `file_path`（必填）, `line_user_id`, `line_group_id`, `telegram_chat_id`, `ctos_user_id` |
| `list_library_folders` | 瀏覽擎添圖書館的資料夾結構 | `path`（子路徑）, `max_depth`（預設 2）, `ctos_user_id` |
| `archive_to_library` | 將檔案歸檔至擎添圖書館 | `source_path`（必填）, `category`（必填）, `filename`（必填）, `folder`, `ctos_user_id` |

> **文件讀取支援格式**：`read_document` 可讀取 `.docx`、`.xlsx`、`.pptx`、`.pdf` 檔案，將內容轉為純文字供 AI 分析。不支援舊版格式（`.doc`、`.xls`、`.ppt`）和加密文件。

### 分享功能（share_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `create_share_link` | 建立公開分享連結 | `resource_type`（必填，knowledge/project/nas_file/project_attachment/content）, `resource_id`（必填）, `expires_in`（1h/24h/7d/null）, `password`（選填，4 位數密碼） |
| `share_knowledge_attachment` | 分享知識庫附件（.md2ppt/.md2doc） | `kb_id`（必填，如 kb-001）, `attachment_idx`（必填，附件索引從 0 開始）, `expires_in`（1h/24h/7d/null） |

> **密碼保護**：分享連結可設定 4 位數密碼保護，5 次輸入錯誤後將鎖定 30 分鐘。

### 媒體工具（media_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `download_web_image` | 下載網路圖片到 NAS | `url`（必填）, `ctos_user_id` |
| `download_web_file` | 下載網路檔案到 NAS | `url`（必填）, `filename`, `ctos_user_id` |
| `convert_pdf_to_images` | 將 PDF 轉為圖片 | `pdf_path`（必填）, `pages`（預設 "all"） |

### 簡報/文件生成（presentation_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `generate_presentation` | 生成 PowerPoint 簡報 | `topic`, `num_slides`, `theme`, `include_images`, `image_source`, `outline_json`, `design_json` |
| `generate_md2ppt` | 產生 MD2PPT 格式簡報 | `markdown_content`（必填）, `ctos_user_id` |
| `generate_md2doc` | 產生 MD2DOC 格式文件 | `markdown_content`（必填）, `ctos_user_id` |
| `prepare_print_file` | 將虛擬路徑轉換為可列印的絕對路徑 | `file_path`（必填）, `ctos_user_id` |

#### 基本用法（指定主題）

```python
result = await execute_tool("generate_presentation", {
    "topic": "AI 在製造業的應用",
    "num_slides": 5,
    "theme": "uncover",
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

#### MD2PPT/MD2DOC 使用範例

```python
# 產生簡報
result = await execute_tool("generate_md2ppt", {
    "markdown_content": "# AI 解決方案\n\n## 產品特色\n- 智慧分析\n- 自動化流程"
})
# 回傳：分享連結 + 4 位數密碼

# 產生文件
result = await execute_tool("generate_md2doc", {
    "markdown_content": "# 設備操作 SOP\n\n## 開機步驟\n1. 檢查電源..."
})
# 回傳：分享連結 + 4 位數密碼
```

> **與 generate_presentation 的差異**：
> - `generate_presentation`：直接生成 PowerPoint 檔案（使用 Marp）
> - `generate_md2ppt`：產生可線上編輯的 MD2PPT 格式內容，透過分享連結在 MD2PPT 網站編輯後匯出 PPTX
>
> MD2PPT/MD2DOC 的優勢：
> - 可線上即時編輯內容
> - 支援更豐富的排版功能（圖表、雙欄、動畫等）
> - 可匯出為多種格式（PPTX、Word、PDF）

### 排程管理（scheduler_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `manage_scheduled_task` | 管理動態排程任務（create/update/delete/enable/disable） | `action`（必填）, `name`, `description`, `trigger_type`, `trigger_config`, `executor_type`, `executor_config`, `task_id`, `is_enabled`, `ctos_user_id` |
| `list_scheduled_tasks` | 查詢排程列表（含動態與靜態排程） | `is_enabled`, `include_static`（預設 true）, `ctos_user_id` |

> **排程管理**需要管理員權限（`ctos_user_id` 必須對應管理員帳號）。

### 語音合成（voice_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `text_to_speech` | 將文字轉換為語音檔案 | `text`（必填，上限 500 字）, `ctos_user_id` |

> **使用時機**：使用者用語音訊息發問時，優先使用語音回覆。需要 extends/voice 模組安裝。

### 網頁擷取（web_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `browse_webpage` | 用瀏覽器開啟網頁並擷取渲染後內容 | `url`（必填，僅 HTTPS）, `max_length`（預設 8000）, `timeout`（預設 30000ms）, `ctos_user_id` |

> **適用場景**：JavaScript 渲染的 SPA 網站（如 React、Next.js）。一般靜態網頁請優先使用 WebFetch。

### AI Skills（skill_script_tools.py）

| 工具名稱 | 說明 | 參數 |
|----------|------|------|
| `run_skill_script` | 執行 Skill 腳本 | `skill`（必填）, `script`（必填）, `input`, `ctos_user_id` |

> **AI Skills 系統**：支援 media-downloader（影片/音訊下載）和 media-transcription（逐字稿轉錄）等 Skill，透過 Script-first 或 MCP-first 路由策略執行。
>
> 目前 native `base`、`file-manager` 也已採 script-first，並以 `script_mcp_fallback` 對應回舊 MCP tool。
> fallback 僅在 script 明確回傳 `fallback_required`（或 `allow_fallback: true`）時觸發；參數驗證錯誤不會 fallback。

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
claude "幫我搜尋知識庫中關於水切爐的資料"
claude "找一下亦達 layout 的 pdf"
claude "畫一隻可愛的貓"  # AI 圖片生成（需設定 nanobanana）
```

Claude 會自動使用對應的 MCP 工具執行操作。

### 透過程式碼呼叫

```python
from ching_tech_os.services.mcp import get_mcp_tools, execute_tool

# 取得工具列表（符合 Claude API 格式）
tools = await get_mcp_tools()

# 執行工具
result = await execute_tool("search_knowledge", {"query": "水切爐"})
print(result)

# 新增筆記
result = await execute_tool("add_note", {
    "title": "會議紀錄",
    "content": "今日討論事項...",
    "category": "meeting"
})
```

## 權限控制

### 機制說明

1. **工具權限**：`check_mcp_tool_permission()` 會根據使用者角色和權限設定，檢查是否允許呼叫特定工具
2. **專案權限**：`check_project_member_permission()` 檢查使用者是否為專案成員
3. **環境變數 Fallback**：`resolve_ctos_user_id()` 在 AI 未傳入 `ctos_user_id` 時，自動讀取 `CTOS_USER_ID` 環境變數
4. **Agent 存取限制**：`resolve_agent_allowed_shared_sources()` 和 `resolve_agent_allowed_library_paths()` 可限制受限 Agent 的檔案存取範圍

### 錯誤訊息

- 未關聯 CTOS 帳號：使用預設權限判斷
- 工具已停用（遷移至 ERPNext）：回傳停用訊息
- 權限不足：回傳需要的功能權限名稱

## 新增工具

1. 在對應的工具檔案（或建立新檔案）中使用 `@mcp.tool()` 裝飾器定義函數
2. Import `server.py` 的共用元件：`mcp`, `ensure_db_connection`, `check_mcp_tool_permission` 等
3. 使用 type hints 定義參數類型，在 docstring 中描述工具和參數
4. 如果建立新檔案，需在 `modules.py` 的對應模組中設定 `mcp_module` 路徑
5. 如果需要權限控制，加入 `ctos_user_id` 參數並呼叫 `check_mcp_tool_permission()`
6. 更新 `linebot_agents.py` 中的 prompt（讓 Line Bot AI 知道新工具）
7. 建立新的 migration 更新資料庫中的 prompt
8. 執行 `alembic upgrade head` 套用變更

範例：

```python
from .server import mcp, ensure_db_connection, check_mcp_tool_permission
from ...database import get_connection

@mcp.tool()
async def my_new_tool(
    required_param: str,
    optional_param: int = 5,
    ctos_user_id: int | None = None,
) -> str:
    """
    工具功能說明

    Args:
        required_param: 必填參數說明
        optional_param: 選填參數說明，預設 5
        ctos_user_id: CTOS 用戶 ID
    """
    await ensure_db_connection()

    # 權限檢查（視需要）
    allowed, error_msg = await check_mcp_tool_permission("my_new_tool", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    async with get_connection() as conn:
        # 執行資料庫查詢
        ...
    return "結果"
```

### Extends 模組提供 MCP 工具

Extends 模組可在 `contributes.yaml` 中指定 `mcp_tools` 欄位，提供 in-process MCP 工具：

```yaml
# extends/my-module/contributes.yaml
mcp_tools: core/mcp_tools.py
```

工具檔案會由 `load_extends_mcp_tools()` 在啟動時動態載入，支援相對 import（如 `from .services import ...`）。
