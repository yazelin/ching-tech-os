## Context

`generate_md2ppt` 和 `generate_md2doc` 是 MCP 工具，原本的職責是「接收原始主題 → 呼叫 Claude 產生格式化 markdown → 儲存 + 建立分享連結」。其中第二步呼叫 `call_claude()` 會在 MCP Server 子行程中再產生一個 Claude CLI 行程，形成巢狀架構。

目前涉及的檔案和它們的角色：

| 檔案 | 角色 |
|------|------|
| `services/mcp/presentation_tools.py` | MCP 工具定義 + MD2PPT/MD2DOC system prompt（各 ~230 行）+ 格式修正函數 |
| `skills/ai-assistant/SKILL.md` | 外層 Claude 的工具使用說明（SkillManager 優先載入） |
| `services/bot/agents.py` | `AI_DOCUMENT_TOOLS_PROMPT` fallback prompt |
| `services/linebot_agents.py` | `LINEBOT_PERSONAL_PROMPT` / `LINEBOT_GROUP_PROMPT` 中的工具段落 |

## Goals / Non-Goals

**Goals:**
- 消除 MCP 工具內的巢狀 `call_claude()` 呼叫
- 讓外層 Claude 直接產生 MD2PPT/MD2DOC 格式內容
- 維持簡報/文件品質（格式正確、設計合理）
- 維持現有的使用者體驗（用戶說「做簡報」就得到分享連結）

**Non-Goals:**
- 不改變 `generate_presentation`（Marp 簡報）工具，它沒有巢狀呼叫問題
- 不修改 `fix_md2ppt_format()` / `fix_md2doc_format()` 的邏輯
- 不修改分享連結建立、NAS 儲存等下游邏輯
- 不引入新的外部依賴（如 Anthropic API key）

## Decisions

### 1. 工具參數：`content` → `markdown_content`

**選擇**：重新命名參數為 `markdown_content`，型別不變（str），語義從「原始主題」改為「已格式化的 MD2PPT/MD2DOC markdown」。移除 `style` 參數（風格由外層 Claude 直接控制）。

**理由**：參數名稱是 Claude 判斷「該傳什麼」的最重要信號。改名後 Claude 會自然地先產生 markdown 再傳入，而不是傳一句「公司產品介紹」。

**替代方案**：
- 保持 `content` 不改名 → 現有 prompt 裡都寫「content: 簡報主題或內容說明」，Claude 會繼續傳原始文字
- 加 `format` 旗標 → 過度工程，增加 Claude 判斷負擔

### 2. 格式規範放在 SKILL.md

**選擇**：把精簡版的 MD2PPT/MD2DOC 格式規範放在 `skills/ai-assistant/SKILL.md`，同步更新 `agents.py` 中的 fallback prompt。

**理由**：
- SKILL.md 只在用戶有 `ai-assistant` 權限時才載入，不影響其他對話
- 已有完善的 SkillManager 載入機制，不需新增基礎設施
- fallback prompt (`AI_DOCUMENT_TOOLS_PROMPT`) 是 SKILL.md 失效時的保底，必須同步

**替代方案**：
- 放在工具 docstring 裡 → MCP 工具描述會被所有 MCP 呼叫載入，即使不做簡報也計入 token
- 分成兩步工具（先 `get_md2ppt_format()` 再 `save_md2ppt()`）→ 多一次工具呼叫 round-trip，使用者等更久

### 3. 格式規範精簡策略

**選擇**：將 236 行的 `MD2PPT_SYSTEM_PROMPT` 精簡為 ~60 行，保留：
- 所有格式結構規則（frontmatter、===、layout、chart、mesh）
- 配色建議表格
- 設計原則（4 條）
- **一個緊湊範例**（~20 行，取代原本 100+ 行的完整範例）

刪除：
- 「你是專業的 MD2PPT-Evolution 簡報設計師」角色扮演開頭
- 冗長的重複說明
- 過度詳細的完整範例（每種 layout 都示範）

`MD2DOC_SYSTEM_PROMPT` 同理，精簡為 ~40 行。

**理由**：外層 Claude 已經是高能力模型，給它格式規則和簡短範例就足夠。冗長範例是因為之前作為獨立 system prompt 需要「教會」一個沒有上下文的 Claude，現在外層 Claude 有完整對話上下文，不需要那麼多引導。

### 4. 工具內的基礎驗證

**選擇**：在工具中加入輕量驗證，確認傳入的 `markdown_content` 基本符合格式要求：
- MD2PPT：必須以 `---` 開頭（frontmatter）
- MD2DOC：必須以 `---` 開頭（frontmatter）
- 驗證失敗回傳錯誤訊息，引導 Claude 重新產生

**理由**：防止外層 Claude 錯誤地傳入原始文字而非格式化 markdown。`fix_md2ppt_format()` 處理的是格式微調（空行、JSON 引號等），不是完全無格式的內容。

### 5. 保留 system prompt 常數作為參考

**選擇**：將 `MD2PPT_SYSTEM_PROMPT` 和 `MD2DOC_SYSTEM_PROMPT` 從程式碼中移除（不再 import），但在 `presentation_tools.py` 頂部保留簡短註解指向 SKILL.md 中的格式規範位置。

**理由**：這些常數不再被執行時使用。保留在程式碼中會造成維護負擔（要同時維護兩處格式規範）。

## Risks / Trade-offs

**[品質下降] 外層 Claude 產生的簡報設計品質可能不如專用 system prompt**
→ 緩解：`fix_md2ppt_format()` 自動修正常見格式問題；精簡版格式規範保留了所有設計原則和配色建議；外層 Claude 擁有完整對話上下文，對用戶需求的理解更好

**[Prompt 膨脹] SKILL.md 增加 ~100 行格式規範，增加每次對話的 token 用量**
→ 緩解：僅在 `ai-assistant` 權限啟用時載入；省去的內層呼叫（~6000 tokens/次）遠超增加的 prompt 成本

**[格式不正確] 外層 Claude 可能不嚴格遵守 MD2PPT 格式**
→ 緩解：工具內的基礎驗證 + `fix_md2ppt_format()` 自動修正；驗證失敗會回傳錯誤讓 Claude 重試

## Migration Plan

1. 更新程式碼（presentation_tools.py、SKILL.md、agents.py、linebot_agents.py）
2. 重啟服務（`systemctl restart ching-tech-os`）
3. 手動測試：在 Line Bot 中說「幫我做一份簡報」，確認流程正常
4. 回滾：`git revert` + 重啟服務即可，無資料庫遷移
