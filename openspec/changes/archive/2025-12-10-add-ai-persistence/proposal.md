# Change: AI 對話持久化與 System Prompt 管理

## Why
目前 AI 助手的對話記錄僅存在 localStorage，有以下限制：
1. 使用者換裝置或清除瀏覽器資料後，對話歷史消失
2. 多使用者環境無法區分不同人的對話
3. 沒有 System Prompt 機制來定義 AI 的行為模式

## What Changes
- 新增 `ai_chats` 資料表儲存對話（含 JSONB messages）
- 新增 `data/prompts/*.md` 管理 System Prompts
- 自己管理對話歷史，不依賴 Claude CLI session
- 前端改為從資料庫載入/儲存對話

## Impact
- Affected specs: 新增 `ai-persistence` spec
- Affected code:
  - `docker/init.sql` - 新增 `ai_chats` 表
  - `data/prompts/` - System Prompt 檔案
  - `backend/src/ching_tech_os/api/ai.py` - 新增對話 CRUD API
  - `backend/src/ching_tech_os/services/claude_agent.py` - 整合 system prompt + 對話歷史
  - `frontend/js/ai-assistant.js` - 改用 API 存取對話

## Technical Notes

### 資料表設計

```sql
CREATE TABLE ai_chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(100) DEFAULT '新對話',
    model VARCHAR(50) DEFAULT 'claude-sonnet',
    prompt_name VARCHAR(50) DEFAULT 'default',  -- 對應 data/prompts/{name}.md
    messages JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_chats_user_id ON ai_chats(user_id);
CREATE INDEX idx_ai_chats_updated_at ON ai_chats(updated_at DESC);
```

### Messages JSONB 結構

```json
[
  {"role": "user", "content": "你好", "timestamp": 1702345678},
  {"role": "assistant", "content": "你好！有什麼可以幫助你的？", "timestamp": 1702345680}
]
```

### System Prompt 檔案結構

```
data/prompts/
├── default.md          # 預設助手
├── code-assistant.md   # 程式碼助手
└── pm-assistant.md     # 專案管理助手
```

### 對話歷史管理（不依賴 Claude CLI session）

```python
async def call_claude(prompt: str, history: list, system_prompt: str, model: str):
    # 組合完整 prompt
    messages = []
    for msg in history:
        messages.append(f"{msg['role']}: {msg['content']}")

    full_prompt = "\n".join(messages) + f"\nuser: {prompt}"

    cmd = [
        "claude", "-p", full_prompt,
        "--system-prompt", system_prompt,
        "--model", model,
    ]
    # ... 執行
```

### API 設計

```
GET    /api/ai/chats              - 取得使用者的對話列表
POST   /api/ai/chats              - 建立新對話
GET    /api/ai/chats/:id          - 取得對話詳情
DELETE /api/ai/chats/:id          - 刪除對話
PATCH  /api/ai/chats/:id          - 更新對話（標題、訊息等）
GET    /api/ai/prompts            - 取得可用的 prompt 列表
```

### 流程

1. 前端發送 `ai_chat` 事件（含 chatId, message, model）
2. 後端從 DB 載入對話歷史和 prompt
3. 組合完整 prompt（history + system prompt + 新訊息）
4. 呼叫 Claude CLI（不用 --session-id）
5. 回應存入 DB，發送 `ai_response` 給前端

## Database Migration（Alembic）

### 為什麼需要
- `init.sql` 只能「第一次建立」，無法更新已存在的 DB
- 之後會有越來越多表，需要版本控制 schema 變更
- 支援多環境部署（dev → staging → production）

### 目錄結構
```
backend/
├── alembic.ini                 # Alembic 設定
├── migrations/
│   ├── env.py                  # 環境設定（讀取 config.py）
│   ├── script.py.mako          # migration 範本
│   └── versions/
│       ├── 001_create_users.py       # 現有 users 表
│       └── 002_create_ai_chats.py    # 新增 ai_chats 表
```

### 常用指令
```bash
# 建立新 migration
alembic revision -m "create_ai_chats"

# 執行 migration（升級到最新）
alembic upgrade head

# 回滾一個版本
alembic downgrade -1

# 查看目前版本
alembic current
```

### Docker Compose 整合
```yaml
services:
  backend:
    command: sh -c "alembic upgrade head && uvicorn ..."
```

### init.sql 處理
- 保留作為「全新安裝」的參考
- 實際部署用 `alembic upgrade head`
- 第一個 migration 對應現有 users 表

## Dependencies
- 已完成 `add-ai-agent-backend`
- 已有 PostgreSQL 資料庫

## Token 管理與對話壓縮

### 估算方式
- 使用字數估算：中文約 1.5 字/token，英文約 4 字/token
- 閾值：75% of 200k = 150,000 tokens

### 壓縮策略
```
壓縮前：[msg1, msg2, msg3, ..., msg50, msg51, ..., msg60]
                     ↓ 壓縮舊訊息
壓縮後：[{role: "system", content: "[摘要] 之前討論了..."}, msg51, ..., msg60]
```
- 保留最近 N 則訊息（例如 10 則）
- 較舊的訊息交給壓縮 Agent 產生摘要
- 摘要以 system role 插入對話開頭

### 壓縮 Agent
- Prompt：`data/prompts/summarizer.md`
- 輸入：需要壓縮的舊訊息
- 輸出：結構化摘要（保留關鍵資訊、決策、結論）

### UI 流程
```
對話 tokens > 75% → 顯示警告條
  ⚠️ 對話過長 (78%)，建議壓縮
  [🗜️ 壓縮對話]
     ↓ 點擊
  顯示「壓縮中...」
     ↓ Agent 完成
  更新 messages，警告消失
```

## Out of Scope
- 對話分享功能
- 對話匯出/匯入
