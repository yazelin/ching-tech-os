# AI Agent 設計與對話管理

## 概覽

ChingTech OS 的 AI 助手透過 `claude-code-acp`（ClaudeClient in-process）與 Claude API 溝通，支援 Line Bot、Telegram Bot 和 Web 前端三個平台。系統包含完整的 Agent 管理、動態工具分配、身份分流、頻率限制和對話壓縮機制。

> Codex ACP provider、用量監測與安全路由核心已實作，但預設仍為固定 Claude，且尚無正式入口改用 `call_ai()`。部署 readiness、可觀測性與 canary gate 尚未完成，因此目前不得開啟正式流量。評估、風險與後續 gate 見 [Codex ACP 備援評估報告](codex-acp-failover-evaluation.md) 與 `openspec/changes/add-codex-acp-failover/`。

## 架構

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │  ai-assistant.js │◄──►│ socket-client.js│                 │
│  └────────┬────────┘    └────────┬────────┘                 │
│           │ REST API              │ Socket.IO                │
└───────────┼───────────────────────┼─────────────────────────┘
            │                       │
┌───────────┼───────────────────────┼─────────────────────────┐
│           ▼                       ▼           Backend        │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │  ai_router.py   │    │    api/ai.py    │                 │
│  │  (REST API)     │    │  (Socket.IO)    │                 │
│  └────────┬────────┘    └────────┬────────┘                 │
│           │                       │                          │
│           ▼                       ▼                          │
│  ┌────────────────────────────────────────┐                 │
│  │         services/linebot_ai.py         │ ← Bot 對話主流程 │
│  │         services/claude_agent.py       │ ← AI 推論核心    │
│  └────────────────┬───────────────────────┘                 │
│                   │                                          │
│     ┌─────────────┼─────────────┐                           │
│     ▼             ▼             ▼                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐                │
│  │ Agent 系統│ │ Skills   │ │ MCP Server   │                │
│  │ 管理/切換 │ │ 工具路由  │ │ 工具執行     │                │
│  └──────────┘ └──────────┘ └──────────────┘                │
│     │             │             │                           │
│     ▼             ▼             ▼                           │
│  ┌────────────────────────────────────────┐                 │
│  │              PostgreSQL                 │                 │
│  │  ai_agents / ai_prompts / ai_logs      │                 │
│  │  bot_users / bot_groups                 │                 │
│  │  bot_usage_tracking                     │                 │
│  └────────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│              claude-code-acp (ClaudeClient)                   │
│  In-process Claude 呼叫，支援 MCP 工具、權限控制、token 統計   │
└─────────────────────────────────────────────────────────────┘
```

### Provider Router 安全骨架

`services/ai_router.py::call_ai()` 目前尚未被正式入口使用。`ProviderRouter` 以 Claude/Codex registry 與 `is_ready()` 建立可測試的 pre-start fallback 邊界：只有尚未進入 `provider.call()` 前可改選明確 fallback；進入 call 後，不論回應失敗或拋錯都保持 provider sticky，避免重複副作用。預設 mode 仍固定 Claude：

| 環境變數 | 預設值 | 目前行為 |
|---------|--------|----------|
| `AI_PROVIDER_MODE` | `claude` | 接受 `claude`、`codex`、`auto`；非法值明確告警並回到 Claude |
| `AI_PROVIDER_CANARY_CONTEXTS` | `internal_admin,internal_test` | context exact-match allowlist |
| `AI_PROVIDER_CANARY_AGENTS` | `test-agent` | Agent exact-match allowlist |

`codex` 或符合 canary 的 `auto` 決策可以選到已註冊的 Codex provider；binary/circuit readiness 失敗才會在 session 前回 Claude並記錄 `codex_unready`。`RoutingContext` 只供 router 判斷，不會傳入 prompt 或 provider。fake provider tests 已鎖住 readiness false/error/missing、fallback unavailable 與執行後禁止跨 provider retry。由於目前沒有正式 caller 使用 `call_ai()`，既有 Line、Telegram、Web 與特殊 pipeline 完全不受影響。

### Claude Usage Monitor

`services/claude_usage.py` 以背景 single-flight request 更新記憶體快照，Router 不會在使用者請求路徑等待外部 Usage API。快照分為 unknown、fresh、stale、error；預設 TTL 60 秒、max-stale 300 秒。只有 `AI_PROVIDER_MODE=auto` 會在 FastAPI lifespan 啟動，forced Claude 不讀取 credentials。

自動路由採 hysteresis：fresh utilization `>=90%` 選 Codex、已在 Codex 時必須 `<85%` 才切回 Claude；85%–90% 或 max-stale 內的 stale 快照維持前一個穩定 provider。unknown、error 或超過 max-stale 一律回 Claude。

### Codex ACP Compatibility Layer

`services/codex_acp.py` 固定搭配 `@agentclientprotocol/codex-acp` 1.1.9、`@openai/codex` 0.146.0 與 Python ACP 0.8.0。此層只處理協定差異：ordered message delta、tool terminal event 去重、token/model metadata、stdio/HTTP MCP schema 與 tool-call-id permission identity correlation；provider 的工作目錄、權限、callback、timeout 與資源限制由 `codex_agent.py` 負責。

真實 smoke 使用本機單一唯讀 MCP fixture，已驗證 stdio tool、Streamable HTTP handshake、canonical server/tool identity、timeout/cancel 與 subprocess cleanup。若 pin 組合升級後任一契約失敗，Codex readiness 必須 fail closed，不可退回模糊工具名稱判斷。

### Codex Provider 安全邊界

`services/codex_agent.py` 沿用 Claude 的 per-request session workdir、MCP merge 與 framework identity/env injection，但只載入 allowlist canonical name 實際引用且同時位於 required set 的 server。permission 必須同時具有完全一致的 `mcp.server.tool` title、結構化 server/tool 與 `mcp__server__tool` allowlist；Unknown、短名稱、同名 server 衝突或 event correlation 不一致全部拒絕。

Provider 強制 read-only、`on-request` approval、停用 multi-agent，並拒絕 terminal、file-write 與 Codex 原生圖片工具。允許的圖片需求只能走既有 MCP 工具，且仍受 nanobanana/codex-image 全域上限。每次呼叫也受 semaphore、queue timeout 與 circuit breaker 控制；timeout 會 cancel、保留 partial result，再 disconnect 並清除 session 目錄。stderr 只保留有界尾端且遮罩 credential-like 內容。

## Agent 系統

### Agent 定義與儲存

Agent 設定儲存在 PostgreSQL `ai_agents` 表格，每個 Agent 包含：

| 欄位 | 說明 |
|------|------|
| `name` | 唯一名稱（如 `linebot-personal`） |
| `display_name` | 顯示名稱 |
| `model` | 使用的模型（如 `claude-sonnet`） |
| `system_prompt_id` | 關聯的 Prompt ID |
| `tools` | 工具白名單（JSON 陣列） |
| `settings` | 擴展設定（JSONB，如 `user_selectable`、`welcome_message`） |
| `is_active` | 是否啟用 |

### 預設 Agent

系統啟動時自動建立以下預設 Agent（若不存在）：

| Agent 名稱 | 用途 | 預設模型 |
|------------|------|----------|
| `linebot-personal` | Line/Telegram 個人對話 | `claude-sonnet` |
| `linebot-group` | Line/Telegram 群組對話 | `claude-haiku` |
| `bot-restricted` | 未綁定用戶的受限模式 | `claude-haiku`（可由 `BOT_RESTRICTED_MODEL` 覆蓋） |
| `bot-debug` | 管理員系統診斷 | `claude-sonnet`（可由 `BOT_DEBUG_MODEL` 覆蓋） |

### Agent 來源

Agent 可從三個來源建立：

1. **內建 Agent**：定義在 `linebot_agents.py` 的 `DEFAULT_LINEBOT_AGENTS` 和 `DEFAULT_BOT_MODE_AGENTS`
2. **Extends Agent**：從 `extends/*/clients/*/agents/*.md` 掃描載入（YAML frontmatter + Prompt body）
3. **手動建立**：透過 AI 管理介面或 API 建立

### Agent 切換機制（/agent 指令）

管理員可使用 `/agent` 斜線指令切換對話使用的 Agent：

```
/agent                        — 顯示目前 Agent 和可切換清單
/agent <name>                 — 用名稱切換
/agent <number>               — 用編號切換
/agent reset                  — 恢復預設
/agent restricted [...]       — 管理受限模式 Agent（群組限定）
```

**可切換清單的條件**：Agent 必須 `is_active=true` 且 `settings.user_selectable='true'`。

**偏好持久化**：

| 對話類型 | 儲存位置 | 欄位 |
|---------|---------|------|
| 個人對話 | `bot_users` | `active_agent_id` |
| 群組對話 | `bot_groups` | `active_agent_id` |
| 群組受限模式 | `bot_groups` | `restricted_agent_id` |

### Agent 路由優先級

```
Bot 訊息進入
    │
    ├─ 已綁定用戶
    │   ├─ 群組：bot_groups.active_agent_id → 預設 linebot-group
    │   └─ 個人：bot_users.active_agent_id → 預設 linebot-personal
    │
    └─ 未綁定用戶（依 BOT_UNBOUND_USER_POLICY）
        ├─ reject：回覆綁定提示（群組靜默忽略）
        └─ restricted：進入受限模式
            └─ 群組 restricted_agent_id → BOT_DEFAULT_RESTRICTED_AGENT → bot-restricted
```

預設 Agent 名稱可透過環境變數覆蓋：

| 環境變數 | 說明 | 預設值 |
|---------|------|--------|
| `BOT_DEFAULT_PERSONAL_AGENT` | 個人對話預設 Agent | `linebot-personal` |
| `BOT_DEFAULT_GROUP_AGENT` | 群組對話預設 Agent | `linebot-group` |
| `BOT_DEFAULT_RESTRICTED_AGENT` | 受限模式預設 Agent | `bot-restricted` |

## 身份分流（Identity Router）

未綁定帳號的用戶由 `identity_router.py` 決定處理路徑：

### 策略設定

```
BOT_UNBOUND_USER_POLICY = reject | restricted
```

| 策略 | 個人對話 | 群組對話 |
|------|---------|---------|
| `reject`（預設） | 回覆綁定提示 | 靜默忽略 |
| `restricted` | 進入受限模式 AI | 進入受限模式 AI |

### 受限模式特性

受限模式與一般模式的差異：

| 項目 | 一般模式 | 受限模式 |
|------|---------|---------|
| 對話歷史 | 最近 20 則 | 最近 10 則 |
| 超時時間 | 480 秒 | 120 秒 |
| 工具權限 | 依使用者 App 權限 | 僅 Agent 定義的工具 |
| 頻率限制 | 無 | 每小時/每日限額 |
| 檔案傳送 | 支援 | 不支援（過濾 FILE_MESSAGE） |
| 免責聲明 | 無 | 可附加自訂免責聲明 |

### 受限 Agent Settings

`bot-restricted` Agent 的 `settings` JSONB 欄位支援以下 key：

| Key | 說明 |
|-----|------|
| `welcome_message` | 歡迎訊息（/start 和 FollowEvent 使用） |
| `binding_prompt` | 自訂綁定提示（reject 模式使用） |
| `rate_limit_hourly_msg` | 每小時超限訊息（支援 `{limit}`、`{count}` 變數） |
| `rate_limit_daily_msg` | 每日超限訊息 |
| `disclaimer` | 免責聲明（附加在每則回覆後） |
| `error_message` | AI 處理失敗時的錯誤訊息 |
| `allowed_shared_sources` | NAS 共享來源限制 |
| `allowed_library_paths` | 圖書館路徑限制 |

群組受限模式 Agent（`/agent restricted <name>` 設定）的 settings 邏輯：
- **AI prompt / tools / model**：從實際選用的 Agent 讀取
- **rate_limit / disclaimer 等框架設定**：始終從 `bot-restricted` 讀取

## 頻率限制（Rate Limiter）

### 啟用條件

同時滿足以下條件時生效：
1. `BOT_UNBOUND_USER_POLICY=restricted`
2. `BOT_RATE_LIMIT_ENABLED=true`（預設 true）

### 限額設定

| 環境變數 | 說明 | 預設值 |
|---------|------|--------|
| `BOT_RATE_LIMIT_HOURLY` | 每小時訊息上限 | 20 |
| `BOT_RATE_LIMIT_DAILY` | 每日訊息上限 | 50 |

系統會自動驗證 hourly <= daily，不合理時會修正。

### 實作機制

- 使用 PostgreSQL `bot_usage_tracking` 表追蹤使用量
- 採用 **原子性 UPSERT + Transaction** 避免 TOCTOU 競爭條件
- 超限時 Transaction Rollback，計數器不遞增（不虛增）
- 頻率限制未啟用時仍記錄使用量供統計分析
- **Fail-open**：頻率限制檢查失敗時允許通過

## 黑名單機制

管理員可手動封鎖/解封未綁定用戶，封鎖用戶的訊息靜默忽略。

### 資料欄位

`bot_users` 表新增：`is_blocked`(bool)、`blocked_at`(timestamp)、`blocked_reason`(text)

### 流程位置

```
用戶訊息 → 黑名單檢查 → Rate Limiter → Token 額度 → Intent Guard → 主 Agent
               │
               └── is_blocked=true → return None（靜默忽略）
```

### API

| 方法 | 端點 | 說明 |
|------|------|------|
| PATCH | `/api/bot/users/{id}/block` | 封鎖（body: `{"reason": "..."}` 可選） |
| PATCH | `/api/bot/users/{id}/unblock` | 解封 |
| GET | `/api/bot/users?blocked=true` | 列出被封鎖的用戶 |

### 前端

Bot 管理新增「黑名單」tab，用戶 tab 卡片新增封鎖按鈕。

## 月度 Token 用量上限

按用戶限制受限模式的月度 token 用量，防止單一用戶消耗整月預算。

### 機制

- 複用 `bot_usage_tracking` 表，`period_type='monthly_tokens'`，`period_key='2026-03'`
- AI 呼叫前檢查額度，超額直接拒絕
- AI 呼叫後累加實際 token 數（input + output）
- Fail-open：檢查失敗不阻擋

### settings 設定

| Key | 類型 | 說明 |
|-----|------|------|
| `monthly_token_limit` | int | 月度 token 上限（0 = 不限制） |
| `monthly_token_limit_msg` | string | 超額訊息（支援 `{limit}`、`{count}` 變數） |

### 流程位置

```
Rate Limiter → Token 額度檢查 → Intent Guard → 主 Agent → 累加 token
```

## Intent Guard（意圖守門員）

在訊息進入主 Agent 前進行輕量意圖過濾，使用 Haiku 快速判斷用戶訊息是否在服務範圍內。

### 流程

```
用戶訊息 → Rate Limiter → Intent Guard (Haiku) → 主 Agent (Sonnet/Opus)
                              │
                              ├── allow  → 正常進入主 Agent
                              ├── reject → 直接回覆拒絕訊息（不走主 Agent）
                              └── direct → Haiku 直接回覆（不走主 Agent）
```

### 啟用條件（雙重控制）

- **全域開關**：`INTENT_GUARD_ENABLED=true`（預設 false）
- **Agent 級**：Agent `settings.intent_guard.enabled = true`

兩者都啟用才會觸發。沒有設定 `intent_guard` 的 Agent 完全不受影響。

### 判定順序

1. 短訊息跳過（`min_check_length`）→ allow
2. `allow_keywords` 命中 → allow（不呼叫 AI）
3. `block_keywords` 命中 → reject（不呼叫 AI）
4. Haiku AI 分類 → allow / reject / direct

### AI 呼叫方式

- 優先用 Anthropic SDK 直接呼叫（需 `ANTHROPIC_API_KEY`，~1 秒）
- 無 API Key 時 fallback 到 `call_claude` CLI（~10 秒）

### settings.intent_guard 設定格式

| Key | 類型 | 說明 |
|-----|------|------|
| `enabled` | bool | 是否啟用 |
| `description` | string | Agent 服務描述（用於 Haiku prompt） |
| `allowed_topics` | array | 允許的主題 |
| `blocked_topics` | array | 禁止的主題 |
| `allow_keywords` | array | 關鍵字白名單（命中即放行，不需 AI） |
| `block_keywords` | array | 關鍵字黑名單（命中即拒絕，不需 AI） |
| `reject_message` | string | 拒絕時的回覆訊息 |
| `direct_rules` | array | 可直接回答的情境描述 |
| `examples` | array | 訓練範例（message/action/reason/response） |
| `min_check_length` | int | 最短檢查長度（預設 2） |
| `timeout` | int | AI 判斷超時秒數（預設 15） |

### 設計原則

- **Fail-open**：Guard 失敗（timeout/error/invalid JSON）時自動放行
- **已綁定 + 未綁定用戶都過 Guard**（插入於 `linebot_ai.py` 和 `identity_router.py`）
- 相關檔案：`services/bot/intent_guard.py`

## 斜線指令系統（CommandRouter）

### 架構

斜線指令在 AI 處理流程之前攔截，由 `CommandRouter` 統一路由：

```
用戶訊息 → CommandRouter.parse() → 匹配？
    ├─ 是 → dispatch() → handler → 回覆
    └─ 否 → 進入 AI 處理流程
```

### 內建指令

| 指令 | 別名 | 說明 | 權限 |
|------|------|------|------|
| `/start` | — | 歡迎訊息 | 所有用戶 |
| `/help` | `/說明` | 查看指令說明 | 所有用戶 |
| `/reset` | `/新對話`、`/清除對話`、`/忘記` | 重置對話歷史 | 所有用戶 |
| `/debug` | `/診斷`、`/diag` | 系統診斷 | 管理員 |
| `/agent` | `/切換助理` | 切換 AI Agent | 管理員 |

### 指令特性

- 支援 `require_bound`（需綁定帳號）、`require_admin`（需管理員）
- 支援 `private_only`（僅限個人對話）
- 支援 `platforms`（指定 Line/Telegram）
- 可透過 `BOT_CMD_DISABLED` 環境變數停用特定指令

## Claude 推論核心（claude_agent.py）

### 呼叫方式

系統使用 `claude-code-acp` 的 `ClaudeClient` 進行 in-process AI 呼叫，取代早期的 Claude CLI subprocess：

```python
async def call_claude(
    prompt: str,
    model: str = "sonnet",
    history: list[dict] | None = None,
    system_prompt: str | None = None,
    timeout: int = 180,
    tools: list[str] | None = None,
    required_mcp_servers: set[str] | None = None,
    ctos_user_id: int | None = None,
    extra_mcp_env: dict[str, str] | None = None,
) -> ClaudeResponse:
```

### 模型對應

```python
MODEL_MAP = {
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}
```

### Session 隔離

每次 AI 呼叫建立獨立的工作目錄（`session-XXXXX/`），防止跨 session 污染：
- 在 `_WORKING_DIR_BASE` 下建立臨時子目錄
- 合併 `.mcp.json` 基底 + extends 貢獻的 MCP server 設定
- 建立 `nanobanana-output` 到 NAS 的 symlink
- 呼叫結束後自動清理

### 工具權限控制

1. **白名單模式**：只允許 `tools` 參數中指定的工具，拒絕其他所有工具
2. **工具呼叫次數限制**：支援 `tool_call_limits` 限制單回合呼叫次數（如 nanobanana 圖片生成）
3. **ctos_user_id 注入**：Framework 級自動注入，LLM 無法偽造使用者身份
4. **MCP Server 按需載入**：根據 `required_mcp_servers` 只載入需要的 server，減少啟動開銷

### 超時處理

```
一般模式：480 秒（8 分鐘，支援複雜任務）
受限模式：120 秒（2 分鐘）
/debug：  180 秒（3 分鐘）
```

超時時的 Fallback 機制：
1. 檢查已完成的圖片生成（tool_calls 中的 nanobanana 結果），嘗試發送
2. 從已完成的 WebSearch/WebFetch 結果中組合有用回覆
3. 保留部分文字回應（`_text_buffer`）
4. 最後才顯示超時錯誤

### Token 統計

透過 `ClaudeClient.on_result` callback 擷取 usage 資料（input_tokens / output_tokens），記錄到 `ai_logs` 表格。

## 動態 Prompt 與工具分配

### System Prompt 組裝流程

`build_system_prompt()` 動態組裝完整的 system prompt：

```
Agent 基礎 prompt（從 DB 的 ai_prompts 讀取）
    + 內建工具說明（WebFetch / WebSearch / Read 等）
    + 動態 MCP 工具說明（根據使用者 App 權限）
    + Script Tools 說明（根據 SkillManager）
    + 使用工具的流程建議
    + 自訂記憶（個人記憶或群組記憶）
    + 對話識別資訊（platform_user_id / ctos_user_id / group_id）
    + caller_context 範本（供背景任務附帶）
```

### 工具說明分類（bot/agents.py）

工具說明按 App 權限分類，根據使用者權限動態組合：

| App 權限 | 工具說明常數 | 包含的工具 |
|---------|------------|-----------|
| （基礎） | `BASE_TOOLS_PROMPT` | 對話附件、分享連結、網頁瀏覽 |
| `knowledge-base` | `KNOWLEDGE_TOOLS_PROMPT` | 知識庫 CRUD、附件管理 |
| `file-manager` | `FILE_TOOLS_PROMPT` | NAS 檔案、PDF 轉圖片、圖書館歸檔 |
| `ai-assistant` | `AI_IMAGE_TOOLS_PROMPT` + `AI_DOCUMENT_TOOLS_PROMPT` | 圖片生成、簡報/文件生成 |

### SkillManager 優先載入

工具說明和工具白名單的載入優先使用 `SkillManager`：

```
1. 嘗試從 SkillManager 載入 → 成功則使用
2. SkillManager 失敗 → Fallback 到硬編碼的 Prompt 常數
```

### 工具路由策略（Script vs MCP）

```
SKILL_ROUTE_POLICY = script-first | mcp-first
```

- **script-first**（預設）：Skill 的 Script 優先，有重疊的 MCP 工具會被隱藏
- **mcp-first**：MCP 工具優先
- `SKILL_SCRIPT_FALLBACK_ENABLED`：Script 失敗時是否允許 fallback 到 MCP

## 對話歷史管理

### 設計決策

自己管理對話歷史（不使用 Claude 的 session 機制），原因：

1. **持久化需求**：對話需存入 DB，跨 session 保留
2. **壓縮控制**：需要實作 token 警告和壓縮機制
3. **多裝置支援**：使用者可在不同裝置繼續對話
4. **Prompt 客製化**：可動態切換 System Prompt

### Prompt 組合格式

```
對話歷史：

user[Alice]: 第一則訊息
assistant: AI 回應
user[Bob]: 第二則訊息
assistant: AI 回應

user[Alice]: 最新訊息
```

### 對話上下文

`get_conversation_context()` 從 `bot_messages` 取得對話歷史，支援：
- 文字、圖片、檔案、語音訊息
- 圖片/檔案暫存自動恢復（從 NAS 下載到 `/tmp`）
- 對話重置時間過濾（`conversation_reset_at`）
- PDF 特殊格式處理（原始 PDF + 文字版）

## AI 回應後處理

### 圖片自動發送

`auto_prepare_generated_images()` 檢查 AI 是否呼叫了 `generate_image` 但忘記呼叫 `prepare_file_message`，自動補上 `[FILE_MESSAGE:...]` 標記。

### 語音自動補標記

`auto_extract_voice_messages()` 從 `tool_calls` 中提取 TTS 結果，自動補上 `[VOICE_MESSAGE:...]` 標記。

### 圖片生成 Fallback

當 nanobanana MCP 完全失敗（timeout/overloaded）時：
1. 提取原始 prompt
2. 嘗試 FLUX fallback（`generate_image_with_fallback()`）
3. 成功則發送 fallback 圖片並附加通知
4. 所有服務都失敗才顯示錯誤

### Research Skill 整合

`_extract_research_tool_feedback()` 從 `run_skill_script(research-skill)` 的工具輸出中提取結構化回覆：
- **start-research**：確保回覆包含 job_id
- **check-research**：依狀態顯示進度/完成摘要/失敗訊息
- 完成時自動萃取重點摘要（`_summarize_for_line()`），控制在 LINE 安全字數內

## Token 估算與警告（Web 前端）

### 估算公式

```javascript
function estimateTokens(text) {
    // 中文：約 1.5 字/token
    // 英文：約 4 字/token
    // 簡化：取平均 2 字/token
    return Math.ceil(text.length / 2);
}
```

### 警告閾值

```javascript
const TOKEN_LIMIT = 200000;
const WARNING_THRESHOLD = 0.75;  // 75% = 150,000 tokens
```

當超過 75% 時：
1. Token 數字變成警告色（橘色）
2. 顯示警告條
3. 提供「壓縮對話」按鈕

## 對話壓縮機制（Web 前端）

### 壓縮策略

```
壓縮前：[msg1, msg2, ..., msg40, msg41, ..., msg50]
                    ↓ 壓縮
壓縮後：[{摘要}, msg41, ..., msg50]

保留最近 10 則訊息
較舊訊息交給 Summarizer Agent 產生摘要
```

### Summarizer Prompt 設計

參考 Claude Code SDK 的 compaction 機制，摘要包含 5 個區塊：

```markdown
### 任務概覽 (Task Overview)
- 使用者的主要目標
- 對話在解決什麼問題

### 當前狀態 (Current State)
- 目前進展
- 已完成的部分

### 重要發現 (Important Discoveries)
- 關鍵資訊
- 重要決策及原因

### 下一步 (Next Steps)
- 待辦事項
- 尚未處理的需求

### 需保留的上下文 (Context to Preserve)
- 重要名稱、數字、設定值
- 專有名詞
- 不能遺忘的細節
```

## Socket.IO 事件（Web 前端）

### 發送訊息

```javascript
// 前端
socket.emit('ai_chat_event', {
    chatId: 'uuid-...',
    message: '使用者訊息',
    model: 'claude-sonnet'
});

// 後端回應
socket.on('ai_typing', { chatId, typing: true/false });
socket.on('ai_response', { chatId, message });
socket.on('ai_error', { chatId, error });
```

### 壓縮對話

```javascript
// 前端
socket.emit('compress_chat', { chatId: 'uuid-...' });

// 後端回應
socket.on('compress_started', { chatId });
socket.on('compress_complete', { chatId, messages, compressed_count });
socket.on('compress_error', { chatId, error });
```

## AI Log 記錄

所有 AI 呼叫都記錄到 `ai_logs` 分區表，包含：

| 欄位 | 說明 |
|------|------|
| `agent_id` | 使用的 Agent |
| `context_type` | 來源類型（`linebot-personal` / `linebot-group` / `bot-debug` / `web`） |
| `input_prompt` | 完整輸入（含歷史） |
| `system_prompt` | System Prompt |
| `allowed_tools` | 允許的工具列表 |
| `raw_response` | AI 原始回應 |
| `parsed_response` | 解析後的 JSON（含 tool_calls、tool_timings、tool_routing） |
| `model` | 使用的模型 |
| `input_tokens` / `output_tokens` | Token 統計 |
| `duration_ms` | 耗時 |

## 相關檔案

### 核心

- `services/claude_agent.py` — ClaudeClient 封裝、call_claude()
- `services/linebot_ai.py` — Bot 對話主流程、AI 回應後處理
- `services/linebot_agents.py` — Agent 定義、偏好持久化、啟動時 seed
- `services/ai_manager.py` — Prompt/Agent/Log CRUD

### Agent 與工具

- `services/bot/agents.py` — 平台無關的工具 Prompt 模板
- `services/bot/command_handlers.py` — 斜線指令 handler（/agent、/debug 等）
- `services/bot/commands.py` — CommandRouter 指令路由框架
- `services/bot/identity_router.py` — 未綁定用戶身份分流
- `services/bot/rate_limiter.py` — 受限模式頻率限制
- `services/bot/ai.py` — parse_ai_response()

### MCP 與 Skills

- `services/mcp/` — MCP Server 工具實作
- `skills/` — SkillManager、腳本執行器

### 前端

- `frontend/js/ai-assistant.js` — Web AI 對話介面
- `frontend/js/agent-settings.js` — AI Agent 設定管理介面
- `frontend/js/socket-client.js` — Socket.IO 客戶端

### 資料模型

- `models/ai.py` — Pydantic models
- `api/ai_router.py` — AI 對話 REST API
- `api/ai_management.py` — AI Prompt/Agent CRUD API
