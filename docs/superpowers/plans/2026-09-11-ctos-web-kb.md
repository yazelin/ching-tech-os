# ctos-web 知識庫模組實作計劃（第 3 段）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ctos-web 做出可日常使用的知識庫：清單與搜尋、閱讀（Markdown、附件）、新增與編輯、刪除、分享連結、版本歷史，並在首頁放「最近更新」。全部沿用既有後端 `/api/knowledge` 與 `/api/share`，後端零改動。

**Architecture:** 路由 `/kb`（清單）、`/kb/new`（新增）、`/kb/:id`（閱讀）、`/kb/:id/edit`（編輯）。資料層用 TanStack Query（列表、單筆、tags、歷史各一個 query key；mutation 後 invalidate）。Markdown 用 react-markdown 加 remark-gfm 渲染（不開 raw HTML，天然防 XSS），內容裡的相對圖片路徑改寫成帶 token 的 API 網址。附件與圖片是跨網域的 `<img>`／`<a>`，無法帶 header，走後端支援的 `?token=` 查詢參數。

**Tech Stack:** 既有骨架（Vite 8、React 19、TS strict、Tailwind 4、shadcn/ui、react-router 7）加 `@tanstack/react-query`、`react-markdown`、`remark-gfm`。測試沿用 Vitest 與 Playwright（API 用 `page.route` 攔）。

**Spec:** `docs/superpowers/specs/2026-09-10-ctos-web-react-frontend-design.md` 第三節「知識庫」。前置：第 2 段骨架已合併（ching-tech/ctos-web main，https://os.ching-tech.com）。

## Global Constraints

- 後端不改。API 契約（正式機已驗）：
  - `GET /api/knowledge` 查詢參數 `q`、`project`、`type`、`category`、`role`、`level`、`topics`（可重複）、`scope`（`global`／`personal`／`project`）；回 `{ items: KnowledgeListItem[], total, query }`，無分頁。
  - `GET /api/knowledge/tags` → `{ projects, types, categories, roles, levels, topics }`（皆 `string[]`）。
  - `GET /api/knowledge/{id}` → `KnowledgeResponse`（含 `content` Markdown）。
  - `POST /api/knowledge` body `KnowledgeCreate`；`PUT /api/knowledge/{id}` body `KnowledgeUpdate`（只送有改的欄位）；`DELETE /api/knowledge/{id}`。權限由後端判（403 帶 `detail`），前端顯示訊息即可。
  - `GET /api/knowledge/{id}/history` → `{ id, entries: { commit, author, date, message }[] }`；`GET /api/knowledge/{id}/version/{commit}` → `{ id, commit, content }`。
  - `POST /api/knowledge/{id}/attachments` multipart 欄位 `file`；`DELETE /api/knowledge/{id}/attachments/{idx}`；`PATCH …/{idx}` body `{ type?, description? }`。
  - 附件路徑轉網址：`nas://knowledge/attachments/kb-001/f.bin` → `{API_BASE}/api/knowledge/attachments/kb-001/f.bin`；`local://knowledge/assets/images/x.png` 或 `../assets/images/x.png` → `{API_BASE}/api/knowledge/assets/images/x.png`。這兩個端點接受 `?token=<session token>`。
  - `POST /api/share` body `{ resource_type: "knowledge", resource_id, expires_in: "1h"|"24h"|"7d"|null, password?: string }` → `{ token, url, full_url, resource_type, resource_id, resource_title }`。
- id 形如 `kb-001`。`KnowledgeCreate.author` 送目前使用者的 `username`。
- `apiFetch` 遇到 `FormData` body 不得自動加 `Content-Type`（瀏覽器要自己帶 boundary）。
- UI 文字正體中文、全形標點、不用 emoji。scope 顯示：`global`→「全域」、`personal`→「個人」、`project`→「專案」；type：`context`→「脈絡」、`knowledge`→「知識」、`operations`→「作業」、`reference`→「參考」；category：`technical`→「技術」、`business`→「業務」、`management`→「管理」。
- 手機寬度可用：清單一欄；閱讀頁 metadata 收到內容下方；編輯器單欄。
- 每個 task 一個 commit，branch `feat/kb`，最後一個 PR 設 auto-merge（CI 會在 PR 上跑）。Commit 訊息正體中文，trailer 附實際執行模型。
- 新增依賴只准 `@tanstack/react-query`、`react-markdown`、`remark-gfm`。

## 檔案地圖（新增／修改）

```
src/
├── main.tsx                      # 加 QueryClientProvider
├── routes.tsx                    # kb 四條路由
├── lib/
│   ├── api.ts                    # FormData 不加 Content-Type
│   ├── kb.ts                     # 型別、query 函式、mutation 函式、網址工具、標籤字典
│   └── kb.test.ts
├── pages/kb/
│   ├── list.tsx                  # /kb
│   ├── detail.tsx                # /kb/:id
│   ├── editor.tsx                # /kb/new 與 /kb/:id/edit 共用
│   └── home-recent.tsx           # 首頁「最近更新」卡（Task 6 掛進 home.tsx）
├── components/kb/
│   ├── markdown.tsx              # react-markdown 包裝＋圖片網址改寫
│   ├── attachments.tsx           # 附件清單／上傳／刪除
│   ├── share-dialog.tsx          # 分享連結
│   └── history-sheet.tsx         # 版本歷史
e2e/
├── helpers.ts                    # 加 mockKb(page, fixtures)
├── kb-list.spec.ts, kb-detail.spec.ts, kb-editor.spec.ts, kb-share-history.spec.ts
```

---

### Task 1: 依賴、QueryClient、`kb.ts` 資料層（Vitest）

**Files:**
- Modify: `package.json`（三個依賴）、`src/main.tsx`、`src/lib/api.ts`
- Create: `src/lib/kb.ts`、`src/lib/kb.test.ts`
- Test: `src/lib/api.test.ts`（加一個 FormData 案例）

**Interfaces:**
- Produces（`src/lib/kb.ts`）：
  ```ts
  export type Scope = "global" | "personal" | "project"
  export interface KnowledgeTags { projects: string[]; roles: string[]; topics: string[]; level: string | null }
  export interface KnowledgeAttachment { type: string; path: string; size: string | null; description: string | null }
  export interface KnowledgeListItem { id: string; title: string; type: string; category: string; scope: Scope; owner: string | null; project_id: string | null; is_public: boolean; tags: KnowledgeTags; author: string; updated_at: string; snippet: string | null }
  export interface KnowledgeListResponse { items: KnowledgeListItem[]; total: number; query: string | null }
  export interface Knowledge extends Omit<KnowledgeListItem, "snippet"> { source: { project: string | null; path: string | null; commit: string | null }; related: string[]; attachments: KnowledgeAttachment[]; created_at: string; content: string }
  export interface TagsResponse { projects: string[]; types: string[]; categories: string[]; roles: string[]; levels: string[]; topics: string[] }
  export interface KnowledgeCreate { title: string; content: string; type: string; category: string; scope: Scope; author: string; tags?: Partial<KnowledgeTags>; is_public?: boolean }
  export type KnowledgeUpdate = Partial<Pick<KnowledgeCreate, "title" | "content" | "type" | "category" | "scope" | "is_public">> & { tags?: Partial<KnowledgeTags> }
  export interface HistoryEntry { commit: string; author: string; date: string; message: string }
  export interface ShareLink { token: string; url: string; full_url: string; resource_type: string; resource_id: string; resource_title: string }
  export interface ListFilters { q?: string; scope?: Scope | ""; type?: string; category?: string; project?: string }

  export const SCOPE_LABEL: Record<Scope, string>          // 全域／個人／專案
  export const TYPE_LABEL: Record<string, string>           // 脈絡／知識／作業／參考
  export const CATEGORY_LABEL: Record<string, string>       // 技術／業務／管理
  export function label(dict: Record<string, string>, key: string): string   // 找不到就回 key

  export function listKnowledge(filters: ListFilters): Promise<KnowledgeListResponse>   // 只把有值的參數放進 query string
  export function getKnowledge(id: string): Promise<Knowledge>
  export function getTags(): Promise<TagsResponse>
  export function createKnowledge(data: KnowledgeCreate): Promise<Knowledge>
  export function updateKnowledge(id: string, data: KnowledgeUpdate): Promise<Knowledge>
  export function deleteKnowledge(id: string): Promise<void>
  export function getHistory(id: string): Promise<{ id: string; entries: HistoryEntry[] }>
  export function getVersion(id: string, commit: string): Promise<{ id: string; commit: string; content: string }>
  export function uploadAttachment(id: string, file: File): Promise<unknown>          // FormData 欄位 file
  export function deleteAttachment(id: string, idx: number): Promise<void>
  export function createShareLink(id: string, opts: { expires_in: "1h" | "24h" | "7d" | null; password?: string }): Promise<ShareLink>

  export function attachmentUrl(path: string): string   // 轉成 API 網址並附 ?token=（無 token 就不附）
  export function rewriteImageSrc(src: string): string  // Markdown 圖片：相對 ../assets/images/x 或 local://… → attachmentUrl；http(s) 開頭原樣
  export const kbKeys = { all: ["kb"] as const, list: (f: ListFilters) => ["kb", "list", f] as const, detail: (id: string) => ["kb", "detail", id] as const, tags: ["kb", "tags"] as const, history: (id: string) => ["kb", "history", id] as const }
  ```
- `src/lib/api.ts`：`Content-Type: application/json` 只在 `typeof body === "string"` 時補。
- `src/main.tsx`：`QueryClientProvider`（`new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } })`）包在 `AuthProvider` 外層。

- [ ] **Step 1: 開 branch、裝依賴**

```bash
cd /home/ct/SDD/ctos-web && git checkout main && git pull && git checkout -b feat/kb
npm i @tanstack/react-query react-markdown remark-gfm
```

- [ ] **Step 2: 寫失敗的測試**

`src/lib/api.test.ts` 加：

```ts
  it("does not set JSON content-type for FormData bodies", async () => {
    const fn = mockFetch(200, { ok: 1 })
    const fd = new FormData()
    fd.append("file", new Blob(["x"]), "a.txt")
    await apiFetch("/upload", { method: "POST", body: fd })
    const [, init] = fn.mock.calls[0] as unknown as [string, RequestInit]
    expect(new Headers(init.headers).get("Content-Type")).toBeNull()
  })
```

`src/lib/kb.test.ts`：

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { API_BASE } from "./api"
import { attachmentUrl, label, listKnowledge, rewriteImageSrc, SCOPE_LABEL } from "./kb"
import { setToken } from "./token"

beforeEach(() => {
  const store = new Map<string, string>()
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
})
afterEach(() => vi.unstubAllGlobals())

describe("attachmentUrl", () => {
  it("maps nas:// and local:// and relative paths, appending token", () => {
    setToken("T")
    expect(attachmentUrl("nas://knowledge/attachments/kb-001/f.bin")).toBe(`${API_BASE}/api/knowledge/attachments/kb-001/f.bin?token=T`)
    expect(attachmentUrl("local://knowledge/assets/images/kb-001-x.png")).toBe(`${API_BASE}/api/knowledge/assets/images/kb-001-x.png?token=T`)
    expect(attachmentUrl("../assets/images/kb-001-x.png")).toBe(`${API_BASE}/api/knowledge/assets/images/kb-001-x.png?token=T`)
  })
  it("omits token when not logged in", () => {
    expect(attachmentUrl("nas://knowledge/attachments/a/b")).toBe(`${API_BASE}/api/knowledge/attachments/a/b`)
  })
})

describe("rewriteImageSrc", () => {
  it("leaves absolute urls alone and rewrites relative ones", () => {
    setToken("T")
    expect(rewriteImageSrc("https://example.com/a.png")).toBe("https://example.com/a.png")
    expect(rewriteImageSrc("../assets/images/kb-002-b.png")).toBe(`${API_BASE}/api/knowledge/assets/images/kb-002-b.png?token=T`)
  })
})

describe("listKnowledge", () => {
  it("sends only non-empty filters", async () => {
    const fn = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0, query: null }), { status: 200 }))
    vi.stubGlobal("fetch", fn)
    await listKnowledge({ q: "泵", scope: "", type: "knowledge" })
    const url = (fn.mock.calls[0] as unknown as [string])[0]
    expect(url).toBe(`${API_BASE}/api/knowledge?q=%E6%B3%B5&type=knowledge`)
  })
})

it("label falls back to key", () => {
  expect(label(SCOPE_LABEL, "global")).toBe("全域")
  expect(label(SCOPE_LABEL, "weird")).toBe("weird")
})
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `npm run test`
Expected: `kb.test.ts` 找不到模組；api 的 FormData 案例失敗（Content-Type 是 application/json）。

- [ ] **Step 4: 實作**

`src/lib/api.ts` 改成：

```ts
  if (!headers.has("Content-Type") && typeof rest.body === "string") headers.set("Content-Type", "application/json")
```

`src/lib/kb.ts` 依 Interfaces 實作。重點片段：

```ts
import { API_BASE, apiFetch } from "./api"
import { getToken } from "./token"

export const SCOPE_LABEL = { global: "全域", personal: "個人", project: "專案" } as const satisfies Record<Scope, string>
export const TYPE_LABEL: Record<string, string> = { context: "脈絡", knowledge: "知識", operations: "作業", reference: "參考" }
export const CATEGORY_LABEL: Record<string, string> = { technical: "技術", business: "業務", management: "管理" }
export function label(dict: Record<string, string>, key: string): string { return dict[key] ?? key }

export function listKnowledge(filters: ListFilters): Promise<KnowledgeListResponse> {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v)
  const qs = params.toString()
  return apiFetch<KnowledgeListResponse>(`/api/knowledge${qs ? `?${qs}` : ""}`)
}

export function uploadAttachment(id: string, file: File) {
  const fd = new FormData()
  fd.append("file", file)
  return apiFetch<unknown>(`/api/knowledge/${id}/attachments`, { method: "POST", body: fd })
}

export function createShareLink(id: string, opts: { expires_in: "1h" | "24h" | "7d" | null; password?: string }) {
  return apiFetch<ShareLink>("/api/share", { method: "POST", body: JSON.stringify({ resource_type: "knowledge", resource_id: id, expires_in: opts.expires_in, password: opts.password || undefined }) })
}

function withToken(url: string): string {
  const t = getToken()
  return t ? `${url}?token=${encodeURIComponent(t)}` : url
}

export function attachmentUrl(path: string): string {
  if (path.startsWith("nas://knowledge/")) return withToken(`${API_BASE}/api/knowledge/${path.slice("nas://knowledge/".length)}`)
  const file = path.split("/").pop() ?? path
  return withToken(`${API_BASE}/api/knowledge/assets/images/${file}`)
}

export function rewriteImageSrc(src: string): string {
  if (/^(https?:)?\/\//.test(src) || src.startsWith("data:")) return src
  return attachmentUrl(src)
}
```

`src/main.tsx`：

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } })
// …
<ThemeProvider …>
  <QueryClientProvider client={queryClient}>
    <AuthProvider>…</AuthProvider>
  </QueryClientProvider>
</ThemeProvider>
```

- [ ] **Step 5: 跑測試與建置**

Run: `npm run test && npm run build`
Expected: 全過。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(kb): 知識庫資料層——型別、查詢與 mutation 函式、附件網址工具；FormData 不加 JSON 標頭

Co-Authored-By: <實際模型> <noreply@anthropic.com>"
```

---

### Task 2: 清單頁 `/kb`（搜尋、篩選、新增按鈕）

**Files:**
- Create: `src/pages/kb/list.tsx`、`e2e/kb-list.spec.ts`
- Modify: `src/routes.tsx`（`kb` 換 `KbListPage`；`kb/new`、`kb/:id`、`kb/:id/edit` 先指到 `PlaceholderPage`，後續 task 換）、`e2e/helpers.ts`（加 `mockKb`）
- shadcn: `npx shadcn@latest add select badge skeleton -y -o`（`badge`、`skeleton` 若已存在會略過）

**Interfaces:**
- Consumes: `listKnowledge`、`getTags`、`kbKeys`、`SCOPE_LABEL`／`TYPE_LABEL`／`CATEGORY_LABEL`、`label`。
- Produces:
  - `KbListPage`：頂部一列：搜尋框（`placeholder="搜尋標題與內容"`，`aria-label="搜尋"`，輸入後 300ms debounce 或按 Enter）、scope 下拉（全部／全域／個人／專案）、type 下拉（全部＋`tags.types`）、category 下拉（全部＋`tags.categories`）、右側「新增知識」按鈕（連到 `/kb/new`）。
  - 篩選狀態同步到 URL query（`?q=&scope=&type=&category=`），重新整理保留。
  - 清單：每筆是連到 `/kb/{id}` 的卡片（`role="link"` 由 `<Link>` 提供），顯示標題、`Badge` 三個（scope、type、category 的中文）、作者、更新日期、搜尋時顯示 `snippet`。
  - 狀態：載入中顯示 3 個 `Skeleton`；空清單顯示「沒有符合的知識」；錯誤顯示 `role="alert"` 帶 `ApiError.detail`。
  - 標題列顯示總數：「共 N 筆」。
- `mockKb(page, { items?, tags? })`（`e2e/helpers.ts`）：攔 `GET {API}/api/knowledge/tags`、`GET {API}/api/knowledge?*`（依 query 過濾 fixture：`q` 比對 title 包含、`scope`／`type`／`category` 相等；有 `q` 時 `snippet` 填「…含 q 的片段…」）、`GET {API}/api/knowledge/{id}`（找不到 404 `{detail:"找不到"}`）。fixture 至少三筆：`kb-001`（global／knowledge／technical，標題「泵浦保養 SOP」）、`kb-002`（personal／reference／business，標題「客戶報價流程」）、`kb-003`（project／operations／management，標題「案場巡檢清單」）。每筆含 `content`（Markdown，含一個 `# 標題` 與一張 `![圖](../assets/images/kb-001-a.png)`）與 `attachments`（kb-001 有一個 `nas://knowledge/attachments/kb-001/manual.pdf`）。

- [ ] **Step 1: helper 與 fixture**

在 `e2e/helpers.ts` 加 `kbFixtures`（三筆，含 `content`、`attachments`、`tags`、日期字串 `"2026-09-01"`）與 `mockKb` 如上；`mockKb` 內部維護一份可變的 `items` 陣列副本供後續 task 的 mutation mock 使用，並回傳 `{ items }` 讓測試能斷言。

- [ ] **Step 2: 寫失敗的 e2e**

`e2e/kb-list.spec.ts`：

```ts
import { expect, test } from "@playwright/test"
import { mockApi, mockKb, seedToken } from "./helpers"

test.beforeEach(async ({ page }) => { await mockApi(page); await mockKb(page); await seedToken(page) })

test("清單列出全部並顯示中文標籤與總數", async ({ page }) => {
  await page.goto("/kb")
  await expect(page.getByText("共 3 筆")).toBeVisible()
  const first = page.getByRole("link", { name: /泵浦保養 SOP/ })
  await expect(first).toBeVisible()
  await expect(first).toContainText("全域")
  await expect(first).toContainText("知識")
  await expect(first).toContainText("技術")
})

test("搜尋送 q、顯示 snippet、寫進網址", async ({ page }) => {
  await page.goto("/kb")
  const req = page.waitForRequest((r) => r.url().includes("/api/knowledge?") && r.url().includes("q="))
  await page.getByLabel("搜尋").fill("報價")
  await page.getByLabel("搜尋").press("Enter")
  expect(new URL((await req).url()).searchParams.get("q")).toBe("報價")
  await expect(page.getByText("共 1 筆")).toBeVisible()
  await expect(page.getByText(/含 報價 的片段/)).toBeVisible()
  await expect(page).toHaveURL(/q=%E5%A0%B1%E5%83%B9|q=報價/)
})

test("scope 篩選送參數，重新整理保留", async ({ page }) => {
  await page.goto("/kb?scope=personal")
  await expect(page.getByText("共 1 筆")).toBeVisible()
  await expect(page.getByRole("link", { name: /客戶報價流程/ })).toBeVisible()
  await page.reload()
  await expect(page.getByText("共 1 筆")).toBeVisible()
})

test("空結果與新增按鈕", async ({ page }) => {
  await page.goto("/kb?q=zzz-none")
  await expect(page.getByText("沒有符合的知識")).toBeVisible()
  await page.getByRole("link", { name: "新增知識" }).click()
  await expect(page).toHaveURL(/\/kb\/new$/)
})
```

- [ ] **Step 3: 跑 e2e 確認失敗**

Run: `npx playwright test e2e/kb-list.spec.ts --project=desktop`
Expected: FAIL（/kb 還是佔位頁）。

- [ ] **Step 4: 實作 `src/pages/kb/list.tsx`**

用 `useSearchParams` 讀寫篩選；`useQuery({ queryKey: kbKeys.list(filters), queryFn: () => listKnowledge(filters) })`；`useQuery({ queryKey: kbKeys.tags, queryFn: getTags })`。下拉用 shadcn `Select`（value `""` 代表全部時改用 `"all"` 佔位再轉回空字串，Radix Select 不接受空字串 value）。卡片：

```tsx
<Link to={`/kb/${item.id}`} className="block rounded-lg border p-4 hover:bg-accent">
  <div className="flex flex-wrap items-center gap-2">
    <span className="font-medium">{item.title}</span>
    <Badge variant="secondary">{label(SCOPE_LABEL, item.scope)}</Badge>
    <Badge variant="outline">{label(TYPE_LABEL, item.type)}</Badge>
    <Badge variant="outline">{label(CATEGORY_LABEL, item.category)}</Badge>
  </div>
  <div className="mt-1 text-sm text-muted-foreground">{item.author}・{item.updated_at}</div>
  {item.snippet && <p className="mt-2 text-sm">{item.snippet}</p>}
</Link>
```

`routes.tsx`：`{ path: "kb", element: <KbListPage /> }, { path: "kb/new", element: <PlaceholderPage title="新增知識" /> }, { path: "kb/:id", element: <PlaceholderPage title="知識" /> }, { path: "kb/:id/edit", element: <PlaceholderPage title="編輯知識" /> }`。`titleForPath` 對 `/kb/...` 仍回「知識庫」，不用改。

- [ ] **Step 5: 跑全部測試**

Run: `npx playwright test && npm run test && npm run build`
Expected: 全過（含 mobile）。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(kb): 清單頁——搜尋、scope／type／category 篩選、URL 同步、新增入口

Co-Authored-By: <實際模型> <noreply@anthropic.com>"
```

---

### Task 3: 閱讀頁 `/kb/:id`（Markdown、metadata、附件、刪除）

**Files:**
- Create: `src/components/kb/markdown.tsx`、`src/components/kb/attachments.tsx`、`src/pages/kb/detail.tsx`、`e2e/kb-detail.spec.ts`
- Modify: `src/routes.tsx`（`kb/:id` 換 `KbDetailPage`）、`e2e/helpers.ts`（`mockKb` 加 `DELETE /api/knowledge/{id}`、`POST /api/knowledge/{id}/attachments`、`DELETE …/attachments/{idx}`、`GET {API}/api/knowledge/attachments/**` 與 `assets/**` 回一個 1×1 PNG）
- shadcn: `npx shadcn@latest add alert-dialog -y -o`

**Interfaces:**
- `Markdown({ content })`：`react-markdown` + `remark-gfm`，`components={{ img: ({src, alt}) => <img src={rewriteImageSrc(src ?? "")} alt={alt ?? ""} className="max-w-full rounded" /> , a: 外部連結加 target=_blank rel=noreferrer }}`，外層 `className="prose prose-neutral dark:prose-invert max-w-none"`（若沒裝 typography plugin，改成自訂幾條標題／段落／程式碼樣式，不加新依賴）。
- `Attachments({ id, attachments, canEdit })`：清單每筆顯示檔名（path 最後一段）、`type`、`size`、`description`，「下載」連結 `href={attachmentUrl(path)}` `target="_blank"`；圖片類（`type === "image"` 或副檔名 png/jpg/jpeg/gif/webp）顯示縮圖。上傳：`<input type="file" aria-label="上傳附件">` 選檔後即 `uploadAttachment` → invalidate detail；刪除：按「刪除附件」→ `AlertDialog` 確認 → `deleteAttachment(id, idx)` → invalidate。
- `KbDetailPage`：`useQuery(kbKeys.detail(id))`。版面：標題 + 三個 Badge；動作列：「編輯」（連 `/kb/{id}/edit`）、「分享」「版本歷史」（Task 5 接上，本 task 先放按鈕但 disabled）、「刪除」（AlertDialog 確認「確定刪除這篇知識？」→ `deleteKnowledge` → invalidate list → navigate `/kb`）。內容區 `Markdown`；右側（桌機）／下方（手機）metadata 卡：作者、建立、更新、scope、owner、專案、標籤（projects／roles／topics／level 各一行，空的不顯示）、相關知識（`related` 每個是連到 `/kb/{rid}` 的連結）。404 顯示「找不到這篇知識」與回清單連結。403／其他錯誤 `role="alert"`。

- [ ] **Step 1: helper 補 mock**（如上；DELETE 知識要把 fixture 從 `items` 移除；上傳成功把 `{type:"file", path:"nas://knowledge/attachments/<id>/<filename>", size:"1 KB", description:null}` 推進該筆 `attachments`；刪附件用 idx 移除）

- [ ] **Step 2: 寫失敗的 e2e**

`e2e/kb-detail.spec.ts`：

```ts
import { expect, test } from "@playwright/test"
import { mockApi, mockKb, seedToken } from "./helpers"

test.beforeEach(async ({ page }) => { await mockApi(page); await mockKb(page); await seedToken(page, "TK") })

test("渲染 Markdown、圖片帶 token、metadata 與附件", async ({ page }) => {
  await page.goto("/kb/kb-001")
  await expect(page.getByRole("heading", { level: 1, name: "泵浦保養 SOP" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "保養步驟" })).toBeVisible()   // fixture content 的 # 標題
  const img = page.locator("article img").first()
  await expect(img).toHaveAttribute("src", /\/api\/knowledge\/assets\/images\/kb-001-a\.png\?token=TK$/)
  await expect(page.getByText("全域")).toBeVisible()
  const dl = page.getByRole("link", { name: /manual\.pdf/ })
  await expect(dl).toHaveAttribute("href", /\/api\/knowledge\/attachments\/kb-001\/manual\.pdf\?token=TK$/)
})

test("上傳附件後清單出現新檔；刪除附件要確認", async ({ page }) => {
  await page.goto("/kb/kb-002")
  await page.getByLabel("上傳附件").setInputFiles({ name: "note.txt", mimeType: "text/plain", buffer: Buffer.from("hi") })
  await expect(page.getByRole("link", { name: /note\.txt/ })).toBeVisible()
  await page.getByRole("button", { name: "刪除附件" }).first().click()
  await page.getByRole("button", { name: "確定" }).click()
  await expect(page.getByRole("link", { name: /note\.txt/ })).toHaveCount(0)
})

test("刪除知識要確認，成功後回清單", async ({ page }) => {
  await page.goto("/kb/kb-003")
  await page.getByRole("button", { name: "刪除" , exact: true }).click()
  await page.getByRole("button", { name: "確定" }).click()
  await expect(page).toHaveURL(/\/kb$/)
  await expect(page.getByText("共 2 筆")).toBeVisible()
})

test("找不到顯示提示", async ({ page }) => {
  await page.goto("/kb/kb-999")
  await expect(page.getByText("找不到這篇知識")).toBeVisible()
})
```

- [ ] **Step 3: 跑 e2e 確認失敗** — `npx playwright test e2e/kb-detail.spec.ts --project=desktop`

- [ ] **Step 4: 實作**（依 Interfaces；`AlertDialog` 的確認按鈕文字「確定」、取消「取消」；內容區用 `<article>` 包）

- [ ] **Step 5: 跑全部** — `npx playwright test && npm run test && npm run build`

- [ ] **Step 6: Commit** — `feat(kb): 閱讀頁——Markdown 渲染、附件上傳下載刪除、metadata、刪除知識`

---

### Task 4: 編輯器 `/kb/new` 與 `/kb/:id/edit`

**Files:**
- Create: `src/pages/kb/editor.tsx`、`e2e/kb-editor.spec.ts`
- Modify: `src/routes.tsx`、`e2e/helpers.ts`（`mockKb` 加 `POST /api/knowledge`（回 201 新筆，id `kb-00N` 遞增，推進 items）、`PUT /api/knowledge/{id}`（合併欄位））
- shadcn: `npx shadcn@latest add textarea -y -o`

**Interfaces:**
- `KbEditorPage`：以 `useParams().id` 判斷新增或編輯。欄位：標題（必填）、scope（Select：全域／個人／專案，新增預設「個人」）、type（Select，預設「知識」）、category（Select，預設「技術」）、is_public（Checkbox「允許未綁定的 Bot 使用者查詢」）、內容（`Textarea` Markdown，`aria-label="內容"`，至少 16 列）、右側／下方「預覽」切換（`Markdown` 元件）。按鈕：「儲存」「取消」（回上一頁或 `/kb`）。
- 新增：`createKnowledge({ …, author: user.username })` → invalidate list → navigate `/kb/{newId}`。
- 編輯：載入 `getKnowledge(id)` 填表；儲存只送有變動的欄位（`KnowledgeUpdate`）→ invalidate detail 與 list → navigate `/kb/{id}`。
- 錯誤 `role="alert"`。儲存中按鈕 disabled 顯示「儲存中…」。

- [ ] **Step 1–2: helper 與失敗的 e2e**

`e2e/kb-editor.spec.ts`：

```ts
import { expect, test } from "@playwright/test"
import { mockApi, mockKb, seedToken } from "./helpers"

test.beforeEach(async ({ page }) => { await mockApi(page); await mockKb(page); await seedToken(page) })

test("新增：送出正確 body，成功後到新頁", async ({ page }) => {
  await page.goto("/kb/new")
  const req = page.waitForRequest((r) => r.method() === "POST" && r.url().endsWith("/api/knowledge"))
  await page.getByLabel("標題").fill("新的 SOP")
  await page.getByLabel("內容").fill("# 第一步\n\n內容")
  await page.getByRole("button", { name: "儲存" }).click()
  const body = (await req).postDataJSON()
  expect(body).toMatchObject({ title: "新的 SOP", scope: "personal", type: "knowledge", category: "technical", author: "yazelin" })
  await expect(page).toHaveURL(/\/kb\/kb-004$/)
  await expect(page.getByRole("heading", { level: 1, name: "新的 SOP" })).toBeVisible()
})

test("編輯：只送有改的欄位", async ({ page }) => {
  await page.goto("/kb/kb-001/edit")
  await expect(page.getByLabel("標題")).toHaveValue("泵浦保養 SOP")
  const req = page.waitForRequest((r) => r.method() === "PUT" && r.url().endsWith("/api/knowledge/kb-001"))
  await page.getByLabel("標題").fill("泵浦保養 SOP v2")
  await page.getByRole("button", { name: "儲存" }).click()
  expect((await req).postDataJSON()).toEqual({ title: "泵浦保養 SOP v2" })
  await expect(page).toHaveURL(/\/kb\/kb-001$/)
})

test("預覽切換會渲染 Markdown；標題空白不送出", async ({ page }) => {
  await page.goto("/kb/new")
  await page.getByLabel("內容").fill("## 預覽標題")
  await page.getByRole("button", { name: "預覽" }).click()
  await expect(page.getByRole("heading", { name: "預覽標題" })).toBeVisible()
  await page.getByRole("button", { name: "儲存" }).click()
  await expect(page).toHaveURL(/\/kb\/new$/)
})
```

- [ ] **Step 3–5: 失敗確認、實作、全部測試**

- [ ] **Step 6: Commit** — `feat(kb): 編輯器——新增與編輯共用、預覽、只送變動欄位`

---

### Task 5: 分享連結與版本歷史

**Files:**
- Create: `src/components/kb/share-dialog.tsx`、`src/components/kb/history-sheet.tsx`、`e2e/kb-share-history.spec.ts`
- Modify: `src/pages/kb/detail.tsx`（接上兩個按鈕）、`e2e/helpers.ts`（`mockKb` 加 `POST /api/share` 回 `{ token:"s1", url:"/public/s1", full_url:"https://ching-tech.ddns.net/ctos/public.html?token=s1", resource_type:"knowledge", resource_id, resource_title }`；`GET …/history` 回兩筆 entries；`GET …/version/{commit}` 回 `content: "# 舊版 "+commit`）
- shadcn: `npx shadcn@latest add dialog sheet radio-group -y -o`

**Interfaces:**
- `ShareDialog({ id, open, onOpenChange })`：`RadioGroup` 有效期（1 小時／24 小時／7 天／永久，預設 24 小時）、`Input` 密碼（選填，4 位數字，`aria-label="密碼（選填）"`）、「建立連結」→ `createShareLink` → 顯示 `full_url`（`<input readonly aria-label="分享連結">`）與「複製」按鈕（`navigator.clipboard.writeText`，成功顯示「已複製」）。
- `HistorySheet({ id, open, onOpenChange })`：`Sheet` 右側；`useQuery(kbKeys.history(id))` 列出 entries（date、author、message、commit 前 7 碼）；點一筆 → `getVersion` → 在 sheet 內用 `Markdown` 顯示該版內容，上方有「回到清單」。

- [ ] **Step 1–2: helper 與失敗的 e2e**

```ts
import { expect, test } from "@playwright/test"
import { mockApi, mockKb, seedToken } from "./helpers"

test.beforeEach(async ({ page }) => { await mockApi(page); await mockKb(page); await seedToken(page) })

test("分享：送 expires_in 與密碼，顯示連結可複製", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"])
  await page.goto("/kb/kb-001")
  await page.getByRole("button", { name: "分享" }).click()
  await page.getByRole("radio", { name: "7 天" }).check()
  await page.getByLabel("密碼（選填）").fill("1234")
  const req = page.waitForRequest((r) => r.url().endsWith("/api/share"))
  await page.getByRole("button", { name: "建立連結" }).click()
  expect((await req).postDataJSON()).toMatchObject({ resource_type: "knowledge", resource_id: "kb-001", expires_in: "7d", password: "1234" })
  await expect(page.getByLabel("分享連結")).toHaveValue(/public\.html\?token=s1/)
  await page.getByRole("button", { name: "複製" }).click()
  await expect(page.getByText("已複製")).toBeVisible()
})

test("版本歷史：列出版本並可看舊版內容", async ({ page }) => {
  await page.goto("/kb/kb-001")
  await page.getByRole("button", { name: "版本歷史" }).click()
  await expect(page.getByText("第一版")).toBeVisible()       // fixture entries[1].message
  await page.getByRole("button", { name: /第一版/ }).click()
  await expect(page.getByRole("heading", { name: /舊版/ })).toBeVisible()
})
```

- [ ] **Step 3–5: 失敗確認、實作、全部測試**（mobile 的 clipboard 權限若不可用，該測試 `test.skip(({ browserName, isMobile }) => isMobile)`）

- [ ] **Step 6: Commit** — `feat(kb): 分享連結對話框與版本歷史`

---

### Task 6: 首頁最近更新、README、PR、真站冒煙

**Files:**
- Create: `src/pages/kb/home-recent.tsx`
- Modify: `src/pages/home.tsx`（掛 `HomeRecentKb`）、`README.md`（模組現況：知識庫 完成；新依賴；e2e 檔案）、`e2e/shell.spec.ts`（首頁多一個「最近更新」區塊的斷言）

**Interfaces:**
- `HomeRecentKb`：`useQuery(kbKeys.list({}))` 取全部後依 `updated_at` 降冪取前 5，卡片標題「知識庫最近更新」，每筆連到 `/kb/{id}`，右上「查看全部」連 `/kb`。

- [ ] **Step 1: 實作與 e2e**（`shell.spec.ts` 加：`await mockKb(page)` 後進 `/`，`getByRole("heading", { name: "知識庫最近更新" })` 可見，且有 `link` 名含「泵浦保養 SOP」）

- [ ] **Step 2: README**：模組現況把知識庫移到「已完成」；技術棧加三個依賴；測試段加四個 kb spec。

- [ ] **Step 3: 全部測試、commit、推 branch、開 PR、auto-merge**

```bash
npm run test && npx playwright test && npm run build
git add -A && git commit -m "feat(home): 首頁知識庫最近更新；README 模組現況" -m "Co-Authored-By: <實際模型> <noreply@anthropic.com>"
git push -u origin feat/kb
gh pr create --title "feat(kb): 知識庫模組——清單搜尋、閱讀附件、編輯、分享、版本歷史" --body "<做了什麼、驗證清單、計劃路徑>"
gh pr merge --auto --merge
```

- [ ] **Step 4: 合併部署後真站冒煙**（控制端）：未登入開 `https://os.ching-tech.com/kb` 導到 `/login`；用 yazelin 的 token 無法取得，所以清單真資料的驗證留給 yazelin 登入後看。

## 明確不做（本計劃）

- 標籤（projects／roles／topics／level）的編輯 UI：先沿用既有值顯示，編輯器不提供修改（後端 `KnowledgeUpdate.tags` 之後再接）。
- `related` 的編輯、附件 `PATCH`（type／description 修改）、`rebuild-index`。
- project scope 綁定專案（`project_id` 選擇）：專案模組那段再做。
- 首頁其他 dashboard 區塊。
