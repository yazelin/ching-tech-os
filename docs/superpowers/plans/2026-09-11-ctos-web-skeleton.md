# ctos-web 前端骨架實作計劃（第 2 段）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `ching-tech/ctos-web` 新前端 repo，做出能在 https://os.ching-tech.com 登入（NAS 帳號或平台帳號）、有左側邊欄與各模組空頁、可綁定 NAS 帳號的骨架，並用 GitHub Pages 自動部署。

**Architecture:** 純前端 SPA，打正式後端 `https://ching-tech.ddns.net/ctos`（CORS 已放行）。認證是 Bearer token 放 localStorage。路由用 react-router；版面用 shadcn/ui 的 sidebar 區塊改成 CTOS 的模組清單；設計變數沿用舊桌面的主色與背景色。部署：push main → Actions 建置 → Pages；自訂網域 os.ching-tech.com（CNAME 已在 Cloudflare 加好，指 ching-tech.github.io）。

**Tech Stack:** Vite 8、React 19、TypeScript、Tailwind 4、shadcn/ui（radix 版，preset nova）、react-router 7、lucide-react、Vitest、Playwright。不用 TanStack Query（骨架用不到，知識庫列表那段再加）。

**Spec:** `docs/superpowers/specs/2026-09-10-ctos-web-react-frontend-design.md`（ching-tech-os repo）第一、二節與第三節的「帳號」段。後端第 1 段（PR #177）已上線，本計劃只碰前端。

## Global Constraints

- 新 repo `ching-tech/ctos-web`，**公開**（org Free 方案，Pages 只給公開 repo），本機路徑 `/home/ct/SDD/ctos-web`。LICENSE 為 MIT，版權行 `Copyright (c) 2026 擎添工業 Ching Tech Industrial Co., Ltd.`。
- API 位址由 `VITE_API_BASE` 注入，預設 `https://ching-tech.ddns.net/ctos`。token 存 localStorage key `ctos-web.token`，使用者快取 key `ctos-web.user`。
- 登入端點 `POST {API}/api/auth/login`，body `{username, password, method}`，method 明確送 `"nas"` 或 `"local"`（不送 auto）。回應 `{success, token, username, error, role, must_change_password}`。
- 使用者資訊 `GET {API}/api/user/me`：`{id, username, display_name, is_admin, role, account_role, auth_type, has_password, nas_username, permissions}`。
- NAS 綁定：`POST {API}/api/user/me/nas-binding` body `{nas_username, password}`，401＝NAS 帳密錯、409＝已被別人綁、503＝NAS 連不到；`DELETE` 同路徑解綁；成功回 `{success, nas_username}`。錯誤回應的訊息在 `detail` 欄位。
- 登出 `POST {API}/api/auth/logout`（Bearer）。任何 API 回 401 → 清 token 與快取、導回 `/login`。
- UI 文字一律正體中文，全形標點，不用 emoji。模組名稱與順序：首頁、知識庫、專案、Bot 管理、AI Log、使用者管理（僅 admin）、設定。
- 顏色：主色 `#0891b2`、主色 hover `#0ea5c9`、強調色 `#ea580c`、暗色背景 `#1a1a1a`、亮色背景 `#f5f5f5`，預設暗色主題，可切亮色。字體堆疊要含 CJK fallback：`'Geist Variable', 'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', system-ui, sans-serif`。
- 手機寬度（375px）側邊欄要縮成抽屜（shadcn sidebar 內建），頁面不可橫向捲動。
- TypeScript strict（scaffold 預設），`npm run build` 內含 `tsc -b`，必須零錯誤。
- 測試：Vitest 測 `src/lib`；Playwright 用 `page.route` 攔 API 做 e2e，不打真後端。CI（deploy workflow）要跑 `npm run test` 與 `npx playwright test` 通過才部署。
- Commit 訊息正體中文，結尾附實際執行模型的 `Co-Authored-By`。Task 1 直接推 `main`（初始化與 Pages 開通需要 main 上有 workflow）；Task 2 起在 branch `feat/skeleton`，最後開一個 PR 設 auto-merge，合併即部署。
- 不裝 ESLint/Prettier 以外的工具，不加 promo footer（公司內部系統，不是 yazelin 個人公開專案）。

## 檔案地圖（最終狀態）

```
ctos-web/
├── .github/workflows/deploy.yml   # 測試 + 建置 + Pages 部署
├── LICENSE, README.md, .env.example
├── public/CNAME                   # os.ching-tech.com
├── playwright.config.ts, vitest.config.ts（vite.config.ts 內設 test 亦可）
├── e2e/                           # Playwright，API 用 route 攔
│   ├── helpers.ts                 # mockApi(page, {user, loginResult})
│   ├── login.spec.ts
│   ├── shell.spec.ts
│   └── settings.spec.ts
└── src/
    ├── main.tsx                   # ThemeProvider + AuthProvider + RouterProvider
    ├── index.css                  # shadcn 產生 + CTOS 顏色覆寫 + 字體
    ├── lib/
    │   ├── api.ts                 # apiFetch、ApiError、API_BASE
    │   ├── token.ts               # get/set/clear token 與 user 快取
    │   ├── auth.ts                # login/logout/fetchMe/bindNas/unbindNas
    │   ├── types.ts               # LoginResponse、UserInfo、NasBindingResponse
    │   ├── auth-context.tsx       # AuthProvider、useAuth
    │   └── nav.ts                 # 模組清單（title/path/icon/adminOnly）
    ├── routes.tsx                 # createBrowserRouter
    ├── pages/
    │   ├── login.tsx
    │   ├── home.tsx
    │   ├── placeholder.tsx        # 知識庫/專案/Bot/AI Log/使用者管理共用
    │   └── settings.tsx
    └── components/
        ├── app-shell.tsx          # SidebarProvider + AppSidebar + header + <Outlet/>
        ├── app-sidebar.tsx        # 改自 sidebar-07 區塊
        ├── nav-user.tsx           # 使用者選單：主題、登出
        ├── theme-provider.tsx     # scaffold 產生
        └── ui/…                   # shadcn 元件
```

---

### Task 1: 建 repo、scaffold、Pages 部署到 os.ching-tech.com

**Files:**
- Create: 整個 `/home/ct/SDD/ctos-web`（scaffold）、`LICENSE`、`README.md`（暫）、`public/CNAME`、`.github/workflows/deploy.yml`、`src/App.tsx`（暫代首頁）
- Remote: 建 `ching-tech/ctos-web`，開 Pages（workflow 模式）並設 cname

**Interfaces:**
- Produces: repo 與 main 分支；`npm run build` 輸出 `dist/`；`https://os.ching-tech.com` 回 200 且內容含「ChingTech OS」。

- [ ] **Step 1: 建 GitHub repo 與本機 scaffold**

```bash
cd /home/ct/SDD
gh repo create ching-tech/ctos-web --public --description "ChingTech OS 新前端（React）— 擎添工業內部系統的 Web 介面" 
npx --yes shadcn@latest init -t vite -b radix -p nova -y --no-monorepo -n ctos-web
cd ctos-web
git init -b main && git remote add origin https://github.com/ching-tech/ctos-web.git
```

（`shadcn init -t vite` 會產生 Vite 8 + React 19 + TS + Tailwind 4 + `components.json` + `src/components/theme-provider.tsx` + `ui/button.tsx`，實測過。若它問 monorepo 或 preset，就是少了 `--no-monorepo` 或 `-p nova`。）

- [ ] **Step 2: LICENSE、CNAME、暫代首頁**

`LICENSE`：MIT 全文，版權行 `Copyright (c) 2026 擎添工業 Ching Tech Industrial Co., Ltd.`（可從 `/home/ct/SDD/ching-tech-os/LICENSE` 複製後改年份）。

`public/CNAME` 內容一行：`os.ching-tech.com`

`src/App.tsx` 換成：

```tsx
export default function App() {
  return (
    <main className="flex min-h-svh items-center justify-center">
      <h1 className="text-2xl font-semibold">ChingTech OS</h1>
    </main>
  )
}
```

`index.html` 的 `<title>` 改成 `ChingTech OS`，`<html lang="zh-TW">`。

- [ ] **Step 3: Deploy workflow**

`.github/workflows/deploy.yml`：

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npm run test --if-present
      - run: npx playwright install --with-deps chromium
        if: hashFiles('playwright.config.ts') != ''
      - run: npx playwright test
        if: hashFiles('playwright.config.ts') != ''
      - run: npm run build
      - run: cp dist/index.html dist/404.html
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

（`404.html` 複製 `index.html` 是 Pages 單頁路由的慣用法。）

- [ ] **Step 4: 本機驗建置，commit，推 main**

Run: `npm run build`
Expected: `dist/index.html` 存在，無 TypeScript 錯誤。

```bash
git add -A
git commit -m "chore: 以 Vite、React、Tailwind、shadcn/ui 初始化 ctos-web，加 Pages 部署

Co-Authored-By: <實際模型> <noreply@anthropic.com>"
git push -u origin main
```

- [ ] **Step 5: 開通 Pages（workflow 模式）並設自訂網域**

```bash
gh api -X POST repos/ching-tech/ctos-web/pages -f build_type=workflow 2>&1 | tail -1
gh api -X PUT repos/ching-tech/ctos-web/pages -f build_type=workflow -f cname=os.ching-tech.com
gh api repos/ching-tech/ctos-web/pages --jq '{cname, https_enforced, status, build_type}'
```

若 POST 回 409（已存在）直接做 PUT。

- [ ] **Step 6: 等 workflow 綠，驗網址**

Run: `gh run watch --repo ching-tech/ctos-web --exit-status $(gh run list --repo ching-tech/ctos-web --limit 1 --json databaseId --jq '.[0].databaseId')`
Expected: success。

Run: `curl -s -o /dev/null -w "%{http_code}\n" https://os.ching-tech.com/` 與 `curl -s https://os.ching-tech.com/ | grep -o "ChingTech OS"`
Expected: 200 與字串。若 HTTPS 憑證還沒發（curl 回 SSL 錯），改打 `http://os.ching-tech.com/` 先驗 200，並在報告寫明；憑證通常幾分鐘內好，之後執行 `gh api -X PUT repos/ching-tech/ctos-web/pages -F https_enforced=true`。

- [ ] **Step 7: 報告**（本 task 直接在 main，不另開 branch）

---

### Task 2: API client、token、auth 函式（Vitest）

**Files:**
- Create: `src/lib/api.ts`、`src/lib/token.ts`、`src/lib/auth.ts`、`src/lib/types.ts`、`.env.example`
- Test: `src/lib/api.test.ts`、`src/lib/auth.test.ts`
- Modify: `package.json`（scripts.test = `vitest run`；devDeps vitest）、`vite.config.ts`（`test` 區塊）

**Interfaces:**
- Produces:
  - `API_BASE: string`
  - `class ApiError extends Error { status: number; detail: string }`
  - `apiFetch<T>(path: string, init?: RequestInit & { auth?: boolean }): Promise<T>` — 自動帶 `Content-Type: application/json`、`Authorization: Bearer <token>`（有 token 時）；非 2xx 丟 `ApiError`（detail 取回應 JSON 的 `detail` 或 `error`，都沒有就 `HTTP <status>`）；204 回 `undefined`；**401 時先 `clearSession()` 再丟**。
  - `getToken(): string | null`、`setToken(t)`、`getCachedUser(): UserInfo | null`、`setCachedUser(u)`、`clearSession()`。
  - `login(username, password, method: "nas" | "local"): Promise<LoginResponse>` — 成功時 `setToken(token)`；`success=false` 時**不丟錯**，原樣回傳讓頁面顯示 `error`。
  - `logout(): Promise<void>` — 呼叫 `/api/auth/logout`（失敗也吞掉）再 `clearSession()`。
  - `fetchMe(): Promise<UserInfo>`、`bindNas(nas_username, password): Promise<NasBindingResponse>`、`unbindNas(): Promise<NasBindingResponse>`。

- [ ] **Step 1: 開 branch、裝 vitest**

```bash
cd /home/ct/SDD/ctos-web && git checkout -b feat/skeleton
npm i -D vitest
```

`package.json` scripts 加 `"test": "vitest run"`。`vite.config.ts` 加：

```ts
/// <reference types="vitest/config" />
// defineConfig 內：
  test: { environment: "node", globals: false },
```

- [ ] **Step 2: 型別**

`src/lib/types.ts`：

```ts
export type LoginMethod = "nas" | "local"

export interface LoginResponse {
  success: boolean
  token: string | null
  username: string | null
  error: string | null
  role: string | null
  must_change_password: boolean
}

export interface UserInfo {
  id: number
  username: string
  display_name: string | null
  is_admin: boolean
  role: string
  account_role: string
  auth_type: string
  has_password: boolean
  nas_username: string | null
  permissions: Record<string, boolean> | null
}

export interface NasBindingResponse {
  success: boolean
  nas_username: string | null
}
```

- [ ] **Step 3: 寫失敗的測試**

`src/lib/api.test.ts`：

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { apiFetch, ApiError, API_BASE } from "./api"
import { clearSession, getToken, setToken } from "./token"

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }))
  vi.stubGlobal("fetch", fn)
  return fn
}

beforeEach(() => {
  const store = new Map<string, string>()
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
})
afterEach(() => vi.unstubAllGlobals())

describe("apiFetch", () => {
  it("prefixes API_BASE and sends bearer token", async () => {
    setToken("t1")
    const fn = mockFetch(200, { ok: 1 })
    await apiFetch<{ ok: number }>("/api/user/me")
    const [url, init] = fn.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`${API_BASE}/api/user/me`)
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer t1")
  })
  it("throws ApiError with detail on 409", async () => {
    mockFetch(409, { detail: "此 NAS 帳號已綁定其他使用者" })
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 409, detail: "此 NAS 帳號已綁定其他使用者" })
  })
  it("clears session on 401", async () => {
    setToken("t1")
    mockFetch(401, { detail: "no" })
    await expect(apiFetch("/x")).rejects.toBeInstanceOf(ApiError)
    expect(getToken()).toBeNull()
  })
  it("returns undefined on 204", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })))
    expect(await apiFetch("/x")).toBeUndefined()
    clearSession()
  })
})
```

`src/lib/auth.test.ts`：

```ts
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { login, logout, bindNas } from "./auth"
import { getToken, setToken } from "./token"

beforeEach(() => {
  const store = new Map<string, string>()
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
})
afterEach(() => vi.unstubAllGlobals())

it("login sends method and stores token on success", async () => {
  const fn = vi.fn(async () => new Response(JSON.stringify({ success: true, token: "abc", username: "u", error: null, role: "user", must_change_password: false }), { status: 200 }))
  vi.stubGlobal("fetch", fn)
  const res = await login("u", "p", "local")
  expect(res.success).toBe(true)
  expect(getToken()).toBe("abc")
  const body = JSON.parse((fn.mock.calls[0] as [string, RequestInit])[1].body as string)
  expect(body).toEqual({ username: "u", password: "p", method: "local" })
})

it("login failure returns response without throwing and stores nothing", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ success: false, token: null, username: null, error: "帳號或密碼錯誤", role: null, must_change_password: false }), { status: 200 })))
  const res = await login("u", "bad", "nas")
  expect(res.success).toBe(false)
  expect(res.error).toBe("帳號或密碼錯誤")
  expect(getToken()).toBeNull()
})

it("logout clears session even if the request fails", async () => {
  setToken("abc")
  vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("network") }))
  await logout()
  expect(getToken()).toBeNull()
})

it("bindNas posts credentials", async () => {
  setToken("abc")
  const fn = vi.fn(async () => new Response(JSON.stringify({ success: true, nas_username: "n" }), { status: 200 }))
  vi.stubGlobal("fetch", fn)
  expect((await bindNas("n", "pw")).nas_username).toBe("n")
  const [url, init] = fn.mock.calls[0] as [string, RequestInit]
  expect(url).toMatch(/\/api\/user\/me\/nas-binding$/)
  expect(init.method).toBe("POST")
})
```

- [ ] **Step 4: 跑測試確認失敗**

Run: `npm run test`
Expected: FAIL（模組不存在）。

- [ ] **Step 5: 實作**

`src/lib/token.ts`：

```ts
import type { UserInfo } from "./types"

const TOKEN_KEY = "ctos-web.token"
const USER_KEY = "ctos-web.user"

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}
export function getCachedUser(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) as UserInfo } catch { return null }
}
export function setCachedUser(user: UserInfo) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
```

`src/lib/api.ts`：

```ts
import { clearSession, getToken } from "./token"

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ??
  "https://ching-tech.ddns.net/ctos"

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail)
    this.name = "ApiError"
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!headers.has("Content-Type") && init.body) headers.set("Content-Type", "application/json")
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (res.status === 204) return undefined as T
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const data = (await res.json()) as { detail?: unknown; error?: unknown }
      if (typeof data.detail === "string") detail = data.detail
      else if (typeof data.error === "string") detail = data.error
    } catch { /* 非 JSON 回應 */ }
    if (res.status === 401) clearSession()
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}
```

`src/lib/auth.ts`：

```ts
import { apiFetch } from "./api"
import { clearSession, setToken } from "./token"
import type { LoginMethod, LoginResponse, NasBindingResponse, UserInfo } from "./types"

export async function login(username: string, password: string, method: LoginMethod): Promise<LoginResponse> {
  const res = await apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password, method }),
  })
  if (res.success && res.token) setToken(res.token)
  return res
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/api/auth/logout", { method: "POST" })
  } catch { /* 登出失敗也要清本機 */ }
  clearSession()
}

export function fetchMe(): Promise<UserInfo> {
  return apiFetch<UserInfo>("/api/user/me")
}

export function bindNas(nas_username: string, password: string): Promise<NasBindingResponse> {
  return apiFetch<NasBindingResponse>("/api/user/me/nas-binding", {
    method: "POST",
    body: JSON.stringify({ nas_username, password }),
  })
}

export function unbindNas(): Promise<NasBindingResponse> {
  return apiFetch<NasBindingResponse>("/api/user/me/nas-binding", { method: "DELETE" })
}
```

`.env.example`：

```
# 後端 API 位址（正式機）。本機開發打本機後端就改成 http://127.0.0.1:8088
VITE_API_BASE=https://ching-tech.ddns.net/ctos
```

- [ ] **Step 6: 跑測試與建置**

Run: `npm run test && npm run build`
Expected: 全過、零 TS 錯誤。

- [ ] **Step 7: Commit**

```bash
git add src/lib .env.example package.json package-lock.json vite.config.ts
git commit -m "feat(lib): API client、token 存取與登入／登出／綁定函式

Co-Authored-By: <實際模型> <noreply@anthropic.com>"
```

---

### Task 3: 路由、AuthProvider、登入頁（Playwright）

**Files:**
- Create: `src/lib/auth-context.tsx`、`src/routes.tsx`、`src/pages/login.tsx`、`src/pages/home.tsx`、`src/components/require-auth.tsx`、`playwright.config.ts`、`e2e/helpers.ts`、`e2e/login.spec.ts`
- Modify: `src/main.tsx`、`src/App.tsx`（刪除，改由 routes）、`package.json`（devDeps `@playwright/test`；scripts `"e2e": "playwright test"`）
- Install: `react-router`（v7，單一套件）

**Interfaces:**
- Consumes: Task 2 的 `login`、`fetchMe`、`logout`、`getToken`、`getCachedUser`、`setCachedUser`、`clearSession`。
- Produces:
  - `AuthProvider` + `useAuth(): { user: UserInfo | null; loading: boolean; refresh(): Promise<void>; signOut(): Promise<void> }` — 掛載時若有 token 就 `fetchMe()`（成功 `setCachedUser`；401 已由 apiFetch 清掉）。
  - `RequireAuth`：無 token → `<Navigate to="/login" replace />`；有 token 但 `loading` → 顯示「載入中…」；載入後 `user` 為 null（token 失效）→ 導 `/login`。
  - 路由：`/login`；`/` 用 `RequireAuth` 包 `AppShell`（Task 4 才做，這個 task 先用最小殼 `<Outlet/>` 加登出鈕），子路由 index=`home`。
  - 登入頁：兩個 Tabs「NAS 帳號」（value `nas`）、「平台帳號」（value `local`），各自 username/password 欄位與「登入」按鈕；送出時呼叫 `login(u, p, tab)`；`success=false` 顯示 `error` 於 Alert（`role="alert"`）；成功 → `refresh()` 後 `navigate("/")`；已有 token 進 `/login` 直接導 `/`。表單元素要有 label：「帳號」「密碼」，NAS 分頁的帳號 label 為「NAS 帳號」。

- [ ] **Step 1: 裝套件**

```bash
npm i react-router
npm i -D @playwright/test
npx shadcn@latest add tabs card input label alert -y -o
```

- [ ] **Step 2: Playwright 設定與 helper**

`playwright.config.ts`：

```ts
import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:4173", trace: "retain-on-failure" },
  webServer: {
    command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"] } },
  ],
})
```

`e2e/helpers.ts`：

```ts
import type { Page } from "@playwright/test"

export const API = "https://ching-tech.ddns.net/ctos"

export const userFixture = {
  id: 2, username: "yazelin", display_name: "亞澤", is_admin: false, role: "user",
  account_role: "user", auth_type: "session", has_password: true, nas_username: "yazelin", permissions: {},
}
export const adminFixture = { ...userFixture, id: 1, username: "admin", display_name: "管理員", is_admin: true, role: "admin", account_role: "admin" }

export async function mockApi(page: Page, opts: { user?: typeof userFixture | null; loginOk?: boolean } = {}) {
  const user = opts.user === undefined ? userFixture : opts.user
  const loginOk = opts.loginOk ?? true
  await page.route(`${API}/api/auth/login`, async (route) => {
    const body = route.request().postDataJSON() as { username: string; password: string; method: string }
    await route.fulfill({ json: loginOk
      ? { success: true, token: "tok-" + body.method, username: body.username, error: null, role: "user", must_change_password: false }
      : { success: false, token: null, username: null, error: "帳號或密碼錯誤", role: null, must_change_password: false } })
  })
  await page.route(`${API}/api/auth/logout`, (route) => route.fulfill({ json: { success: true } }))
  await page.route(`${API}/api/user/me`, (route) => {
    const auth = route.request().headers()["authorization"]
    if (!auth || !user) return route.fulfill({ status: 401, json: { detail: "未授權" } })
    return route.fulfill({ json: user })
  })
}

export async function seedToken(page: Page, token = "tok-seeded") {
  await page.addInitScript((t) => localStorage.setItem("ctos-web.token", t), token)
}
```

- [ ] **Step 3: 寫失敗的 e2e**

`e2e/login.spec.ts`：

```ts
import { expect, test } from "@playwright/test"
import { mockApi, seedToken } from "./helpers"

test("未登入進首頁會導到登入頁", async ({ page }) => {
  await mockApi(page)
  await page.goto("/")
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole("tab", { name: "NAS 帳號" })).toBeVisible()
})

test("NAS 分頁登入成功，送 method=nas，落在首頁", async ({ page }) => {
  await mockApi(page)
  const req = page.waitForRequest((r) => r.url().endsWith("/api/auth/login"))
  await page.goto("/login")
  await page.getByLabel("NAS 帳號").fill("yazelin")
  await page.getByLabel("密碼").first().fill("pw")
  await page.getByRole("button", { name: "登入" }).first().click()
  expect((await req).postDataJSON().method).toBe("nas")
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText("亞澤")).toBeVisible()
})

test("平台帳號分頁送 method=local", async ({ page }) => {
  await mockApi(page)
  await page.goto("/login")
  await page.getByRole("tab", { name: "平台帳號" }).click()
  const req = page.waitForRequest((r) => r.url().endsWith("/api/auth/login"))
  await page.getByLabel("帳號", { exact: true }).fill("yazelin")
  await page.getByLabel("密碼").last().fill("pw")
  await page.getByRole("button", { name: "登入" }).last().click()
  expect((await req).postDataJSON().method).toBe("local")
  await expect(page).toHaveURL(/\/$/)
})

test("帳密錯誤顯示後端訊息", async ({ page }) => {
  await mockApi(page, { loginOk: false })
  await page.goto("/login")
  await page.getByLabel("NAS 帳號").fill("x")
  await page.getByLabel("密碼").first().fill("y")
  await page.getByRole("button", { name: "登入" }).first().click()
  await expect(page.getByRole("alert")).toContainText("帳號或密碼錯誤")
  await expect(page).toHaveURL(/\/login$/)
})

test("已有 token 進登入頁會導回首頁；token 失效導回登入頁", async ({ page }) => {
  await mockApi(page)
  await seedToken(page)
  await page.goto("/login")
  await expect(page).toHaveURL(/\/$/)

  await mockApi(page, { user: null })
  await page.goto("/")
  await expect(page).toHaveURL(/\/login$/)
})
```

- [ ] **Step 4: 跑 e2e 確認失敗**

Run: `npx playwright test e2e/login.spec.ts --project=desktop`
Expected: FAIL（沒有 /login 路由）。

- [ ] **Step 5: 實作**

`src/lib/auth-context.tsx`：

```tsx
/* eslint-disable react-refresh/only-export-components */
import * as React from "react"
import { fetchMe, logout } from "./auth"
import { getCachedUser, getToken, setCachedUser } from "./token"
import type { UserInfo } from "./types"

interface AuthState {
  user: UserInfo | null
  loading: boolean
  refresh: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = React.createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<UserInfo | null>(() => (getToken() ? getCachedUser() : null))
  const [loading, setLoading] = React.useState<boolean>(() => Boolean(getToken()))

  const refresh = React.useCallback(async () => {
    if (!getToken()) { setUser(null); setLoading(false); return }
    setLoading(true)
    try {
      const me = await fetchMe()
      setCachedUser(me)
      setUser(me)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const signOut = React.useCallback(async () => {
    await logout()
    setUser(null)
  }, [])

  React.useEffect(() => { void refresh() }, [refresh])

  return <AuthContext.Provider value={{ user, loading, refresh, signOut }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = React.useContext(AuthContext)
  if (!ctx) throw new Error("useAuth 必須在 AuthProvider 內使用")
  return ctx
}
```

`src/components/require-auth.tsx`：

```tsx
import { Navigate, Outlet } from "react-router"
import { useAuth } from "@/lib/auth-context"
import { getToken } from "@/lib/token"

export function RequireAuth() {
  const { user, loading } = useAuth()
  if (!getToken()) return <Navigate to="/login" replace />
  if (loading) return <div className="p-6 text-muted-foreground">載入中…</div>
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}
```

`src/pages/login.tsx`（重點；欄位 id 要獨一，兩個分頁各自一組）：

```tsx
import * as React from "react"
import { Navigate, useNavigate } from "react-router"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { login } from "@/lib/auth"
import { useAuth } from "@/lib/auth-context"
import { getToken } from "@/lib/token"
import type { LoginMethod } from "@/lib/types"

function LoginForm({ method }: { method: LoginMethod }) {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const userLabel = method === "nas" ? "NAS 帳號" : "帳號"

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const res = await login(username, password, method)
      if (!res.success) { setError(res.error ?? "登入失敗"); return }
      await refresh()
      navigate("/", { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "登入失敗")
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor={`${method}-username`}>{userLabel}</Label>
        <Input id={`${method}-username`} autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${method}-password`}>密碼</Label>
        <Input id={`${method}-password`} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </div>
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      <Button type="submit" className="w-full" disabled={busy}>{busy ? "登入中…" : "登入"}</Button>
    </form>
  )
}

export default function LoginPage() {
  if (getToken()) return <Navigate to="/" replace />
  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>ChingTech OS</CardTitle>
          <CardDescription>擎添工業內部系統</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="nas">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="nas">NAS 帳號</TabsTrigger>
              <TabsTrigger value="local">平台帳號</TabsTrigger>
            </TabsList>
            <TabsContent value="nas"><LoginForm method="nas" /></TabsContent>
            <TabsContent value="local"><LoginForm method="local" /></TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </main>
  )
}
```

（shadcn 的 `Alert` 若沒有自帶 `role="alert"`，在 `<Alert role="alert" …>` 明確加上。）

`src/pages/home.tsx`：

```tsx
import { useAuth } from "@/lib/auth-context"

export default function HomePage() {
  const { user } = useAuth()
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold">首頁</h1>
      <p className="text-muted-foreground">你好，{user?.display_name || user?.username}。管理層 dashboard 之後在這裡。</p>
    </div>
  )
}
```

`src/routes.tsx`（這個 task 的殼先最小化，Task 4 會換成 `AppShell`）：

```tsx
import { createBrowserRouter, Outlet } from "react-router"
import { RequireAuth } from "@/components/require-auth"
import HomePage from "@/pages/home"
import LoginPage from "@/pages/login"

function MinimalShell() {
  return <div className="p-6"><Outlet /></div>
}

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/", element: <MinimalShell />, children: [{ index: true, element: <HomePage /> }] },
    ],
  },
])
```

`src/main.tsx`：

```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router"
import { ThemeProvider } from "@/components/theme-provider"
import { AuthProvider } from "@/lib/auth-context"
import { router } from "@/routes"
import "./index.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="ctos-web.theme">
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
)
```

刪除 `src/App.tsx`。`package.json` scripts 加 `"e2e": "playwright test"`。

- [ ] **Step 6: 跑測試**

Run: `npx playwright install chromium`（第一次）然後 `npm run test && npx playwright test e2e/login.spec.ts && npm run build`
Expected: 兩個 project（desktop、mobile）都過。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(auth): 路由、AuthProvider 與 NAS／平台雙分頁登入頁

Co-Authored-By: <實際模型> <noreply@anthropic.com>"
```

---

### Task 4: App shell：側邊欄、header、模組空頁、主題與顏色

**Files:**
- Create: `src/lib/nav.ts`、`src/components/app-shell.tsx`、`src/components/app-sidebar.tsx`（改寫 sidebar-07 產出）、`src/components/nav-user.tsx`（改寫）、`src/pages/placeholder.tsx`、`e2e/shell.spec.ts`
- Modify: `src/routes.tsx`（換 AppShell、加子路由）、`src/index.css`（顏色與字體）
- Delete: sidebar-07 帶進來但不用的 `team-switcher.tsx`、`nav-projects.tsx`、`nav-main.tsx`

**Interfaces:**
- Consumes: `useAuth`。
- Produces:
  - `NAV_ITEMS: { title: string; path: string; icon: LucideIcon; adminOnly?: boolean }[]`，順序：首頁 `/`（Home）、知識庫 `/kb`（BookOpen）、專案 `/projects`（FolderKanban）、Bot 管理 `/bot`（Bot）、AI Log `/ai-log`（ScrollText）、使用者管理 `/admin/users`（Users，adminOnly）、設定 `/settings`（Settings）。
  - `AppShell`：`SidebarProvider` + `AppSidebar` + `SidebarInset`（header 含 `SidebarTrigger`、目前頁面標題）+ `<Outlet/>`。
  - `AppSidebar`：`SidebarHeader` 放「ChingTech OS」字樣；`SidebarContent` 依 `NAV_ITEMS` 產 `SidebarMenuButton`（`asChild` 包 `NavLink`，`isActive` 依路徑），`adminOnly` 項目在 `user.is_admin` 為 false 時**不渲染**；`SidebarFooter` 放 `NavUser`。
  - `NavUser`：顯示 display_name（無則 username）與 role，DropdownMenu 有「亮色／暗色／跟隨系統」三個切換與「登出」；登出後 `navigate("/login")`。
  - `PlaceholderPage({ title })`：標題 + 一句「這個模組還在建置中，先用舊桌面。」+ 連到 `https://ching-tech.ddns.net/ctos/` 的連結「開啟舊桌面」。

- [ ] **Step 1: 加區塊**

```bash
npx shadcn@latest add sidebar-07 dropdown-menu -y -o
```

會產生 `src/components/{app-sidebar,nav-main,nav-projects,nav-user,team-switcher}.tsx` 與 `ui/{sidebar,sheet,tooltip,separator,breadcrumb,avatar,collapsible,skeleton}.tsx`。刪掉 `nav-main.tsx`、`nav-projects.tsx`、`team-switcher.tsx`，`app-sidebar.tsx` 與 `nav-user.tsx` 依上面 Interfaces 重寫（可保留其結構與 className）。

- [ ] **Step 2: 寫失敗的 e2e**

`e2e/shell.spec.ts`：

```ts
import { expect, test } from "@playwright/test"
import { adminFixture, mockApi, seedToken } from "./helpers"

const MODULES = ["首頁", "知識庫", "專案", "Bot 管理", "AI Log", "設定"]

test("側邊欄列出模組，一般使用者看不到使用者管理", async ({ page }) => {
  await mockApi(page)
  await seedToken(page)
  await page.goto("/")
  const nav = page.getByRole("navigation").first()
  for (const m of MODULES) await expect(nav.getByRole("link", { name: m })).toBeVisible()
  await expect(nav.getByRole("link", { name: "使用者管理" })).toHaveCount(0)
})

test("admin 看得到使用者管理，點模組會切換右欄", async ({ page }) => {
  await mockApi(page, { user: adminFixture })
  await seedToken(page)
  await page.goto("/")
  const nav = page.getByRole("navigation").first()
  await expect(nav.getByRole("link", { name: "使用者管理" })).toBeVisible()
  await nav.getByRole("link", { name: "知識庫" }).click()
  await expect(page).toHaveURL(/\/kb$/)
  await expect(page.getByRole("heading", { name: "知識庫" })).toBeVisible()
  await expect(page.getByRole("link", { name: "開啟舊桌面" })).toHaveAttribute("href", "https://ching-tech.ddns.net/ctos/")
})

test("登出回到登入頁並清掉 token", async ({ page }) => {
  await mockApi(page)
  await seedToken(page)
  await page.goto("/")
  await page.getByRole("button", { name: /亞澤/ }).click()
  await page.getByRole("menuitem", { name: "登出" }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(await page.evaluate(() => localStorage.getItem("ctos-web.token"))).toBeNull()
})

test("頁面不可橫向捲動", async ({ page }) => {
  await mockApi(page)
  await seedToken(page)
  await page.goto("/settings")
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(overflow).toBe(false)
})
```

（mobile project 下側邊欄預設收在抽屜裡，`getByRole("navigation")` 抓不到時先按 `SidebarTrigger`：在測試開頭加 `if (test.info().project.name === "mobile") await page.getByRole("button", { name: /Toggle Sidebar/i }).click()`。以 shadcn 產生的 `sr-only` 文字為準，抓不到就改用 `data-sidebar="trigger"` 選擇器。）

- [ ] **Step 3: 跑 e2e 確認失敗**

Run: `npx playwright test e2e/shell.spec.ts --project=desktop`
Expected: FAIL（沒有側邊欄）。

- [ ] **Step 4: 實作**

`src/lib/nav.ts`：

```ts
import { BookOpen, Bot, FolderKanban, Home, ScrollText, Settings, Users, type LucideIcon } from "lucide-react"

export interface NavItem { title: string; path: string; icon: LucideIcon; adminOnly?: boolean }

export const NAV_ITEMS: NavItem[] = [
  { title: "首頁", path: "/", icon: Home },
  { title: "知識庫", path: "/kb", icon: BookOpen },
  { title: "專案", path: "/projects", icon: FolderKanban },
  { title: "Bot 管理", path: "/bot", icon: Bot },
  { title: "AI Log", path: "/ai-log", icon: ScrollText },
  { title: "使用者管理", path: "/admin/users", icon: Users, adminOnly: true },
  { title: "設定", path: "/settings", icon: Settings },
]

export function titleForPath(pathname: string): string {
  return NAV_ITEMS.find((i) => (i.path === "/" ? pathname === "/" : pathname.startsWith(i.path)))?.title ?? "ChingTech OS"
}
```

`src/components/app-sidebar.tsx`：

```tsx
import { NavLink } from "react-router"
import { NavUser } from "@/components/nav-user"
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarRail } from "@/components/ui/sidebar"
import { useAuth } from "@/lib/auth-context"
import { NAV_ITEMS } from "@/lib/nav"

export function AppSidebar() {
  const { user } = useAuth()
  const items = NAV_ITEMS.filter((i) => !i.adminOnly || user?.is_admin)
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-3 py-2 text-base font-semibold group-data-[collapsible=icon]:hidden">ChingTech OS</SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {items.map((item) => (
              <SidebarMenuItem key={item.path}>
                <NavLink to={item.path} end={item.path === "/"}>
                  {({ isActive }) => (
                    <SidebarMenuButton asChild={false} isActive={isActive} tooltip={item.title}>
                      <item.icon />
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                  )}
                </NavLink>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter><NavUser /></SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
```

（`NavLink` 包在外層讓 `getByRole("link", { name })` 抓得到；`SidebarMenuButton` 內用 icon+span。若 shadcn 版本的 `SidebarMenuButton` 需要 `asChild` 才能當 link，改成 `<SidebarMenuButton asChild isActive={…}><NavLink …><Icon/><span/></NavLink></SidebarMenuButton>`，兩種都符合測試。）

`src/components/nav-user.tsx`：

```tsx
import { ChevronsUpDown, LogOut, Monitor, Moon, Sun } from "lucide-react"
import { useNavigate } from "react-router"
import { useTheme } from "@/components/theme-provider"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from "@/components/ui/sidebar"
import { useAuth } from "@/lib/auth-context"

export function NavUser() {
  const { user, signOut } = useAuth()
  const { setTheme } = useTheme()
  const { isMobile } = useSidebar()
  const navigate = useNavigate()
  const name = user?.display_name || user?.username || ""

  async function onLogout() {
    await signOut()
    navigate("/login", { replace: true })
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg">
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{name}</span>
                <span className="truncate text-xs text-muted-foreground">{user?.role === "admin" ? "管理員" : "使用者"}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side={isMobile ? "bottom" : "right"} align="end" className="min-w-48">
            <DropdownMenuLabel>主題</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => setTheme("light")}><Sun />亮色</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("dark")}><Moon />暗色</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("system")}><Monitor />跟隨系統</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onLogout}><LogOut />登出</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
```

（`useTheme` 的名稱以 scaffold 產生的 `theme-provider.tsx` 為準，若它匯出的是別的名字就用那個。）

`src/components/app-shell.tsx`：

```tsx
import { Outlet, useLocation } from "react-router"
import { AppSidebar } from "@/components/app-sidebar"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { titleForPath } from "@/lib/nav"

export function AppShell() {
  const { pathname } = useLocation()
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <span className="text-sm font-medium">{titleForPath(pathname)}</span>
        </header>
        <div className="flex-1 overflow-x-hidden p-4 md:p-6"><Outlet /></div>
      </SidebarInset>
    </SidebarProvider>
  )
}
```

`src/pages/placeholder.tsx`：

```tsx
export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-muted-foreground">這個模組還在建置中，先用舊桌面。</p>
      <a className="text-primary underline underline-offset-4" href="https://ching-tech.ddns.net/ctos/" target="_blank" rel="noreferrer">開啟舊桌面</a>
    </div>
  )
}
```

`src/routes.tsx` 改成：

```tsx
import { createBrowserRouter } from "react-router"
import { AppShell } from "@/components/app-shell"
import { RequireAuth } from "@/components/require-auth"
import HomePage from "@/pages/home"
import LoginPage from "@/pages/login"
import PlaceholderPage from "@/pages/placeholder"

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        path: "/",
        element: <AppShell />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "kb", element: <PlaceholderPage title="知識庫" /> },
          { path: "projects", element: <PlaceholderPage title="專案" /> },
          { path: "bot", element: <PlaceholderPage title="Bot 管理" /> },
          { path: "ai-log", element: <PlaceholderPage title="AI Log" /> },
          { path: "admin/users", element: <PlaceholderPage title="使用者管理" /> },
          { path: "settings", element: <PlaceholderPage title="設定" /> },
        ],
      },
    ],
  },
])
```

`src/index.css`：在 `:root` 與 `.dark` 區塊覆寫（shadcn nova preset 用 oklch，直接改成 hex 也合法）：

```css
:root {
  --primary: #0891b2;
  --primary-foreground: #ffffff;
  --accent: #ea580c;
  --accent-foreground: #ffffff;
  --background: #f5f5f5;
  --ring: #0891b2;
  --sidebar-primary: #0891b2;
  --sidebar-primary-foreground: #ffffff;
}
.dark {
  --primary: #0ea5c9;
  --primary-foreground: #0b1416;
  --accent: #ea580c;
  --accent-foreground: #ffffff;
  --background: #1a1a1a;
  --ring: #0ea5c9;
  --sidebar-primary: #0ea5c9;
  --sidebar-primary-foreground: #0b1416;
}
```

`@theme inline` 裡的 `--font-sans` 改成 `'Geist Variable', 'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', system-ui, sans-serif`。若 `--accent` 在 preset 中是「hover 底色」語意而不是品牌強調色（shadcn 慣例是前者），就**不要覆寫 `--accent`**，改成新增 `--brand-accent: #ea580c` 並在 `@theme inline` 加 `--color-brand-accent: var(--brand-accent)`；報告裡寫清楚採哪個。

- [ ] **Step 5: 跑測試**

Run: `npx playwright test && npm run test && npm run build`
Expected: 全過（含 mobile project）。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(shell): 側邊欄、header、模組空頁與 CTOS 主題色

Co-Authored-By: <實際模型> <noreply@anthropic.com>"
```

---

### Task 5: 設定頁：帳號資訊與 NAS 綁定

**Files:**
- Create: `src/pages/settings.tsx`、`e2e/settings.spec.ts`
- Modify: `src/routes.tsx`（`settings` 換 `SettingsPage`）、`e2e/helpers.ts`（加綁定端點 mock）

**Interfaces:**
- Consumes: `useAuth`（`user`、`refresh`）、`bindNas`、`unbindNas`、`ApiError`。
- Produces: `/settings` 頁：
  - 「帳號」卡：帳號、顯示名稱、角色（管理員／使用者）、登入方式（`has_password` 為 true 顯示「已設定平台密碼」否則「尚未設定平台密碼」）。
  - 「NAS 帳號綁定」卡：`nas_username` 有值 → 顯示「已綁定：<name>」與「解除綁定」按鈕（按下呼叫 `unbindNas` 後 `refresh()`）；無值 → 表單「NAS 帳號」「NAS 密碼」與「綁定」按鈕（呼叫 `bindNas`，成功 `refresh()`；`ApiError` 顯示其 `detail` 於 `role="alert"`）。

- [ ] **Step 1: helper 加 mock**

`e2e/helpers.ts` 的 `mockApi` 內加（放在 `/api/user/me` 之前，避免被前綴匹配吃掉；`page.route` 是後註冊先匹配，所以把 nas-binding 註冊在 me 之後也可以——以實測為準）：

```ts
  await page.route(`${API}/api/user/me/nas-binding`, async (route) => {
    const method = route.request().method()
    if (method === "DELETE") { if (user) user.nas_username = null; return route.fulfill({ json: { success: true, nas_username: null } }) }
    const body = route.request().postDataJSON() as { nas_username: string; password: string }
    if (body.password === "wrong") return route.fulfill({ status: 401, json: { detail: "NAS 帳號或密碼錯誤" } })
    if (body.nas_username === "taken") return route.fulfill({ status: 409, json: { detail: "此 NAS 帳號已綁定其他使用者" } })
    if (user) user.nas_username = body.nas_username
    return route.fulfill({ json: { success: true, nas_username: body.nas_username } })
  })
```

`mockApi` 的 `user` 要是每次呼叫新建的物件（`{ ...userFixture }`），避免測試間互相污染。

- [ ] **Step 2: 寫失敗的 e2e**

`e2e/settings.spec.ts`：

```ts
import { expect, test } from "@playwright/test"
import { mockApi, seedToken, userFixture } from "./helpers"

test("已綁定顯示 NAS 帳號，可解除綁定", async ({ page }) => {
  await mockApi(page)
  await seedToken(page)
  await page.goto("/settings")
  await expect(page.getByText("已綁定：yazelin")).toBeVisible()
  await page.getByRole("button", { name: "解除綁定" }).click()
  await expect(page.getByLabel("NAS 帳號")).toBeVisible()
})

test("未綁定可綁定；錯誤訊息來自後端", async ({ page }) => {
  await mockApi(page, { user: { ...userFixture, nas_username: null } })
  await seedToken(page)
  await page.goto("/settings")
  await page.getByLabel("NAS 帳號").fill("yazelin")
  await page.getByLabel("NAS 密碼").fill("wrong")
  await page.getByRole("button", { name: "綁定" }).click()
  await expect(page.getByRole("alert")).toContainText("NAS 帳號或密碼錯誤")

  await page.getByLabel("NAS 密碼").fill("ok")
  await page.getByRole("button", { name: "綁定" }).click()
  await expect(page.getByText("已綁定：yazelin")).toBeVisible()
})

test("帳號卡顯示角色與密碼狀態", async ({ page }) => {
  await mockApi(page)
  await seedToken(page)
  await page.goto("/settings")
  await expect(page.getByText("使用者", { exact: true })).toBeVisible()
  await expect(page.getByText("已設定平台密碼")).toBeVisible()
})
```

- [ ] **Step 3: 跑 e2e 確認失敗**

Run: `npx playwright test e2e/settings.spec.ts --project=desktop`
Expected: FAIL。

- [ ] **Step 4: 實作 `src/pages/settings.tsx`**

```tsx
import * as React from "react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError } from "@/lib/api"
import { bindNas, unbindNas } from "@/lib/auth"
import { useAuth } from "@/lib/auth-context"

function NasBindingCard() {
  const { user, refresh } = useAuth()
  const [nasUser, setNasUser] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setError(null)
    try { await fn(); await refresh(); setPassword("") }
    catch (e) { setError(e instanceof ApiError ? e.detail : "操作失敗，請稍後再試") }
    finally { setBusy(false) }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>NAS 帳號綁定</CardTitle>
        <CardDescription>綁定後可用 NAS 帳號登入，檔案功能也會用這個帳號連線。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {user?.nas_username ? (
          <div className="flex items-center justify-between gap-4">
            <span>已綁定：{user.nas_username}</span>
            <Button variant="outline" disabled={busy} onClick={() => run(unbindNas)}>解除綁定</Button>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void run(() => bindNas(nasUser, password)) }}>
            <div className="space-y-2">
              <Label htmlFor="nas-username">NAS 帳號</Label>
              <Input id="nas-username" value={nasUser} onChange={(e) => setNasUser(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="nas-password">NAS 密碼</Label>
              <Input id="nas-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <Button type="submit" disabled={busy}>綁定</Button>
          </form>
        )}
        {error && <Alert variant="destructive" role="alert"><AlertDescription>{error}</AlertDescription></Alert>}
      </CardContent>
    </Card>
  )
}

export default function SettingsPage() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <div className="grid max-w-3xl gap-6">
      <h1 className="text-2xl font-semibold">設定</h1>
      <Card>
        <CardHeader><CardTitle>帳號</CardTitle></CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
          <div className="text-muted-foreground">帳號</div><div>{user.username}</div>
          <div className="text-muted-foreground">顯示名稱</div><div>{user.display_name || "（未設定）"}</div>
          <div className="text-muted-foreground">角色</div><div>{user.role === "admin" ? "管理員" : "使用者"}</div>
          <div className="text-muted-foreground">平台密碼</div><div>{user.has_password ? "已設定平台密碼" : "尚未設定平台密碼"}</div>
        </CardContent>
      </Card>
      <NasBindingCard />
    </div>
  )
}
```

`src/routes.tsx` 的 `settings` 改用 `SettingsPage`。

- [ ] **Step 5: 跑測試**

Run: `npx playwright test && npm run test && npm run build`
Expected: 全過。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(settings): 帳號資訊與 NAS 帳號綁定／解綁

Co-Authored-By: <實際模型> <noreply@anthropic.com>"
```

---

### Task 6: README、PR、部署後真機驗證

**Files:**
- Modify: `README.md`（ctos-web）

- [ ] **Step 1: README**

內容（正體中文）：專案是什麼（ChingTech OS 新前端，後端在 ching-tech-os）、線上網址 https://os.ching-tech.com、技術棧、本機開發（`npm i`、`.env` 設 `VITE_API_BASE`、`npm run dev`；本機後端要在 `CORS_EXTRA_ORIGINS` 放 `http://localhost:5173`，正式機已放）、測試（`npm run test`、`npm run e2e`）、部署（push main 自動；自訂網域與 CNAME）、目錄結構（照上面檔案地圖）、登入方式（NAS／平台）與 token 存放位置、目前完成的模組與尚未完成的模組清單、對應 spec 與計劃的路徑（ching-tech-os repo）。

- [ ] **Step 2: Commit、推 branch、開 PR、auto-merge**

```bash
git add README.md && git commit -m "docs: README——開發、測試、部署與模組現況

Co-Authored-By: <實際模型> <noreply@anthropic.com>"
git push -u origin feat/skeleton
gh pr create --title "feat: 前端骨架——登入、側邊欄、模組空頁、設定與 NAS 綁定" --body "<內容：做了什麼、驗證清單（vitest、playwright desktop+mobile、build）、對應計劃路徑>" 
gh repo edit ching-tech/ctos-web --enable-auto-merge
gh pr merge --auto --merge
```

- [ ] **Step 3: 合併後驗正式站**（由控制端做）

```bash
gh run watch --repo ching-tech/ctos-web --exit-status <run id>
curl -s -o /dev/null -w "%{http_code}\n" https://os.ching-tech.com/login
curl -s -o /dev/null -w "%{http_code}\n" https://os.ching-tech.com/settings   # 404.html fallback 要回 200
```

然後用 Playwright 打**真站**（不 mock）：開 https://os.ching-tech.com/login，NAS 分頁輸入假帳密，按登入，預期 alert 顯示「帳號或密碼錯誤」——這一步證明 CORS 與 API 接線在正式環境真的通。指令：

```bash
cd /home/ct/SDD/ctos-web && cat > /tmp/prod-smoke.spec.ts <<'EOS'
import { expect, test } from "@playwright/test"
test("正式站登入頁打到真後端", async ({ page }) => {
  await page.goto("https://os.ching-tech.com/login")
  await page.getByLabel("NAS 帳號").fill("nobody-zzz")
  await page.getByLabel("密碼").first().fill("x")
  await page.getByRole("button", { name: "登入" }).first().click()
  await expect(page.getByRole("alert")).toContainText("帳號或密碼錯誤")
})
EOS
npx playwright test --config=/dev/null /tmp/prod-smoke.spec.ts   # 或複製進 e2e/ 暫跑後刪除
```

## 明確不做（本計劃）

- 知識庫、專案、Bot、AI Log、使用者管理的實際內容（各自一段）。
- 首頁 dashboard 內容。
- 修改密碼、LINE 綁定（LINE 綁定碼流程沿用舊桌面，之後再搬）。
- i18n、ESLint 規則調整、Storybook。
