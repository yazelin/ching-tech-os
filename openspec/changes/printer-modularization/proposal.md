# Change: Printer 整合模組化

## Why

Printer 整合與 ERPNext 有相同的架構問題：MCP server 設定綁在主系統 `.mcp.json`，Prompt 和工具白名單硬編碼在 `bot/agents.py`，無法按部署選配。

但 Printer 比 ERPNext 簡單得多：
- **無遺留死碼**（不像 ERPNext 有舊 services 要清理）
- **無前端頁面**（純 MCP 工具 + Skill）
- **已有完整 Skill 定義**（`skills/printer/SKILL.md`）

因此適合作為 **MCP 合併機制的第一個實踐案例**，為後續 ERPNext 模組化鋪路。

## What Changes

### 一、實作 contributes.yaml 的 MCP server 合併機制

修改 `claude_agent.py` 的 `_create_session_workdir()`：

- 目前：直接 copy 專案根目錄 `.mcp.json` 到 session 目錄
- 改為：讀取 `.mcp.json` + 掃描 `extends/*/contributes.yaml` 中的 `mcp_servers` 宣告 → 合併後寫入 session 目錄

```
.mcp.json（核心 server: ching-tech-os, nanobanana）
+ extends/printer/contributes.yaml → mcp_servers.printer
──────────────────────────────────────────────────────
= /tmp/session-xxx/.mcp.json
```

現有的 `required_mcp_servers` 過濾機制不變。

### 二、建立 extends/printer 模組

```
extends/printer/
├── contributes.yaml          # MCP server 設定宣告
└── skills/
    └── printer/
        └── SKILL.md          # 從 backend skills/printer/ 搬過來
```

`contributes.yaml`：

```yaml
# printer 模組對主系統的貢獻宣告
mcp_servers:
  printer:
    command: uvx
    args: [printer-mcp]
```

### 三、清理主系統

- 移除 `bot/agents.py` 中的 `PRINTER_TOOLS_PROMPT`、`APP_PROMPT_MAPPING["printer"]`、`_FALLBACK_TOOLS["printer"]`
- 移除 `.mcp.json.example` 中的 printer server 設定
- 移除 `modules.py` 中 `docs-tools` 的 `app_ids` 裡的 `"printer"`
- 移除 `backend/src/ching_tech_os/skills/printer/` 內建 Skill（搬到 extends）

### 四、保留在主系統

- `services/mcp/presentation_tools.py` 中的 `prepare_print_file` — 這是 ching-tech-os MCP server 的工具，負責路徑轉換和 Office 轉 PDF，與 printer 外部 MCP server 無關
- `services/permissions.py` 中的 `"printer"` 權限定義 — App 權限是主系統的一部分

## What Doesn't Change

- `prepare_print_file` MCP 工具仍在主系統（它屬於 ching-tech-os server）
- 權限系統中的 `"printer"` app 權限不動
- ERPNext 模組化為獨立 change，不在此範圍
- HIS 模組不受影響

## 額外價值

此 change 實作的 **MCP server 合併機制**是通用的，完成後：
- ERPNext 模組化可直接使用相同機制
- 未來任何外部整合都能透過 `contributes.yaml` 宣告 MCP server
- 不需要再手動編輯 `.mcp.json`

## Risk

- **低風險**：Printer 無遺留碼、無前端、Skill 已存在
- **中風險**：MCP 合併機制是新功能，需測試 extends 模組的 MCP server 能正確啟動
- **驗證方式**：合併後在 Line Bot 中測試列印功能是否正常
