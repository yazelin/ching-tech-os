# Spec: contributes.yaml MCP Server 合併機制

## 概述

讓 `extends/` 模組可以透過 `contributes.yaml` 宣告自己需要的 MCP server 啟動設定，主系統在建立 AI session 時自動合併到 `.mcp.json`。

## 現狀

```
_create_session_workdir()
  → shutil.copy2(project_root/.mcp.json, session_dir/.mcp.json)
```

所有 MCP server 設定集中在專案根目錄 `.mcp.json`，無法由外部模組貢獻。

## 目標行為

```
_create_session_workdir()
  → 讀取 project_root/.mcp.json（核心 server）
  → 掃描 extends/*/contributes.yaml 的 mcp_servers 區塊
  → 合併為單一 dict
  → 寫入 session_dir/.mcp.json
```

## contributes.yaml 格式

擴充現有 `contributes.yaml`，新增 `mcp_servers` 頂層 key：

```yaml
# extends/printer/contributes.yaml
mcp_servers:
  printer:
    command: uvx
    args: [printer-mcp]

# extends/erpnext/contributes.yaml（未來）
mcp_servers:
  erpnext:
    command: bash
    args: ["-c", "set -a && source ${PROJECT_ROOT}/.env && set +a && uvx erpnext-mcp"]
```

格式與 `.mcp.json` 的 `mcpServers` 內容一致（`command`、`args`、`env`），但用 YAML 撰寫。

## 合併規則

1. 以 `.mcp.json` 為基底
2. 依序掃描 `extends/*/contributes.yaml`（按目錄名排序，確保確定性）
3. 合併 `mcp_servers` 到 `mcpServers` dict 中
4. **衝突處理**：`.mcp.json` 優先（核心設定不被覆蓋）
5. 支援 `${PROJECT_ROOT}` 變數替換（替換為 `settings.project_root`）

## 不變的部分

- `required_mcp_servers` 過濾機制不變（Skill 宣告需要哪些 server → `_build_mcp_servers` 過濾）
- `contributes.yaml` 的 `lifespan` 區塊處理不變
- `.mcp.json` 仍然是核心 server 的來源（ching-tech-os、nanobanana）

## 邊界條件

- `extends/` 目錄不存在：跳過掃描，行為同目前
- `contributes.yaml` 無 `mcp_servers` key：跳過該模組
- `contributes.yaml` 格式錯誤：log warning，跳過該模組，不影響其他模組
- `.mcp.json` 不存在：只用 extends 貢獻的 server（極端情況）
