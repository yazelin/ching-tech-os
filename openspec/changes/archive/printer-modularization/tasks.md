# Tasks: Printer 整合模組化

## 1. 實作 MCP server 合併機制

- [x] 1.1 在 `claude_agent.py` 新增 `_load_extends_mcp_servers()` 函式
  - 掃描 `extends/*/contributes.yaml` 的 `mcp_servers` 區塊
  - 模組級快取（首次呼叫掃描，後續直接回傳）
  - 支援 `${PROJECT_ROOT}` 變數替換
  - YAML 解析失敗時 log warning 並跳過
- [x] 1.2 修改 `_create_session_workdir()` 的 `.mcp.json` 寫入邏輯
  - 讀取 `.mcp.json` 為基底 dict
  - 呼叫 `_load_extends_mcp_servers()` 取得 extends 貢獻的 server
  - 合併（`.mcp.json` 優先，不被覆蓋）
  - 以 `json.dump` 寫入 session 目錄（取代 `shutil.copy2`）

## 2. 建立 extends/printer 模組

- [x] 2.1 建立 `extends/printer/contributes.yaml`
  - 宣告 `mcp_servers.printer`（command: uvx, args: [printer-mcp]）
- [x] 2.2 搬移 `backend/src/ching_tech_os/skills/printer/SKILL.md` → `extends/printer/skills/printer/SKILL.md`
  - 內容不變，確認 SkillManager 能從 extends 路徑載入

## 3. 清理主系統

- [x] 3.1 `services/bot/agents.py` — 移除 printer 相關硬編碼
  - 刪除 `PRINTER_TOOLS_PROMPT` 常數
  - 從 `APP_PROMPT_MAPPING` 移除 `"printer"` 項目
  - 從 `_FALLBACK_TOOLS` 移除 `"printer"` 項目
- [x] 3.2 `modules.py` — `docs-tools.app_ids` 移除 `"printer"`
- [x] 3.3 `.mcp.json.example` — 移除 printer server 設定
- [x] 3.4 刪除 `backend/src/ching_tech_os/skills/printer/` 目錄

## 4. 驗證

- [x] 4.1 重啟服務，確認日誌中出現 `extends MCP servers: printer`
- [x] 4.2 Line Bot 測試：「列出印表機」→ 成功呼叫 mcp__printer__list_printers，回傳 RICOH 印表機狀態
- [x] 4.3 確認 ENABLED_MODULES 不含 printer 時，extends MCP servers 不載入 printer
