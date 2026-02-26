# 模組索引（Module Index）

> 修改功能前先查閱此檔案，快速定位需要修改的檔案。
> 路徑皆相對於 `backend/src/ching_tech_os/`（後端）或 `frontend/`（前端）。

## 後端模組地圖

### 基礎設施

| 檔案 | 用途 |
|------|------|
| `main.py` | FastAPI 入口、路由註冊、lifespan（啟動 scheduler/MCP/Telegram） |
| `modules.py` | 模組 registry、`ENABLED_MODULES` 條件啟停、Skill contributes 合併 |
| `config.py` | 環境變數設定（Pydantic Settings） |
| `database.py` | asyncpg 連線池 |
| `__init__.py` | 版本號 `__version__` |
| `middleware/cache_control.py` | 快取控制中介層 |
| `services/errors.py` | ServiceError 基礎類別 |

### Line Bot

```
api/linebot_router.py          ← webhook 入口
services/bot_line/webhook.py   ← 簽名驗證、事件解析
services/bot_line/client.py    ← Line Bot API 客戶端（共用）
services/bot_line/message_store.py ← 訊息儲存
services/bot_line/file_handler.py  ← 檔案下載、NAS 操作
services/bot_line/user_manager.py  ← 使用者資料管理
services/bot_line/group_manager.py ← 群組資料管理
services/bot_line/binding.py       ← 帳號綁定、驗證碼
services/bot_line/memory.py        ← 記憶/筆記
services/bot_line/messaging.py     ← 發送訊息
services/bot_line/trigger.py       ← @提及偵測
services/bot_line/admin.py         ← 管理功能
services/bot_line/adapter.py       ← BotAdapter 協定實作
services/linebot.py                ← 核心函式（save_message 等）
services/linebot_ai.py             ← AI 回應（prompt 建構、context、logging）
models/linebot.py                  ← 資料模型
```

### Telegram Bot

```
api/telegram_router.py             ← webhook 入口
services/bot_telegram/polling.py   ← 長輪詢
services/bot_telegram/handler.py   ← 更新處理（935 行）
services/bot_telegram/adapter.py   ← TelegramBotAdapter
services/bot_telegram/media.py     ← 媒體下載
services/linebot_ai.py             ← AI 回應（與 Line Bot 共用）
```

### Bot 共用層（跨平台）

```
services/bot/adapter.py            ← BotAdapter 協定定義
services/bot/agents.py             ← 平台無關的 prompt 模板（758 行）
services/bot/ai.py                 ← parse_ai_response()
services/bot/commands.py           ← CommandRouter 斜線指令路由框架
services/bot/command_handlers.py   ← 內建指令（/start、/help、/reset、/debug）
services/bot/identity_router.py    ← 未綁定用戶身份分流（reject / restricted）
services/bot/rate_limiter.py       ← 受限模式頻率限制（bot_usage_tracking）
services/bot/media.py              ← 媒體處理
services/bot/message.py            ← 訊息處理
services/claude_agent.py           ← call_claude() AI 推論
```

### AI Agent / AI 管理

```
api/ai_management.py               ← AI prompt/agent CRUD API
api/ai_router.py                   ← AI 對話 API（chats）
services/linebot_agents.py         ← agent 定義、prompt 生成、工具分配
services/bot/agents.py             ← prompt 模板（按功能分類）
services/claude_agent.py           ← Claude API 呼叫
services/linebot_ai.py             ← AI 訊息處理流程
services/ai_manager.py             ← AI 管理邏輯（859 行）
models/ai.py                       ← AI 相關資料模型
```

### Knowledge Base（知識庫）

```
api/knowledge.py               ← CRUD + 附件 API
services/knowledge.py          ← 知識庫邏輯（1,202 行）
services/local_file.py         ← 本地檔案 I/O
services/permissions.py        ← 權限檢查
models/knowledge.py            ← 資料模型
```

### File Manager / NAS

```
api/files.py                       ← 檔案 API
api/nas.py                         ← NAS 瀏覽/上傳/下載 API
services/path_manager.py           ← StorageZone 路徑路由
services/smb.py                    ← SMB/CIFS 操作（722 行）
services/nas_connection.py         ← NAS 連線池
services/local_file.py             ← 本地檔案操作
services/workers/thread_pool.py    ← SMB 執行緒池
models/nas.py                      ← 資料模型
```

### MCP Server（AI 工具）

```
services/mcp/server.py             ← FastMCP 核心（ensure_db_connection、權限檢查）
services/mcp/__init__.py           ← 模組註冊、get_mcp_tools()、execute_tool()
services/mcp/knowledge_tools.py    ← 知識庫工具（764 行）
services/mcp/nas_tools.py          ← NAS/檔案工具（1,066 行）
services/mcp/memory_tools.py       ← 記憶工具
services/mcp/message_tools.py      ← 訊息工具
services/mcp/media_tools.py        ← 媒體工具
services/mcp/presentation_tools.py ← 簡報/文件工具（653 行）
services/mcp/share_tools.py        ← 分享工具
services/mcp/skill_script_tools.py ← Skill 腳本執行
mcp_cli.py                         ← MCP CLI 入口
```

### User / Auth（使用者與認證）

```
api/auth.py                ← 登入/登出/session API
api/user.py                ← 使用者 CRUD + admin 路由
services/user.py           ← 使用者邏輯（693 行）
services/password.py       ← 密碼雜湊與驗證
services/session.py        ← SessionManager（記憶體 session）
services/permissions.py    ← 角色權限（622 行）
services/login_record.py   ← 登入紀錄
services/geoip.py          ← GeoIP 定位
models/auth.py             ← LoginRequest/Response
models/user.py             ← UserInfo、AdminUserInfo
```

### Sharing（公開分享）

```
api/share.py               ← 分享 API（含 public_router 無須認證）
services/share.py          ← 分享邏輯（772 行）
models/share.py            ← ShareLink 資料模型
```

### Skills（技能系統）

```
api/skills.py                      ← Skills API（安裝/卸載/Hub）
services/skills/__init__.py        ← SkillManager（718 行）
services/skills/script_runner.py   ← 腳本執行器
services/skills/seed_external.py   ← 外部 Skill 載入
services/hub_meta.py               ← SKILL.md frontmatter 解析
services/clawhub_client.py         ← ClawHub 市集客戶端
services/skillhub_client.py        ← SkillHub 市集客戶端
modules.py                         ← Skill contributes 轉 module registry
services/mcp/skill_script_tools.py ← MCP 整合
skills/base/                       ← 內建：基礎工具（script-first）
skills/file-manager/               ← 內建：檔案管理（script-first）
skills/media-downloader/           ← 內建：影片下載
skills/media-transcription/        ← 內建：語音轉字幕
```

### Scheduler（排程）

```
services/scheduler.py      ← APScheduler 任務定義
  ├─ core jobs（固定）
  │   └─ create_next_month_partitions()   每月 25 日 04:00
  └─ module jobs（依 ENABLED_MODULES / contributes.scheduler）
      ├─ cleanup_old_messages()           每日 03:00
      ├─ cleanup_linebot_temp_files()     每小時
      ├─ cleanup_expired_share_links()    每小時
      ├─ cleanup_ai_images()              每日 04:30
      └─ cleanup_media_temp_folders()     每日 05:00
```

### 其他服務

| 檔案 | 用途 |
|------|------|
| `services/document_reader.py` | 文件讀取（docx/xlsx/pptx/pdf） |
| `services/message.py` | 系統訊息 |
| `services/project.py` | 專案管理（1,157 行） |
| `services/inventory.py` | 庫存管理（1,150 行） |
| `utils/crypto.py` | 加密工具 |

---

## 前端模組地圖

### 核心模組（所有頁面載入）

| 檔案 | 用途 |
|------|------|
| `js/config.js` | 環境設定、`API_BASE`、fetch 攔截 |
| `js/icons.js` | SVG 圖示庫（Material Design Icons） |
| `js/ui-helpers.js` | loading/error/empty 狀態 UI |
| `js/file-utils.js` | 檔案類型偵測、大小格式化 |
| `js/path-utils.js` | NAS/CTOS 路徑轉換 |
| `js/api-client.js` | REST API 封裝 |
| `js/socket-client.js` | Socket.IO 即時通訊 |
| `js/theme.js` | 深色/淺色主題 |
| `js/login.js` | 認證、session、token |
| `js/notification.js` | Toast 通知 |
| `js/permissions.js` | 角色權限（前端） |

### 桌面環境

| 檔案 | 用途 |
|------|------|
| `js/desktop.js` | 應用程式啟動器、圖示、lazy-loading、`/api/config/apps` 動態清單 |
| `js/window.js` | 視窗管理（1,208 行） |
| `js/taskbar.js` | 工作列 |
| `js/header.js` | 頂部導航列 |
| `js/command-palette.js` | 快捷鍵啟動器（Cmd+K） |

### 功能應用（由 desktop.js 延遲載入）

| 檔案 | 功能 | 主要 API 路徑 |
|------|------|---------------|
| `js/ai-assistant.js` | AI 對話 | `/api/ai/chats/*`, `/api/ai/agents` |
| `js/knowledge-base.js` | 知識庫 | `/api/knowledge/*` |
| `js/file-manager.js` | 檔案管理（1,901 行） | `/api/nas/*` |
| `js/settings.js` | 系統設定 | `/api/admin/users/*`, `/api/admin/bot-settings/*` |
| `js/agent-settings.js` | AI Agent 設定（1,649 行） | `/api/ai/agents/*`, `/api/skills/*` |
| `js/prompt-editor.js` | Prompt 編輯 | `/api/ai/prompts/*` |
| `js/ai-log.js` | AI 日誌 | `/api/ai/logs/*` |
| `js/linebot.js` | Bot 管理 | `/api/bot/*` |
| `js/message-center.js` | 訊息中心 | `/api/messages/*` |
| `js/share-manager.js` | 分享管理 | `/api/share/*` |
| `js/memory-manager.js` | 記憶管理 | `/api/bot/memories/*` |
| `js/terminal.js` | 終端機 | WebSocket（xterm.js） |
| `js/code-editor.js` | 程式編輯器 | iframe → code-server |

### 檢視器（按需載入）

| 檔案 | 格式 |
|------|------|
| `js/file-opener.js` | 路由：檔案 → 對應檢視器 |
| `js/image-viewer.js` | JPG/PNG/GIF/WebP/SVG |
| `js/text-viewer.js` | TXT/MD/JSON/log/程式碼 |
| `js/pdf-viewer.js` | PDF |

### 對話框與其他

| 檔案 | 用途 |
|------|------|
| `js/share-dialog.js` | 建立分享連結 Modal |
| `js/user-profile.js` | 個人資料、改密碼 |
| `js/onboarding.js` | 新手導覽 |
| `js/external-app.js` | 外部 URL 啟動器 |
| `js/device-fingerprint.js` | 裝置識別 |
| `js/matrix-rain.js` | 登入頁動畫 |
| `js/lazy-bg.js` | 延遲背景載入 |

### CSS 對應

| CSS 檔案 | 對應功能 |
|----------|---------|
| `css/main.css` | 設計系統變數定義（**改樣式前必讀**） |
| `css/desktop.css` | 桌面環境 |
| `css/window.css` | 視窗 |
| `css/header.css` | 頂部導航 |
| `css/taskbar.css` | 工作列 |
| `css/ai-assistant.css` | AI 對話 |
| `css/knowledge-base.css` | 知識庫（1,784 行） |
| `css/file-manager.css` | 檔案管理（1,281 行） |
| `css/settings.css` | 設定 |
| `css/agent-settings.css` | Agent 設定（1,211 行） |
| `css/ai-log.css` | AI 日誌 |
| `css/linebot.css` | Bot 管理 |
| `css/message-center.css` | 訊息中心 |
| `css/share-manager.css` | 分享管理 |
| `css/share-dialog.css` | 分享對話框 |
| `css/memory-manager.css` | 記憶管理 |
| `css/terminal.css` | 終端機 |
| `css/code-editor.css` | 程式編輯器 |
| `css/prompt-editor.css` | Prompt 編輯器 |
| `css/viewer.css` | 檢視器共用 |
| `css/file-common.css` | 檔案 UI 共用 |
| `css/mobile-common.css` | 手機版 |
| `css/login.css` | 登入頁 |
| `css/onboarding.css` | 新手導覽 |
| `css/user-profile.css` | 個人資料 |
| `css/notification.css` | 通知 |
| `css/command-palette.css` | 快捷鍵面板 |
| `css/external-app.css` | 外部應用 |
| `css/public.css` | 公開分享頁 |

### HTML 入口

| 檔案 | 用途 | 注意 |
|------|------|------|
| `index.html` | 主應用程式 | 新增 JS/CSS 需加入此檔 |
| `login.html` | 登入頁 | 新增 JS/CSS 也需加入此檔 |
| `public.html` | 公開分享頁 | |

---

## 常見修改場景速查

### 「新增一個 MCP 工具」
1. `services/mcp/` 下對應的 `*_tools.py`（或新建）
2. `modules.py`（確認模組 `mcp_module` 或 skill `contributes.mcp_tools` 對應）
3. `services/mcp/__init__.py`（確認條件載入流程）
4. `services/bot/agents.py`（更新 prompt 模板）
5. 新增 migration 更新資料庫中的 prompt
6. `docs/mcp-server.md`（更新文件）

### 「新增一個前端應用」
1. `frontend/js/xxx.js`（IIFE 模組）
2. `frontend/css/xxx.css`
3. 內建 app：更新 `modules.py` 的 `app_manifest` / 模組設定
4. skill app：在 `SKILL.md` 宣告 `contributes.app`（loader / css）
5. `frontend/js/desktop.js`（必要時調整 loader）
6. `frontend/index.html`、`frontend/login.html`（僅靜態內建資源需引入）
7. `frontend/js/icons.js`（如需新圖示）

### 「新增一個 API 端點」
1. `api/xxx.py`（路由定義）
2. `modules.py`（新增 router spec，由 `main.py` 動態註冊）
3. `services/xxx.py`（業務邏輯）
4. `models/xxx.py`（資料模型）
5. `migrations/versions/`（如需新表格）

### 「新增/修改 Bot 斜線指令」
1. `services/bot/command_handlers.py`（新增 handler 函式 + 註冊 SlashCommand）
2. `services/bot/commands.py`（如需修改 CommandRouter 框架）
3. `config.py`（如需新增環境變數控制）
4. `docs/linebot.md` 和 `docs/telegram-bot.md`（更新指令表）

### 「修改 Bot 受限模式訊息模板」
1. 在「AI 管理」應用程式中找到 `bot-restricted` Agent
2. 編輯 `settings` JSONB 欄位中的對應 key（`welcome_message`、`binding_prompt`、`rate_limit_hourly_msg`、`rate_limit_daily_msg`、`disclaimer`、`error_message`）
3. 空字串表示使用程式碼中的預設值

### 「修改 Bot AI 行為」
1. `services/bot/agents.py`（prompt 模板）
2. `services/linebot_agents.py`（agent 定義、工具分配）
3. `services/linebot_ai.py`（訊息處理流程）
4. `services/claude_agent.py`（API 呼叫邏輯）
5. 新增 migration 同步 prompt 到資料庫

### 「修改使用者權限」
1. `services/permissions.py`（權限邏輯）
2. `api/user.py`（API 端點）
3. `services/user.py`（使用者邏輯）
4. `frontend/js/permissions.js`（前端權限）
5. `frontend/js/settings.js`（設定 UI）

### 「修改分享功能」
1. `api/share.py`
2. `services/share.py`
3. `models/share.py`
4. `frontend/js/share-manager.js` + `css/share-manager.css`
5. `frontend/js/share-dialog.js` + `css/share-dialog.css`
6. `frontend/public.html`（公開頁面）

### 「版本號更新」
同步修改三個檔案：
1. `backend/pyproject.toml` → `version`
2. `backend/src/ching_tech_os/__init__.py` → `__version__`
3. `backend/src/ching_tech_os/main.py` → FastAPI `version`
