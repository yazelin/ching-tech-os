# Tailscale 多站 CTOS 部署指南

## 概覽

本文件說明如何透過 Tailscale VPN，將部署在不同地點的 CTOS 實例連回主站，由主站 nginx 統一對外提供服務。每個遠端站點擁有獨立的 CTOS 後端與資料庫，主站僅負責 SSL 終止與路徑路由。

### 架構圖

```
Line Platform
    |
    v
ching-tech.ddns.net (主站 nginx)
    |
    |-- /ctos/*           --> localhost:8088      (主站 CTOS)
    |-- /client-a/*       --> 100.64.0.2:8088    (遠端 A，經 Tailscale)
    |-- /bot/client-a/*   --> 100.64.0.2:8088    (遠端 A Line webhook)
    |-- /client-b/*       --> 100.64.0.3:8088    (遠端 B，經 Tailscale)
    |-- /bot/client-b/*   --> 100.64.0.3:8088    (遠端 B Line webhook)
         |
         |  Tailscale VPN (WireGuard)
         |
    +---------+------------------+
    |                            |
100.64.0.2                 100.64.0.3
遠端 A                      遠端 B
|- CTOS 後端 :8088          |- CTOS 後端 :8088
|- PostgreSQL (Docker)      |- PostgreSQL (Docker)
|- Tailscale                |- Tailscale
```

### 角色分工

| 角色 | 職責 |
|------|------|
| 主站 nginx | SSL 終止、路徑路由、反向代理到 Tailscale IP |
| 主站 Tailscale | 與遠端節點建立加密隧道 |
| 遠端 CTOS | 完整的 CTOS 應用（後端 + DB），獨立運作 |
| 遠端 Tailscale | 與主站建立加密隧道，取得固定 IP |

### 設計原則

- **路徑區分客戶**：每個客戶一個 URL 路徑前綴，只需一個域名與一張 SSL 憑證。
- **固定 Tailscale IP**：每台遠端主機的 Tailscale IP 固定，直接寫在 nginx 設定中。
- **nginx strip prefix**：主站 nginx 去掉路徑前綴後轉發，遠端 CTOS 不需要知道自己的子路徑。
- **程式碼不需修改**：前端 `config.js` 已有子路徑自動偵測機制，現有架構直接支援。

---

## 主站設定

### 1. 安裝 Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

執行後會顯示一個授權連結，在瀏覽器開啟並登入帳號完成授權。

### 2. nginx 設定

每新增一個遠端客戶時，需要在主站 nginx 設定中加入對應的 location block。

範本檔案位於 `scripts/nginx/ctos-remote-site.conf.template`，內容如下：

```nginx
# ============================================
# 遠端 CTOS: <CLIENT_ID>
# Tailscale IP: <TAILSCALE_IP>
# Port: 8088
# ============================================

# CTOS 完整應用（strip prefix 後轉發）
location /<CLIENT_ID>/ {
    proxy_pass http://<TAILSCALE_IP>:8088/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Line Bot Webhook（改寫路徑後轉發）
location = /bot/<CLIENT_ID>/webhook {
    proxy_pass http://<TAILSCALE_IP>:8088/api/bot/line/webhook;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Line-Signature $http_x_line_signature;
}
```

使用時複製此範本，將以下佔位符替換為實際值：

| 佔位符 | 說明 | 範例 |
|--------|------|------|
| `<CLIENT_ID>` | 客戶識別碼（用於 URL 路徑） | `company-a` |
| `<TAILSCALE_IP>` | 遠端主機的 Tailscale IP | `100.64.0.2` |

替換完成後將內容加入主站 nginx 設定檔，然後測試並重新載入：

```bash
sudo nginx -t && sudo nginx -s reload
```

**注意事項**：

- `proxy_pass` 尾部的 `/` 不可省略，這是 nginx strip prefix 的關鍵。
- CTOS 應用的 location block 必須包含 WebSocket 相關 header（`Upgrade`、`Connection`），否則 Socket.IO 連線會失敗。
- Line webhook 的 location block 必須傳遞 `X-Line-Signature` header，否則簽章驗證會失敗。

---

## 新增客戶 SOP

以下為新增一個遠端客戶站點的完整步驟。

### 步驟 1：產生 Tailscale Auth Key

1. 登入 [Tailscale 管理後台](https://login.tailscale.com/admin/settings/keys)。
2. 點選 **Generate auth key**。
3. 選擇 **One-off**，設定適當的到期日。
4. 記下產生的 Auth Key（格式為 `tskey-auth-xxxxxxxx`）。

### 步驟 2：部署遠端主機

依照下一節「遠端主機部署步驟」完成遠端 CTOS 的安裝與 Tailscale 連線。

### 步驟 3：記錄遠端的 Tailscale IP

在遠端主機上執行：

```bash
tailscale ip -4
```

記下輸出的 IP 位址（如 `100.64.0.2`）。

### 步驟 4：設定主站 nginx

1. 複製 `scripts/nginx/ctos-remote-site.conf.template` 範本。
2. 將 `<CLIENT_ID>` 替換為客戶識別碼（如 `company-a`）。
3. 將 `<TAILSCALE_IP>` 替換為步驟 3 取得的 IP。
4. 將替換後的內容加入主站 nginx 設定檔。
5. 測試並重新載入 nginx：

```bash
sudo nginx -t && sudo nginx -s reload
```

### 步驟 5：設定 Line Bot webhook

在 [Line Developer Console](https://developers.line.biz/console/) 中設定 webhook URL（詳見下方「Line Bot webhook 設定」章節）。

### 步驟 6：驗證

依照下方「驗證與除錯」章節的檢查清單逐步確認。

---

## 遠端主機部署步驟

### 前置需求

| 項目 | 用途 |
|------|------|
| Ubuntu 22.04+ 或 Debian 12+ | 作業系統 |
| Docker + Docker Compose | 執行 PostgreSQL |
| Python 3.11+ | 後端執行環境 |
| uv | Python 套件管理 |
| git | 取得程式碼 |

### 步驟 1：安裝 Tailscale 並加入 tailnet

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --authkey=tskey-auth-xxxxxxxx
```

將 `tskey-auth-xxxxxxxx` 替換為在「新增客戶 SOP - 步驟 1」中產生的 Auth Key。

確認已取得 Tailscale IP：

```bash
tailscale ip -4
```

### 步驟 2：部署 CTOS 應用

```bash
# 取得程式碼
git clone https://github.com/yazelin/ching-tech-os.git
cd ching-tech-os

# 安裝 Docker（若尚未安裝）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 需重新登入以套用 docker group

# 安裝 uv（若尚未安裝）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝後端依賴
cd backend && uv sync && cd ..

# 設定環境變數
cp .env.example .env
```

編輯 `.env` 檔案，至少需要設定以下項目：

| 變數 | 說明 |
|------|------|
| `DB_HOST` | 資料庫主機（通常為 `localhost`） |
| `DB_PORT` | 資料庫埠號（預設 `5432`） |
| `DB_USER` | 資料庫使用者 |
| `DB_PASSWORD` | 資料庫密碼 |
| `DB_NAME` | 資料庫名稱 |
| `LINE_CHANNEL_SECRET` | 此客戶的 Line Bot Channel Secret |
| `LINE_CHANNEL_ACCESS_TOKEN` | 此客戶的 Line Bot Access Token |

### 步驟 3：啟動資料庫

```bash
cd docker && docker compose up -d && cd ..
```

執行資料庫 migration：

```bash
cd backend && uv run alembic upgrade head && cd ..
```

### 步驟 4：安裝 systemd 服務

使用專案中的 `scripts/install-service.sh`，但遠端主機的環境通常與主站不同，需要先調整以下項目：

| 變數/區段 | 預設值 | 調整說明 |
|-----------|--------|---------|
| `PROJECT_DIR`（第 12 行） | `/home/ct/SDD/ching-tech-os` | 改為遠端主機上的實際 clone 路徑 |
| `User` / `Group`（systemd unit） | `ct` | 改為遠端主機的使用者名稱 |
| node 路徑（第 248 行附近） | `v24.13.0` | 改為遠端實際的 node 版本，或在不需要前端建置時移除 |
| NAS 設定檢查（第 34-43 行） | 必填 | 若遠端主機無 NAS，註解掉 NAS 相關段落（約第 34-209 行） |

調整完成後執行：

```bash
sudo ./scripts/install-service.sh
```

### 步驟 5：確認服務啟動

```bash
# 檢查服務狀態
sudo systemctl status ching-tech-os

# 測試 API 回應
curl http://localhost:8088/api/health
```

如果服務未正常啟動，查看日誌排查問題：

```bash
journalctl -u ching-tech-os -n 50 --no-pager
```

---

## Line Bot webhook 設定

每個遠端站點的 Line Bot 需要獨立的 webhook URL，由主站 nginx 統一接收後轉發。

### 設定步驟

1. 登入 [Line Developer Console](https://developers.line.biz/console/)。
2. 選擇對應客戶的 Line Bot Channel。
3. 進入 **Messaging API** 設定頁面。
4. 將 **Webhook URL** 設定為：

```
https://ching-tech.ddns.net/bot/<CLIENT_ID>/webhook
```

將 `<CLIENT_ID>` 替換為該客戶的識別碼（與 nginx 設定中一致）。

5. 開啟 **Use webhook** 開關。
6. 點選 **Verify** 按鈕確認 webhook 可正常連線。

### URL 對應關係

主站 nginx 會將 webhook 請求的路徑從 `/bot/<CLIENT_ID>/webhook` 改寫為 `/api/bot/line/webhook`，再轉發到遠端 CTOS。遠端 CTOS 收到的是標準的 Line webhook 路徑，不需要做任何特殊處理。

---

## 驗證與除錯

### 逐步驗證清單

部署完成後，按照以下順序逐步確認各環節是否正常。

**1. 遠端：確認 CTOS 後端正常運作**

```bash
curl http://localhost:8088/api/health
```

預期回應為 HTTP 200。

**2. 遠端：確認 Tailscale 已連線**

```bash
tailscale status
```

應顯示為 online 狀態，並列出 tailnet 中的其他節點。

**3. 主站：確認可透過 Tailscale 連到遠端**

```bash
ping <TAILSCALE_IP>
curl http://<TAILSCALE_IP>:8088/api/health
```

**4. 主站：確認 nginx 設定語法正確**

```bash
sudo nginx -t
```

**5. 外部：確認完整路徑可存取**

```bash
curl https://ching-tech.ddns.net/<CLIENT_ID>/api/health
```

**6. 外部：測試 Line webhook 路徑**

```bash
curl -X POST https://ching-tech.ddns.net/bot/<CLIENT_ID>/webhook \
  -H "Content-Type: application/json" \
  -d '{"events":[]}'
```

### 常見問題

| 症狀 | 可能原因 | 排查方式 |
|------|---------|---------|
| 502 Bad Gateway | 遠端 CTOS 未啟動或 Tailscale 斷線 | 檢查遠端 `systemctl status ching-tech-os` 和 `tailscale status` |
| 404 Not Found | nginx location 路徑設定錯誤 | 確認 `CLIENT_ID` 在 nginx 設定與 URL 中拼寫一致 |
| WebSocket 連線失敗 | nginx 缺少 Upgrade header | 確認 CTOS 的 location block 包含 `proxy_set_header Upgrade` 和 `Connection "upgrade"` |
| Webhook 簽章驗證失敗 | `X-Line-Signature` header 未傳遞 | 確認 webhook 的 location block 包含 `proxy_set_header X-Line-Signature` |
| 靜態資源 404 | 路徑前綴未正確去除 | 確認 `proxy_pass` 尾部有 `/`（此為 nginx strip prefix 的必要條件） |
| Tailscale 無法連線 | Auth Key 已過期或已使用 | 重新產生 Auth Key，執行 `sudo tailscale up --authkey=<NEW_KEY>` |

---

## 未來規劃

- **install-service.sh 參數化**：將 Tailscale 部署整合進安裝腳本，支援路徑參數與 NAS 可選模式，減少手動調整步驟。
- **管理介面**：在 CTOS 後台新增遠端站點管理功能，可管理路由對應並自動產生 nginx 設定。
- **Headscale 評估**：當連線設備超過 100 台時，評估遷移到 Headscale（自架 Tailscale 協調伺服器）以降低成本。
