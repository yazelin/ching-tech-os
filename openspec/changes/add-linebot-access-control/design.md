# Design: Line Bot 存取控制

## Context
Line Bot 目前對所有訊息都會回應，沒有任何存取控制。需要實作：
1. Line 用戶與 CTOS 用戶的綁定機制
2. 群組 AI 回應的開關控制
3. 基於綁定狀態的存取控制

## Goals / Non-Goals

### Goals
- 只有綁定 CTOS 帳號的 Line 用戶才能使用 Bot
- 群組需要明確開啟才會回應 AI
- 用戶可以解除綁定以更換 Line 帳號
- 管理員可以查看所有用戶的綁定狀態

### Non-Goals
- 不實作完整的權限系統（另一個 proposal）
- 不限制 Line 用戶可以綁定多少個 CTOS 帳號（一個 Line 只能綁一個 CTOS）
- 不實作 CTOS 帳號綁定多個 Line 帳號

## Decisions

### 資料模型

**line_users 表（現有，修改使用方式）**
```sql
-- 現有欄位
user_id INTEGER REFERENCES users(id)  -- 綁定的 CTOS 用戶 ID
-- 已存在，開始使用
```

**line_groups 表（新增欄位）**
```sql
allow_ai_response BOOLEAN DEFAULT false  -- 是否允許 AI 回應
```

**line_binding_codes 表（新增）**
```sql
CREATE TABLE line_binding_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id),
    code VARCHAR(6) NOT NULL,  -- 6 位數字
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    used_by_line_user_id UUID REFERENCES line_users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_binding_codes_code ON line_binding_codes(code);
CREATE INDEX idx_binding_codes_user_id ON line_binding_codes(user_id);
```

### API 設計

**綁定相關 API**
```
POST /api/linebot/binding/generate-code
  - 需登入
  - 產生 6 位數字驗證碼
  - 回傳 { code: "123456", expires_at: "..." }

GET /api/linebot/binding/status
  - 需登入
  - 回傳目前用戶的 Line 綁定狀態
  - { is_bound: true, line_display_name: "...", bound_at: "..." }

DELETE /api/linebot/binding
  - 需登入
  - 解除目前用戶的 Line 綁定

GET /api/linebot/users
  - 需登入（管理員功能）
  - 回傳所有 Line 用戶列表，包含綁定狀態
```

**群組控制 API**
```
PATCH /api/linebot/groups/{id}
  - 需登入
  - 可設定 allow_ai_response
```

### Webhook 流程修改

```python
async def process_message_event(event):
    # 1. 取得 Line 用戶
    line_user = await get_or_create_user(...)

    # 2. 檢查是否為驗證碼（個人對話）
    if not is_group and is_binding_code_format(content):
        await handle_binding_code(line_user, content)
        return

    # 3. 存取控制檢查
    if not await check_access(line_user, line_group):
        if not is_group:
            await reply_text(reply_token, "請先在 CTOS 綁定您的 Line 帳號")
        return  # 群組靜默不回應

    # 4. 正常處理訊息
    await save_message(...)
    await handle_text_message(...)
```

### 存取控制邏輯

```python
async def check_access(line_user_id: UUID, line_group_id: UUID | None) -> bool:
    """
    檢查用戶是否有權限使用 Bot

    規則：
    1. Line 用戶必須綁定 CTOS 帳號
    2. 如果是群組訊息，群組必須設為 allow_ai_response = true
    """
    # 檢查用戶綁定
    line_user = await get_line_user(line_user_id)
    if not line_user or not line_user.user_id:
        return False

    # 如果是群組，檢查群組設定
    if line_group_id:
        group = await get_line_group(line_group_id)
        if not group or not group.allow_ai_response:
            return False

    return True
```

## Risks / Trade-offs

### 風險：驗證碼被濫用
- **緩解**：驗證碼 5 分鐘過期，每個用戶同時只能有一個有效驗證碼

### 風險：用戶忘記綁定
- **緩解**：個人對話會回覆提示訊息

### Trade-off：群組預設不回應
- **優點**：安全性高，不會意外在不適當的群組回應
- **缺點**：需要手動開啟每個群組
- **決定**：接受此 trade-off，安全優先

### Trade-off：一個 Line 帳號只能綁定一個 CTOS 帳號
- **優點**：簡化邏輯，明確對應
- **缺點**：若有多人共用 Line 帳號則無法使用
- **決定**：接受此限制，共用帳號不是預期的使用情境

## Migration Plan

1. 執行 migration 新增 `line_groups.allow_ai_response` 欄位（預設 false）
2. 執行 migration 新增 `line_binding_codes` 表
3. 部署新版後端
4. （可選）將現有已綁定專案的群組設為 `allow_ai_response = true`
5. 通知用戶需要綁定 Line 帳號
