# mcp-tools Spec Delta

## ADDED Requirements

### Requirement: 搜尋 NAS 共享檔案 MCP 工具
MCP Server SHALL 提供 `search_nas_files` 工具讓 AI 助手搜尋 NAS 共享掛載點中的檔案。

#### Scenario: 基本關鍵字搜尋
- **GIVEN** AI 助手收到用戶查詢「找一下亦達 layout pdf」
- **WHEN** 呼叫 `search_nas_files(keywords="亦達,layout", file_types="pdf")`
- **THEN** 系統列出路徑包含「亦達」且包含「layout」的 PDF 檔案（大小寫不敏感）
- **AND** 回傳檔案路徑列表（最多 100 筆）

#### Scenario: 搜尋多種檔案類型
- **GIVEN** AI 助手需要搜尋多種檔案
- **WHEN** 呼叫 `search_nas_files(keywords="亦達", file_types="pdf,xlsx,dwg")`
- **THEN** 系統列出符合任一檔案類型的檔案

#### Scenario: 僅指定關鍵字
- **GIVEN** AI 助手收到用戶查詢「給我亦達時程規劃」
- **WHEN** 呼叫 `search_nas_files(keywords="亦達")`
- **THEN** 系統列出路徑包含「亦達」的所有檔案
- **AND** AI 從列表中語意匹配「時程規劃」找到「時間估算.xlsx」

#### Scenario: 大小寫不敏感匹配
- **GIVEN** 用戶輸入小寫「layout」但實際資料夾是「Layout」
- **WHEN** 呼叫 `search_nas_files(keywords="layout")`
- **THEN** 系統能匹配到「Layout」資料夾下的檔案

#### Scenario: 無符合結果
- **WHEN** 呼叫 `search_nas_files(keywords="不存在的關鍵字")`
- **THEN** 回傳空列表和提示訊息

#### Scenario: 安全限制
- **GIVEN** 搜尋範圍限定於 `/mnt/nas/projects`（唯讀掛載）
- **WHEN** AI 嘗試搜尋其他路徑
- **THEN** 系統拒絕並回傳錯誤

---

### Requirement: 取得 NAS 檔案資訊 MCP 工具
MCP Server SHALL 提供 `get_nas_file_info` 工具讓 AI 助手取得特定檔案的詳細資訊。

#### Scenario: 取得檔案詳細資訊
- **GIVEN** AI 已透過搜尋找到檔案路徑
- **WHEN** 呼叫 `get_nas_file_info(file_path="/mnt/nas/projects/亞達光學/擎添資料/Layout/xxx.pdf")`
- **THEN** 回傳檔案大小、修改時間、完整路徑
- **AND** 回傳可供分享的相對路徑或建議（供後續功能使用）

#### Scenario: 檔案不存在
- **WHEN** 呼叫 `get_nas_file_info` 且檔案不存在
- **THEN** 回傳錯誤訊息「檔案不存在」

#### Scenario: 路徑超出允許範圍
- **WHEN** 呼叫 `get_nas_file_info` 且路徑不在 `/mnt/nas/projects` 下
- **THEN** 回傳錯誤訊息「不允許存取此路徑」

---

### Requirement: 擴充分享連結支援 NAS 檔案
現有的 `create_share_link` MCP 工具 SHALL 擴充支援 `nas_file` resource_type，讓 AI 助手產生 NAS 檔案的暫時下載連結。

#### Scenario: 透過現有工具產生檔案連結
- **GIVEN** 用戶說「給我亦達layout圖」且 AI 已找到檔案
- **WHEN** 呼叫 `create_share_link(resource_type="nas_file", resource_id="/mnt/nas/projects/.../xxx.pdf", expires_in="24h")`
- **THEN** 系統產生暫時下載連結
- **AND** 回傳連結 URL 和過期時間

#### Scenario: 設定過期時間
- **WHEN** 呼叫 `create_share_link(resource_type="nas_file", resource_id="...", expires_in="1h")`
- **THEN** 連結在 1 小時後過期
- **AND** 預設過期時間為 24 小時

#### Scenario: 檔案不存在
- **WHEN** 呼叫 `create_share_link` 且 resource_type="nas_file" 但檔案不存在
- **THEN** 回傳錯誤訊息「檔案不存在」

#### Scenario: 路徑超出允許範圍
- **WHEN** 呼叫 `create_share_link` 且 resource_id 路徑不在 `/mnt/nas/projects` 下
- **THEN** 回傳錯誤訊息「不允許存取此路徑」

#### Scenario: 公開連結存取下載
- **GIVEN** 用戶透過分享連結存取
- **WHEN** 開啟 `/s/{token}` 且 resource_type="nas_file"
- **THEN** 直接下載檔案（或顯示下載頁面）

---

### Requirement: Line Bot 直接發送檔案
當 AI 找到單一檔案且大小合理時，Line Bot SHALL 根據檔案類型選擇最佳發送方式。

#### Scenario: 直接發送小圖片
- **GIVEN** 用戶說「給我亦達layout圖」且找到單一 PNG/JPG 檔案
- **AND** 檔案大小 < 5MB
- **WHEN** AI 決定直接發送
- **THEN** 系統產生暫時公開連結
- **AND** Line Bot 以 ImageMessage 直接發送圖片（用戶可直接查看）

#### Scenario: 直接發送小檔案
- **GIVEN** 用戶要求取得檔案且找到單一 PDF/XLSX/DOC 等檔案
- **AND** 檔案大小 < 50MB
- **WHEN** AI 決定直接發送
- **THEN** 系統產生暫時公開連結
- **AND** Line Bot 以 FileMessage 直接發送檔案（用戶可直接儲存）

#### Scenario: 大檔案改用連結
- **GIVEN** 找到檔案但大小超過限制（圖片 >= 5MB，其他檔案 >= 50MB）
- **WHEN** AI 判斷檔案過大
- **THEN** 改用文字連結方式回覆

#### Scenario: 多檔案先詢問
- **GIVEN** 找到多個符合條件的檔案
- **WHEN** AI 準備回覆
- **THEN** 列出檔案清單並詢問用戶要哪一個

#### Scenario: 用戶要求全部
- **GIVEN** 找到多個檔案且用戶明確說「都給我」或「全部」
- **WHEN** AI 判斷用戶要多個檔案
- **THEN** 提供多個下載連結（或逐一發送小檔案）

---

### Requirement: 檔案管理器產生暫時連結
檔案管理器 UI SHALL 提供對 NAS 檔案產生暫時分享連結的功能，但僅限於系統掛載點可存取的檔案。

#### Scenario: 右鍵選單產生連結（可分享路徑）
- **GIVEN** 用戶在檔案管理器瀏覽「擎添共用區/在案資料分享」下的檔案
- **AND** 該路徑對應系統掛載點 `/mnt/nas/projects`
- **WHEN** 對檔案右鍵選擇「產生分享連結」
- **THEN** 系統產生暫時下載連結
- **AND** 顯示連結並可複製

#### Scenario: 不可分享的路徑
- **GIVEN** 用戶在檔案管理器瀏覽其他 NAS 共享（如私人共享）
- **AND** 該路徑不在系統掛載點範圍內
- **WHEN** 用戶查看右鍵選單
- **THEN** 「產生分享連結」選項不顯示或顯示為灰色
- **OR** 選擇後顯示提示「此檔案無法產生公開連結」

#### Scenario: 設定連結有效期
- **GIVEN** 用戶產生分享連結
- **WHEN** 選擇有效期（1小時/24小時/7天）
- **THEN** 連結在指定時間後過期

#### Scenario: 路徑對應規則
- **GIVEN** 檔案管理器路徑為 `/擎添共用區/在案資料分享/亦達光學/xxx.pdf`
- **WHEN** 系統驗證可分享性
- **THEN** 對應到系統掛載點 `/mnt/nas/projects/亦達光學/xxx.pdf`
- **AND** 驗證檔案存在後允許產生連結

---

### Requirement: 定期清理過期連結
系統 SHALL 定期清理過期的分享連結，避免資料庫累積過多無效記錄。

#### Scenario: 自動清理過期連結
- **GIVEN** 系統每日執行清理任務（或每小時）
- **WHEN** 掃描 `public_share_links` 表
- **THEN** 刪除所有 `expires_at < 當前時間` 的記錄

#### Scenario: 保留永久連結
- **GIVEN** 連結的 `expires_at` 為 NULL（永久）
- **WHEN** 執行清理任務
- **THEN** 該連結不會被刪除
