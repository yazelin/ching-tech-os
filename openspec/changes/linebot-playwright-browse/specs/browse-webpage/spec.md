## ADDED Requirements

### Requirement: browse_webpage MCP 工具可擷取 JS 渲染網頁內容

系統 SHALL 提供 `browse_webpage` MCP 工具，使用 Playwright Chromium headless 開啟指定 URL，等待 JavaScript 渲染完成後回傳頁面的 accessibility snapshot。

工具參數：
- `url`（必填）：目標網頁 URL
- `max_length`（選填，預設 8000）：回傳內容最大字數
- `timeout`（選填，預設 30000）：頁面載入超時毫秒數
- `ctos_user_id`（選填）：CTOS 用戶 ID

#### Scenario: 成功擷取 SPA 網頁

- **WHEN** 呼叫 `browse_webpage(url="https://example-spa.com")`
- **THEN** 系統啟動 Chromium headless，導航到 URL，等待渲染完成，回傳包含頁面標題與 accessibility snapshot 文字的結果

#### Scenario: 擷取靜態網頁

- **WHEN** 呼叫 `browse_webpage(url="https://example.com")`
- **THEN** 系統同樣能正常擷取並回傳內容（不限於 SPA）

### Requirement: 僅允許 HTTPS URL

系統 SHALL 拒絕非 HTTPS 的 URL（包括 `http://`、`file://`、`javascript:` 等 scheme）。

#### Scenario: 拒絕 HTTP URL

- **WHEN** 呼叫 `browse_webpage(url="http://example.com")`
- **THEN** 系統回傳錯誤訊息，不啟動瀏覽器

#### Scenario: 拒絕 file:// URL

- **WHEN** 呼叫 `browse_webpage(url="file:///etc/passwd")`
- **THEN** 系統回傳錯誤訊息，不啟動瀏覽器

### Requirement: 回傳格式為 accessibility snapshot

系統 SHALL 將 Playwright 的 accessibility snapshot tree 轉換為可讀文字格式：
- `heading` 節點 → Markdown 標題（依 level：`#`、`##`、`###` 等）
- `link` 節點 → `[文字](url)`
- `list` / `listitem` 節點 → `- 項目`
- 其餘節點 → 取 `name` 屬性作為純文字

#### Scenario: 保留語意結構

- **WHEN** 網頁包含標題、連結、列表等元素
- **THEN** 回傳的文字 MUST 保留對應的 Markdown 結構標記

#### Scenario: 頁面無可讀內容

- **WHEN** 頁面的 accessibility snapshot 為空或無文字節點
- **THEN** 系統回傳「頁面無可讀內容」錯誤訊息

### Requirement: 內容長度可設定且預設 8000 字

系統 SHALL 支援 `max_length` 參數控制回傳內容的最大字數，預設為 8000。

#### Scenario: 內容超過 max_length

- **WHEN** 頁面文字超過 `max_length` 字
- **THEN** 系統截斷內容至 `max_length` 字，並在末尾附加截斷提示

#### Scenario: 自訂 max_length

- **WHEN** 呼叫 `browse_webpage(url="...", max_length=15000)`
- **THEN** 系統回傳最多 15000 字的內容

### Requirement: 頁面載入超時處理

系統 SHALL 先以 `networkidle` 等待頁面載入；若超時，MUST fallback 到 `domcontentloaded` 並額外等待 3 秒後擷取當前內容。

#### Scenario: networkidle 成功

- **WHEN** 頁面在 timeout 內達到 networkidle 狀態
- **THEN** 系統立即擷取 snapshot 並回傳

#### Scenario: networkidle 超時 fallback

- **WHEN** 頁面在 timeout 內未達到 networkidle
- **THEN** 系統以 domcontentloaded 重新等待，額外等 3 秒後擷取當前已渲染的內容

#### Scenario: 完全超時

- **WHEN** 頁面連 domcontentloaded 都無法在 timeout 內完成
- **THEN** 系統回傳「頁面載入超時」錯誤訊息

### Requirement: 瀏覽器每次新開新關

系統 SHALL 在每次 `browse_webpage` 呼叫時啟動新的 Chromium 實例，並在擷取完成後（含錯誤情況）立即關閉，不保持常駐。

#### Scenario: 正常關閉

- **WHEN** 擷取成功或失敗
- **THEN** 瀏覽器實例 MUST 在回傳前完全關閉

#### Scenario: 異常情況

- **WHEN** 擷取過程中發生未預期例外
- **THEN** 瀏覽器實例 MUST 透過 finally 區塊確保關閉

### Requirement: Chromium 不可用時優雅降級

系統 SHALL 在 Playwright 或 Chromium 不可用時回傳清楚的錯誤訊息，不造成 MCP server crash。

#### Scenario: Chromium 未安裝

- **WHEN** 系統未安裝 Chromium binary
- **THEN** 回傳「瀏覽器啟動失敗，請確認已安裝 Chromium」錯誤訊息
