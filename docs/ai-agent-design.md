# AI Agent 設計與對話管理

## 概覽

ChingTech OS 的 AI 助手透過 Claude CLI 與 Claude API 溝通。本文件記錄對話管理、Token 控制、壓縮機制等設計決策。

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
│  │         services/claude_agent.py        │                 │
│  │         services/ai_chat.py             │                 │
│  └────────────────┬───────────────────────┘                 │
│                   │                                          │
│           ┌───────┴───────┐                                  │
│           ▼               ▼                                  │
│  ┌────────────────┐ ┌─────────────────┐                     │
│  │   PostgreSQL   │ │ data/prompts/   │                     │
│  │   ai_chats     │ │ *.md files      │                     │
│  └────────────────┘ └─────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Claude CLI                               │
│  claude -p "prompt" --system-prompt "..." --model sonnet    │
└─────────────────────────────────────────────────────────────┘
```

## 對話歷史管理策略

### 方案比較

| 方案 | 優點 | 缺點 |
|------|------|------|
| Claude CLI Session (`--session-id`) | CLI 自動管理歷史 | 無法控制 context、難以壓縮 |
| **自己管理歷史** | 完全控制、可壓縮、可持久化 | 需自己組合 prompt |

### 選擇：自己管理歷史

我們選擇自己管理對話歷史，原因：

1. **持久化需求**：對話需存入 DB，跨 session 保留
2. **壓縮控制**：需要實作 token 警告和壓縮機制
3. **多裝置支援**：使用者可在不同裝置繼續對話
4. **Prompt 客製化**：可動態切換 System Prompt

### 實作方式

每次發送訊息時：

```python
async def call_claude(prompt, model, history, system_prompt):
    # 1. 組合歷史訊息
    full_prompt = compose_prompt_with_history(history, prompt)

    # 2. 呼叫 Claude CLI（不使用 --session-id）
    cmd = [
        "claude", "-p", full_prompt,
        "--system-prompt", system_prompt,
        "--model", model
    ]

    # 3. 執行並取得回應
    proc = await asyncio.create_subprocess_exec(*cmd, ...)
    stdout, stderr = await proc.communicate()

    return stdout
```

### Prompt 組合格式

```
對話歷史：

user: 第一則訊息
assistant: AI 回應
user: 第二則訊息
assistant: AI 回應

user: 最新訊息
```

## System Prompt 設計

### 檔案結構

```
data/prompts/
├── default.md          # 預設助手
├── code-assistant.md   # 程式碼助手
├── pm-assistant.md     # 專案管理助手
└── summarizer.md       # 對話壓縮（內部使用）
```

### Prompt 範本結構

```markdown
# 角色名稱

你是 ChingTech AI [角色]，[角色描述]。

## 你的個性
- 特點 1
- 特點 2

## 對話語氣
- 風格指引

## 能力範圍
- 能做什麼

## 注意事項
- 限制和提醒
```

### 動態載入

```python
def get_prompt_content(prompt_name: str) -> str | None:
    prompt_file = PROMPTS_DIR / f"{prompt_name}.md"
    if not prompt_file.exists():
        return None
    return prompt_file.read_text(encoding="utf-8")
```

## Token 估算與警告

### 為什麼需要

Claude 有 context window 限制（約 200k tokens）。當對話過長時：
- 回應品質下降
- 可能截斷重要上下文
- API 成本增加

### 估算公式

```javascript
function estimateTokens(text) {
    // 中文：約 1.5 字/token
    // 英文：約 4 字/token
    // 簡化：取平均 2 字/token
    return Math.ceil(text.length / 2);
}

function getChatTokens(messages) {
    return messages.reduce((sum, msg) =>
        sum + estimateTokens(msg.content), 0);
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

## 對話壓縮機制

### 壓縮策略

```
壓縮前：[msg1, msg2, ..., msg40, msg41, ..., msg50]
                    ↓ 壓縮
壓縮後：[{摘要}, msg41, ..., msg50]

保留最近 10 則訊息
較舊訊息交給 Summarizer Agent 產生摘要
```

### 壓縮流程

```
Frontend                    Backend                     Claude CLI
   │                           │                           │
   │── compress_chat ─────────►│                           │
   │                           │── 分割訊息 ──────────────►│
   │◄─ compress_started ──────│   (保留最近10則)           │
   │                           │                           │
   │                           │── 讀取 summarizer.md ────►│
   │                           │── claude -p "壓縮..." ───►│
   │                           │◄─ 摘要 ──────────────────│
   │                           │                           │
   │                           │── 更新 DB ───────────────►│
   │◄─ compress_complete ─────│                           │
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

### 壓縮後的 Messages 結構

```json
[
  {
    "role": "system",
    "content": "[對話摘要]\n### 任務概覽\n...",
    "timestamp": 1702345600,
    "is_summary": true
  },
  {"role": "user", "content": "最近的訊息1", "timestamp": 1702345700},
  {"role": "assistant", "content": "回應1", "timestamp": 1702345701},
  // ... 最近 10 則訊息
]
```

## Claude CLI 整合

### 模型對應

```python
MODEL_MAP = {
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}
```

### 命令格式

```bash
claude -p "prompt" \
       --system-prompt "system prompt content" \
       --model sonnet
```

### 不使用的參數

- `--session-id`：不使用，自己管理歷史
- `--resume`：不使用，每次都帶完整歷史

### 錯誤處理

```python
try:
    proc = await asyncio.create_subprocess_exec(...)
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(), timeout=120
    )
except asyncio.TimeoutError:
    return ClaudeResponse(success=False, error="請求超時")
except FileNotFoundError:
    return ClaudeResponse(success=False, error="找不到 Claude CLI")
```

## Socket.IO 事件

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

## 最佳實踐

### 1. Token 管理

- 定期檢查 token 使用量
- 超過 75% 提醒使用者壓縮
- 壓縮使用較便宜的模型（haiku）

### 2. System Prompt

- 保持簡潔，避免過長
- 使用繁體中文
- 明確定義角色和限制

### 3. 錯誤處理

- 所有 Claude CLI 呼叫都設定 timeout
- 錯誤訊息回傳給前端顯示
- 失敗時不更新 DB

### 4. 效能考量

- 使用 asyncio 非同步呼叫 CLI
- 大型對話考慮分頁載入
- 壓縮在背景執行，不阻塞 UI

## 相關檔案

- `backend/src/ching_tech_os/services/claude_agent.py` - Claude CLI 封裝
- `backend/src/ching_tech_os/services/ai_chat.py` - 對話 CRUD
- `backend/src/ching_tech_os/api/ai.py` - Socket.IO 事件
- `backend/src/ching_tech_os/api/ai_router.py` - REST API
- `backend/src/ching_tech_os/models/ai.py` - Pydantic models
- `data/prompts/*.md` - System Prompts
- `frontend/js/ai-assistant.js` - 前端 AI 助手
- `frontend/js/socket-client.js` - Socket.IO 客戶端

## 未來擴展

- [ ] Streaming 回應（即時顯示 AI 回覆）
- [ ] 多輪對話記憶優化
- [ ] 對話匯出/匯入
- [ ] 對話分享功能
- [ ] 自動壓縮（達閾值自動觸發）
