## 1. 現況盤點與遷移基準

- [x] 1.1 盤點 native `base`、`file-manager` 現有 `allowed-tools` 與 external 同名 scripts 的對應表
- [x] 1.2 定義每個能力的 script 參數契約、輸出格式與錯誤行為（作為功能等價基準）

## 2. Native skill script 化實作

- [x] 2.1 調整 native `base` skill：以 `mcp__ching-tech-os__run_skill_script` 為主要工具入口
- [x] 2.2 調整 native `file-manager` skill：以 `mcp__ching-tech-os__run_skill_script` 為主要工具入口
- [x] 2.3 對齊或補齊 native skills 所需 scripts，讓核心能力可由 scripts 完成

## 3. 執行策略與相容性

- [x] 3.1 明確實作 script-first / fallback 邊界（參數/權限錯誤不得 fallback）
- [x] 3.2 確認 Agent/Bot prompt 與工具白名單在切換後仍可正確引導與呼叫
- [x] 3.3 確認不啟用外部 MCP（erpnext/printer/nanobanana）時，base/file-manager 主要能力仍可運作

## 4. 測試與驗證

- [x] 4.1 新增或更新測試：`allowed-tools`、script 執行路徑、fallback 邊界
- [x] 4.2 新增或更新測試：native 與 external 對照案例（成功與失敗輸出）
- [x] 4.3 執行回歸驗證（至少 backend pytest 與前端 build）

## 5. 文件與運維同步

- [x] 5.1 更新 README 與 docs（backend/mcp-server/module-index）描述 script-first 與 MCP 最小化策略
- [x] 5.2 補充部署建議：哪些 skills 可 script-only、哪些仍依賴外部 MCP
