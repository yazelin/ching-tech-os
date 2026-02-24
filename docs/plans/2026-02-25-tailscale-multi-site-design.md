# Tailscale 多站 CTOS 架構設計

## 目的

讓部署在不同地點的 CTOS 實例，透過 Tailscale VPN 連回主站 (ching-tech.ddns.net)，由主站 nginx 統一對外提供服務，包含：
- 完整 CTOS Web UI（登入頁、桌面等）
- Line Bot webhook 接收

## 架構概覽

```
Line Platform
    │
    ▼
ching-tech.ddns.net (192.168.11.11) ── 主站 nginx
    │
    ├─ /ctos/*           → localhost:8088      (主站自己的 CTOS)
    ├─ /client-a/*       → 100.64.0.2:8088    (遠端 A，Tailscale)
    ├─ /bot/client-a/*   → 100.64.0.2:8088    (遠端 A 的 Line webhook)
    ├─ /client-b/*       → 100.64.0.3:8088    (遠端 B，Tailscale)
    └─ /bot/client-b/*   → 100.64.0.3:8088    (遠端 B 的 Line webhook)
         │
         │  Tailscale VPN (WireGuard)
         │
    ┌────┴────────────────────┐
    │                         │
100.64.0.2                100.64.0.3
遠端 A                     遠端 B
├─ CTOS 後端 :8088         ├─ CTOS 後端 :8088
├─ PostgreSQL (Docker)     ├─ PostgreSQL (Docker)
└─ Tailscale              └─ Tailscale
```

### 角色分工

| 角色 | 職責 |
|------|------|
| 主站 nginx | SSL 終止、路徑路由、反向代理到 Tailscale IP |
| 主站 Tailscale | 與遠端節點建立加密隧道 |
| 遠端 CTOS | 完整的 CTOS 應用（後端 + DB），獨立運作 |
| 遠端 Tailscale | 與主站建立加密隧道，取得固定 IP |

### 設計決策

- **路徑區分客戶**：每個客戶一個 URL 路徑前綴，只需一個域名 + 一張 SSL 憑證
- **固定 Tailscale IP**：每台遠端的 Tailscale IP 固定，直接寫在 nginx 設定中
- **nginx strip prefix**：主站 nginx 去掉路徑前綴後轉發，遠端 CTOS 跑在根路徑 `/`，不需要知道自己的子路徑
- **CTOS 程式碼不改**：前端 `config.js` 已有子路徑自動偵測機制，現有架構足以支援

## 主站設定

### 1. 安裝 Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# 在瀏覽器開啟授權連結，登入帳號
```

### 2. nginx 設定範本

每新增一個遠端客戶，在 nginx 設定中加入以下 location block（需修改三個值）：

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

**需替換的值：**

| 佔位符 | 說明 | 範例 |
|--------|------|------|
| `<CLIENT_ID>` | 客戶識別碼（URL 路徑） | `company-a` |
| `<TAILSCALE_IP>` | 遠端的 Tailscale IP | `100.64.0.2` |

### 3. 新增客戶 SOP

1. 在 Tailscale 管理後台產生 Auth Key（One-off）
2. 遠端主機安裝 Tailscale 並加入 tailnet（見下方「遠端主機部署」）
3. 記下遠端的 Tailscale IP
4. 複製上方 nginx 範本，填入 `CLIENT_ID` 和 `TAILSCALE_IP`
5. `sudo nginx -t && sudo nginx -s reload`
6. 在 Line Developer Console 設定 webhook URL：`https://ching-tech.ddns.net/bot/<CLIENT_ID>/webhook`
7. 驗證（見下方「驗證與除錯」）

## 遠端主機部署

### 前置需求

| 項目 | 用途 |
|------|------|
| Ubuntu 22.04+ 或 Debian 12+ | 作業系統 |
| Docker + Docker Compose | 執行 PostgreSQL |
| Python 3.11+ | 後端執行環境 |
| uv | Python 套件管理 |
| git | 取得程式碼 |

### 步驟 1：安裝 Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --authkey=tskey-auth-xxxxxxxx
# 確認取得 IP
tailscale ip -4
```

Auth Key 產生方式：
1. 登入 https://login.tailscale.com/admin/settings/keys
2. 點 Generate auth key
3. 選 One-off + 設定到期日

### 步驟 2：部署 CTOS

```bash
# Clone 程式碼
git clone https://github.com/yazelin/ching-tech-os.git
cd ching-tech-os

# 安裝 Docker（如果還沒裝）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重新登入以套用 docker group

# 安裝 uv（如果還沒裝）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝後端依賴
cd backend && uv sync && cd ..

# 設定環境變數
cp .env.example .env
# 編輯 .env，至少需要設定：
#   DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
#   LINE_CHANNEL_SECRET（此客戶的 Line Bot secret）
#   LINE_CHANNEL_ACCESS_TOKEN（此客戶的 Line Bot token）
```

### 步驟 3：安裝 systemd 服務

使用現有的 `install-service.sh`，但需先手動調整以下項目：

| 行號 | 變數 | 預設值 | 調整說明 |
|------|------|--------|---------|
| 12 | `PROJECT_DIR` | `/home/ct/SDD/ching-tech-os` | 改為實際的 clone 路徑 |
| 244 | `User=ct` | `ct` | 改為遠端主機的使用者 |
| 244 | `Group=ct` | `ct` | 同上 |
| 248 | node 路徑 | `v24.13.0` | 改為遠端實際的 node 版本（或移除） |
| 39-43 | NAS 設定檢查 | 必填 | 若無 NAS，註解掉 NAS 相關段落（第 34-209 行） |

調整完畢後執行：

```bash
sudo ./scripts/install-service.sh
```

### 步驟 4：確認服務啟動

```bash
sudo systemctl status ching-tech-os
curl http://localhost:8088/api/health
```

## Line Bot 設定

在 [Line Developer Console](https://developers.line.biz/console/) 中：

1. 選擇對應的 Line Bot Channel
2. 進入 Messaging API 設定
3. Webhook URL 設定為：`https://ching-tech.ddns.net/bot/<CLIENT_ID>/webhook`
4. 開啟 Use webhook

## 驗證與除錯

### 逐步驗證清單

```bash
# 1. 遠端：確認 CTOS 後端正常
curl http://localhost:8088/api/health

# 2. 遠端：確認 Tailscale 已連線
tailscale status

# 3. 主站：確認可透過 Tailscale 連到遠端
ping <TAILSCALE_IP>
curl http://<TAILSCALE_IP>:8088/api/health

# 4. 主站：確認 nginx 設定正確
sudo nginx -t

# 5. 外部：確認完整路徑可存取
curl https://ching-tech.ddns.net/<CLIENT_ID>/api/health

# 6. 外部：測試 webhook（模擬 Line 請求）
curl -X POST https://ching-tech.ddns.net/bot/<CLIENT_ID>/webhook \
  -H "Content-Type: application/json" \
  -d '{"events":[]}'
```

### 常見問題

| 症狀 | 可能原因 | 排查 |
|------|---------|------|
| 502 Bad Gateway | 遠端 CTOS 未啟動或 Tailscale 斷線 | 檢查遠端 `systemctl status ching-tech-os` 和 `tailscale status` |
| 404 | nginx location 路徑設定錯誤 | 確認 `CLIENT_ID` 拼寫一致 |
| WebSocket 連線失敗 | nginx 缺少 Upgrade header | 確認 location block 包含 `proxy_set_header Upgrade` |
| Webhook 簽章驗證失敗 | `X-Line-Signature` header 未傳遞 | 確認 webhook location 包含 `proxy_set_header X-Line-Signature` |
| 靜態資源 404 | 路徑前綴問題 | 確認 `proxy_pass` 尾部有 `/`（strip prefix） |

## 未來規劃

- 將 Tailscale 部署整合進 `scripts/install-service.sh`（參數化路徑、NAS 可選）
- 管理介面：在 CTOS 後台管理路由對應，自動產生 nginx 設定
- 超過 100 台設備時評估遷移到 Headscale（自架協調伺服器）
