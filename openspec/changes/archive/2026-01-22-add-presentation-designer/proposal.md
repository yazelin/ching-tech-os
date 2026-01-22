# Change: 新增簡報設計師 AI Agent

## Why

目前的簡報生成功能使用預設風格模板，設計較為單調。用戶希望 AI 能根據「內容類型」、「簡報對象」、「展示場景」等因素，智慧地設計簡報的視覺風格（配色、字型、版面、裝飾元素等），而非套用固定模板。

## What Changes

### 1. 新增簡報設計師 Agent
- 新增 `presentation_designer` prompt，專門負責簡報視覺設計
- 新增對應的 `ai_agents` 記錄
- 設計師根據內容和場景輸出 `design_json` 設計規格

### 2. 定義 design_json 規格
- `colors`: 配色方案（背景、標題、強調、內文、項目符號）
- `typography`: 字型設定（字型名稱、大小、粗細）
- `layout`: 版面配置（標題位置、內容欄數、圖片位置）
- `decorations`: 裝飾元素（標題底線、側邊裝飾條、頁碼）

### 3. 擴展 python-pptx 製作能力
- 支援更多配色選項（漸層背景、項目符號顏色）
- 支援字型設定
- 支援裝飾元素（底線、裝飾條、形狀）
- 支援多種版面配置

### 4. 整合到現有流程
- MCP 工具 `generate_presentation` 新增 `design_json` 參數
- Line Bot AI 可先查詢知識庫/專案內容，再呼叫設計師生成設計
- 設計師根據內容類型、對象、場景自動決定風格

## Impact

- Affected specs: `mcp-tools`, `ai-management`
- Affected code:
  - `backend/src/ching_tech_os/services/presentation.py`（擴展設計參數支援）
  - `backend/src/ching_tech_os/services/mcp_server.py`（新增 design_json 參數）
  - `backend/migrations/versions/`（新增 prompt 和 agent 的 migration）
- Affected database:
  - `prompts` 表格（新增 presentation_designer prompt）
  - `ai_agents` 表格（新增簡報設計師 agent）
