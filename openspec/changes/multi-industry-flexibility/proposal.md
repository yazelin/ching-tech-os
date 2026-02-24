## Why

CTOS 目前各功能模組高度耦合——所有路由無條件註冊、所有 MCP 工具無條件載入、
Prompt 硬編碼所有模組的工具說明、前端應用清單靜態宣告。
當要為不同產業部署時（如 kb036 診所只需知識庫 + Line Bot + AI），
無法「只啟用需要的模組」，必須整包部署，多餘的功能佔據 UI、混入 AI Prompt、
浪費 token 並造成使用者困惑。

此外，目前沒有任何機制讓系統「安裝新功能」——新增模組必須修改原始碼。
系統需要一套類似 VSCode Extension / Chrome Extension 的可插拔架構，
讓每個功能模組可獨立啟用/停用，並且透過安裝 Skill 即可擴充新功能，
有或沒有某個功能都能正常運行。

## What Changes

### 1. Skill 升級為模組擴充系統
- 將 Skill 系統從「script 工具替代」升級為「完整的模組擴充機制」，類似 VSCode Extension
- `SKILL.md` frontmatter 新增 `contributes` 區塊，可宣告：前端 App、權限定義、MCP 工具、排程任務
- 安裝 Skill 即自動擴充系統功能（出現在桌面、MCP 工具可用、Prompt 包含說明），不需改程式碼
- 內建功能也用相同的模組描述格式（`source: builtin`），統一管理

### 2. 內建模組可插拔
- 新增 `modules.py` 定義內建模組 registry（`BUILTIN_MODULES`）
- `config.py` 新增 `ENABLED_MODULES` 環境變數，控制啟用哪些模組（預設 `"*"` 全啟用）
- `main.py` 路由改為 `importlib` 條件載入，停用的模組不註冊 router
- 停用模組的 Python 套件可不安裝（如停用 Line Bot → 不裝 `line-bot-sdk`）

### 3. MCP 工具條件載入
- `services/mcp/__init__.py` 改為依啟用模組動態載入工具子模組
- 停用 file-manager → `nas_tools.py` 的 15+ 個工具不註冊
- Skill 的 `contributes.mcp_tools` 也依啟用狀態條件載入

### 4. Prompt 與工具白名單自動連動
- 停用模組 → 其 `app_id` 從權限中移除 → `generate_tools_prompt()` 自動跳過 → AI 不知道該功能存在
- 利用現有的 `APP_PROMPT_MAPPING` + `_FALLBACK_TOOLS` + SkillManager 機制，不需重構

### 5. 前端應用清單動態化
- 新增 `/api/config/apps` 端點，回傳啟用模組的前端應用清單
- `desktop.js` 改為從 API 動態取得應用清單
- Skill 擴充的 App 包含 `loader` 欄位，前端動態載入 Skill 提供的 JS/CSS
- API 失敗時 fallback 到靜態清單

### 6. Scheduler 條件排程
- `scheduler.py` 改為只註冊啟用模組的排程任務

## Capabilities

### New Capabilities
- `feature-modules`: 模組 registry、`ENABLED_MODULES` 設定、`is_module_enabled()` 查詢、條件載入邏輯（路由、MCP、排程、前端清單）
- `skill-contributes`: Skill 的 `contributes` 宣告格式、`hub_meta.py` 解析擴充、SkillManager 模組註冊、前端 Skill App 載入

### Modified Capabilities
- `infrastructure`: `main.py` 路由改為條件註冊、`config.py` 新增 `enabled_modules`
- `mcp-tools`: `mcp/__init__.py` 改為條件載入、支援 Skill MCP 工具
- `bot-platform`: prompt 組裝依啟用模組過濾、工具白名單依啟用模組過濾
- `web-desktop`: 應用清單改為後端 API 動態提供、支援 Skill App 動態載入
- `skill-management`: SkillManager 擴充支援 `contributes` 解析與模組註冊

## Impact

### 後端
- **新增 modules.py**: 模組 registry、`is_module_enabled()`、`get_module_registry()`
- **main.py**: 路由註冊重構為 `importlib` 條件載入
- **config.py**: 新增 `enabled_modules` 設定
- **mcp/__init__.py**: 靜態 import 改為條件動態載入
- **scheduler.py**: 排程註冊改為遍歷啟用模組
- **hub_meta.py**: 支援解析 `contributes` frontmatter
- **skills/__init__.py** (SkillManager): 擴充模組註冊邏輯
- **permissions.py**: `get_effective_app_permissions()` 排除停用模組

### 前端
- **desktop.js**: `applications` 陣列改為 `/api/config/apps` API 動態載入、支援 Skill App loader
- **config.js**: 新增 apps fetch 邏輯

### 模組分類（以 kb036 診所場景為例）

| 模組 ID | 包含功能 | 診所 | 擎添 |
|---------|---------|------|------|
| `core` | 認證、使用者管理、DB | 必要 | 必要 |
| `knowledge-base` | 知識庫 CRUD + 搜尋 | 啟用 | 啟用 |
| `ai-agent` | AI 對話、Prompt、MCP | 啟用 | 啟用 |
| `line-bot` | Line Bot webhook | 啟用 | 啟用 |
| `telegram-bot` | Telegram polling | 停用 | 啟用 |
| `file-manager` | NAS / 本地檔案 | 停用 | 啟用 |
| `erpnext` | ERPNext MCP + Prompt | 停用 | 啟用 |
| `public-share` | 公開分享 | 停用 | 啟用 |
| `skills` | Skill 市集 | 啟用 | 啟用 |
| `terminal` | Web 終端機 | 停用 | 啟用 |
| `code-editor` | Code Server | 停用 | 啟用 |
| `printer` | 列印服務 | 停用 | 啟用 |

### 相容性
- `ENABLED_MODULES` 預設 `"*"`，**現有部署零影響升級**
- 停用模組的 API 端點不註冊（回 404）
- 前端不顯示停用模組的 App、不載入對應 JS/CSS
- Skill 安裝的模組預設啟用（安裝即生效）
