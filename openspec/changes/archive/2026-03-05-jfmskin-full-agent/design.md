## Context

現有的 `ensure_default_linebot_agents()` 在 CTOS 啟動時（lifespan）呼叫，從硬編碼的 `DEFAULT_LINEBOT_AGENTS` 和 `DEFAULT_BOT_MODE_AGENTS` 列表 seed Agent 到 DB。ct-his 的客戶 Agent prompt 放在 `extends/his/clients/jfmskin/agents/*.md`，需要一個通用機制把這些檔案 seed 進 DB。

## Goals / Non-Goals

**Goals:**
- 建立通用的 extends Agent seed 函式，掃描 `extends/*/clients/*/agents/*.md`
- 在 `ensure_default_linebot_agents()` 尾端呼叫
- Agent 已存在時不覆蓋（與現有 seed 行為一致）

**Non-Goals:**
- 不做 Agent 的自動更新（檔案變更同步到 DB）
- 不建立 migration（seed 在 runtime 執行，非 schema 變更）
- 不實作 HIS MCP 工具（骨架已存在，runtime 實作另做）

## Decisions

### D1: 複用現有 _ensure_agents() 流程

不另寫 DB 操作，而是將 `.md` 檔案解析成與 `DEFAULT_BOT_MODE_AGENTS` 相同的 dict 格式，直接餵給 `_ensure_agents()`。

**理由**：最小改動，複用已驗證的 seed 邏輯。

### D2: 用 YAML frontmatter 解析 Agent metadata

`.md` 檔案格式：
```yaml
---
model: sonnet
display_name: 杰膚美助理
tools:
  - search_knowledge
  - query_his_patient
---
prompt 內容...
```

用現有的 `parse_skill_md()` 或簡單的 frontmatter 解析器讀取。

### D3: 掃描路徑為 extends/*/clients/*/agents/*.md

遍歷所有 extends 子模組的所有客戶，自動找到所有 Agent 定義。不硬編碼 jfmskin。

## Risks / Trade-offs

**[tools 欄位中的 HIS 工具尚未實作]** → jfmskin-full 的 tools 包含 `query_his_patient` 等工具，但 MCP 工具目前是 NotImplementedError。Agent 建立不受影響，工具呼叫時會報錯。這是預期行為，待 HIS runtime 實作後自然可用。
