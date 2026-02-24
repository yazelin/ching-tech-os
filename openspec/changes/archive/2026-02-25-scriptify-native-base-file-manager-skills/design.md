## Context

目前 `base` 與 `file-manager` native skills 仍有多數能力直接列在 `allowed-tools`（MCP 直接呼叫），而 external 同名 skills 已有 script 版本可參考。這造成同一能力存在雙軌維護（native MCP / external script），也讓預設 MCP 載入面與工具白名單持續膨脹。  
本次變更聚焦「第一批低風險 script 化」：僅處理 `base`、`file-manager` 兩個技能，維持功能等價，並延續既有 `script-first` 路由策略。

## Goals / Non-Goals

**Goals:**
- 將 `base`、`file-manager` 改為以 `run_skill_script` 作為主要工具入口。
- 對齊既有 external scripts 行為（參數、輸出、錯誤型態），降低雙軌差異。
- 在不破壞既有 Agent/Bot 使用流程前提下，降低預設 MCP 依賴面。
- 補齊測試與文件，讓後續 `share-links`、`pdf-converter` 併回 native 時可沿用同套路徑。

**Non-Goals:**
- 不處理 `project`、`inventory`、`printer`、`ai-assistant`（涉及外部 MCP server，另案處理）。
- 不在此變更新增 `contributes.app` 實作（僅保留架構能力與後續規劃）。
- 不改動權限模型（`requires_app` 與現有 permission 流程保持不變）。

## Decisions

### Decision 1：base/file-manager 採「單一工具入口」策略

**選擇**：兩個 skill 的 `allowed-tools` 以 `mcp__ching-tech-os__run_skill_script` 為主，功能由 skill scripts 實作。  
**替代方案**：保留現有 MCP 工具並逐步混用。  
**理由**：混用會讓 prompt/tool 白名單與維護路徑持續複雜；先收斂入口可直接降低複雜度並對齊已存在的 script-first 架構。

### Decision 2：優先沿用 external 同名 scripts，native 作為整合載體

**選擇**：把 external `base/file-manager/share-links/pdf-converter` 既有 scripts 視為行為基準，將 native 對齊。  
**替代方案**：重寫一套新 scripts。  
**理由**：重寫風險高且無必要；沿用既有腳本可加速遷移並保留已驗證行為。

### Decision 3：明確定義 script-first / fallback 邊界

**選擇**：僅在 script 執行失敗且符合 `SKILL_SCRIPT_FALLBACK_ENABLED` 條件時允許 fallback；參數驗證錯誤與權限錯誤不 fallback。  
**替代方案**：所有失敗都 fallback。  
**理由**：全面 fallback 會掩蓋腳本問題並增加不可預期行為；應保留可觀測、可修復的失敗訊號。

### Decision 4：文件與設定同步視為同等交付

**選擇**：同步更新 README/docs 的 MCP 載入與 skill 路由描述，避免實作與操作文件落差。  
**替代方案**：後續再補文件。  
**理由**：此變更直接影響維運對 `.mcp.json` 與 skill 配置策略判斷，文件延後會造成錯誤操作。

## Risks / Trade-offs

- **[Risk] script 行為與舊 MCP 行為不完全一致** → 以 external 既有腳本作為 golden behavior，加入對照測試（成功/失敗輸出）。
- **[Risk] rollout 後工具名稱切換影響既有 prompt** → 在 migration 階段檢查 Agent seed prompt 與技能 allowed-tools 是否一致，必要時保留短期相容提示。
- **[Risk] script 執行環境依賴差異** → 在 scripts 層加入前置檢查與明確錯誤訊息，避免 silent failure。
- **[Trade-off] `run_skill_script` 成為集中入口**：可降低工具面，但 debug 需下鑽到 script 執行與參數映射，需靠測試與日誌補強可觀測性。

## Migration Plan

1. 盤點 `base`、`file-manager` 現行 native 能力與 external scripts 對應表。
2. 調整 native skill metadata（`allowed-tools`、必要時 `mcp_servers` 描述）為 script-first。
3. 對齊 scripts 參數契約與輸出格式，補齊缺漏腳本。
4. 更新相關測試（skills API、script runner、工具白名單/權限行為）。
5. 更新 README 與 docs，明確標示 script-first 與 fallback 策略。
6. 驗證 `ENABLED_MODULES=*` 與裁剪模組部署下皆維持可用。

Rollback:
- 還原 `SKILL.md` 的 `allowed-tools` 到先前 MCP 清單。
- 保留 scripts 檔案但暫停使用 script-first（必要時切回 mcp-first）。
- 透過既有測試回歸確認回滾後行為一致。

## Open Questions

1. `base` skill 中 `Read` 工具是否保留為非 script 例外，或納入 script 化替代流程？
2. external 同名 skill 與 native skill 的最終策略是「merge」還是「保留雙軌並標準化」？
3. 是否需要在 UI 額外暴露「此 skill 為 script-only」標記，協助維運辨識？
