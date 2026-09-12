# 安全機制

## 概覽

ChingTech OS 的安全機制包含：
- 雙重認證（CTOS 本地密碼 + NAS SMB）
- 管理員使用者管理（CRUD）
- Session 管理
- 登入記錄與追蹤
- 裝置指紋識別
- GeoIP 地理位置

---

## 認證機制

系統支援兩種認證方式，CTOS 本地密碼認證優先於 NAS SMB 認證。

```
使用者 ──登入請求──▶ 後端 ──(1) 檢查 password_hash──▶ 有密碼 → bcrypt 驗證
         username          ──(2) password_hash 為 NULL──▶ NAS SMB 認證
         password
```

### CTOS 本地密碼認證

使用者在 `users.password_hash` 欄位有值時，系統以 bcrypt 驗證密碼，不經過 NAS。

**特點：**
- 密碼以 bcrypt hash 儲存於資料庫，安全性高
- 密碼最低 8 個字元
- 支援 `must_change_password` 強制首次登入改密碼
- 管理員可重設密碼或清除密碼（恢復 NAS 認證）

**預設管理員帳號：**
- Migration 007 自動建立帳號 `ct`，密碼 `36274806`（bcrypt hash）
- `role` 為 `admin`、`must_change_password` 為 `True`
- 首次登入後強制變更密碼

### NAS SMB 認證

使用者無本地密碼（`password_hash` 為 NULL）時，系統透過 NAS SMB 驗證。可透過環境變數 `ENABLE_NAS_AUTH` 控制是否啟用（預設啟用）。

**優點：**
- 使用既有的 NAS 帳號，無需另外管理
- 密碼存放於 NAS，後端不儲存
- 登入成功後可直接存取 NAS 檔案

### 停用帳號

`is_active` 為 `False` 的使用者無法登入，系統回傳「此帳號已被停用」。

**實作位置：**
- `backend/src/ching_tech_os/api/auth.py` — 認證 API
- `backend/src/ching_tech_os/services/smb.py` — SMB 連線
- `backend/src/ching_tech_os/services/password.py` — 密碼雜湊與驗證

---

## 管理員使用者管理

管理員（`role = 'admin'`）可透過 API 管理所有使用者帳號。

### API 端點

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/admin/users` | 使用者列表（含 `has_password` 認證方式） |
| POST | `/api/admin/users` | 建立使用者（密碼 bcrypt hash，`must_change_password: true`） |
| PATCH | `/api/admin/users/{user_id}` | 編輯使用者（display_name、email、role） |
| PATCH | `/api/admin/users/{user_id}/permissions` | 更新使用者功能權限 |
| POST | `/api/admin/users/{user_id}/reset-password` | 重設密碼 |
| POST | `/api/admin/users/{user_id}/clear-password` | 清除密碼（恢復 NAS 認證） |
| PATCH | `/api/admin/users/{user_id}/status` | 停用/啟用帳號 |
| DELETE | `/api/admin/users/{user_id}` | 永久刪除使用者 |

### 管理員自我保護

管理員不能對自己執行以下操作：
- 降級自己的角色（admin → user）
- 停用自己的帳號
- 清除自己的密碼
- 刪除自己的帳號

非管理員呼叫管理端點會收到 403 錯誤。

**實作位置：**
- `backend/src/ching_tech_os/api/user.py` — 管理員 API
- `backend/src/ching_tech_os/services/user.py` — 使用者服務
- `backend/src/ching_tech_os/models/user.py` — 資料模型

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
    username: str        # 使用者帳號
    password: str | None # SMB 密碼（供檔案操作用，本地密碼認證時為 None）
    nas_host: str        # NAS 主機位址
    user_id: int         # 資料庫使用者 ID
    role: str            # 使用者角色（admin / user）
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
| `SESSION_TTL_HOURS` | 8 | Session 有效時間（小時） |
| `ENABLE_NAS_AUTH` | True | 是否啟用 NAS SMB 認證 |

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

## Bot 憑證加密

### 加密演算法

Bot 憑證（Line Channel Secret / Access Token、Telegram Bot Token 等）使用 AES-256-GCM 加密儲存於 `bot_settings` 表。

| 項目 | 說明 |
|------|------|
| 演算法 | AES-256-GCM（NIST 認證的 AEAD 加密） |
| 金鑰來源 | `BOT_SECRET_KEY` 環境變數，經 SHA-256 衍生 32 bytes |
| Nonce | 每次加密產生 12 bytes 隨機 nonce |
| 儲存格式 | `Base64(nonce + ciphertext + tag)` |

**實作位置**：`backend/src/ching_tech_os/utils/crypto.py`

### 環境變數

| 變數 | 說明 |
|------|------|
| `BOT_SECRET_KEY` | 加密金鑰（必要，未設定時使用預設開發金鑰並發出警告） |

> 生產環境必須設定 `BOT_SECRET_KEY`，否則加密金鑰為公開的預設值。

### 使用者角色

| 角色 | 說明 |
|------|------|
| `admin` | 管理員，可存取 Bot 設定、使用者管理等管理功能 |
| `user` | 一般使用者 |

---

## Socket.IO 連線驗證

Socket.IO 與 REST 走同一套身分：連線（`connect`）時就驗 token，驗不過直接拒絕，
之後所有事件一律以連線時存下的身分為準，不看 client payload 送來的 `user_id` / `userId`。

### 連線流程

1. Client 連線時以 `auth.token` 帶 token。舊桌面前端在 `frontend/js/socket-client.js` 寫
   `auth: (cb) => cb({ token: LoginModule.getToken() })`（function 形式，重連時會重新取最新 token）。
   **不接受 query string 帶 token**，那會留在 nginx access log 與瀏覽器歷史紀錄裡。
2. 後端 `main.py` 的 `connect(sid, environ, auth)` 取 `auth["token"]`，交給 `api/auth.py` 的
   `_resolve_session()` 解析，與 REST 同一條路徑，支援 session token 與 PAT。
3. 取不到 token、解析回 `None`、解析過程出錯（記 warning）→
   `raise socketio.exceptions.ConnectionRefusedError("unauthorized")`。
4. 成功 → `sio.save_session(sid, {...})` 存下 `user_id`、`username`、`role`、`app_permissions`、
   `read_only`、`token`。
5. 前端收到 `connect_error` 且 `error.message === 'unauthorized'` 時，走 `LoginModule.logout()`
   清 token 並導回登入頁。

### 事件如何用連線身分

| 事件 | 行為 |
|------|------|
| `ai_chat_event`、`compress_chat` | 進入時用存下的 token 重新解析一次身分；以該身分的 `user_id` 呼叫 `ai_chat.get_chat(chat_id, user_id)`，不是自己的對話就回 `ai_error` / `compress_error`（「對話不存在或無權限」），不呼叫 AI provider |
| `terminal:create` | 進入時重新解析身分；忽略 payload 的 `user_id`，並要求 `terminal` app 權限 |
| `terminal:list`、`terminal:reconnect` | 只看得到、只能重連自己的 session；連線身分沒有 `user_id` 一律拒絕 |
| `join_user_room`、`leave_user_room`、`get_unread_count_event` | 房間固定是 `user:<連線身分的 user_id>`，忽略 payload 的 `userId`；取不到身分就不回未讀數 |

### 為什麼高風險事件要重新解析 token

Socket.IO 連線可以掛很久。跑 AI（燒 token）與開終端機（能執行指令）這兩類事件，
在進入時用連線時存下的 token 再跑一次 `_resolve_session()`：連線之後才登出、
session 過期或 PAT 被撤銷的連線，會收到錯誤事件並被 `disconnect()`。
其餘事件（加入房間、查未讀數）沿用連線時存下的身分，不再查一次。

唯讀 PAT（`read_only`）不能跑 AI 對話、壓縮對話與開終端機，與 REST 的
`require_app_permission` 對非 GET 方法的處理一致。

raw token 為了這道重新驗證，存在 python-socketio 的記憶體 session 裡（`sio.save_session`），
不寫入資料庫，連線斷掉就跟著消失。

取不到連線身分時（例如連線已消失），事件回錯誤或直接略過，不會往下執行。

> 部署後舊桌面前端要重新整理頁面，才會載到會帶 token 的新版 `socket-client.js`。

---

## App 功能權限（後端強制）

App 權限定義在 `services/permissions.py` 的 `DEFAULT_APP_PERMISSIONS`，
以 `require_app_permission(app_id)` 這個 FastAPI dependency 套在端點上；admin 一律放行。

| App 權限 | 預設 | 套用範圍 |
|----------|------|----------|
| `ai-log` | 關閉 | `GET /api/ai/logs`、`/api/ai/logs/stats`、`/api/ai/logs/{id}` |
| `prompt-editor` | 關閉 | `POST` / `PUT` / `DELETE /api/ai/prompts*` |
| `agent-settings` | 關閉 | `POST` / `PUT` / `DELETE /api/ai/agents*`、`POST /api/ai/test` |
| `terminal` | 關閉 | Socket.IO `terminal:create` |
| `share-manager` | 關閉（issue #217） | `POST /api/share`（建立分享連結） |
| `nvr-viewer` | 開啟 | `GET /api/nvr/recording-status`、`GET /api/nvr/snapshot/{channel}`（`extends/nvr`，issue #261） |

`prompt-editor` 與 `agent-settings` 預設關閉、由管理員逐人開放：`ai_prompts` 與 `ai_agents`
是全域表，一個人改 system prompt 或工具白名單就影響所有人。**GET 不受影響**，
AI 管理的讀取端點（prompts、agents、agents/by-name、agents/{id}）維持登入即可，
AI 助手選 agent、AI Log 篩選、排程 UI 都要讀。

`share-manager` 原本預設開放，issue #217 改成預設關閉：#205 只保證「分享連結不能繞過
資源存取檢查」，但 `check_knowledge_permission_async(action="read")` 對 `scope=global`
一律放行、`scope=project` 不看成員，加上這道 app 權限預設開放，等於任何已登入者都能把
公司整理過的 global 知識或專案文件變成不需要帳號就打得開的公開連結——「內部讀得到」
不該直接等於「可以發到網路上」。改成預設關閉後，管理員逐人開放才能建立分享連結；
`GET /api/share`（列出）與 `DELETE /api/share/{token}`（撤銷）維持只要登入即可，
不掛這道權限——權限被收回之後，使用者仍要能撤掉自己先前建立的連結，不能被鎖在外面。

session 的權限快取沒帶到某個 `app_id` 時，`require_app_permission` 會回退到
`get_effective_app_permissions()` 的預設值，與 `has_app_permission()` 一致。

`extends/nvr` 的兩支端點原本連登入都不用（issue #261），已補上 `nvr-viewer` 權限閘。
`/api/nvr/snapshot/{channel}` 是給 `<img src>` 用的、帶不了 header，所以用
`require_app_permission("nvr-viewer", allow_query_token=True)`——token 可以走 `?token=`，
但權限判斷與 header 版完全同一條路，不是後門。

`prompt-editor` 與 `agent-settings` 原本只在舊桌面前端擋 `openApp` 點擊，後端沒有對應檢查；
新前端沒有那道客戶端防護，缺口因此浮上檯面，修法是把防護移到後端。這是既有的客戶端防護缺口，不是新功能。

---

## 公開端點清單（以測試為準）

每條 `/api` 路由都必須掛上身分依賴（`get_current_session`、`require_admin`、
`require_app_permission(...)` 這一類）。少數端點設計上就是公開，或有自己的驗證方式
（平台簽章、來源 IP、不可猜測的分享 token），這些例外**列在測試裡**，不在這份文件裡再抄一份：

`backend/tests/test_route_guards.py`

- `ALLOWED_PUBLIC`：允許公開的端點，每一條都附一句理由。
- `KNOWN_UNGUARDED`：已知沒閘、已開 issue 待修的端點（目前只剩 #256），用 `xfail(strict=True)` 盯著；
  修好之後測試會 XPASS 而變紅，提醒把條目刪掉。
- `REGRESSION_PINS`：修過的端點釘住它必須掛哪道閘（目前 #261 的 nvr 兩支），不准退回沒閘的狀態。
- `IDENTITY_DEPENDENCIES`：什麼算「有掛身分」的認定清單。

測試的作法是 FastAPI route 內省：在 `ENABLED_MODULES='*'` 下把 `app.routes`（含 `extends/` 模組）
每條路由的 `route.dependant` 依賴樹整棵走過，看有沒有出現身分依賴。
新端點忘了掛登入或權限，這個測試會直接紅並印出那條路由。

要新增公開端點，就在 `ALLOWED_PUBLIC` 加一條並寫清楚為什麼可以公開；
測試同時會檢查清單裡的每一條都真的存在於 `app.routes`，避免路由改名後留下死條目。

---

## Bot 對外開放、未綁定者的工具範圍

LINE／Telegram Bot 是對外開放的入口：任何人加好友或把 bot 拉進群組就能對話，
`ctos_user_id is None`（沒有綁定 CTOS 帳號）是常態，不是例外。這套權限設計原本
假設呼叫者是已綁定的自己人，未綁定者因此一路走得進來——issue #201、#204、#205、
#207、#209、#210 都是同一個根因的不同出口，都已修。

**逐支工具的實際範圍看 [MCP 工具存取矩陣](mcp-tool-access-matrix.md)**
（由 `backend/scripts/gen_tool_access_matrix.py` 從程式內省產生，測試會比對逐字相同）。

四道關卡各擋不同的東西：

| 關卡 | 實作 | 擋什麼 |
|------|------|--------|
| app 權限 | `check_mcp_tool_permission()`＋`APPS_REQUIRE_BOUND_USER` | 這個人有沒有這個功能；專案／往來／物料／NAS 檔案／分享未綁定一律拒絕（#201、#205） |
| 條目層級 | 知識庫 `_check_item_access()`、記憶的擁有者條件 | 這一筆是不是你的；未綁定只讀得到 `scope=global` 且 `is_public` |
| 工具內部自檢 | `require_bound_user()`＋`TOOLS_REQUIRE_BOUND_USER` | 憑空建立新資料的寫入（`add_note`、`add_note_with_attachments`，#207；文件生成三支與 `run_skill_script`，#210） |
| 資源存取檢查 | `share.check_resource_access()` | 把讀不到的東西送出去（#205，見下節） |
| 連線身分解析 | `resolve_bot_identity()`／`resolve_conversation_scope()` | 模型宣稱別的群組／別人（#204、#209，見下節） |

### 身分注入補齊（#209）

`resolve_bot_identity()`（#204）原本只套在記憶工具，其餘收
`line_group_id`／`line_user_id` 的工具仍然是模型說了算。這些 id 不是裝飾：

- `add_note`／`add_note_with_attachments`：id 決定知識庫的 scope 與專案歸屬。
- `send_nas_file`：id 就是發送目標。
- `summarize_chat`／`get_message_attachments`：id 就是讀取範圍。

現在這些工具都先過 `resolve_bot_identity()`，有注入就以注入值為準。讀群組對話與
附件的兩支再多一層 `resolve_conversation_scope()`：沒有注入時要求有
`ctos_user_id`，而且指定的群組／個人身分必須與這個 CTOS 帳號有既有關聯
（`bot_users.user_id` 綁定 ＋ `bot_messages` 在該群組留過訊息），否則拒絕。

**這兩層的強度差很多，不要混為一談：**

- **bot 路徑（LINE／Telegram）**：`CTOS_BOT_*` 由伺服器注入，模型帶什麼都會被
  覆蓋，這條路是真的擋住了。
- **網頁聊天**：`api/ai.py` 連 `CTOS_USER_ID` 都沒注入，所以
  `resolve_ctos_user_id()` 拿到的就是**模型參數本身**。那道群組關聯檢查是拿
  「模型宣稱的身分」去比對，擋得住「完全沒帶身分」，擋不住「宣稱別人的身分」。
  只是提高門檻，**不是修好了**；真正的解是讓 `api/ai.py` 把 session 的
  `user_id` 注入 MCP 子行程（issue #231）。

殘留：`send_nas_file` 的 `telegram_chat_id` 本身不在 `build_bot_mcp_env()` 的注入
範圍（issue #232）。跨平台那一半已經擋掉——`build_bot_mcp_env()` 現在會注入
`CTOS_BOT_PLATFORM`（`line`／`telegram`），連線不是 Telegram 對話時模型帶的
chat id 一律忽略並記 warning，LINE 使用者沒辦法把 NAS 檔案推到任意 Telegram
聊天室；剩下的是 Telegram 對話裡模型仍可指定同平台的別的 chat id。

### 每一支工具都要有決定（#210）

以前「沒呼叫 `check_mcp_tool_permission()`」和「刻意開放」長得一模一樣：工具沒登錄
`TOOL_APP_MAPPING` 就等於不檢查，預設是開的。現在每一支不做 app 權限檢查的工具
都必須登記在 `permissions.TOOLS_INTENTIONALLY_OPEN`（工具名 → 一句理由），
矩陣會原樣列出理由，沒登記又沒檢查的工具矩陣測試會紅。

這一輪的決定：

- 送到外部或實體世界：`prepare_print_file` 的權限檢查本來寫成 `if ctos_user_id:`，
  未綁定反而整個跳過；改成一律檢查，`printer` 進 `APPS_REQUIRE_BOUND_USER`
  （預設權限維持 True，內部員工既有用法不變）。
- 會持久化、之後自動執行：排程兩支對到 `task-scheduler`（模組提供、預設 False），
  同樣進 `APPS_REQUIRE_BOUND_USER`。
- `run_skill_script`：對到 `ai-assistant`，另加未綁定自檢——等同讓對話端跑
  伺服器上的程式。
- 文件生成三支：對到既有的 `md2ppt`／`md2doc`，另加未綁定自檢——都會在 NAS 的
  `ai-generated` 目錄產檔，`generate_md2ppt`／`generate_md2doc` 還會建立
  不需帳號就打得開的分享連結。
- `codex_image_tool`：`reference_images` 會讀 NAS 根目錄底下的檔案並送到外部服務，
  對到 `file-manager`（已在 `APPS_REQUIRE_BOUND_USER`）。
- 登記為有意開放的九支（記憶四支、讀對話兩支、`download_web_image`、
  `text_to_speech`、`browse_webpage`）逐支的理由見矩陣。其中 `browse_webpage`
  的「只讀公開網頁」不能只靠 scheme 是 https：
  `web_tools.check_public_http_target()` 會把主機名稱解析出來，
  loopback／私有（10/8、172.16/12、192.168/16）／link-local（169.254/16）／
  CGNAT（100.64/10）／IPv6 unique-local 與 loopback、無點主機名稱、
  `.local`／`.internal`／`.lan` 這類內網後綴一律拒絕，DNS 解析結果**任何一個**
  不是公開位址就拒絕。沒有這一層，未綁定者可以叫 bot 去讀內網頁面
  （SSRF），「只讀公開網頁」這個開放理由就不成立。

  **檢查套在三個地方**，因為只看最初的 URL 擋不住重新導向——公開網域 302 到
  `https://192.168.11.11/`，Chromium 照樣會去載入它：

  | 時機 | 實作 | 擋什麼 |
  |------|------|--------|
  | 呼叫進來 | `browse_webpage` 開頭 | 模型直接指定內網位址 |
  | 每一個 request | `page.route("**/*", block_non_public_requests)` | 重新導向與 subresource（img／xhr／iframe）打內網；非公開一律 `abort()`，檢查本身出錯也 abort |
  | 讀內容之前 | `check_public_http_target(page.url)` | 導航最後停在內網位址（meta refresh、history API），在取 title／snapshot 之前就拒絕 |

  **沒有封死的**：`check_public_http_target()` 的 `getaddrinfo()` 與瀏覽器自己的
  DNS 是兩次獨立解析，中間換答案（DNS rebinding）仍有空隙。要完全封死得讓
  瀏覽器只走一個會做同樣檢查的 proxy，不在這次範圍。

### 公開分享連結（#205）

分享連結不需要帳號就打得開，所以「能不能建立連結」必須等於「建立的人讀不讀得到」。

`services/share.py` 的 `get_resource_title()` 只驗資源存在，原本 knowledge 不看
scope／owner／is_public、nas_file 也沒帶 `source_permissions`，任何呼叫者都能把
別人的知識條目或自己讀不到的 NAS 檔案變成公開連結。修法是兩層：

1. `create_share_link`／`share_knowledge_attachment` 在 `TOOL_APP_MAPPING` 對到
   `share-manager`，`share-manager` 進 `APPS_REQUIRE_BOUND_USER`：未綁定一律拒絕，
   已綁定者還要有 `share-manager` app 權限（issue #217 之後**預設關閉**，見下節）。
2. `share.check_resource_access()`（REST 的 `POST /api/share` 與 MCP 工具共用這一層）
   在建立連結前做真正的存取檢查，而且刻意走與「讀」完全相同的路：

   | 資源類型 | 走哪條路 | 與哪支工具相同 |
   |----------|----------|----------------|
   | `knowledge` | `check_knowledge_permission_async(..., action="read")`；未綁定只放行 `scope=global` 且 `is_public` | `get_knowledge_item` 的 `_check_item_access()` |
   | `nas_file` | `validate_nas_file_path(..., source_permissions=...)`；未綁定一律拒絕 | `read_document`／`send_nas_file` |
   | `content` | 內容由呼叫端自己提供，沒有別人的資源可洩漏，不檢查 | — |

   沒權限回 403（`ShareAccessDenied`），連結不會被建立。

### `share-manager` 預設關閉（#217）

`check_knowledge_permission_async(action="read")` 對 `scope=global` 一律放行、
`scope=project` 不看成員——這是既有的讀取行為，不是這次改的。問題出在分享連結拿
「讀得到」直接當「可以公開」：`share-manager` 原本預設開放，等於任何已登入使用者
都能把公司整理過的 global 知識條目或專案文件變成不需要帳號就打得開的公開連結。
「內部讀得到」不該等於「可以發到網路上」。

最小修法：

- `services/permissions.py` 的 `DEFAULT_APP_PERMISSIONS["share-manager"]` 改 `False`，
  管理員逐人開放（同 `ai-log`／`prompt-editor`／`agent-settings` 的模式）。
- REST `POST /api/share`（建立）原本只掛 `get_current_session`，等於完全沒檢查
  這道 app 權限（MCP 工具走的 `check_mcp_tool_permission()` 一直都有檢查）；
  改掛 `require_app_permission("share-manager")`，與 MCP 工具同一個判斷式
  （`has_app_permission()`），行為一致。
- `GET /api/share`（列出）與 `DELETE /api/share/{token}`（撤銷）維持
  `get_current_session`，不掛這道權限：管理員收回權限之後，使用者仍要能撤掉
  自己先前建立的連結，不能被鎖在外面看不到、關不掉。

`share-manager` 改預設關閉之後 session 帶的權限快照要更新才生效：**已登入的
session 帶的是登入當下算出的快照，權限被管理員收回或新開放，都要重新登入
才會套用**（session TTL 由 `SESSION_TTL_HOURS` 控制，預設 8 小時，到期或登出後
重新登入就會拿到最新值；同一份權限快照設計也適用其他 app 權限，不是
`share-manager` 獨有）。PAT（長效 API token）不受影響，因為它每次請求都走
`require_app_permission()` 的 `has_app_permission()` 判斷式現查現算，不吃
session 快照。

#### 間接建立連結的工具也要擋（review 追加）

`create_share_link`／`share_knowledge_attachment` 這兩支工具本身會呼叫
`check_mcp_tool_permission("create_share_link", ...)`，對到 `share-manager`。
但 `services/mcp/nas_tools.py` 的 `send_nas_file`（直接把 NAS 檔案發給
Line／Telegram 使用者）與 `prepare_file_message`（準備 Line Bot 回覆用的檔案
訊息）在 `TOOL_APP_MAPPING` 只對到 `file-manager`，內部卻直接呼叫
`share_service.create_share_link()` 產生公開連結——只有 `file-manager` 沒有
`share-manager` 的使用者，原本仍能透過這兩支工具把 NAS 檔案或知識庫附件變成
公開連結，等於繞過 `create_share_link` 工具本身的權限檢查。

修法：在這兩支工具真的建立連結那一步之前，額外呼叫一次
`check_mcp_tool_permission("create_share_link", ctos_user_id)`
（`_require_share_manager_for_link()`），沒有 `share-manager` 就回
「需要「分享管理」功能權限才能產生分享連結」，不影響這兩支工具其餘不建立連結
的路徑（檔案不存在、路徑解析失敗等既有驗證錯誤都發生在這道檢查之前，訊息不變）。

[MCP 工具存取矩陣](mcp-tool-access-matrix.md) 是從 `TOOL_APP_MAPPING` 逐工具
內省產生的，`send_nas_file`／`prepare_file_message` 的「App 權限」欄位只會顯示
`file-manager`——矩陣目前沒有「這支工具還會間接檢查別的 app 權限」這一種欄位，
所以看不出這道額外檢查，這裡先用文字記錄，避免看矩陣以為這兩支工具只受
`file-manager` 保護。

bot 走的路徑上，身分一律由伺服器注入，模型在工具參數裡宣稱的一律不算數：

| 環境變數 | 內容 | 注入處 | 讀取處 |
|----------|------|--------|--------|
| `CTOS_USER_ID` | 綁定的 CTOS 使用者 ID | `claude_agent.py`／`codex_agent.py` | `resolve_ctos_user_id()` |
| `CTOS_BOT_GROUP_ID`（＋沿用的 `CTOS_GROUP_ID`） | `bot_groups.id` | `build_bot_mcp_env()`，由 `linebot_ai.py`／`bot_telegram/handler.py`／`bot/identity_router.py` 呼叫 | `resolve_bot_identity()` |
| `CTOS_BOT_USER_ID` | `bot_users.platform_user_id` | 同上 | `resolve_bot_identity()` |
| `CTOS_BOT_PLATFORM` | `line`／`telegram` | 同上 | `resolve_bot_platform()`（`send_nas_file` 用它擋跨平台推送） |

環境變數不存在時工具才會採用參數——**網頁聊天就是這種情況**：
`api/ai.py` 的 Socket.IO `ai_message` 呼叫 `call_ai()` 時沒有帶 `ctos_user_id`，
也沒有帶 `extra_mcp_env`（雖然 session 裡就有 `user_id`），所以那條路會起一個
沒有任何身分環境變數的 MCP 子行程：工具的 `ctos_user_id` 由模型參數決定、
記憶工具吃模型帶的 `line_group_id`／`line_user_id`、`update_memory`／`delete_memory`
沒有擁有者範圍。進 socket 之前有 session 認證，所以不是匿名者能打的路，
但同一個登入者可以指定別人的 id。這條缺口記在
[存取矩陣的「已知缺口」](mcp-tool-access-matrix.md#已知缺口)，尚未修。
`summarize_chat`／`get_message_attachments` 在這條路上多擋了一層（#209 的
`resolve_conversation_scope()` 會要求 `ctos_user_id` 並驗群組關聯），但那個
`ctos_user_id` 在這條路上同樣是模型帶的，所以只是提高門檻，**不是修好了**。
其餘工具仍然照舊。

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

`GET /api/config/apps`（回傳已啟用模組與 skill 貢獻 app 的 manifest，含 loader 路徑）與
`GET /api/skills/{name}/frontend/{file_path}`（skill 前端 JS/CSS）都需要登入。這兩支端點
會被 `<script src>`／`<link href>` 這類無法帶 header 的請求呼叫，因此用
`get_session_from_token_or_query`（header 優先，否則吃 `?token=`），沒 token 或 token 無效一律 401。

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
| `backend/src/ching_tech_os/api/user.py` | 使用者管理 API（含管理員端點） |
| `backend/src/ching_tech_os/services/session.py` | Session 管理 |
| `backend/src/ching_tech_os/services/smb.py` | SMB 認證 |
| `backend/src/ching_tech_os/services/user.py` | 使用者服務（CRUD、密碼管理） |
| `backend/src/ching_tech_os/services/password.py` | 密碼雜湊與驗證 |
| `backend/src/ching_tech_os/services/geoip.py` | GeoIP 解析 |
| `backend/src/ching_tech_os/services/login_record.py` | 登入記錄 |
| `backend/src/ching_tech_os/models/user.py` | 使用者資料模型 |
| `backend/src/ching_tech_os/models/login_record.py` | 登入記錄模型 |
| `backend/migrations/versions/007_seed_admin_user.py` | 預設管理員帳號 migration |
| `frontend/js/device-fingerprint.js` | 裝置指紋 |
| `backend/src/ching_tech_os/services/permissions.py` | App 功能權限與 `require_app_permission` |
| `backend/tests/test_route_guards.py` | 路由守衛回歸測試與公開端點允許清單（唯一事實來源） |
| `backend/src/ching_tech_os/services/socket_auth.py` | Socket.IO 連線身分工具（token 擷取、讀連線 session） |
| `frontend/js/login.js` | 登入模組 |
| `frontend/js/socket-client.js` | Socket.IO 客戶端（連線帶 token） |
