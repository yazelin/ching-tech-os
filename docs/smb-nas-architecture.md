# SMB/NAS 檔案系統架構

本文件說明 Ching-Tech OS 如何連接 NAS 並提供檔案管理功能。

## 概述

系統透過 SMB (Server Message Block) 協定連接 Synology NAS，提供檔案瀏覽、預覽、上傳、下載等功能。

## 系統架構

```
┌─────────────────┐     HTTP/REST      ┌──────────────────┐     SMB      ┌─────────────┐
│   前端瀏覽器     │ ◄─────────────────► │   FastAPI 後端   │ ◄──────────► │  NAS 伺服器  │
│  (JavaScript)   │                     │    (Python)      │              │  (Synology)  │
└─────────────────┘                     └──────────────────┘              └─────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │  PostgreSQL  │
                                        │   (使用者)    │
                                        └──────────────┘
```

## SMB 連線方式

### 使用的工具

| 操作類型 | 工具 | 原因 |
|----------|------|------|
| 列出共享 | `smbclient` (CLI) | `smbprotocol` 不支援 NetShareEnum RPC |
| 其他操作 | `smbprotocol` (Python) | 純 Python 實作，效能好 |

### 為什麼需要混合使用？

SMB 協定中「列出共享清單」需要透過 SRVSVC (Server Service) RPC 介面呼叫 NetShareEnum。
`smbprotocol` 是純 Python 的 SMB 實作，專注於檔案操作，沒有實作 SRVSVC RPC。

**解決方案**：使用系統的 `smbclient -L -g` 命令列出共享，其他操作繼續使用 `smbprotocol`。

## SMBService 類別

位置：`backend/src/ching_tech_os/services/smb.py`

### 公開方法

| 方法 | 功能 | 使用工具 |
|------|------|----------|
| `list_shares()` | 列出 NAS 所有共享資料夾 | `smbclient -L -g` |
| `browse_directory(share, path)` | 瀏覽資料夾內容 | `smbprotocol` |
| `read_file(share, path)` | 讀取檔案內容 | `smbprotocol` |
| `write_file(share, path, data)` | 寫入/上傳檔案 | `smbprotocol` |
| `delete_item(share, path, recursive)` | 刪除檔案或資料夾 | `smbprotocol` |
| `rename_item(share, old_path, new_name)` | 重命名 | `smbprotocol` |
| `create_directory(share, path)` | 建立資料夾 | `smbprotocol` |

### 使用範例

```python
from ching_tech_os.services.smb import create_smb_service

# 建立服務實例
smb = create_smb_service(username="user", password="pass")

# 使用 context manager 確保連線正確關閉
with smb:
    # 列出共享（不需要先連線，內部使用 smbclient）
    shares = smb.list_shares()
    # [{"name": "home", "type": "disk"}, {"name": "共用區", "type": "disk"}]

    # 瀏覽資料夾
    items = smb.browse_directory("home", "文件")
    # [{"name": "report.txt", "type": "file", "size": 1024, "modified": "2025-12-10T10:00:00"}]

    # 讀取檔案
    content = smb.read_file("home", "文件/report.txt")
    # bytes
```

### 錯誤處理

| 例外類別 | 情境 |
|----------|------|
| `SMBAuthError` | 帳號密碼錯誤 |
| `SMBConnectionError` | 無法連線到 NAS |
| `SMBError` | 其他 SMB 操作錯誤（無權限、檔案不存在等） |

## API 端點

位置：`backend/src/ching_tech_os/api/nas.py`

### 共享與瀏覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/nas/shares` | 列出使用者可存取的共享 |
| GET | `/api/nas/browse?path=/share/folder` | 瀏覽資料夾內容 |

### 檔案操作

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/nas/file?path=/share/file.txt` | 讀取檔案內容（預覽用） |
| GET | `/api/nas/download?path=/share/file.txt` | 下載檔案（attachment） |
| POST | `/api/nas/upload` | 上傳檔案（multipart/form-data） |
| DELETE | `/api/nas/file?path=/share/file.txt` | 刪除檔案或資料夾 |
| PATCH | `/api/nas/rename` | 重命名 |
| POST | `/api/nas/mkdir` | 建立資料夾 |

### 路徑格式

所有路徑以 `/共享名稱/子資料夾/檔案` 格式傳遞：

```
/home/文件/report.txt
│     │     └── 檔案名稱
│     └── 子資料夾路徑
└── 共享名稱（share）
```

內部會解析成：
- `share_name`: `home`
- `relative_path`: `文件/report.txt`

## 認證流程

```
1. 使用者登入
   POST /api/auth/login { username, password }
         │
         ▼
2. 後端驗證 NAS 帳密
   SMBService.test_auth() → 嘗試 SMB 連線
         │
         ▼
3. 建立 Session
   SessionManager.create_session(username, password)
   └── 儲存帳密在記憶體（用於後續 NAS 操作）
         │
         ▼
4. 回傳 Token
   { token: "uuid", username: "user" }
         │
         ▼
5. 後續請求帶 Token
   Authorization: Bearer <token>
         │
         ▼
6. 取得 Session 中的帳密
   get_current_session(token) → { username, password }
         │
         ▼
7. 建立 SMB 連線執行操作
   with create_smb_service(username, password) as smb:
       smb.browse_directory(...)
```

## 系統需求

### Python 套件

```toml
# pyproject.toml
dependencies = [
    "smbprotocol>=1.14.0",  # SMB 協定操作
    "python-multipart",      # 檔案上傳
]
```

### 系統套件

```bash
# Ubuntu/Debian
apt install smbclient

# 驗證安裝
smbclient --version
```

## 設定

位置：`backend/src/ching_tech_os/config.py`

```python
class Settings:
    nas_host: str = "192.168.11.50"  # NAS IP 位址
    nas_port: int = 445              # SMB 埠號
    session_ttl_hours: int = 8       # Session 存活時間
```

## 安全考量

1. **帳密儲存**：Session 中的 NAS 密碼儲存在伺服器記憶體，不寫入資料庫
2. **Session TTL**：8 小時後自動過期清除
3. **Per-request 連線**：每次操作建立新 SMB 連線，用完即關閉
4. **權限繼承**：檔案操作權限由 NAS 本身控制（使用者登入的 NAS 帳號權限）

## 除錯

### 測試 NAS 連線

```bash
# 測試帳密和列出共享
smbclient -L //192.168.11.50 -U username%password

# 測試存取特定共享
smbclient //192.168.11.50/home -U username%password -c "ls"
```

### 測試 API

```bash
# 登入取得 token
TOKEN=$(curl -s -X POST http://localhost:8088/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"pass"}' | jq -r '.token')

# 列出共享
curl -s http://localhost:8088/api/nas/shares \
  -H "Authorization: Bearer $TOKEN" | jq

# 瀏覽資料夾
curl -s "http://localhost:8088/api/nas/browse?path=/home" \
  -H "Authorization: Bearer $TOKEN" | jq
```

## 已知限制

1. **不支援 SMB1**：`smbprotocol` 只支援 SMB2/SMB3
2. **大檔案**：目前一次讀取整個檔案到記憶體，大檔案可能有問題
3. **併發**：每個 request 建立新連線，高併發時可能影響效能
4. **smbclient 依賴**：列出共享需要系統安裝 smbclient

## 未來改進方向

- [ ] 實作 streaming 讀取大檔案
- [ ] 連線池（Connection Pool）減少連線開銷
- [ ] 用純 Python 實作 SRVSVC RPC 移除 smbclient 依賴
- [ ] 支援 WebSocket 即時顯示上傳進度
