## Why

`generate_md2ppt` 和 `generate_md2doc` MCP 工具內部透過 `call_claude()` 產生第二個 Claude CLI 行程來做格式轉換。這造成巢狀行程架構（App → Claude CLI → MCP Server → Claude CLI），在 MCP Server 子行程中啟動內層 Claude CLI 時容易卡死（`start_session()` 無超時保護），導致整個請求 480 秒超時。AI logs 顯示此問題已多次發生（2026-01-28、02-03、02-10）。

## What Changes

- **BREAKING** `generate_md2ppt` 工具參數從 `content`（原始主題描述）改為 `markdown_content`（已格式化的 MD2PPT markdown），工具不再內部呼叫 Claude
- **BREAKING** `generate_md2doc` 工具參數從 `content` 改為 `markdown_content`（已格式化的 MD2DOC markdown），工具不再內部呼叫 Claude
- 兩個工具從「AI 生成 + 儲存」簡化為「驗證格式 + 儲存 + 建立分享連結」
- 移除工具內部的 `call_claude` 依賴，消除巢狀行程架構
- 在 SKILL.md 和 fallback prompt 中加入精簡版 MD2PPT/MD2DOC 格式規範，讓外層 Claude 自行產生格式化內容
- 保留 `fix_md2ppt_format()` / `fix_md2doc_format()` 作為後處理修正
- 保留先前已套用的 `call_claude()` 超時修正（將 `start_session` 包進統一 timeout）作為防禦性改善

## Capabilities

### New Capabilities

_無新增功能_

### Modified Capabilities

- `mcp-tools`: MCP 工具介面變更（generate_md2ppt/doc 參數和行為改變）

## Impact

- **後端 MCP 工具**：`presentation_tools.py` — 重寫 `generate_md2ppt` 和 `generate_md2doc`，移除 `call_claude` 呼叫
- **Skill Prompt**：`skills/ai-assistant/SKILL.md` — 加入 MD2PPT/MD2DOC 格式規範（約 100 行）
- **Fallback Prompt**：`bot/agents.py` 的 `AI_DOCUMENT_TOOLS_PROMPT` — 同步更新
- **LineBot Agent Prompt**：`linebot_agents.py` 中 `LINEBOT_PERSONAL_PROMPT` 和 `LINEBOT_GROUP_PROMPT` 的工具說明段落 — 更新參數描述
- **claude_agent.py**：保留已套用的超時修正（獨立於本變更，但相關）
- **Token 用量**：外層 prompt 增加約 100 行格式規範，但省去內層完整 Claude 呼叫（每次省 ~4000 input tokens + ~2000 output tokens）
- **風險**：外層 Claude 產生的 MD2PPT 品質可能不如專用 system prompt，由 `fix_md2ppt_format()` 後處理緩解
