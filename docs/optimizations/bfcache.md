# BFCache 優化指南：移除 `Cache-Control: no-store` 阻礙

> **狀態**：提案（Proposal）
> **影響範圍**：後端 HTTP 回應標頭、前端頁面導航體驗
> **優先級**：中高 — 直接影響 Lighthouse Performance 分數與使用者感知速度

---

## 目錄

1. [問題描述](#問題描述)
2. [什麼是 BFCache？](#什麼是-bfcache)
3. [問題根因分析](#問題根因分析)
4. [影響評估](#影響評估)
5. [建議變更方案](#建議變更方案)
6. [FastAPI 實作範例](#fastapi-實作範例)
7. [Nginx 反向代理範例](#nginx-反向代理範例)
8. [前端配合事項](#前端配合事項)
9. [驗證方法](#驗證方法)
10. [風險與注意事項](#風險與注意事項)
11. [參考資料](#參考資料)

---

## 問題描述

目前後端 API 或頁面回應可能帶有 `Cache-Control: no-store` 標頭，此標頭會**完全阻止瀏覽器使用 BFCache（Back/Forward Cache）**。當使用者按下「上一頁／下一頁」時，頁面無法從記憶體快照中即時還原，而是必須重新載入，導致：

- 頁面導航延遲 1～3 秒（取決於網路與伺服器回應速度）
- Lighthouse 審計中出現 **"Page prevented back/forward cache restoration"** 警告
- 使用者體驗（UX）明顯下降，特別是在行動裝置上

---

## 什麼是 BFCache？

**BFCache（Back/Forward Cache）** 是現代瀏覽器（Chrome 96+、Firefox 、Safari）內建的優化機制。當使用者離開頁面時，瀏覽器會將整個頁面狀態（DOM、JavaScript heap、Layout tree）保存在記憶體中。當使用者按下上一頁／下一頁時，頁面可以**瞬間還原**（通常 < 100ms），無需重新請求伺服器。

### BFCache 的阻斷因素

| 阻斷因素 | 說明 |
|---|---|
| `Cache-Control: no-store` | **最常見的阻斷原因**。瀏覽器視為「此頁面不可快取」 |
| 未關閉的 `beforeunload` listener | 瀏覽器無法確定是否安全凍結頁面 |
| 使用 `unload` 事件 | 已被棄用，會阻止 BFCache |
| 活躍的 WebSocket / WebRTC 連線 | 需要在 `pagehide` 時適當關閉 |

---

## 問題根因分析

在本專案（ching-tech-os）中，可能觸發 `no-store` 的場景：

### 1. FastAPI 預設行為
FastAPI/Starlette 的 `JSONResponse` 與 `HTMLResponse` 預設不帶 `Cache-Control` 標頭，但某些中介層（middleware）或反向代理可能自動加入 `no-store`。

### 2. 安全性中介層
登入相關路由（如 `/api/auth/*`）的回應若包含敏感資訊，可能被安全套件自動加上 `no-store`。

### 3. 靜態檔案服務
FastAPI 的 `StaticFiles` mount 預設不設定長效快取標頭，可能導致瀏覽器每次都重新驗證。

### 4. 前端 SPA 頁面服務
`FileResponse` 回傳 `index.html` 時若帶有 `no-store`，將直接阻止整個 SPA 進入 BFCache。

---

## 影響評估

| 指標 | 目前（預估） | 優化後（預估） |
|---|---|---|
| 上一頁導航時間 | 1,000 ~ 3,000 ms | < 100 ms |
| Lighthouse Performance | 扣分項存在 | 消除該扣分項 |
| 行動端使用者體驗 | 頁面閃白重載 | 瞬間還原 |
| 伺服器負載 | 每次導航觸發 full request | 減少約 30~50% 導航請求 |

---

## 建議變更方案

### 方案 A：依路由類型設定差異化 Cache-Control 標頭

| 路由類別 | 建議 Cache-Control 值 | 原因 |
|---|---|---|
| 公開頁面（`/share/*`、`/public/*`） | `public, max-age=300` | 可安全快取，支援 BFCache |
| SPA 入口（`index.html`） | `no-cache`（非 no-store） | 允許 BFCache，但每次驗證新鮮度 |
| 靜態資源（JS/CSS/圖片） | `public, max-age=31536000, immutable` | 帶 hash 的檔案可長效快取 |
| API 回應（`/api/*`） | `private, no-cache` | 不影響 BFCache（非導航回應） |
| 認證端點（`/api/auth/*`） | `private, no-store` | 含敏感資訊，保留 no-store |

> **關鍵**：`no-cache` ≠ `no-store`。`no-cache` 允許快取但要求驗證；`no-store` 完全禁止快取（包括 BFCache）。

### 方案 B：新增 Middleware 統一管理

在 FastAPI 中新增一個中介層，根據路由路徑自動設定合適的 `Cache-Control` 標頭。

### 方案 C：在反向代理（Nginx）層處理

若未來部署使用 Nginx 作為反向代理，可在 Nginx 層統一管理快取標頭。

---

## FastAPI 實作範例

### 範例 1：BFCache 友善的 Middleware

```python
# backend/src/ching_tech_os/middleware/cache_control.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CacheControlMiddleware(BaseHTTPMiddleware):
    """
    依路由類型設定合適的 Cache-Control 標頭，
    避免 no-store 阻止 BFCache。
    """

    # 必須保留 no-store 的路徑前綴（含敏感資訊）
    NO_STORE_PREFIXES = ("/api/auth/", "/api/login/")

    # 公開且可安全快取的路徑前綴
    CACHEABLE_PREFIXES = ("/share/", "/public/", "/api/config/public")

    # 靜態資源目錄
    STATIC_PREFIXES = ("/static/", "/assets/")

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path

        # 已明確設定 Cache-Control 的回應不覆蓋
        if "cache-control" in response.headers:
            return response

        if any(path.startswith(p) for p in self.NO_STORE_PREFIXES):
            response.headers["Cache-Control"] = "private, no-store"
        elif any(path.startswith(p) for p in self.STATIC_PREFIXES):
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable"
            )
        elif any(path.startswith(p) for p in self.CACHEABLE_PREFIXES):
            response.headers["Cache-Control"] = "public, max-age=300"
        elif path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-cache"
        else:
            # SPA 入口頁面 — 使用 no-cache（允許 BFCache）
            response.headers["Cache-Control"] = "no-cache"

        return response
```

### 範例 2：在 main.py 中掛載 Middleware

```python
# 在 create_app() 或 app 建立後加入：
from .middleware.cache_control import CacheControlMiddleware

app.add_middleware(CacheControlMiddleware)
```

### 範例 3：單一路由設定（適用於特定公開端點）

```python
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/share/{share_id}")
async def get_shared_page(share_id: str):
    # ... 取得分享頁面內容 ...
    html_content = render_share_page(share_id)
    return HTMLResponse(
        content=html_content,
        headers={
            "Cache-Control": "public, max-age=300",
        },
    )
```

---

## Nginx 反向代理範例

若未來在 Nginx 層處理（例如 Docker 部署加入 Nginx 服務），可參考以下配置：

```nginx
# /etc/nginx/conf.d/cache-control.conf

server {
    listen 80;
    server_name ching-tech-os.example.com;

    # SPA 入口 — 允許 BFCache，但每次驗證
    location / {
        proxy_pass http://backend:8000;
        add_header Cache-Control "no-cache" always;
    }

    # 靜態資源 — 長效快取（檔名含 hash）
    location ~* \.(js|css|png|jpg|jpeg|webp|avif|svg|woff2?)$ {
        proxy_pass http://backend:8000;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
    }

    # 公開分享頁面 — 可快取
    location /share/ {
        proxy_pass http://backend:8000;
        add_header Cache-Control "public, max-age=300" always;
    }

    location /public/ {
        proxy_pass http://backend:8000;
        add_header Cache-Control "public, max-age=300" always;
    }

    # API 端點 — 私有快取
    location /api/ {
        proxy_pass http://backend:8000;
        add_header Cache-Control "private, no-cache" always;
    }

    # 認證端點 — 保留 no-store（安全需求）
    location /api/auth/ {
        proxy_pass http://backend:8000;
        add_header Cache-Control "private, no-store" always;
    }
}
```

---

## 前端配合事項

### 1. 避免使用 `unload` 事件

```javascript
// ❌ 不要使用（會阻止 BFCache）
window.addEventListener('unload', () => { /* ... */ });

// ✅ 改用 pagehide
window.addEventListener('pagehide', (event) => {
  if (event.persisted) {
    // 頁面即將進入 BFCache
    console.log('Page is entering BFCache');
  }
});
```

### 2. 正確處理 `beforeunload`

```javascript
// ✅ 只在有未儲存變更時才註冊 beforeunload
let hasUnsavedChanges = false;

function onBeforeUnload(e) {
  if (hasUnsavedChanges) {
    e.preventDefault();
    // 部分瀏覽器需要 returnValue
    e.returnValue = '';
  }
}

// 有未儲存變更時才加入 listener
function setUnsavedChanges(value) {
  hasUnsavedChanges = value;
  if (value) {
    window.addEventListener('beforeunload', onBeforeUnload);
  } else {
    window.removeEventListener('beforeunload', onBeforeUnload);
  }
}
```

### 3. 使用 `sendBeacon` 替代同步請求

```javascript
// ❌ 不要在 beforeunload/pagehide 中使用同步 XHR
window.addEventListener('beforeunload', () => {
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/analytics', false); // 同步！會阻塞
  xhr.send(data);
});

// ✅ 使用 sendBeacon（非同步、不阻塞導航）
window.addEventListener('pagehide', () => {
  const data = JSON.stringify({ event: 'page_leave', timestamp: Date.now() });
  navigator.sendBeacon('/api/analytics', data);
});
```

### 4. BFCache 還原時重新初始化

```javascript
// 頁面從 BFCache 還原時，重新建立連線等
window.addEventListener('pageshow', (event) => {
  if (event.persisted) {
    // 頁面從 BFCache 還原
    console.log('Page restored from BFCache');

    // 重新建立 WebSocket 連線（若需要）
    reconnectWebSocket();

    // 重新驗證登入狀態
    validateSession();

    // 更新頁面時間戳等動態資料
    refreshDynamicContent();
  }
});
```

---

## 驗證方法

### 1. Chrome DevTools 檢測

1. 開啟 DevTools → **Application** → **Back/forward cache**
2. 點擊 **Test back/forward cache**
3. 查看結果：若顯示 `Cache-Control: no-store` 為阻斷原因，表示問題仍存在

### 2. Lighthouse 審計

```bash
# 使用 Lighthouse CLI 檢測
npx lighthouse https://your-site.com --only-categories=performance \
  --output=json --output-path=./bfcache-audit.json

# 檢查 bfcache 相關的審計項目
cat bfcache-audit.json | jq '.audits["bf-cache"]'
```

### 3. 手動驗證流程

```
1. 開啟目標頁面
2. 在 Network tab 確認回應標頭中無 `Cache-Control: no-store`
3. 點擊站內連結導航到其他頁面
4. 按下瀏覽器「上一頁」
5. 確認頁面是否從 BFCache 瞬間還原（Network tab 應無新請求）
```

### 4. 程式化驗證

```javascript
// 在 console 中執行，檢測 BFCache 是否生效
window.addEventListener('pageshow', (event) => {
  if (event.persisted) {
    console.log('✅ BFCache 還原成功！');
  } else {
    console.log('⚠️ 頁面是全新載入的（非 BFCache 還原）');
  }
});
```

---

## 風險與注意事項

| 風險 | 緩解方式 |
|---|---|
| 敏感資料快取洩漏 | 認證端點保留 `no-store`；BFCache 僅在同一瀏覽器 Session 內有效 |
| 頁面過時資料 | `pageshow` 事件中重新驗證 Session 與更新動態內容 |
| WebSocket 斷線 | `pageshow` 事件中重新建立連線 |
| Socket.IO 連線狀態 | 本專案使用 Socket.IO，需在 `pageshow` 中呼叫 `socket.connect()` |

---

## 參考資料

- [web.dev — Back/forward cache](https://web.dev/articles/bfcache)
- [Chrome Developers — Optimize for BFCache](https://developer.chrome.com/docs/devtools/application/back-forward-cache/)
- [MDN — Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)
- [Lighthouse BFCache Audit](https://developer.chrome.com/docs/lighthouse/performance/bf-cache/)
- [Navigator.sendBeacon()](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/sendBeacon)
