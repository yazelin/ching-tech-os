# Tasks: add-linebot-md-converter-agents

## Task List

### 1. 擴充分享資料表 ✅
- [x] 修改 `public_share_links` 資料表，新增欄位：
  - `content` (TEXT, nullable) - 直接儲存的內容（MD2PPT/MD2DOC markdown）
  - `content_type` (VARCHAR(50), nullable) - MIME type（如 `text/markdown`）
  - `filename` (VARCHAR(255), nullable) - 檔案名稱
  - `password_hash` (VARCHAR(255), nullable) - bcrypt hash
  - `attempt_count` (INTEGER, default 0) - 密碼錯誤嘗試次數
  - `locked_at` (TIMESTAMP WITH TIME ZONE, nullable) - 鎖定時間
- [x] 建立 Alembic migration

**驗證**：migration 可成功執行 ✅

### 2. 擴充分享 API ✅
- [x] 修改 `ShareLinkCreate` model 新增 `password` 可選參數
- [x] 修改 `create_share_link` 支援密碼
  - 如果提供密碼，hash 後儲存
  - 回應中包含原始密碼（僅建立時回傳一次）
- [x] 修改 `GET /api/public/{token}` 支援密碼驗證
  - 如果連結有密碼，要求 `password` query parameter
  - 驗證密碼，錯誤次數限制（5 次鎖定）
  - 無密碼的連結維持原有行為
- [x] 新增 CORS 設定允許 MD2PPT/MD2DOC 網站存取
- [x] 新增 `content` 資源類型，直接儲存內容而非引用

**驗證**：API 可正常建立/驗證帶密碼的分享連結

### 3. 格式驗證器 ✅
- [x] 建立 `md_validators.py` 模組
- [x] MD2PPT 驗證規則：
  - 全域 Frontmatter 在開頭，theme 必須是 amber/midnight/academic/material
  - `===` 分頁符前後必須有空行
  - 每頁 layout 必須是有效值 (default/impact/center/grid/two-column/quote/alert)
  - 圖表 `::: chart-xxx {JSON}` 的 JSON 必須有效（雙引號）
  - 圖表區塊與表格前後必須有空行
  - `:: right ::` 前後必須有空行
- [x] MD2DOC 驗證規則：
  - Frontmatter 必須有 title 和 author
  - 只支援 H1-H3，禁止 H4 以上
  - Callout 只支援 TIP/NOTE/WARNING
  - 對話語法正確：`"::` (左)、`::"` (右)、`:":` (中)
- [x] 驗證失敗時回傳詳細錯誤清單，方便 AI 修正

**驗證**：驗證器能正確識別格式錯誤 ✅

### 4. MCP Tool: generate_presentation
- [ ] 在 `mcp_server.py` 新增 `generate_presentation` tool
- [ ] 建立 MD2PPT Agent system prompt（內嵌完整規範）
  - 包含核心指令與致命錯誤預防
  - 包含配色盤與背景使用規則
  - 包含輸出範本
- [ ] 呼叫 AI 產生內容
- [ ] 使用驗證器檢查格式
- [ ] 若驗證失敗，將錯誤回傳給 AI 重新產生（最多 3 次）
- [ ] 驗證通過後自動建立分享連結
- [ ] 回傳連結和密碼

**驗證**：Tool 可產生並驗證正確格式的 MD2PPT 內容

### 5. MCP Tool: generate_document
- [ ] 在 `mcp_server.py` 新增 `generate_document` tool
- [ ] 建立 MD2DOC Agent system prompt（內嵌完整規範）
  - 包含七大核心規範
  - 包含對話語法詳細說明
  - 包含轉換範例
- [ ] 呼叫 AI 產生內容
- [ ] 使用驗證器檢查格式
- [ ] 若驗證失敗，將錯誤回傳給 AI 重新產生（最多 3 次）
- [ ] 驗證通過後自動建立分享連結
- [ ] 回傳連結和密碼

**驗證**：Tool 可產生並驗證正確格式的 MD2DOC 內容

### 6. LineBot Agent Prompt 更新
- [ ] 更新 linebot_agents.py 的 system prompt
- [ ] 新增判斷「產生簡報/文件」意圖的指引
- [ ] 說明何時呼叫 generate_presentation / generate_document
- [ ] 建立 migration 更新資料庫 prompt

**驗證**：LineBot AI 可正確判斷並呼叫 MCP Tools

### 7. MD2PPT shareToken 支援
- [ ] 檢測 URL 中的 shareToken 參數
- [ ] 顯示密碼輸入對話框
- [ ] 呼叫後端 API 驗證密碼
- [ ] 驗證成功後載入內容
- [ ] 錯誤處理（密碼錯誤、連結過期、已鎖定）

**驗證**：MD2PPT 可透過分享連結載入內容

### 8. MD2DOC shareToken 支援
- [ ] 檢測 URL 中的 shareToken 參數
- [ ] 顯示密碼輸入對話框
- [ ] 呼叫後端 API 驗證密碼
- [ ] 驗證成功後載入內容
- [ ] 錯誤處理

**驗證**：MD2DOC 可透過分享連結載入內容

### 9. 整合測試
- [ ] 測試 LineBot 產生簡報流程
- [ ] 測試 LineBot 產生文件流程
- [ ] 測試分享連結密碼驗證
- [ ] 測試過期連結處理
- [ ] 測試錯誤次數鎖定

**驗證**：完整流程可正常運作

### 10. 清理過期分享
- [ ] 建立定期清理任務或在 API 中清理過期記錄
- [ ] 清理超過 24 小時的分享連結

**驗證**：過期連結會被自動清理

## 依賴關係

```
Task 1 (資料庫)
    ↓
Task 2 (公開 API)
    ↓
Task 3 (格式驗證器)
    ↓
Task 4, 5 (MCP Tools) ← 可平行
    ↓
Task 6 (LineBot Prompt)
    ↓
Task 7, 8 (MD2PPT/MD2DOC) ← 可平行，外部專案
    ↓
Task 9 (整合測試)
    ↓
Task 10 (清理任務)
```

## 完成後的檔案變更

### 新增檔案
- `backend/migrations/versions/002_add_share_password_and_content.py`
- `backend/src/ching_tech_os/services/md_validators.py` - 格式驗證器

### 修改檔案
- `backend/src/ching_tech_os/models/share.py` - 新增 password, content 欄位
- `backend/src/ching_tech_os/services/share.py` - 密碼驗證、content 類型
- `backend/src/ching_tech_os/api/share.py` - 密碼驗證 API
- `backend/src/ching_tech_os/config.py` - CORS 設定
- `backend/src/ching_tech_os/services/mcp_server.py` - 新增 MCP Tools
- `backend/src/ching_tech_os/services/linebot_agents.py` - 更新 prompt

### 外部專案
- MD2PPT-Evolution: 新增 shareToken 處理
- MD2DOC-Evolution: 新增 shareToken 處理
