# ctos-web AI Log 模組實作計劃（第 4 段之一）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ctos-web 做出 AI Log：用量統計卡、依 Agent／情境／成功與否／日期篩選的分頁清單、單筆明細頁。唯讀，後端零改動。Bot 管理另開計劃。

**Architecture:** 路由 `/ai-log`（統計＋清單）與 `/ai-log/:id`（明細）。資料層 `src/lib/ai-log.ts`（TanStack Query）。篩選與分頁同步到 URL query。統計卡與清單共用同一組篩選（`start_date`／`end_date`／`agent_id`）。

**Tech Stack:** 既有骨架與依賴（不加新依賴）。shadcn `table` 元件。

**Spec:** `docs/superpowers/specs/2026-09-10-ctos-web-react-frontend-design.md` 第三節「AI Log」。前置：第 2、3 段已合併（ching-tech/ctos-web main）。

## Global Constraints

- 後端不改。API 契約（正式機 `/api/ai`）：
  - `GET /api/ai/logs?agent_id=<uuid>&context_type=<str>&success=<true|false>&start_date=<ISO datetime>&end_date=<ISO datetime>&page=<n≥1>&page_size=<1..100>` → `{ items: AiLogListItem[], total, page, page_size }`。
  - `AiLogListItem`：`{ id, agent_id, agent_name, context_type, model, script_label, allowed_tools, used_tools, success, duration_ms, input_tokens, output_tokens, created_at }`（uuid 與 datetime 都是字串）。
  - `GET /api/ai/logs/stats?agent_id&start_date&end_date` → `{ total_calls, success_count, failure_count, success_rate, avg_duration_ms, total_input_tokens, total_output_tokens }`。
  - `GET /api/ai/logs/{id}` → `AiLogResponse`：list item 欄位加 `prompt_id, context_id, input_prompt, system_prompt, raw_response, parsed_response (object|null), error_message`。
  - `GET /api/ai/agents` → `{ items: { id, name, display_name, model, is_active, tools, updated_at }[], total }`。
  - 權限：`ai-log` app 預設所有登入者可看；403 就顯示 `detail`。
- 日期篩選：UI 用 `<input type="date">`，送出時 `start_date` 轉 `YYYY-MM-DDT00:00:00`、`end_date` 轉 `YYYY-MM-DDT23:59:59`。
- 情境（context_type）中文：`web-chat`→「Web 對話」、`linebot-group`→「Line 群組」、`linebot-personal`→「Line 個人」、`telegram-group`→「Telegram 群組」、`telegram-personal`→「Telegram 個人」、`scheduler`→「排程」、`presentation`→「簡報」、`compress`→「壓縮」、`script`→「腳本」、`test`→「測試」；其他原樣顯示。
- 篩選與分頁狀態放 URL query：`agent`、`context`、`success`（`true`／`false`）、`from`、`to`、`page`。`page_size` 固定 50。
- UI 正體中文、全形標點、不用 emoji；手機寬度表格放在 `overflow-x-auto` 容器內，頁面本身不橫向捲。
- 每 task 一個 commit，branch `feat/ai-log`，最後 PR 設 auto-merge。commit trailer 附實際執行模型。
- e2e 一律用 `page.route` 攔 `/api/ai/*`；任何會落到首頁或側邊欄的測試要同時掛 `mockApi`＋`mockKb`（首頁會打 `/api/knowledge`）。

## 檔案地圖

```
src/lib/ai-log.ts, ai-log.test.ts       # 型別、query 函式、CONTEXT_LABEL、buildLogQuery、toDayStart/toDayEnd、aiLogKeys
src/pages/ai-log/list.tsx               # /ai-log：統計卡 + 篩選 + 表格 + 分頁
src/pages/ai-log/detail.tsx             # /ai-log/:id
src/routes.tsx                          # 兩條路由
e2e/helpers.ts                          # mockAiLog(page, { logs?, agents? })
e2e/ai-log.spec.ts
README.md                               # 模組現況
```

---

### Task 1: 資料層 `src/lib/ai-log.ts`（Vitest）

**Files:** Create `src/lib/ai-log.ts`、`src/lib/ai-log.test.ts`

**Interfaces（Produces）:**

```ts
export interface AiLogListItem { id: string; agent_id: string | null; agent_name: string | null; context_type: string | null; model: string | null; script_label: string | null; allowed_tools: string[] | null; used_tools: string[] | null; success: boolean; duration_ms: number | null; input_tokens: number | null; output_tokens: number | null; created_at: string }
export interface AiLogListResponse { items: AiLogListItem[]; total: number; page: number; page_size: number }
export interface AiLogStats { total_calls: number; success_count: number; failure_count: number; success_rate: number; avg_duration_ms: number | null; total_input_tokens: number; total_output_tokens: number }
export interface AiLog extends AiLogListItem { prompt_id: string | null; context_id: string | null; input_prompt: string; system_prompt: string | null; raw_response: string | null; parsed_response: Record<string, unknown> | null; error_message: string | null }
export interface AiAgentListItem { id: string; name: string; display_name: string | null; model: string; is_active: boolean; tools: string[] | null; updated_at: string }
export interface LogFilters { agent?: string; context?: string; success?: "true" | "false" | ""; from?: string; to?: string; page?: number }

export const CONTEXT_LABEL: Record<string, string>
export function contextLabel(t: string | null): string          // null → "—"
export function toDayStart(d: string): string                    // "2026-09-01" → "2026-09-01T00:00:00"
export function toDayEnd(d: string): string                      // → "2026-09-01T23:59:59"
export function buildLogQuery(f: LogFilters, pageSize = 50): string   // 回 "?a=b&…"，空值略過；page 預設 1
export function listLogs(f: LogFilters): Promise<AiLogListResponse>
export function getLogStats(f: Pick<LogFilters, "agent" | "from" | "to">): Promise<AiLogStats>
export function getLog(id: string): Promise<AiLog>
export function listAgents(): Promise<{ items: AiAgentListItem[]; total: number }>
export const aiLogKeys = { all: ["ai-log"] as const, list: (f: LogFilters) => ["ai-log", "list", f] as const, stats: (f: Pick<LogFilters,"agent"|"from"|"to">) => ["ai-log", "stats", f] as const, detail: (id: string) => ["ai-log", "detail", id] as const, agents: ["ai-log", "agents"] as const }
```

- [ ] **Step 1: branch**

```bash
cd /home/ct/SDD/ctos-web && git checkout main && git pull && git checkout -b feat/ai-log
```

- [ ] **Step 2: 寫失敗的測試** `src/lib/ai-log.test.ts`

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { API_BASE } from "./api"
import { buildLogQuery, contextLabel, getLogStats, listLogs, toDayEnd, toDayStart } from "./ai-log"

beforeEach(() => {
  const store = new Map<string, string>()
  vi.stubGlobal("localStorage", { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k) })
})
afterEach(() => vi.unstubAllGlobals())

describe("buildLogQuery", () => {
  it("maps ui filters to api params and skips empties", () => {
    expect(buildLogQuery({ agent: "a1", context: "linebot-group", success: "false", from: "2026-09-01", to: "2026-09-10", page: 2 }))
      .toBe("?agent_id=a1&context_type=linebot-group&success=false&start_date=2026-09-01T00%3A00%3A00&end_date=2026-09-10T23%3A59%3A59&page=2&page_size=50")
    expect(buildLogQuery({})).toBe("?page=1&page_size=50")
    expect(buildLogQuery({ success: "" })).toBe("?page=1&page_size=50")
  })
})

it("day boundaries", () => {
  expect(toDayStart("2026-09-01")).toBe("2026-09-01T00:00:00")
  expect(toDayEnd("2026-09-01")).toBe("2026-09-01T23:59:59")
})

it("context labels", () => {
  expect(contextLabel("linebot-group")).toBe("Line 群組")
  expect(contextLabel("weird")).toBe("weird")
  expect(contextLabel(null)).toBe("—")
})

it("listLogs and getLogStats hit the right urls", async () => {
  const fn = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 50 }), { status: 200 }))
  vi.stubGlobal("fetch", fn)
  await listLogs({ context: "test" })
  expect((fn.mock.calls[0] as unknown as [string])[0]).toBe(`${API_BASE}/api/ai/logs?context_type=test&page=1&page_size=50`)
  await getLogStats({ agent: "a1" })
  expect((fn.mock.calls[1] as unknown as [string])[0]).toBe(`${API_BASE}/api/ai/logs/stats?agent_id=a1`)
})
```

- [ ] **Step 3: 跑 `npm run test` 確認失敗**，**Step 4: 實作**（`getLogStats` 只帶 `agent_id`／`start_date`／`end_date`，不帶 page），**Step 5: `npm run test && npm run build`**，**Step 6: Commit** `feat(ai-log): 資料層——型別、查詢函式、篩選轉換與 query key`

---

### Task 2: `/ai-log` 清單頁（統計卡、篩選、表格、分頁）＋ e2e

**Files:** Create `src/pages/ai-log/list.tsx`、`e2e/ai-log.spec.ts`；Modify `src/routes.tsx`（`ai-log` 換 `AiLogListPage`；`ai-log/:id` 先佔位）、`e2e/helpers.ts`（`mockAiLog`）；shadcn `npx shadcn@latest add table -y -o`

**Interfaces:**
- `mockAiLog(page, { logs?, agents? })`：fixture 12 筆 logs（id `log-01`…`log-12`，時間遞減，agent 兩個 `ag-1`「群組助理」／`ag-2`「個人助理」，context 混 `linebot-group`／`web-chat`／`scheduler`，`success` 有 3 筆 false，`duration_ms`、tokens 有值），agents 兩筆。攔：`GET /api/ai/agents`；`GET /api/ai/logs/stats?*`（依 agent／日期算：total、success、failure、rate＝success/total、avg duration、token 加總）；`GET /api/ai/logs?*`（依 agent／context／success／日期過濾、依 `page`／`page_size` 切片；用 pathname 精準比對，避免吃到 `/logs/stats` 與 `/logs/{id}`）；`GET /api/ai/logs/{id}`（回完整欄位，`input_prompt` 「請幫我查泵浦保養週期」、`raw_response` 「每三個月」、`system_prompt` 「你是擎添的助理」、`parsed_response` `{ answer: "每三個月" }`；找不到 404）。
- `AiLogListPage`：
  - 篩選列：Agent `Select`（全部＋agents 的 `display_name || name`，value 為 id）、情境 `Select`（全部＋`CONTEXT_LABEL` 的鍵）、結果 `Select`（全部／成功／失敗）、起日 `<input type="date" aria-label="起日">`、迄日 `aria-label="迄日"`、「清除篩選」按鈕。改變即寫 URL 並把 `page` 重設為 1。
  - 統計卡四張：「呼叫次數」`total_calls`、「成功率」`Math.round(success_rate*100)%`（附 `success_count/failure_count`）、「平均耗時」`avg_duration_ms` 取整數加「ms」（null 顯示「—」）、「Token」`total_input_tokens` 進／`total_output_tokens` 出。
  - 表格（`Table`）欄：時間（`created_at` 以 `toLocaleString("zh-TW")` 顯示）、Agent（`agent_name || "—"`）、情境（`contextLabel`）、模型、結果（`Badge`「成功」／「失敗」）、耗時、Token（`in/out`）、工具（`used_tools?.length ?? 0`）。每列是連到 `/ai-log/{id}` 的連結（第一欄用 `Link`，整列 `cursor-pointer` 並 `onClick` 導頁）。
  - 分頁：「共 N 筆」、「上一頁」「下一頁」按鈕（邊界 disabled）、「第 p／P 頁」。
  - 載入 Skeleton、錯誤 `role="alert"`、空「沒有符合的紀錄」。

- [ ] **Step 1–2: helper 與失敗的 e2e** `e2e/ai-log.spec.ts`：

```ts
import { expect, test } from "@playwright/test"
import { mockAiLog, mockApi, mockKb, seedToken } from "./helpers"

test.beforeEach(async ({ page }) => { await mockApi(page); await mockKb(page); await mockAiLog(page); await seedToken(page) })

test("統計卡與表格", async ({ page }) => {
  await page.goto("/ai-log")
  await expect(page.getByText("呼叫次數")).toBeVisible()
  await expect(page.getByText("12", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("75%")).toBeVisible()            // 9 成功 / 12
  await expect(page.getByRole("link", { name: /泵浦|log-01|群組助理/ }).first()).toBeVisible()
  await expect(page.getByText("共 12 筆")).toBeVisible()
})

test("篩選送對參數並重設頁碼", async ({ page }) => {
  await page.goto("/ai-log?page=2")
  const req = page.waitForRequest((r) => r.url().includes("/api/ai/logs?") && r.url().includes("success=false"))
  await page.getByLabel("結果").click()
  await page.getByRole("option", { name: "失敗" }).click()
  const u = new URL((await req).url())
  expect(u.searchParams.get("page")).toBe("1")
  await expect(page.getByText("共 3 筆")).toBeVisible()
  await expect(page).toHaveURL(/success=false/)
})

test("日期與 agent 篩選會帶到統計", async ({ page }) => {
  await page.goto("/ai-log")
  const req = page.waitForRequest((r) => r.url().includes("/api/ai/logs/stats?") && r.url().includes("start_date="))
  await page.getByLabel("起日").fill("2026-09-05")
  const u = new URL((await req).url())
  expect(u.searchParams.get("start_date")).toBe("2026-09-05T00:00:00")
})

test("分頁", async ({ page }) => {
  // fixture 12 筆，mock 的 page_size 由前端固定 50，改用 page_size 查詢參數 5 的情境：mock 尊重 page_size
  await page.goto("/ai-log")
  await expect(page.getByRole("button", { name: "上一頁" })).toBeDisabled()
  await expect(page.getByRole("button", { name: "下一頁" })).toBeDisabled()   // 12 < 50
})
```

（分頁按鈕的啟用情境用 `mockAiLog(page, { logs: 60 筆自動產生 })` 另寫一個 test：進 `/ai-log` 後「下一頁」可按，按下 URL 變 `page=2`，表格換內容。）

- [ ] **Step 3–5: 失敗確認、實作、全部測試**（`npx playwright test && npm run test && npm run build`）
- [ ] **Step 6: Commit** `feat(ai-log): 清單頁——統計卡、篩選、表格與分頁`

---

### Task 3: `/ai-log/:id` 明細頁、README、PR

**Files:** Create `src/pages/ai-log/detail.tsx`；Modify `src/routes.tsx`、`e2e/ai-log.spec.ts`（加兩個 test）、`README.md`

**Interfaces:**
- `AiLogDetailPage`：`useQuery(aiLogKeys.detail(id))`。上方摘要：時間、Agent、情境、模型、結果 Badge、耗時、Token、`context_id`、`script_label`。區塊：「輸入」（`input_prompt`，`<pre class="whitespace-pre-wrap">`）、「系統提示」（可收合，預設收起，`system_prompt`）、「原始回應」（`raw_response`）、「解析結果」（`parsed_response` 以 `JSON.stringify(…, null, 2)`）、「錯誤」（`error_message`，只在失敗時顯示，紅字）、「允許的工具」與「使用的工具」（Badge 列）。「回清單」連結（保留來時的 query：用 `useLocation().state?.from` 或直接 `/ai-log`）。404 「找不到這筆紀錄」。
- e2e 加：
  ```ts
  test("明細頁顯示輸入、回應與解析結果", async ({ page }) => {
    await page.goto("/ai-log/log-01")
    await expect(page.getByText("請幫我查泵浦保養週期")).toBeVisible()
    await expect(page.getByText("每三個月").first()).toBeVisible()
    await page.getByRole("button", { name: "系統提示" }).click()
    await expect(page.getByText("你是擎添的助理")).toBeVisible()
  })
  test("失敗紀錄顯示錯誤訊息", async ({ page }) => {
    await page.goto("/ai-log/log-03")   // fixture 中 success=false 且 error_message 「模型逾時」
    await expect(page.getByText("模型逾時")).toBeVisible()
  })
  ```

- [ ] **Step 1–3: 實作、e2e、全部測試**
- [ ] **Step 4: README**：模組現況 AI Log → 已完成（統計、篩選、分頁、明細）；e2e 檔案清單加 `ai-log`；目錄結構加 `src/pages/ai-log/*`、`src/lib/ai-log.ts`。跑 `speak-tw README.md`。
- [ ] **Step 5: Commit** `feat(ai-log): 明細頁；README 模組現況`；**推 branch、開 PR、auto-merge**（控制端）。

## 明確不做

- AI 管理（Agent／Prompt 編輯）、Bot 管理：另開計劃。
- 匯出 CSV、圖表（dashboard 段再說）。
