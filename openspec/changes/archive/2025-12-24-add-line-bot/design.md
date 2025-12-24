## Context

本專案需要整合 Line Bot 作為訊息收集與助理入口。Line Bot 需要：
1. 記錄群組對話，將對話內容歸檔到對應的專案
2. 收集群組分享的圖片與檔案，統一儲存到 NAS
3. 提供個人對話助理功能，支援查詢知識庫、專案狀態、新增筆記/待辦

參考現有的 jaba-ai 專案中的 Line Bot 實作，採用相似的架構模式。

**依賴關係**：此提案依賴 `add-ai-management` 提案，使用其 AI Agent 設定和 AI Log 記錄功能。

## Goals / Non-Goals

### Goals
- 實作 Line Bot Webhook 接收訊息
- 群組訊息記錄到資料庫
- 群組與專案的手動綁定機制
- 圖片/檔案統一儲存到 NAS
- 個人對話的助理功能（查詢知識庫、專案狀態、新增筆記/待辦）
- 前端管理介面（群組管理、對話歷史、檔案瀏覽）

### Non-Goals
- 不實作群組申請審核流程（簡化為手動管理）
- 不實作複雜的 AI 對話（使用現有 AI 架構）
- 不實作 Line 支付功能

## Decisions

### 1. 架構設計

採用與 jaba-ai 相似的架構：

```
backend/src/ching_tech_os/
├── api/
│   └── linebot.py          # Webhook 路由與管理 API
├── services/
│   └── linebot.py          # Line Bot 業務邏輯
└── models/
    └── linebot.py          # Line 相關 Pydantic 模型

frontend/
├── js/apps/linebot.js      # Line Bot 管理前端
└── css/apps/linebot.css    # Line Bot 管理樣式
```

### 2. 資料庫設計

新增以下資料表：

```sql
-- Line 群組
CREATE TABLE line_groups (
    id UUID PRIMARY KEY,
    line_group_id VARCHAR(64) UNIQUE NOT NULL,  -- LINE 原生群組 ID
    name VARCHAR(256),
    project_id UUID REFERENCES projects(id),    -- 綁定的專案（可選）
    status VARCHAR(32) DEFAULT 'active',        -- active, inactive
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

-- Line 使用者
CREATE TABLE line_users (
    id UUID PRIMARY KEY,
    line_user_id VARCHAR(64) UNIQUE NOT NULL,   -- LINE 原生使用者 ID
    display_name VARCHAR(256),
    picture_url TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

-- Line 訊息記錄
CREATE TABLE line_messages (
    id UUID PRIMARY KEY,
    line_group_id UUID REFERENCES line_groups(id),  -- 群組 ID（群組訊息）
    line_user_id UUID REFERENCES line_users(id),    -- 發送者
    message_type VARCHAR(32) NOT NULL,              -- text, image, file, sticker, etc.
    content TEXT,                                    -- 文字內容
    media_path TEXT,                                 -- 媒體檔案路徑（NAS）
    metadata JSONB,                                  -- 額外資訊（檔名、大小等）
    source_type VARCHAR(32) NOT NULL,               -- group, user
    created_at TIMESTAMPTZ
);

-- Line 檔案
CREATE TABLE line_files (
    id UUID PRIMARY KEY,
    line_message_id UUID REFERENCES line_messages(id),
    line_group_id UUID REFERENCES line_groups(id),
    file_name VARCHAR(512),
    file_type VARCHAR(64),
    file_size BIGINT,
    storage_path TEXT NOT NULL,                      -- NAS 路徑
    thumbnail_path TEXT,                             -- 縮圖路徑（圖片用）
    created_at TIMESTAMPTZ
);
```

### 3. Line SDK 整合

使用 `line-bot-sdk` 套件的 v3 版本：

```python
# pyproject.toml 新增
dependencies = [
    "line-bot-sdk>=3.0.0",
]
```

Webhook 處理流程：
1. 接收 `/api/linebot/webhook` POST 請求
2. 驗證 X-Line-Signature
3. 解析事件（MessageEvent, JoinEvent, LeaveEvent 等）
4. 依事件類型分發處理

### 4. 訊息處理策略

#### 群組訊息
- 所有訊息記錄到 `line_messages` 表
- 圖片/檔案：下載到 NAS，記錄路徑到 `line_files` 表
- 如果群組已綁定專案，訊息自動關聯到該專案

#### 個人訊息（助理功能）
- 記錄對話歷史
- 使用 `linebot-personal` AI Agent 處理訊息（來自 ai-management）
- 支援以下指令格式：
  - `查詢 <關鍵字>` - 搜尋知識庫
  - `專案 <專案名>` - 查詢專案狀態
  - `筆記 <內容>` - 新增知識庫筆記
  - `待辦 <內容>` - （保留，待後續實作）
  - 一般對話 - 使用 AI 回應
- 所有 AI 調用自動記錄到 `ai_logs` 表

### 5. 檔案儲存策略

所有 Line 傳送的圖片/檔案統一儲存到 NAS：

```
//192.168.11.50/擎添開發/ching-tech-os/linebot/
├── groups/
│   └── {line_group_id}/
│       ├── images/
│       │   └── {date}/
│       │       └── {message_id}.{ext}
│       └── files/
│           └── {date}/
│               └── {message_id}_{filename}
└── users/
    └── {line_user_id}/
        └── ... (同上結構)
```

### 6. 前端管理介面

新增 Line Bot 管理應用程式，包含：

1. **群組管理**
   - 群組列表（顯示名稱、狀態、綁定專案）
   - 專案綁定設定（下拉選擇專案）
   - 群組啟用/停用

2. **對話歷史**
   - 選擇群組或使用者查看對話
   - 訊息列表（時間、發送者、內容）
   - 支援搜尋

3. **檔案庫覽**
   - 依群組/使用者瀏覽檔案
   - 圖片縮圖預覽
   - 檔案下載

## Risks / Trade-offs

### Risks
1. **Line API 限制** - Line Messaging API 有訊息發送限制
   - 緩解：主要用於記錄，主動發送訊息較少
2. **NAS 存取效能** - 大量檔案可能影響效能
   - 緩解：使用日期分目錄，避免單一目錄過多檔案
3. **Webhook 可靠性** - 需確保 Webhook 正確設定
   - 緩解：加入簽章驗證、錯誤處理

### Trade-offs
- **簡化 vs 完整**：選擇簡化的群組管理（手動綁定），不實作申請審核流程
- **即時 vs 批次**：選擇即時下載檔案，確保資料完整性

## Migration Plan

1. 建立 Alembic migration 新增資料表
2. 後端新增 API 路由與服務
3. 前端新增管理應用程式
4. 設定 Line Channel 並註冊 Webhook URL
5. 測試群組訊息記錄與助理功能

## Open Questions

1. ~~Line Bot 的群組訊息歸類方式？~~ 已確認：手動選擇專案
2. ~~個人對話的助理功能預計需要哪些操作？~~ 已確認：查詢知識庫、專案狀態、新增筆記/待辦、基本對話記錄
3. ~~圖片/檔案的儲存策略？~~ 已確認：統一用 NAS 儲存
