## Context

目前 `call_claude()` 每次呼叫的流程：

```
_create_session_workdir()
  └─ 複製完整 .mcp.json（4 個 server 全部）
      ↓
_build_mcp_servers(session_dir)
  └─ 載入全部 4 個 McpServerStdio
      ↓
ClaudeClient(mcp_servers=全部4個)
  └─ 每次都啟動 ching-tech-os + nanobanana + erpnext + printer
```

問題：
- 一個只有「知識庫」權限的用戶，只需要 ching-tech-os server，卻也啟動了 nanobanana、erpnext、printer
- SkillManager 已有 `get_required_mcp_servers()` 可回傳所需的 server 名稱集合，但沒人呼叫

前端 AI logs 的 `renderToolsBadges()` 把 `allowed_tools`（80+ 個）全部列出，用邊框/實心區分是否使用。大部分是灰色邊框的未使用工具，資訊過載。

## Goals / Non-Goals

**Goals:**
- MCP server 依用戶權限按需載入，減少不必要的啟動開銷
- 前端 AI logs Tools 欄位預設只顯示 used tools，allowed tools 可展開查看
- 保持 ching-tech-os server 永遠載入（所有用戶都需要基礎工具）

**Non-Goals:**
- 不改變 SkillManager 本身的邏輯
- 不改變 `allowed_tools` 記錄到 ai_logs 的行為（仍記錄完整白名單）
- 不重構 ClaudeClient 的 MCP 啟動機制

## Decisions

### 1. MCP server 過濾：在 `_build_mcp_servers` 層面過濾，不改 `.mcp.json`

**選擇**：讓 `_build_mcp_servers()` 接受一個 `required_servers: set[str]` 參數，載入後只回傳名稱在集合中的 server。

**理由**：
- 不需要修改 `_create_session_workdir()` 的 `.mcp.json` 複製邏輯
- 過濾邏輯集中在一處，清晰易懂
- `.mcp.json` 保持完整副本，需要時（如 fallback）可載入全部

**替代方案**：
- 在 `_create_session_workdir()` 寫入精簡的 `.mcp.json` → 更乾淨但要改兩處
- 在 `call_claude()` 呼叫後過濾 → 語意不清晰

### 2. 參數傳遞：`call_claude()` 新增 `required_mcp_servers` 參數

**選擇**：新增可選參數 `required_mcp_servers: set[str] | None = None`，`None` 表示載入全部（向後相容）。

**理由**：
- 保持向後相容，現有的 web chat 等呼叫者不需要修改
- handler 透過 SkillManager 取得 server 集合後直接傳入

### 3. ching-tech-os server 永遠載入

**選擇**：`ching-tech-os` 作為基礎 server 永遠載入，不受過濾影響。

**理由**：所有用戶都有 base skill，而 base skill 需要 ching-tech-os。即使 SkillManager 回傳的集合中已包含它，加一個保底邏輯更安全。

### 4. 前端：預設只顯示 used tools，可展開 allowed

**選擇**：
- `renderToolsBadges()` 預設只渲染 `used_tools`
- 如果有 `allowed_tools` 且數量 > `used_tools`，顯示一個 `+N` 的展開按鈕
- 點擊展開後顯示完整的 allowed_tools（未使用的用較淡的樣式）

**替代方案**：
- 完全移除 allowed_tools 顯示 → 失去了檢視白名單的能力
- 放在詳情面板裡 → 但列表視圖也需要快速辨識

## Risks / Trade-offs

- **SkillManager 載入失敗** → `get_required_mcp_servers` 回傳空集合 → 使用 fallback 載入全部 server（與目前行為一致）
- **Skill YAML 中 mcp_servers 設定遺漏** → 某個工具被允許但對應 server 沒啟動，Claude 呼叫會失敗 → 透過日誌監控，短期可手動修復 YAML
- **前端展開互動** → 需注意表格行高變化對排版的影響
