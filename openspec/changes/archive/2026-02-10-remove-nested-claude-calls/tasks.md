## 1. 精簡格式規範

- [x] 1.1 從 `presentation_tools.py` 中的 `MD2PPT_SYSTEM_PROMPT`（~236 行）精簡為 ~60 行格式規範，保留格式結構規則、配色建議、設計原則、一個緊湊範例
- [x] 1.2 從 `presentation_tools.py` 中的 `MD2DOC_SYSTEM_PROMPT`（~208 行）精簡為 ~40 行格式規範，同樣保留核心規則和範例

## 2. 更新 Prompt 檔案

- [x] 2.1 在 `skills/ai-assistant/SKILL.md` 中加入精簡版 MD2PPT 格式規範，並更新 `generate_md2ppt` 工具描述（參數改為 `markdown_content`）
- [x] 2.2 在 `skills/ai-assistant/SKILL.md` 中加入精簡版 MD2DOC 格式規範，並更新 `generate_md2doc` 工具描述（參數改為 `markdown_content`）
- [x] 2.3 更新 `bot/agents.py` 中 `AI_DOCUMENT_TOOLS_PROMPT`，同步加入精簡版格式規範作為 fallback
- [x] 2.4 更新 `linebot_agents.py` 中 `LINEBOT_PERSONAL_PROMPT` 的 `generate_md2ppt` / `generate_md2doc` 工具描述段落
- [x] 2.5 更新 `linebot_agents.py` 中 `LINEBOT_GROUP_PROMPT` 的 `generate_md2ppt` / `generate_md2doc` 工具描述段落

## 3. 重寫 MCP 工具

- [x] 3.1 重寫 `generate_md2ppt`：參數從 `content`+`style` 改為 `markdown_content`；移除 `call_claude` 呼叫；加入 frontmatter 驗證（必須以 `---` 開頭）；保留 `fix_md2ppt_format()` + 儲存 + 分享連結邏輯
- [x] 3.2 重寫 `generate_md2doc`：參數從 `content` 改為 `markdown_content`；移除 `call_claude` 呼叫；加入 frontmatter 驗證；保留 `fix_md2doc_format()` + 儲存 + 分享連結邏輯
- [x] 3.3 移除 `presentation_tools.py` 中的 `MD2PPT_SYSTEM_PROMPT` 和 `MD2DOC_SYSTEM_PROMPT` 常數，加入註解指向 SKILL.md

## 4. 驗證

- [x] 4.1 確認 `presentation_tools.py` 不再 import `call_claude`（除非 `generate_presentation` 仍需使用）
- [x] 4.2 檢查 `SKILL.md`、`agents.py`、`linebot_agents.py` 三處格式規範內容一致
- [x] 4.3 檢查 Python 語法無誤（`python -m py_compile`）
