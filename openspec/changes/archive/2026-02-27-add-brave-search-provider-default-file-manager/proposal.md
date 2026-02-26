## Why

目前研究流程雖已導入 `research-skill`，但未綁定或預設權限情境仍可能因缺少 `file-manager` 權限而無法使用；同時搜尋來源仍偏向舊路徑（WebSearch/WebFetch 或 DDG Instant API），需要導入可控且完整度更高的 Brave Search provider。

## What Changes

- 調整預設 App 權限，讓未綁定或預設權限情境可使用 `file-manager`（至少可啟用 `research-skill` 的 start/check）。
- 在 `research-skill` 新增搜尋 provider 抽象，優先支援 Brave Search API。
- 新增 Brave Search 的環境變數設定與 `.env.example` 範例欄位，方便填入 API key。
- 保留 fallback 策略：Brave 不可用時仍可回退既有搜尋路徑，避免服務中斷。
- 更新 bot 提示與路由行為，確保研究型請求優先走 `run_skill_script(skill=\"research-skill\", script=\"start-research\")`。

## Capabilities

### New Capabilities
- `research-provider-brave`: 在 research-skill 內提供 Brave Search API provider，輸出結構化搜尋結果供後續抓取與統整。

### Modified Capabilities
- `bot-platform`: 調整預設權限策略，讓未綁定/預設權限情境可使用 `file-manager` 所需能力。
- `research-skill`: 新增 provider 選擇與 fallback 流程，優先使用 Brave Search。
- `infrastructure`: 新增 Brave API key 相關設定與 `.env.example` 範例。

## Impact

- 受影響程式：
  - `backend/src/ching_tech_os/services/permissions.py`（或等效預設權限來源）
  - `backend/src/ching_tech_os/skills/research-skill/scripts/start-research.py`
  - `backend/src/ching_tech_os/config.py`（如需新增設定欄位）
  - `.env.example` / 相關設定範例檔
  - `backend/src/ching_tech_os/services/bot/agents.py`（必要時調整提示）
- 受影響行為：
  - 未綁定或預設權限情境可走 research-skill，不再因 file-manager 權限缺失失敗
  - 研究任務搜尋結果完整度提升，降低舊搜尋路徑 timeout 風險
- 相依與外部需求：
  - 需申請 Brave Search API key（提供申請網址與 env 欄位）
