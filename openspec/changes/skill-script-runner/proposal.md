## Why

CTOS 已完成 Agent Skills 標準相容和 ClawHub 搜尋/安裝（Skill Hub Phase 1-3），但目前從 ClawHub 安裝的 skill 無法直接使用，因為：

1. **scripts/ 不會變成 tool** — ClawHub skill 多數透過 `scripts/*.py` 提供功能，CTOS 沒有 script runner
2. **assets/ 無法被引用** — skill 附帶的資源檔（模板、設定檔）沒有載入機制
3. **安裝完要手動配** — 管理員需自己填 allowed-tools 和 mcp_servers，但根本不知道填什麼
4. **自己的 MCP tool 也能拆出來** — 現有的 Python MCP tools 可以逐步遷移為 skill scripts，提高模組化

## What Changes

### 1. Script Runner 引擎
- 掃描 skill 的 `scripts/` 目錄，自動註冊為可呼叫的 tool
- Tool 命名規則：`skill__{skill_name}__{script_stem}`（例如 `skill__weather__get_forecast`）
- 執行方式：`subprocess` 跑 Python/Shell script，capture stdout/stderr
- 支援參數傳遞：透過 CLI args 或 stdin JSON
- Timeout 控制：預設 30 秒，可在 SKILL.md 設定
- 安全性：script 在獨立 subprocess 中執行，不共享主進程記憶體

### 2. Script 描述機制
- SKILL.md frontmatter 新增 `scripts` 區塊描述每個 script 的用途和參數：
  ```yaml
  scripts:
    get_forecast:
      description: "取得天氣預報"
      args:
        - name: city
          type: string
          required: true
          description: "城市名稱"
      timeout: 15
  ```
- 若無描述，自動從 script 檔頭的 docstring 或 `# Description:` 註解提取
- 自動產生 tool schema 供 AI 使用

### 3. Assets 載入
- Skill 的 `assets/` 目錄掛載到 script 的工作環境
- 透過環境變數 `SKILL_ASSETS_DIR` 讓 script 存取
- Assets 路徑在 prompt 中自動帶入

### 4. 自動 Tool 註冊
- SkillManager 載入 skill 時，自動掃描 scripts/ 並註冊 tool
- 安裝 ClawHub skill 後不需手動填 allowed-tools，自動從 scripts/ 產生
- 管理員仍可在 UI 覆蓋（移除不想暴露的 tool）

### 5. 環境管理
- Script 執行時注入環境變數：
  - `SKILL_NAME` — skill 名稱
  - `SKILL_DIR` — skill 目錄路徑
  - `SKILL_ASSETS_DIR` — assets 目錄路徑
  - 從 `.env` 繼承的變數（如 API keys）
- SKILL.md `metadata.openclaw.requires.env` 中列出的 env 未設定時，跳過該 skill 並警告

## Capabilities

### New Capabilities

- **skill-script-runner**: 自動將 skill 的 scripts/ 註冊為 AI 可呼叫的 tool
- **skill-auto-tool-registration**: 安裝 skill 後自動產生 tool，無需手動配置
- **skill-assets-access**: Script 可透過環境變數存取 skill 的 assets/ 資源

### Modified Capabilities

- **ai-management**: SkillManager 擴充 script 掃描和 tool 註冊
- **bot-platform**: Claude Code 的 tool calling 支援 script 類 tool

## Impact

### 安全性考量
- Script 在 subprocess 中執行，與主進程隔離
- 預設 timeout 30 秒，防止無限執行
- Script 目錄限定在 skill 目錄下（已有路徑穿越防護）
- 管理員可在 UI 移除不需要的 script tool
- `.env` 中的敏感變數需明確在 SKILL.md 宣告才會注入

### 向下相容
- 現有 7 個 native skill 不受影響（沒有 scripts/）
- 現有 MCP tool 繼續運作
- Script tool 與 MCP tool 並存，命名空間不衝突（`skill__` vs `mcp__`）

## Implementation Phases

### Phase 1: Script Runner 核心
- ScriptToolRunner 類別：掃描、註冊、執行
- SkillManager 整合：載入 skill 時自動掃描 scripts/
- Tool schema 自動產生（從 SKILL.md 或 docstring）
- Subprocess 執行 + timeout + stdout/stderr capture

### Phase 2: 環境與 Assets
- 環境變數注入（SKILL_NAME, SKILL_DIR, SKILL_ASSETS_DIR）
- `.env` 變數繼承（需 SKILL.md 宣告）
- Assets 路徑解析

### Phase 3: AI 整合
- Script tool 加入 Claude Code 的 allowed_tools
- Prompt 自動注入 script tool 的使用說明
- Tool call → script 執行 → 結果回傳的完整流程

### Phase 4: 前端 UI
- Skill 詳情頁顯示 script tools 列表
- Script 執行記錄（整合到 AI Logs）
- 安裝 ClawHub skill 後自動顯示可用的 script tools
