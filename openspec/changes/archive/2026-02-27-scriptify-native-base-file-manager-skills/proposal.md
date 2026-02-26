## Why

目前 `base` 與 `file-manager` native skills 仍以直接 MCP 工具為主，導致預設需要維持較大的 MCP 載入面與設定複雜度。為了降低預設依賴、提升部署彈性並延續既有 script-first 策略，需先完成第一批 native skill 的 script 化改造。

## What Changes

- 將 native `base`、`file-manager` 兩個 skills 改為以 `run_skill_script` 為主要執行路徑，對齊現有 `media-downloader`、`media-transcription` 的模式。
- 把 `base`、`file-manager` 目前常用能力整理為對應 scripts（含參數契約與錯誤輸出規範），並更新 skill metadata 與可用工具宣告。
- 明確化 script-first / MCP fallback 的行為邊界，確保可在不增加預設 MCP 載入的前提下維持可用性。
- 補齊測試與文件，驗證 Agent/Line/Telegram 等入口在改造後仍可使用既有能力。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `skill-management`: 調整 native skills（base、file-manager）的工具路由與 metadata 契約，讓 script-first 成為預設執行模式。
- `mcp-tools`: 調整工具暴露與 fallback 規則，降低 base/file-manager 場景對預設 MCP 載入面的依賴。
- `infrastructure`: 更新部署與設定文件中的 MCP/skill 建議配置，反映 script 化後的預設負載策略。

## Impact

- Affected code:
  - `backend/src/ching_tech_os/skills/`（native skill 定義與 scripts）
  - `backend/src/ching_tech_os/services/skills/`（路由與執行策略）
  - `backend/src/ching_tech_os/services/mcp/`（工具暴露與 fallback）
  - `backend/src/ching_tech_os/services/bot/`（Agent 工具可見性）
- Affected docs:
  - `README.md`, `docs/mcp-server.md`, `docs/backend.md`, `docs/module-index.md`
- Runtime / ops:
  - 預期降低預設 MCP 設定與載入壓力；維持既有功能行為與權限邏輯不變。
