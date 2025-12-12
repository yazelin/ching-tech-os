# 安全機制

## 概覽

ChingTech OS 的安全機制包含：
- NAS SMB 認證
- Session 管理
- 登入記錄與追蹤
- 裝置指紋識別
- GeoIP 地理位置

---

## 認證機制

### NAS SMB 認證

系統使用公司 NAS 的 SMB 帳號進行認證，不自行管理密碼。

```
使用者 ──登入請求──▶ 後端 ──SMB認證──▶ NAS (192.168.11.50)
         username                    驗證帳號密碼
         password
```

**優點：**
- 使用既有的 NAS 帳號，無需另外管理
- 密碼存放於 NAS，後端不儲存
- 登入成功後可直接存取 NAS 檔案

**實作位置：**
- `backend/src/ching_tech_os/api/auth.py`
- `backend/src/ching_tech_os/services/smb.py`

---

## Session 管理

### Session 機制

Session 資料儲存於後端記憶體，使用 UUID token 識別。

| 項目 | 說明 |
|------|------|
| Token 格式 | UUID v4 |
| 儲存方式 | 後端記憶體 |
| 有效時間 | 8 小時（可設定） |
| 清理機制 | 定期清理過期 session |

### SessionData 結構

```python
class SessionData:
    username: str       # 使用者帳號
    password: str       # SMB 密碼（供檔案操作用）
    nas_host: str       # NAS 主機位址
    user_id: int        # 資料庫使用者 ID
    created_at: datetime
    expires_at: datetime
```

### 前端 Token 管理

```javascript
// 登入成功後儲存
localStorage.setItem('session_token', token);

// API 請求時帶入
const response = await fetch('/api/xxx', {
  headers: {
    'X-Session-Token': localStorage.getItem('session_token')
  }
});

// 登出時清除
localStorage.removeItem('session_token');
```

### 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `CHING_TECH_SESSION_TTL_HOURS` | 8 | Session 有效時間（小時） |

---

## 登入記錄

### 記錄內容

每次登入嘗試（成功或失敗）都會記錄：

| 欄位 | 說明 |
|------|------|
| `username` | 帳號 |
| `success` | 是否成功 |
| `failure_reason` | 失敗原因 |
| `ip_address` | 來源 IP |
| `user_agent` | 瀏覽器 UA |
| `geo_*` | 地理位置 |
| `device_*` | 裝置資訊 |
| `session_id` | Session Token |
| `created_at` | 時間 |

### 資料庫表

```sql
CREATE TABLE login_records (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(100) NOT NULL,
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(200),
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    geo_country VARCHAR(100),
    geo_city VARCHAR(100),
    geo_latitude DECIMAL(10, 7),
    geo_longitude DECIMAL(10, 7),
    device_fingerprint VARCHAR(100),
    device_type VARCHAR(20),
    browser VARCHAR(100),
    os VARCHAR(100),
    session_id VARCHAR(100)
);
```

### API 端點

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/login-records` | 查詢登入記錄（支援過濾） |
| GET | `/api/login-records/recent` | 最近登入記錄 |

---

## 裝置指紋

### 前端收集

位置：`frontend/js/device-fingerprint.js`

收集以下資訊產生指紋：

| 項目 | 說明 |
|------|------|
| `fingerprint` | 裝置唯一識別碼 |
| `device_type` | desktop / mobile / tablet |
| `browser` | 瀏覽器名稱和版本 |
| `os` | 作業系統 |
| `screen_resolution` | 螢幕解析度 |
| `timezone` | 時區 |
| `language` | 語言 |

### 用途

- 異常登入偵測（新裝置登入提醒）
- 登入記錄關聯分析
- Session 安全驗證

---

## GeoIP 地理位置

### 技術

使用 MaxMind GeoLite2 資料庫解析 IP 地理位置。

| 項目 | 說明 |
|------|------|
| 資料庫 | GeoLite2-City.mmdb |
| 位置 | `backend/data/GeoLite2-City.mmdb` |
| 更新 | 需定期更新（MaxMind 提供） |

### 解析結果

```python
class GeoLocation:
    country: str | None   # 國家
    city: str | None      # 城市
    latitude: Decimal     # 緯度
    longitude: Decimal    # 經度
```

### 內網 IP 處理

內網 IP（192.168.x.x、10.x.x.x 等）無法解析地理位置，會標記為「內網」。

```python
def is_private_ip(ip_str: str) -> bool:
    """檢查是否為內網 IP"""
    ip = ipaddress.ip_address(ip_str)
    return ip.is_private or ip.is_loopback or ip.is_link_local
```

---

## User-Agent 解析

### 技術

使用 `user-agents` Python 套件解析瀏覽器和作業系統資訊。

```python
from user_agents import parse as parse_user_agent

ua = parse_user_agent(user_agent_string)
browser = f"{ua.browser.family} {ua.browser.version_string}"
os = f"{ua.os.family} {ua.os.version_string}"
device_type = "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop"
```

---

## 安全注意事項

### Session 密碼處理

Session 中暫存 SMB 密碼用於檔案操作，這是必要的設計：

- 密碼僅存於記憶體，不寫入資料庫
- Server 重啟後 session 失效
- Session 過期後密碼隨之清除

### API 認證

所有需要認證的 API 端點都會檢查 `X-Session-Token` header：

```python
async def get_current_session(
    x_session_token: str = Header(None, alias="X-Session-Token")
) -> SessionData:
    if not x_session_token:
        raise HTTPException(status_code=401, detail="未提供 session token")

    session = session_manager.get_session(x_session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Session 無效或已過期")

    return session
```

### CORS 設定

開發環境允許所有來源，生產環境應限制：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # 生產環境
    # allow_origins=["*"],  # 開發環境
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 相關檔案

| 位置 | 說明 |
|------|------|
| `backend/src/ching_tech_os/api/auth.py` | 認證 API |
| `backend/src/ching_tech_os/services/session.py` | Session 管理 |
| `backend/src/ching_tech_os/services/smb.py` | SMB 認證 |
| `backend/src/ching_tech_os/services/geoip.py` | GeoIP 解析 |
| `backend/src/ching_tech_os/services/login_record.py` | 登入記錄 |
| `backend/src/ching_tech_os/models/login_record.py` | 登入記錄模型 |
| `frontend/js/device-fingerprint.js` | 裝置指紋 |
| `frontend/js/login.js` | 登入模組 |
