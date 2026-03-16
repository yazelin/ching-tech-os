# Change: ERPNext 整合模組化

## Why

ERPNext 整合目前處於尷尬的過渡狀態：

1. **程式碼散落**：Agent Prompt（`bot/agents.py`）、模組定義（`modules.py`）、MCP 設定（`.mcp.json`）分散在主系統各處
2. **遺留死碼**：舊的 `services/project.py`（1,158 行）、`inventory.py`、`vendor.py` 已無引用，但仍佔據主系統
3. **無法按客戶選配**：ERPNext 是外部 Docker 服務，不是每個部署都需要，但目前寫死在核心模組中
4. **MCP 設定無法模組化**：Skill 可外部化，但 MCP server 啟動設定綁死在專案根目錄 `.mcp.json`

HIS 已成功用 `extends/` + `contributes.yaml` 實現完全隔離，ERPNext 應採用相同模式。

## What Changes

### 一、清理主系統遺留碼

- 刪除 `services/project.py`、`services/inventory.py`、`services/vendor.py`、`models/project.py`
  - 資料庫已無 project 相關資料表，`inventory`/`vendor` 零引用
- 清理 `services/share.py`、`api/share.py`、`main.py` 中的 `project`/`project_attachment` 死碼分支
- 移除 `modules.py` 中的 `erpnext` builtin 定義
- 移除 `bot/agents.py` 中的 `PROJECT_TOOLS_PROMPT`、`INVENTORY_TOOLS_PROMPT` 及相關 `APP_PROMPT_MAPPING`/`_FALLBACK_TOOLS` 項目
- 移除 `.mcp.json.example` 中的 erpnext server 設定

### 二、建立 extends/erpnext 模組

```
extends/erpnext/
├── contributes.yaml          # MCP server 設定 + 模組宣告
├── skills/
│   ├── project-mgmt/
│   │   └── SKILL.md          # 專案管理 prompt + allowed_tools
│   ├── inventory/
│   │   └── SKILL.md          # 物料庫存 prompt + allowed_tools
│   └── vendor/
│       └── SKILL.md          # 廠商客戶 prompt + allowed_tools
└── clients/
    └── ching-tech/
        └── config.yaml       # 擎添的 ERPNext 連線設定
```

`contributes.yaml` 新增 `mcp_servers` 宣告：

```yaml
mcp_servers:
  erpnext:
    command: bash
    args: ["-c", "set -a && source ${PROJECT_ROOT}/.env && set +a && uvx erpnext-mcp"]
```

### 三、實作 MCP server 合併機制

修改 `claude_agent.py` 的 `_create_session_workdir()`：

- 目前：直接 copy 專案根目錄的 `.mcp.json` 到 session 目錄
- 改為：掃描 `extends/*/contributes.yaml` 中的 `mcp_servers` 宣告，合併到 `.mcp.json` 後寫入 session 目錄
- 現有的 `required_mcp_servers` 過濾機制不變（決定這次 session 實際啟動哪些）

```
合併流程：
  .mcp.json（核心 server）
  + extends/erpnext/contributes.yaml → mcp_servers
  + extends/printer/contributes.yaml → mcp_servers（未來）
  ─────────────────────────────────
  = /tmp/session-xxx/.mcp.json（合併結果）
```

## What Doesn't Change

- `printer` 為獨立模組，不在此次範圍
- HIS 模組（`extends/his/`）不受影響
- Skill 系統的 `mcp_servers` 宣告機制不變（Skill 宣告「需要哪些 server」，此次新增的是「server 怎麼啟動」的來源）
- 前端無影響（ERPNext 無 CTOS 前端頁面）

## Risk

- **低風險**：舊 services 已確認零引用、零資料表
- **中風險**：MCP 合併機制是新功能，需測試 extends 模組的 MCP server 能正確啟動
- **注意**：現有 `.mcp.json` 中的 erpnext 設定移出後，需確保有啟用 `extends/erpnext` 的部署能正常運作
