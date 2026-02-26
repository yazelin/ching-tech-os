## Context

目前 `research-skill` 已採 start/check 非同步流程，但在實際對話中若使用者未綁定或預設權限缺少 `file-manager`，`run_skill_script(skill="research-skill", ...)` 會先被權限層拒絕，導致 AI 回退到舊的 WebSearch/WebFetch 路徑，仍可能觸發長回合超時。另一方面，現行 research 搜尋來源主要是 DuckDuckGo Instant API，結果完整度對產品情報場景（型號、規格、價格、競品）不足。

本變更需同時處理三個面向：
- 權限預設策略（確保 research-skill 能被預設使用）
- 搜尋 provider 升級（優先 Brave Search API）
- 設定與運維（新增 API key 設定與範例）

## Goals / Non-Goals

**Goals:**
- 預設權限情境可直接使用 `research-skill`，避免無綁定/未配置權限時回退舊路徑。
- 在 `research-skill` 內導入 Brave Search provider，提供較完整搜尋結果。
- 保留 fallback 鏈，Brave 失敗時仍可退回既有 provider，確保可用性。
- 新增可配置的環境變數與 `.env.example` 欄位，便於上線前填值。

**Non-Goals:**
- 不在本次導入多供應商計費治理平台或複雜配額管理。
- 不移除所有內建 WebSearch/WebFetch（保留作為 fallback）。
- 不改動整個 Bot 權限模型的資料庫結構。

## Decisions

### 1) 預設啟用 `file-manager` 權限於未綁定/預設權限路徑
- **Decision**: 在預設 App 權限計算邏輯中，將 `file-manager` 設為可用（至少在未綁定或無個人化覆寫時成立）。
- **Why**: `research-skill` 現階段綁定 `requires_app: file-manager`，若預設不開啟會直接失敗並走舊路徑。
- **Alternatives considered**:
  - 移除 `research-skill` 的 `requires_app`：會弱化既有權限治理，不採用。
  - 只在 prompt 層提醒 AI 重試帶 `ctos_user_id`：無法解決未綁定使用者。

### 2) `research-skill` 採 provider 抽象，優先 Brave
- **Decision**: 在 `start-research.py` 中新增 provider 層（例如 `_search_brave()` + `_search_duckduckgo()`），預設先呼叫 Brave，再 fallback 到既有 DDG Instant。
- **Why**: 兼顧結果完整度與穩定性；Brave 不可用時仍有可用路徑。
- **Alternatives considered**:
  - 直接改用 `duckduckgo-search` 套件為唯一來源：易受封鎖與波動，不適合作唯一主路徑。
  - 直接改內建 WebSearch/WebFetch：變更範圍大且不解決兩段式可追蹤優勢。

### 3) Brave API 設定顯式化
- **Decision**: 在 `config.py` 新增 Brave API key 設定（例如 `BRAVE_SEARCH_API_KEY`），並更新 `.env.example`。
- **Why**: 避免硬編碼，降低部署風險，方便使用者自行申請填入。
- **Alternatives considered**:
  - 直接讀取裸環境變數不經 settings：分散設定來源，不易維護。

### 4) fallback 與錯誤透明
- **Decision**: Brave 呼叫失敗時記錄失敗原因並回退至 DDG provider，最終仍維持 start/check 可查進度與錯誤。
- **Why**: 在外部 API 不穩時保證服務可用，且便於除錯。
- **Alternatives considered**:
  - Brave 失敗即中止任務：用戶體驗差且可用性低。

## Risks / Trade-offs

- **[Brave API 配額不足或 key 未配置]** → 自動 fallback 到 DDG，並在狀態中標記 provider/failure reason。
- **[預設放寬 file-manager 權限帶來邊界擴大]** → 僅放寬預設 app 權限，不放寬工具級權限與安全檢查。
- **[搜尋結果來源變動造成輸出不一致]** → 統一轉為結構化 source schema，維持下游摘要格式。
- **[外部 API 延遲]** → 保持 start/check 非同步，不阻塞主回合。

## Migration Plan

1. 調整預設權限邏輯，確保 `file-manager` 在預設路徑可用。
2. 在 `research-skill` 新增 Brave provider 與 fallback 鏈。
3. 在設定層新增 Brave API key，並更新 `.env.example`。
4. 更新相關測試（權限、provider 選擇、fallback）。
5. 執行 build + backend 測試，確認無回歸。

Rollback:
- 若 Brave provider 異常，可暫時移除/關閉 Brave key，系統自動回退 DDG；
- 若權限策略需回復，可退回原預設權限設定。

## Open Questions

- 是否需要在後續版本加入 `SEARCH_PROVIDER_PRIORITY` 可配置順序（brave/ddg/websearch）？
- Brave 回傳結果是否需要額外做網域白名單或可信度打分？
