# Tasks: linebot-agent-integration

## 任務列表

### 1. 建立預設 Agent 初始化模組
- [x] 在 `services/` 目錄建立 `linebot_agents.py`
- [x] 定義 `DEFAULT_LINEBOT_AGENTS` 常數（包含 `linebot-personal` 和 `linebot-group` 的完整設定）
- [x] 實作 `ensure_default_linebot_agents()` 非同步函數
  - 檢查 Agent 是否存在
  - 若不存在則建立 Agent 和對應的 Prompt
  - 若已存在則跳過（保留使用者修改）

### 2. 整合啟動流程
- [x] 在 `main.py` 的 lifespan 事件中調用 `ensure_default_linebot_agents()`
- [x] 加入適當的日誌記錄

### 3. 修改 Line Bot AI 使用 Agent 設定
- [x] 修改 `linebot_ai.py` 的 AI 呼叫邏輯
  - 根據對話類型（個人/群組）選擇對應的 Agent
  - 從 Agent 取得 model 和 system_prompt
  - 保留現有的群組資訊動態注入邏輯
- [x] 實作 fallback 機制（當 Agent 不存在時使用預設值）
- [x] 修正 `log_linebot_ai_call()` 正確關聯 Agent

### 4. 設計 Prompt 內容
- [x] 撰寫 `linebot-personal` Prompt（完整版，包含 MCP 工具說明）
- [x] 撰寫 `linebot-group` Prompt（精簡版，限制回覆長度）

### 5. 驗證與測試
- [x] 驗證應用程式啟動時正確建立預設 Agent
- [x] 驗證資料庫 prompt 已更新（migration 013）
- [x] 驗證程式碼語法正確

## 依賴關係

```
1. 建立預設 Agent 初始化模組
   └── 2. 整合啟動流程
       └── 3. 修改 Line Bot AI 使用 Agent 設定
           └── 5. 驗證與測試

4. 設計 Prompt 內容（可與 1-3 並行）
```

## 驗收標準

- [x] 應用程式啟動時自動建立 `linebot-personal` 和 `linebot-group` Agent
- [x] 個人對話使用 `linebot-personal` 的 model 和 prompt
- [x] 群組對話使用 `linebot-group` 的 model 和 prompt
- [x] AI Log 的 Agent 欄位正確顯示對應的 Agent 名稱
- [x] 可透過前端 AI 管理介面修改 Line Bot 的 Prompt

### 6. 增強功能：個人對話歷史與工具整合
- [x] 增加對話歷史長度（10 → 20 則）
- [x] 修正個人對話歷史查詢（原本只有群組有效）
- [x] 修正 Bot 回應儲存，讓個人對話也能看到歷史回應
- [x] 支援從 Agent 設定讀取內建工具（如 WebSearch）

### 7. 對話重置功能
- [x] 新增 `conversation_reset_at` 欄位（migration 014）
- [x] 實作 `reset_conversation()` 和 `is_reset_command()` 函數
- [x] 修改 `get_conversation_context()` 加入時間過濾
- [x] 個人對話支援 `/新對話`、`/reset` 等重置指令
- [x] 群組發送重置指令時靜默忽略
- [x] 更新 Prompt 說明重置功能

## 實作摘要

### 新增檔案
- `backend/migrations/versions/013_update_linebot_prompts.py` - 更新 prompt 預設內容
- `backend/migrations/versions/014_add_conversation_reset.py` - 新增對話重置時間欄位
- `backend/src/ching_tech_os/services/linebot_agents.py` - Agent 初始化模組

### 修改檔案
- `backend/src/ching_tech_os/main.py` - 在 lifespan 中調用初始化
- `backend/src/ching_tech_os/services/linebot_ai.py` - 使用資料庫 Agent 設定、對話重置處理
- `backend/src/ching_tech_os/services/linebot.py` - 新增重置函數、修正 Bot 回應儲存
