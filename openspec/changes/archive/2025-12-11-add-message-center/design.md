# Design: add-message-center

## Context

ChingTech OS 需要一個集中式的訊息管理系統，用於：
- 安全審計（登入記錄、異常行為追蹤）
- 系統監控（錯誤日誌、警告通知）
- 問題除錯（追蹤問題發生的時間線）
- 應用程式通知持久化（使用者可回顧歷史通知）

## Goals / Non-Goals

### Goals
- 提供統一的訊息儲存與查詢介面
- 完整記錄登入歷史（含 IP、裝置、地理位置）
- 支援多維度訊息分類（嚴重程度 + 來源）
- 即時推送新訊息到前端
- 保留 1 年歷史資料

### Non-Goals（第一階段）
- 不實作日誌匯出功能
- 不實作自動告警規則
- 不整合外部 SIEM 系統
- 不實作日誌分析儀表板

## Decisions

### 決策 1: 訊息資料模型

#### 訊息分類維度

**嚴重程度（Severity）：**
- `debug` - 除錯資訊（僅開發環境）
- `info` - 一般資訊
- `warning` - 警告（需要注意但非錯誤）
- `error` - 錯誤（功能受影響）
- `critical` - 嚴重錯誤（系統層級問題）

**來源分類（Source）：**
- `system` - 系統層級（啟動、關閉、資源）
- `security` - 安全相關（登入、權限、異常存取）
- `app` - 應用程式（各功能模組）
- `user` - 使用者操作（通知、提醒）

#### 資料庫結構

```sql
-- 訊息主表
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 分類
    severity VARCHAR(20) NOT NULL,  -- debug/info/warning/error/critical
    source VARCHAR(20) NOT NULL,    -- system/security/app/user
    category VARCHAR(50),           -- 細分類（如 auth, file-manager, ai-assistant）

    -- 內容
    title VARCHAR(200) NOT NULL,
    content TEXT,
    metadata JSONB,                 -- 結構化附加資料

    -- 關聯
    user_id INTEGER REFERENCES users(id),  -- 關聯使用者（可為空）
    session_id VARCHAR(100),               -- 關聯 session

    -- 索引欄位
    is_read BOOLEAN DEFAULT FALSE,

    -- 分區鍵
    partition_date DATE NOT NULL DEFAULT CURRENT_DATE
) PARTITION BY RANGE (partition_date);

-- 建立月度分區（範例）
CREATE TABLE messages_2025_01 PARTITION OF messages
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- 索引
CREATE INDEX idx_messages_created_at ON messages (created_at DESC);
CREATE INDEX idx_messages_severity ON messages (severity);
CREATE INDEX idx_messages_source ON messages (source);
CREATE INDEX idx_messages_user_id ON messages (user_id);
CREATE INDEX idx_messages_category ON messages (category);
```

---

### 決策 2: 登入記錄追蹤

#### 登入記錄表

```sql
CREATE TABLE login_records (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 使用者
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(100) NOT NULL,

    -- 結果
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(200),  -- 失敗原因

    -- 網路資訊
    ip_address INET NOT NULL,
    user_agent TEXT,

    -- 地理位置（GeoIP）
    geo_country VARCHAR(100),
    geo_city VARCHAR(100),
    geo_latitude DECIMAL(10, 7),
    geo_longitude DECIMAL(10, 7),

    -- 裝置指紋
    device_fingerprint VARCHAR(100),
    device_type VARCHAR(50),      -- desktop/mobile/tablet
    browser VARCHAR(100),
    os VARCHAR(100),

    -- Session 資訊
    session_id VARCHAR(100),

    -- 分區鍵
    partition_date DATE NOT NULL DEFAULT CURRENT_DATE
) PARTITION BY RANGE (partition_date);
```

#### 裝置指紋

前端生成裝置指紋，結合以下資訊：
- Screen resolution
- Timezone
- Language
- Canvas fingerprint（簡化版）
- WebGL renderer

使用 hash 產生 fingerprint ID，用於識別同一裝置的多次登入。

---

### 決策 3: 即時推送架構

#### WebSocket 事件

利用現有的 Socket.IO 基礎設施：

```python
# 新訊息事件
socketio.emit('message:new', {
    'id': message.id,
    'severity': message.severity,
    'source': message.source,
    'title': message.title,
    'created_at': message.created_at.isoformat()
}, room=f'user:{user_id}')

# 未讀計數更新
socketio.emit('message:unread_count', {
    'count': unread_count
}, room=f'user:{user_id}')
```

#### 前端訂閱

```javascript
socket.on('message:new', (message) => {
    // 更新訊息中心
    MessageCenterApp.addMessage(message);

    // 顯示 Toast 通知（僅 warning 以上）
    if (['warning', 'error', 'critical'].includes(message.severity)) {
        NotificationModule.show({
            title: message.title,
            message: '點擊查看詳情',
            icon: getSeverityIcon(message.severity)
        });
    }
});
```

---

### 決策 4: 訊息保留與清理

#### 保留策略

- 預設保留期限：**1 年**
- 使用 PostgreSQL 分區表按月分區
- 每日排程清理超過 1 年的分區

#### 清理機制

```python
# 每日清理任務（可用 APScheduler 或 cron）
async def cleanup_old_messages():
    cutoff_date = datetime.now() - timedelta(days=365)
    # 刪除舊分區
    await db.execute(f"""
        DROP TABLE IF EXISTS messages_{cutoff_date.strftime('%Y_%m')}
    """)
```

---

### 決策 5: 前端訊息中心 UI

#### 視窗佈局

```
+------------------------------------------+
| 訊息中心                           _ □ ✕ |
+------------------------------------------+
| [過濾器] [嚴重程度▼] [來源▼] [日期範圍] |
| [搜尋關鍵字...]                  [🔍搜尋] |
+------------------------------------------+
| 今天                                      |
| ┌──────────────────────────────────────┐ |
| │ 🔴 登入失敗    security  10:30        │ |
| │    來自 192.168.1.100 的登入嘗試失敗   │ |
| └──────────────────────────────────────┘ |
| ┌──────────────────────────────────────┐ |
| │ 🟡 檔案上傳    app       09:15        │ |
| │    已上傳 report.pdf 到 /Documents    │ |
| └──────────────────────────────────────┘ |
| 昨天                                      |
| ┌──────────────────────────────────────┐ |
| │ 🟢 登入成功    security  18:00        │ |
| │    使用者 admin 從 台北 登入          │ |
| └──────────────────────────────────────┘ |
+------------------------------------------+
| 第 1-20 筆，共 156 筆        [< 1 2 3 >] |
+------------------------------------------+
```

#### 訊息詳情面板

點擊訊息展開詳情：
- 完整訊息內容
- 結構化 metadata 顯示
- 相關使用者資訊
- 時間線（相關前後事件）

---

### 決策 6: API 設計

#### 寫入 API（內部使用）

```python
# 服務層函式
async def log_message(
    severity: str,
    source: str,
    title: str,
    content: str = None,
    metadata: dict = None,
    user_id: int = None,
    category: str = None,
    session_id: str = None
) -> Message:
    ...
```

#### 查詢 API

```
GET /api/messages
  ?severity=error,warning
  &source=security,system
  &category=auth
  &user_id=1
  &start_date=2025-01-01
  &end_date=2025-01-31
  &search=登入
  &page=1
  &limit=20

GET /api/messages/{id}

GET /api/messages/unread-count

POST /api/messages/mark-read
  body: { ids: [1, 2, 3] } 或 { all: true }
```

#### 登入記錄 API

```
GET /api/login-records
  ?user_id=1
  &success=true
  &start_date=2025-01-01
  &page=1
  &limit=20

GET /api/login-records/recent
  ?limit=10  # 最近 N 筆登入
```

---

## Migration Plan

### 第一階段：基礎設施
1. 建立資料庫表（含分區）
2. 實作 MessageService 核心邏輯
3. 擴充 AuthService 記錄完整登入資訊

### 第二階段：API 與整合
4. 實作訊息 API
5. 整合 WebSocket 即時推送
6. 將現有日誌改為寫入訊息中心

### 第三階段：前端
7. 實作訊息中心視窗
8. 整合 Header Bar 未讀計數顯示
9. 與 NotificationModule 整合

## Open Questions

~~1. **訊息保留期限**~~ → 1 年
~~2. **登入記錄詳細程度**~~ → 完整（含 GeoIP、裝置指紋）
~~3. **即時推送**~~ → 需要，透過 WebSocket
~~4. **訊息分類方式**~~ → 嚴重程度 + 來源雙維度
