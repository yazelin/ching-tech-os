# Proposal: add-backend-nas-auth

## Summary
建立後端服務基礎架構，實作使用 NAS SMB 認證的登入功能。

## Motivation
目前前端登入為模擬實作，需要建立真實的後端服務，透過區網 NAS (192.168.11.50) 的 SMB 認證來驗證使用者身份，並能瀏覽 NAS 上的資料夾。

## Scope

### In Scope
- 後端專案初始化 (uv + FastAPI + Socket.IO)
- Docker Compose 設定 (PostgreSQL 資料庫容器)
- 使用者表建立（記錄登入過的使用者）
- NAS SMB 認證登入 API
- Session 管理（憑證儲存在 server 記憶體）
- 列出 NAS 共享資料夾 API
- 前端登入頁面整合真實 API

### Out of Scope
- 其他資料庫表結構（AI Agent、知識庫等，後續開發時處理）
- 檔案上傳/下載功能
- 使用者權限管理細節
- Socket.IO 即時通訊功能（本次僅安裝，不實作）

## Approach

### 架構決策
1. **憑證儲存策略**：Session 儲存（選項 B）
   - 登入成功後，憑證存在 server 記憶體
   - 使用 session ID (token) 識別使用者
   - Server 重啟後 session 失效，使用者需重新登入

2. **SMB 連線策略**：按需建立
   - 每次操作時使用儲存的憑證建立 SMB 連線
   - 操作完成後關閉連線
   - 避免長連線的資源消耗和斷線問題

3. **技術選擇**
   - `smbprotocol` Python 套件：純 Python SMB 實作，跨平台
   - FastAPI session middleware 或自訂 token 機制
   - httpx 用於未來 API 呼叫

## Dependencies
- Python 3.11+
- uv (Python 套件管理)
- Docker & Docker Compose
- 區網 NAS (192.168.11.50) 可連線

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| NAS 斷線導致登入失敗 | 清楚的錯誤訊息，前端顯示連線狀態 |
| Session 過期無提示 | 設定合理 TTL，API 回傳 401 時前端導向登入頁 |
| SMB 憑證外洩 | 僅存於記憶體，不寫入 log，HTTPS 傳輸 |

## Success Criteria
1. 可使用 NAS 帳密透過 API 登入
2. 登入後可列出 NAS 上的共享資料夾
3. 前端登入頁面串接真實 API
4. PostgreSQL 容器可正常啟動（暫不使用）
