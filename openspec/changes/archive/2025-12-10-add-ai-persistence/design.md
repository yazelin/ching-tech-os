# Design: AI 對話持久化與 System Prompt 管理

## 架構概覽

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
│  │   api/ai.py     │◄──►│ claude_agent.py │                 │
│  │  (REST + SIO)   │    │  (CLI wrapper)  │                 │
│  └────────┬────────┘    └────────┬────────┘                 │
│           │                       │                          │
│           ▼                       ▼                          │
│  ┌────────────────┐    ┌─────────────────┐                  │
│  │   PostgreSQL   │    │ data/prompts/   │                  │
│  │   ai_chats     │    │ *.md files      │                  │
│  └────────────────┘    └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Claude CLI                               │
│  claude -p "full_prompt" --system-prompt "..." --model ...  │
│  (不使用 --session-id，我們自己管理對話歷史)                   │
└─────────────────────────────────────────────────────────────┘
```

## 資料流程

### 1. 載入對話列表
```
Frontend                    Backend                     Database
   │                           │                           │
   │── GET /api/ai/chats ─────►│                           │
   │                           │── SELECT id,title,... ───►│
   │                           │◄─ rows ──────────────────│
   │◄─ [{id, title, ...}] ────│                           │
```

### 2. 發送訊息（自己管理歷史）
```
Frontend                    Backend                     Claude CLI
   │                           │                           │
   │── ai_chat (SIO) ─────────►│                           │
   │                           │── SELECT messages ───────►│(DB)
   │                           │── 讀取 prompt.md ─────────►│(File)
   │◄─ ai_typing ─────────────│                           │
   │                           │── claude -p "history+msg" ►│
   │                           │   --system-prompt "..."    │
   │                           │◄─ response ──────────────│
   │                           │── UPDATE messages ───────►│(DB)
   │◄─ ai_response ───────────│                           │
```

### 3. 刪除對話
```
Frontend                    Backend                     Database
   │                           │                           │
   │── DELETE /api/ai/chats/id►│                           │
   │                           │── DELETE FROM ai_chats ──►│
   │◄─ 200 OK ────────────────│                           │
```

## 對話歷史組合策略

### Prompt 組合格式

```
[System Prompt 內容]

---

對話歷史：

user: 第一則訊息
assistant: AI 回應
user: 第二則訊息
assistant: AI 回應
...
user: 最新訊息
```

### Token 限制處理

1. **初期策略**：截斷舊訊息
   - 保留最近 N 則訊息（例如 20 則）
   - 或保留最近 X tokens

2. **未來可擴展**：
   - Summarization（把舊對話摘要）
   - 重要訊息標記（保留關鍵訊息）

## System Prompt 設計

### 檔案結構
```
data/prompts/
├── default.md          # 預設助手
├── code-assistant.md   # 程式碼助手
└── pm-assistant.md     # 專案管理助手
```

### Prompt 範本（參考 jaba）
```markdown
你是 ChingTech AI 助手，[角色描述]。

## 你的個性
- [特點 1]
- [特點 2]

## 對話語氣
- [風格指引]

## 可執行動作（未來擴展）
- `action_name`: 動作描述

## 注意事項
- 使用繁體中文回應
- [其他限制]
```

## 安全考量

1. **使用者隔離**
   - API 必須驗證 user_id
   - WHERE user_id = :current_user

2. **SQL Injection 防護**
   - 使用參數化查詢
   - JSONB 操作使用 PostgreSQL 函數

## Token 估算與壓縮

### Token 估算公式
```javascript
function estimateTokens(text) {
    // 中文：約 1.5 字/token，英文：約 4 字/token
    // 簡化：取平均 2 字/token
    return Math.ceil(text.length / 2);
}

function getChatTokens(messages) {
    return messages.reduce((sum, msg) => sum + estimateTokens(msg.content), 0);
}

const TOKEN_LIMIT = 200000;
const WARNING_THRESHOLD = 0.75; // 150,000 tokens
```

### 壓縮流程
```
Frontend                    Backend                     Claude CLI
   │                           │                           │
   │── compress_chat (SIO) ───►│                           │
   │                           │── 取出舊訊息（保留最近10則）│
   │                           │── 讀取 summarizer.md ─────►│
   │◄─ compress_started ──────│                           │
   │                           │── claude -p "壓縮這些..." ►│
   │                           │◄─ 摘要 ──────────────────│
   │                           │── 更新 DB messages ──────►│
   │◄─ compress_complete ─────│                           │
   │   (新 messages, tokens)   │                           │
```

### 壓縮後 Messages 結構
```json
[
  {
    "role": "system",
    "content": "[對話摘要]\n之前的討論重點：\n1. 討論了 X 功能的實作方式\n2. 決定使用 Y 技術\n3. 待辦：完成 Z 模組",
    "timestamp": 1702345600,
    "is_summary": true
  },
  {"role": "user", "content": "最近的訊息1", "timestamp": 1702345700},
  {"role": "assistant", "content": "回應1", "timestamp": 1702345701},
  // ... 最近 10 則訊息
]
```

### summarizer.md Prompt 範本（參考 Claude SDK compaction）
```markdown
你是對話摘要助手。請將以下對話歷史壓縮成結構化摘要，讓 AI 在後續對話中能快速理解上下文。

## 輸出格式
請用以下格式輸出：

### 任務概覽 (Task Overview)
- 使用者的主要目標是什麼？
- 這個對話在解決什麼問題？

### 當前狀態 (Current State)
- 目前進展到哪裡？
- 有什麼已完成的部分？

### 重要發現 (Important Discoveries)
- 過程中發現的關鍵資訊
- 做出的重要決策及原因

### 下一步 (Next Steps)
- 待辦事項
- 使用者提到但尚未處理的需求

### 需保留的上下文 (Context to Preserve)
- 重要的名稱、數字、設定值
- 專有名詞或特定術語
- 任何不能遺忘的細節

## 注意事項
- 保持簡潔，但不要遺漏重要細節
- 使用繁體中文
- 摘要應該讓 AI 讀完後能無縫接續對話
```

## Alembic Migration 設計

### env.py 整合 config.py
```python
# migrations/env.py
from ching_tech_os.config import settings

def get_url():
    return settings.database_url

config.set_main_option("sqlalchemy.url", get_url())
```

### Migration 範例（002_create_ai_chats.py）
```python
"""create ai_chats table

Revision ID: 002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade():
    op.create_table(
        'ai_chats',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('title', sa.String(100), server_default='新對話'),
        sa.Column('model', sa.String(50), server_default='claude-sonnet'),
        sa.Column('prompt_name', sa.String(50), server_default='default'),
        sa.Column('messages', JSONB, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_ai_chats_user_id', 'ai_chats', ['user_id'])
    op.create_index('idx_ai_chats_updated_at', 'ai_chats', ['updated_at'])

def downgrade():
    op.drop_table('ai_chats')
```

### start.sh 整合
```bash
# 啟動前先執行 migration
cd backend && uv run alembic upgrade head
```

## 簡化決策

| 原設計 | 簡化後 |
|--------|--------|
| `ai_chats` + `ai_messages` 兩表 | 單表 `ai_chats` + JSONB messages |
| `ai_prompts` 資料表 | `data/prompts/*.md` 檔案 |
| Claude CLI session | 自己管理對話歷史 |
| localStorage 遷移 | 移除（不保留舊資料）|
| 手動執行 init.sql | Alembic 自動 migration |
