# Tasks: Add Printer MCP Integration

## 前置作業

- [x] 1. **確認 CUPS 環境**：CUPS 已安裝，LibreOffice 24.2 可用
- [x] 2. **安裝 printer-mcp**：`uvx printer-mcp` 可正常執行

## 實作任務

- [x] 3. **更新 `.mcp.json` 和 `.mcp.json.example`**：新增 printer-mcp server 設定
- [x] 4. **新增 `prepare_print_file` MCP 工具**：在 `services/mcp_server.py` 實作路徑轉換工具
   - 接收虛擬路徑或絕對路徑
   - PathManager 路徑轉換
   - 檔案存在性與格式驗證
   - 安全性檢查（路徑限制、防穿越）
   - Office 文件自動透過 LibreOffice headless 轉 PDF
   - 回傳絕對路徑供 printer-mcp 使用（不直接列印）
- [x] 5. ~~新增 `list_printers` MCP 工具~~：改為直接使用 printer-mcp 的 `list_printers`
- [x] 6. **新增權限設定**：在 `services/permissions.py` 新增 `printer` 應用權限
- [x] 7. **更新 AI Agent prompt**：
   - 更新 `bot/agents.py` 中的 prompt，加入列印工具說明（含兩步驟流程）
   - 建立 migration 010 更新資料庫中的 prompt
- [x] 8. **更新 `.mcp.json.example`**：已包含在任務 3

## 架構調整說明

原提案設計為 ching-tech-os 直接呼叫 CUPS 列印，實作時調整為：
- **ching-tech-os MCP**：只負責路徑轉換 + Office 轉 PDF（`prepare_print_file`）
- **printer-mcp**：負責實際列印（`print_file`、`list_printers`、`printer_status`、`cancel_job`）
- 避免兩個 MCP Server 有同名工具造成 AI Agent 混淆

## 驗證

- [ ] 9. **測試列印功能**：需確認 CUPS 印表機已設定後測試
