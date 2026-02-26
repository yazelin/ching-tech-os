# Design: Configurable Restricted Mode

## 核心決策

### 儲存位置：`ai_agents.settings` JSONB

選擇利用現有的 `ai_agents.settings` 欄位而非新增表或設定檔，原因：
- 已有 AI 管理 UI 可編輯 Agent 設定
- JSONB 支援靈活的 key-value 結構
- 不同部署的 DB 天然隔離，無需額外機制
- 與 system_prompt、tools 等設定集中管理

### 讀取模式：Fallback Pattern

所有文字模板採用一致的讀取模式：

```python
def _get_setting(agent: dict, key: str, default: str) -> str:
    settings = agent.get("settings") or {}
    value = settings.get(key)
    return value if value else default
```

### 變數替換：簡單 format

僅 rate limit 訊息需要變數替換，使用 Python `str.format_map()` + `defaultdict` 防止 KeyError：

```python
msg = template.format_map(defaultdict(str, hourly_limit=str(limit)))
```

## 實作設計

### 1. 新增 helper 函式（identity_router.py）

新增 `_get_restricted_setting(agent, key, default)` 函式，統一從 agent settings 讀取文字模板。

### 2. 修改 get_welcome_message（command_handlers.py）

改為 async，先嘗試從 `bot-restricted` Agent settings 讀取 `welcome_message`，未設定時 fallback 到現有預設值。FollowEvent 發送歡迎訊息的地方也需同步改為 async。

### 3. 修改 rate_limiter.py

`check_and_increment()` 新增可選參數 `custom_messages: dict | None`，傳入 `rate_limit_hourly_msg` 和 `rate_limit_daily_msg`。由 `identity_router.py` 從 agent settings 讀取後傳入。

### 4. 修改 identity_router.py

- `handle_restricted_mode()`：讀取 agent settings 後傳入 rate limiter 和免責聲明
- `route_unbound()`：reject 模式時讀取 `binding_prompt`
- 免責聲明：在回覆文字後附加 `settings.disclaimer`

### 5. Migration

更新現有 `bot-restricted` Agent 的 `settings` 欄位，寫入預設值。使用 `COALESCE` 確保不覆蓋已有設定。

## 不改動的部分

- `ai_agents` 表結構（`settings` JSONB 欄位已存在）
- AI 管理 UI（已支援編輯 Agent settings）
- 環境變數（rate limit 數值、model、public folders 維持 env var）
- System prompt（維持在 `ai_prompts` 表，透過 UI 編輯）
