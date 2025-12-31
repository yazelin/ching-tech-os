## Context

Line Bot 的 AI 功能目前使用硬編碼的 System Prompt，未整合 ai-management 系統。需要修改為使用資料庫中的 Agent 設定，以符合原始設計。

### 現狀

```python
# linebot_ai.py - 硬編碼
system_prompt = await build_system_prompt(line_group_id)  # 硬編碼 prompt
response = await call_claude(
    prompt=user_message,
    model="sonnet",  # 硬編碼 model
    ...
)

# log 記錄時
agent = await ai_manager.get_agent_by_name("linebot")  # 找不到
agent_id = agent["id"] if agent else None  # 變成 None
```

### 目標

```python
# 改為從 Agent 取得設定
agent_name = "linebot-group" if is_group else "linebot-personal"
agent = await ai_manager.get_agent_by_name(agent_name)
system_prompt = agent["system_prompt"]["content"]
model = agent["model"]  # claude-haiku 或 claude-sonnet

response = await call_claude(
    prompt=user_message,
    model=model,
    system_prompt=system_prompt,
    ...
)
```

## Goals / Non-Goals

### Goals
- Line Bot 使用資料庫中的 Agent/Prompt 設定
- 區分 `linebot-personal` 和 `linebot-group` 兩種情境
- AI Log 正確關聯到 Agent
- 應用程式啟動時自動建立預設 Agent（如不存在）

### Non-Goals
- 不修改前端 UI
- 不提供 API 動態切換 Agent

## Decisions

### 1. Agent 選擇邏輯

根據對話類型選擇 Agent：
- 個人對話（`line_group_id is None`）→ `linebot-personal`
- 群組對話（`line_group_id is not None`）→ `linebot-group`

### 2. 預設 Agent 初始化

在 FastAPI 啟動時（lifespan event）檢查並建立預設 Agent：

```python
DEFAULT_LINEBOT_AGENTS = [
    {
        "name": "linebot-personal",
        "display_name": "Line Bot 個人助理",
        "model": "claude-sonnet",
        "prompt": {
            "name": "linebot-personal",
            "content": "...",  # 包含 MCP 工具說明
            "category": "linebot",
        }
    },
    {
        "name": "linebot-group",
        "display_name": "Line Bot 群組助理",
        "model": "claude-haiku",
        "prompt": {
            "name": "linebot-group",
            "content": "...",  # 簡短版本
            "category": "linebot",
        }
    },
]
```

### 3. Prompt 內容設計

**linebot-personal**（完整版）：
- 包含 MCP 工具說明（專案查詢、知識庫）
- 語氣親切專業
- 不限制回覆長度

**linebot-group**（精簡版）：
- 包含 MCP 工具說明
- 限制回覆長度（不超過 200 字）
- 語氣簡潔

### 4. 群組綁定專案的處理

保留現有的動態注入邏輯，在 Agent 的 Prompt 基礎上附加群組資訊：

```python
# 從 Agent 取得基礎 prompt
base_prompt = agent["system_prompt"]["content"]

# 如果是群組且有綁定專案，附加資訊
if line_group_id and group_info:
    base_prompt += f"\n\n目前群組：{group_info['name']}"
    if group_info["project_name"]:
        base_prompt += f"\n綁定專案：{group_info['project_name']}"
        base_prompt += f"\n專案 ID：{group_info['project_id']}"
```

### 5. Fallback 機制

如果 Agent 不存在（理論上不會發生，因為啟動時會建立）：
- 使用硬編碼的預設 Prompt 作為 fallback
- 記錄警告日誌

## Risks / Trade-offs

### Risks
1. **啟動時間增加** - 需要檢查/建立 Agent
   - 緩解：僅在 Agent 不存在時才 INSERT

2. **Prompt 被誤刪** - 使用者可能刪除預設 Prompt
   - 緩解：下次啟動時會重新建立

### Trade-offs
- **簡單 vs 靈活**：不提供前端切換 Agent 功能，保持簡單
- **預設 vs 自訂**：保留現有 Agent 設定，不覆蓋使用者修改

## Migration Plan

1. 建立 `ensure_default_linebot_agents()` 函數
2. 在 `main.py` 的 lifespan 中調用
3. 修改 `linebot_ai.py` 使用 Agent 設定
4. 更新現有資料庫中的 Prompt 內容（加入 MCP 工具說明）
