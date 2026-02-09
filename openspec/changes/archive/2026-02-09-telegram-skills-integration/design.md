## Context

目前系統中有兩套工具管理機制：

1. **SkillManager**（`skills/__init__.py`）：從 `skills/*/skill.yaml` 載入 skill 定義，每個 skill 包含 `tools`（工具名稱）和 `mcp_servers`（需要啟動的 MCP server）。目前只用於 `generate_tools_prompt()` 生成 prompt 文字。

2. **硬編碼工具列表**：Telegram handler (`bot_telegram/handler.py:720-761`) 和 Line handler (`linebot_ai.py:504-545`) 各自維護一份幾乎相同的硬編碼工具列表（nanobanana、printer、erpnext）。

兩套機制的工具列表不一致：
- 硬編碼包含完整的 erpnext 工具（27 個），但 skill YAML 只定義了 7 個
- `print_test_page` 在硬編碼中有，但 skill YAML 缺漏
- `Read` 工具在硬編碼中額外加入，但沒有任何 skill 定義

## Goals / Non-Goals

**Goals:**
- 統一工具白名單來源：全部由 SkillManager 的 skill YAML 驅動
- 在 `bot/agents.py` 提供 `get_tools_for_user()` 共用函式，兩個平台都使用
- 補齊 skill YAML 中缺少的工具定義
- 保留 fallback 機制，SkillManager 載入失敗時不中斷服務

**Non-Goals:**
- 不重構 MCP server 的啟動機制（`.mcp.json` → `McpServerStdio`）
- 不改變現有的權限過濾邏輯（`get_mcp_tools_for_user`）
- 不改變 prompt 生成邏輯（已整合 SkillManager）

## Decisions

### 1. 在 `bot/agents.py` 新增 `get_tools_for_user()` 函式

**選擇**：在已有 `generate_tools_prompt()` 的 `bot/agents.py` 新增工具列表函式。

**理由**：`bot/agents.py` 已經是平台無關的 bot 共用模組，且已有 SkillManager 整合邏輯（包含 fallback），工具列表函式放在同一處最自然。

**替代方案**：
- 直接在各 handler 中呼叫 `SkillManager.get_tool_names()` — 但這會讓 fallback 邏輯分散
- 在 `skills/__init__.py` 加入 — 但 SkillManager 不應知道舊版硬編碼的 fallback

### 2. 保留 `get_mcp_tool_names()` + `get_mcp_tools_for_user()` 權限過濾

**選擇**：`get_tools_for_user()` 回傳的是 skill 層級的工具白名單，不取代現有的 MCP 權限過濾。

**理由**：`get_mcp_tool_names()` 取得的是 ching-tech-os MCP server 的內建工具（如 `search_knowledge`），有自己的權限篩選邏輯。SkillManager 管理的是「外部 MCP server 工具」（如 `mcp__erpnext__*`）和「內建工具」的宣告。兩者可以共存，最終合併成 `all_tools`。

### 3. 補齊 skill YAML 而非精簡硬編碼

**選擇**：以目前硬編碼的完整工具列表為基準，補齊 skill YAML 中缺少的工具。

**理由**：硬編碼列表是目前實際運作的版本，代表經過驗證的工具集合。如果以 YAML 為基準反而可能遺漏工具，導致功能退化。

## Risks / Trade-offs

- **SkillManager 載入失敗** → fallback 到硬編碼列表（與 `generate_tools_prompt()` 相同模式）
- **YAML 和硬編碼不同步** → 遷移完成後刪除硬編碼，避免兩套並存。加入啟動時 log 顯示載入的工具數量，方便驗證
- **新增工具時的流程改變** → 只需修改 skill YAML，不再需要改多個 handler 檔案
