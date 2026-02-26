## Context

CTOS Bot 系統目前的訊息處理流程是線性的：

```
訊息進入 → 重置指令檢查 → 觸發判斷 → Agent 選擇(群/個) → 權限查詢 → Prompt 組裝 → Claude 呼叫 → 回覆
```

核心限制：
- **指令系統**：只有 `/reset` 系列，硬編碼在 `trigger.py` 的 `is_reset_command()` 和 `linebot_ai.py` L621-652，無法擴充新指令
- **身份處理**：未綁定用戶的處理邏輯散落在 `linebot_ai.py`（個人對話回覆綁定提示）和 `bot_telegram/handler.py`（檢查綁定狀態），無統一分流點
- **Agent 選擇**：只有 `bot-personal` / `bot-group` 兩種，沒有根據身份或指令切換 Agent 的機制
- **無頻率限制**：所有用戶都無使用量管控

目前處理入口在 `linebot_ai.py:process_message_with_ai()` (L594)，是 Line 和 Telegram 共用的核心函式。

## Goals / Non-Goals

**Goals:**
- 建立可擴充的斜線指令框架，Line/Telegram 共用
- 實作身份分流路由器，支援 `reject`（預設）和 `restricted` 兩種策略
- `/debug` 指令讓管理員透過 AI 分析系統 logs
- 受限模式 Agent 框架，prompt 和工具白名單可透過 DB + 環境變數配置
- Rate limiter 對未綁定用戶限制使用頻率
- 所有新功能向下相容，預設行為與現有系統一致

**Non-Goals:**
- 多租戶（multi-tenant）架構 — 不在此次範圍
- 前端管理 UI 調整（受限模式 Agent 可透過現有 AI 管理介面編輯）
- Telegram 的 `/debug` 指令（先只做 Line，架構預留 Telegram 擴充）
- 未綁定用戶的檔案上傳/圖片處理（受限模式僅支援文字問答）

## Decisions

### Decision 1：指令路由的插入點 — 在 `process_message_with_ai()` 入口前攔截

**方案 A（選用）：在 `process_message_with_ai()` 入口統一攔截**
```
handle_text_message()
  ↓
command = parse_slash_command(content)
if command:
  → slash_command_router.dispatch(command, context)  # 新增
  → return
  ↓
process_message_with_ai()  # 現有流程不變
```

**方案 B（捨棄）：在 trigger.py 的 `should_trigger_ai()` 中擴展**
- 缺點：trigger.py 負責「是否觸發 AI」，指令處理不是 AI 觸發，職責混淆
- 缺點：指令可能需要 DB 查詢（async），但 `should_trigger_ai()` 是同步函式

**理由**：指令處理和 AI 處理是兩條平行路徑，在入口分流最乾淨。現有 `is_reset_command()` 的邏輯也可遷移到新指令框架中。

### Decision 2：指令框架設計 — 註冊式 + 字典路由

新增 `services/bot/commands.py`，採用簡單的字典註冊模式：

```python
# 指令定義
@dataclass
class SlashCommand:
    name: str                          # 指令名稱（如 "debug"）
    aliases: list[str]                 # 別名（如 ["偵錯", "診斷"]）
    handler: Callable                  # async handler(context) -> str | None
    require_bound: bool = False        # 是否要求已綁定 CTOS 帳號
    require_admin: bool = False        # 是否要求管理員
    private_only: bool = False         # 是否僅限個人對話
    platforms: set[str] = {"line", "telegram"}  # 支援的平台

# 路由核心
class CommandRouter:
    _commands: dict[str, SlashCommand]  # key = "/" + name 或 alias

    def parse(self, content: str) -> tuple[SlashCommand, str] | None:
        """解析訊息，回傳 (command, args) 或 None"""

    async def dispatch(self, command, args, context) -> str | None:
        """執行指令，包含權限檢查，回傳回覆文字"""
```

**為什麼不用 class-based handler 或 plugin 系統**：目前指令數量少（reset, debug），字典路由夠用且容易理解。等指令超過 10 個再考慮 plugin 架構。

### Decision 3：身份分流的插入點 — 在 Agent 選擇之前

在 `process_message_with_ai()` 中，現有流程 L704-723 查詢用戶綁定狀態後，**在 Agent 選擇之前**插入分流邏輯：

```
現有流程:
  查詢 bot_user → 取得 ctos_user_id → 選 Agent(群/個) → 組裝 prompt

新流程:
  查詢 bot_user → 取得 ctos_user_id
    ↓
  if ctos_user_id:
    → 已綁定路徑（現有流程不變）
  else:
    → identity_router.route_unbound(policy, context)
      ├─ policy="reject": 回覆綁定提示，return
      └─ policy="restricted": 選 bot-restricted Agent，走簡化 AI 流程
```

**為什麼不獨立成 middleware**：分流需要 `ctos_user_id`、`is_group` 等上下文，這些在 `process_message_with_ai()` 內才能取得。抽成 middleware 反而要傳遞大量參數。

### Decision 4：受限模式 AI 流程 — 可配置的工具鏈

受限模式走與已綁定用戶相似的流程，但使用獨立的 Agent 和受限的工具集：

```
受限模式流程:
  取得 bot-restricted Agent（從 DB）
    ↓
  組裝 system prompt:
    - Agent 基礎 prompt（部署方自訂的衛教/客服 prompt）
    - 受限模式工具說明（根據 Agent 的 tools 設定動態生成）
    - 無自訂記憶
    - 對話識別（platform_user_id，標記為「未綁定用戶」）
    ↓
  取得對話歷史（同現有機制，用 conversation_reset_at 過濾，limit=10）
    ↓
  call_claude(
    model = BOT_RESTRICTED_MODEL,
    tools = Agent 定義的工具白名單
  )
    ↓
  回覆（支援文字，不處理 FILE_MESSAGE）
```

**工具白名單由 Agent 設定決定**：`bot-restricted` Agent 在 DB 中的 `tools` 欄位定義允許的工具。部署方可透過 AI 管理介面調整。

**預設工具範圍**：`search_knowledge`（限公開分類）。但部署方可依需求擴充，例如：
- 診所場景：掛號查詢 skill、衛教知識庫搜尋
- 客服場景：產品查詢 MCP 工具、FAQ 知識庫
- 一般場景：純文字問答（無工具）

**知識庫公開存取控制**：知識庫分類新增「允許未綁定用戶查詢」權限旗標。受限模式呼叫 `search_knowledge` 時，結果自動過濾為僅包含標記為公開的分類/項目。同樣地，圖書館資料夾也可標記為公開，允許未綁定用戶查閱。此權限旗標需在知識庫 spec 中定義（見 Modified Capabilities）。

### Decision 5：`/debug` 指令實作 — 獨立 Agent + debug-skill

`/debug` 不是簡單回覆文字，而是啟動一個**獨立的 AI 對話回合**，使用 `bot-debug` Agent 搭配專用的 `debug-skill`：

```
/debug [問題描述]
  ↓
權限檢查：必須是已綁定的管理員（is_admin=true）
  ↓
取得 bot-debug Agent
  ↓
組裝 debug system prompt:
  - 開發者助理角色
  - 可用的診斷 skill scripts 說明
  ↓
call_claude(
  prompt = 用戶的問題描述（或預設「分析系統目前狀態」）,
  system_prompt = debug_prompt,
  model = BOT_DEBUG_MODEL,
  tools = ["run_skill_script"],  # 透過 skill 執行診斷腳本
)
  ↓
回覆診斷結果
```

**debug-skill 架構**：建立 `skills/debug-skill/`，包含多個診斷腳本：

| Script | 功能 | 說明 |
|--------|------|------|
| `check-server-logs` | 伺服器 logs | `journalctl -u ching-tech-os` 最近 N 行，支援關鍵字過濾 |
| `check-ai-logs` | AI 對話記錄 | 查詢 `ai_logs` 表，支援失敗記錄篩選 |
| `check-nginx-logs` | Nginx logs | `docker logs ching-tech-os-nginx`（Nginx 運行在 Docker 內） |
| `check-db-status` | 資料庫狀態 | 連線數、表大小、慢查詢等 |
| `check-system-health` | 綜合健檢 | 一次跑完所有項目，回傳摘要 |

**為什麼用 debug-skill 而非直接給 Bash 工具**：
- 每個 script 職責明確，比 AI 自行拼 bash 指令更安全可控
- 腳本可隨時擴充新診斷項目，不需改 Agent 設定
- 複用現有 `run_skill_script` 機制，不用開新工具
- Nginx 在 Docker 內，腳本封裝正確的 `docker logs` 指令，AI 不需知道部署細節

**Debug Agent 的 system prompt 核心內容**：
- 角色：CTOS 系統診斷助理
- 可用的 skill scripts 及參數說明
- 輸出格式：問題摘要 + 嚴重程度 + 可能原因 + 建議處理方式
- 安全限制：僅使用 debug-skill 的 scripts，唯讀診斷

### Decision 6：Rate Limiter — 資料庫計數 + 記憶體快取

**資料模型**：

```sql
CREATE TABLE bot_usage_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_user_id UUID NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    period_type VARCHAR(10) NOT NULL,  -- 'hourly' | 'daily'
    period_key VARCHAR(20) NOT NULL,   -- '2026-02-26-14' | '2026-02-26'
    message_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(bot_user_id, period_type, period_key)
);
```

**檢查流程**：
```
收到未綁定用戶訊息
  ↓
查詢 bot_usage_tracking（本小時 + 今日）
  ↓
if 超過限額:
  → 回覆「已達使用上限」提示
  → return
  ↓
處理訊息（受限模式）
  ↓
UPDATE bot_usage_tracking SET message_count = message_count + 1
```

**為什麼不用 Redis**：CTOS 目前不依賴 Redis，為了頻率限制引入新依賴不值得。PostgreSQL 的 UPSERT 效能足夠（未綁定用戶量不大）。

**配置項**（環境變數）：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `BOT_UNBOUND_USER_POLICY` | `reject` | 未綁定用戶策略：`reject` / `restricted` |
| `BOT_RESTRICTED_MODEL` | `haiku` | 受限模式使用的 AI 模型（控制成本） |
| `BOT_DEBUG_MODEL` | `sonnet` | Debug 模式使用的 AI 模型 |
| `BOT_RATE_LIMIT_HOURLY` | `20` | 每小時訊息上限 |
| `BOT_RATE_LIMIT_DAILY` | `50` | 每日訊息上限 |
| `BOT_RATE_LIMIT_ENABLED` | `true` | 是否啟用頻率限制（`restricted` 模式下） |

### Decision 7：Agent 預設初始化 — 複用現有 `ensure_default_agents()` 機制

現有 `linebot_agents.py` 在啟動時建立 `bot-personal` / `bot-group` Agent。新增：

- **`bot-restricted`**：受限模式 Agent，預設 prompt 為通用的「我是 AI 助理，僅能回答特定範圍的問題」，部署方應自行修改
- **`bot-debug`**：管理員診斷 Agent，prompt 包含 log 查詢指引

這兩個 Agent 同樣在 `ensure_default_agents()` 中建立，存在則不覆蓋。部署方可透過 Web UI（AI 管理介面）修改 prompt 和工具設定。

## Risks / Trade-offs

**[Risk] `/debug` 指令的診斷腳本可能暴露敏感資訊**
→ Mitigation：僅限 `is_admin=true` 的已綁定用戶；透過 debug-skill scripts 封裝診斷操作，每個 script 只做特定唯讀查詢；不提供通用 Bash 執行能力。

**[Risk] Rate limiter 用 PostgreSQL 而非記憶體快取，高併發時有瓶頸**
→ Mitigation：未綁定用戶量通常不大（病人/訪客），PostgreSQL UPSERT 效能足夠。若未來需要擴展，可加入記憶體快取層（dict + TTL）。

**[Risk] 受限模式的 `search_knowledge` 可能洩漏內部知識庫資料**
→ Mitigation：知識庫分類新增「公開存取」權限旗標，受限模式查詢時自動過濾為僅回傳公開分類的內容。部署方可精確控制哪些知識對未綁定用戶可見。同理，圖書館資料夾也可標記為公開或內部。

**[Risk] 指令框架遷移 `/reset` 可能影響現有行為**
→ Mitigation：遷移時保留所有現有別名（`/新對話`、`/忘記`等），加入測試確認行為一致。

**[Trade-off] `/debug` 用 skill scripts 而非直接給 AI Bash 工具**
→ 犧牲部分靈活性換取安全性和可維護性。每新增診斷需求要寫新 script，但換來操作可控、方便擴充。

## Migration Plan

1. **新增 `bot_usage_tracking` 表**（Alembic migration）— 無破壞性，純新增
2. **新增 `config.py` 設定項**（有預設值）— 不影響現有部署
3. **新增 `services/bot/commands.py`** — 指令框架，純新增
4. **遷移 `/reset` 到指令框架** — 保留 `trigger.py` 的 `is_reset_command()` 作為 fallback
5. **新增 `bot-restricted` 和 `bot-debug` Agent 初始化** — 在 `ensure_default_agents()` 中
6. **修改 `process_message_with_ai()`** — 插入指令攔截和身份分流
7. **新增 rate limiter 檢查** — 在受限模式入口

**Rollback**：所有行為受 `BOT_UNBOUND_USER_POLICY` 控制，設為 `reject`（預設值）即回到現有行為。指令框架的 `/reset` 遷移保留原函式作為 fallback。

## Open Questions

1. **受限模式是否需要對話歷史？** — 傾向需要（多輪問答體驗更好），但歷史長度可縮短（如 limit=10）
2. **Rate limiter 超限訊息是否需要多語言？** — 目前先用中文，未來可配合 `bot_users.language` 欄位
3. **受限模式是否區分群組/個人？** — 初期只支援個人對話（群組的未綁定用戶本來就不觸發 AI），架構預留群組擴充
4. **知識庫「公開存取」的粒度** — 分類層級（整個分類公開）還是項目層級（單一 knowledge item 公開）？傾向分類層級，管理較簡單
