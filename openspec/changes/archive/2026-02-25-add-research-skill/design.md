## Context

目前外部研究任務主要透過 Claude 內建 WebSearch / WebFetch 同步執行。當回合中前段工具已成功、末段外部擷取卡住時，整體仍會被 session timeout 視為失敗，造成：
- 使用者端沒有拿到完整最終回覆或回覆過晚；
- 已完成的中間成果缺乏可查進度與可恢復流程；
- 群組與個人情境都可能受影響（群組更容易遇到長任務與 reply token 時效壓力）。

本變更需要跨多模組實作（skills、bot tool routing、Line Bot 回覆流程），並沿用現有 script-first 與 `run_skill_script` 能力，導入與 media-downloader / media-transcription 一致的 start/check 非同步互動模式。

## Goals / Non-Goals

**Goals:**
- 建立 `research-skill`，提供「搜尋 + 擷取 + 統整」的一體化能力。
- 以 `start_research`/`check_research` 兩段式流程，讓長任務先快速受理，再由使用者查詢進度與最終結果。
- 讓研究任務可持久化中間狀態（progress、partial results、sources），降低單次同步回合失敗影響。
- 在 bot 路由層讓外部研究任務優先走 skill script，必要時仍可 fallback。
- 群組/個人使用一致流程，並維持可讀、可引用來源的輸出格式。

**Non-Goals:**
- 不在本次變更中全面移除所有 Claude 內建工具。
- 不實作通用爬蟲平台或任意網站的完整渲染擷取（先聚焦可用性與穩定性）。
- 不在首版導入完整分散式佇列系統（如 Celery/RQ）。

## Decisions

### 1) 採用 script-first 的 `research-skill`（start/check）
- **Decision**：新增 `backend/src/ching_tech_os/skills/research-skill/`，至少包含 `start-research.py`、`check-research.py` 與對應 SKILL.md 說明。
- **Why**：可沿用現有 `run_skill_script`、權限控管與 fallback 機制，並以最小改動導入非同步流程。
- **Alternatives considered**：
  - 直接繼續依賴同步 WebSearch/WebFetch：仍受單回合 timeout 影響，不可查進度。
  - 新增獨立 MCP server：彈性高但導入成本與維運面較大，首版不採用。

### 2) 任務狀態採檔案型持久化，格式對齊既有 media skills
- **Decision**：以 `status.json` 儲存 job 狀態，採 atomic write；job 目錄使用 `日期/job_id` 層級，並限制 `job_id` 格式與搜尋範圍。
- **Why**：與既有 start/check skills 一致，無需新增 migration，可快速落地。
- **Alternatives considered**：
  - 直接寫 DB 表：查詢能力佳，但本變更先避免擴大 schema 與 migration 範圍。

### 3) `start_research` 立即回覆、背景程序分階段執行
- **Decision**：`start_research` 驗證輸入後立即回傳 `job_id`；背景流程分為 `searching -> fetching -> synthesizing -> completed/failed`，每階段更新狀態。
- **Why**：避免長時間阻塞同一回合，讓使用者先收到「已受理」回應。
- **Alternatives considered**：
  - 同步執行並回傳結果：使用者體驗最差，且最容易觸發 timeout。

### 4) `check_research` 回傳結構化結果（含部分成果）
- **Decision**：`check_research` 以 JSON 回傳 `status/progress/partial/final/sources/error`；完成時提供可直接給使用者的統整文字與來源列表。
- **Why**：即使尚未完成，也能向使用者回報已取得資料，避免「黑盒等待」。
- **Alternatives considered**：
  - 僅回傳純文字狀態：可讀性與可追蹤性不足，不利後續整合。

### 5) Bot 路由優先導向 research skill，保留受控 fallback
- **Decision**：調整 `services/bot/agents.py` 與 linebot agent prompt，外部研究任務預設呼叫 `run_skill_script(skill=\"research-skill\", script=\"start-research\")`；當腳本明確回傳 `fallback_required` 才轉用既有工具。
- **Why**：維持 script-first 策略一致性，並避免「預設直接走內建 WebFetch」造成相同問題復發。
- **Alternatives considered**：
  - 全面禁止 fallback：可降低複雜度，但會在 script 異常時缺乏保底能力。

## Risks / Trade-offs

- **[搜尋來源品質波動]** → 以多來源收斂、來源去重與失敗來源標註降低單一來源失真。
- **[背景 job 累積造成儲存壓力]** → 設定保留天數與清理策略（至少先清理過舊任務）。
- **[網站擷取失敗率高]** → 在結果中明確標示失敗 URL 與原因，避免誤導為「無資料」。
- **[路由判斷不精準導致誤用工具]** → 在 prompt 加入明確觸發條件，並保留 fallback 作為安全網。
- **[群組回覆時序/mention 複雜度]** → 先統一 start/check 文案，再由既有 reply/push fallback 機制處理 token 過期情境。

## Migration Plan

1. 新增 `research-skill`（SKILL.md + `start-research.py` + `check-research.py`），完成本地腳本驗證。
2. 更新 bot tool routing / prompt（`agents.py`、`linebot_agents.py`）使研究任務預設導向 research skill。
3. 補上必要測試與手動驗證流程（群組@AI、個人對話、長任務中途查詢）。
4. 逐步上線：先以設定開關（policy/fallback）觀察 ai_logs，再擴大使用範圍。
5. **Rollback**：若異常，先將研究任務路由切回既有工具路徑（或停用該 skill）以快速恢復服務。

## Open Questions

- 首版搜尋來源要採用哪些 provider（內建 HTTP + 可公開來源 vs 需外部 API key 的 provider）？
- 單一 research job 的 URL 上限、抓取超時與重試次數預設值要定多少？
- 是否需要在後續版本加入 `cancel_research` 與更細粒度權限（例如僅特定 app 可用）？
