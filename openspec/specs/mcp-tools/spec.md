# mcp-tools Specification

## Purpose
TBD - created by archiving change extend-project-mcp. Update Purpose after archive.
## Requirements
### Requirement: 新增專案成員 MCP 工具
MCP Server SHALL 提供 `add_project_member` 工具讓 AI 助手新增專案成員。

#### Scenario: 新增內部成員
- **GIVEN** AI 助手有專案 ID 和成員資訊
- **WHEN** 呼叫 `add_project_member(project_id, name="王小明", role="工程師", is_internal=true)`
- **THEN** 系統在該專案新增內部成員
- **AND** 回傳新增的成員 ID 和資訊

#### Scenario: 新增外部聯絡人
- **GIVEN** AI 助手有專案 ID 和聯絡人資訊
- **WHEN** 呼叫 `add_project_member(project_id, name="客戶A", company="XX公司", is_internal=false)`
- **THEN** 系統在該專案新增外部聯絡人
- **AND** 回傳新增的成員資訊

#### Scenario: 專案不存在
- **WHEN** 呼叫 `add_project_member` 且專案 ID 不存在
- **THEN** 回傳錯誤訊息「專案不存在」

---

### Requirement: 新增專案里程碑 MCP 工具
MCP Server SHALL 提供 `add_project_milestone` 工具讓 AI 助手新增專案里程碑。

#### Scenario: 新增里程碑含預計日期
- **GIVEN** AI 助手有專案 ID 和里程碑資訊
- **WHEN** 呼叫 `add_project_milestone(project_id, name="設計完成", planned_date="2026-01-15")`
- **THEN** 系統在該專案新增里程碑
- **AND** 回傳新增的里程碑 ID 和資訊

#### Scenario: 新增里程碑指定類型
- **GIVEN** AI 助手有專案 ID
- **WHEN** 呼叫 `add_project_milestone(project_id, name="出貨", milestone_type="delivery")`
- **THEN** 系統新增指定類型的里程碑

#### Scenario: 專案不存在
- **WHEN** 呼叫 `add_project_milestone` 且專案 ID 不存在
- **THEN** 回傳錯誤訊息「專案不存在」

---

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

### Requirement: 準備檔案訊息 MCP 工具
MCP Server SHALL 提供 `prepare_file_message` 工具讓 AI 準備要發送的檔案訊息。

#### Scenario: 準備小圖片訊息
- **GIVEN** AI 找到 NAS 上的圖片檔案（jpg/png/gif/webp）
- **AND** 檔案大小 < 10MB
- **WHEN** 呼叫 `prepare_file_message(file_path="/mnt/nas/projects/.../xxx.png")`
- **THEN** 系統產生 24 小時有效的分享連結
- **AND** 回傳包含 `[FILE_MESSAGE:{"type":"image","url":"...","name":"xxx.png"}]` 的訊息

#### Scenario: 準備大檔案訊息
- **GIVEN** AI 找到 NAS 上的檔案
- **AND** 檔案不是圖片或大小 >= 10MB
- **WHEN** 呼叫 `prepare_file_message(file_path="...")`
- **THEN** 系統產生 24 小時有效的分享連結
- **AND** 回傳包含 `[FILE_MESSAGE:{"type":"file","url":"...","name":"...","size":"..."}]` 的訊息

#### Scenario: 檔案不存在
- **WHEN** 呼叫 `prepare_file_message` 且檔案路徑不存在
- **THEN** 回傳錯誤訊息「檔案不存在」

#### Scenario: 路徑超出允許範圍
- **WHEN** 呼叫 `prepare_file_message` 且路徑不在 `/mnt/nas/projects` 下
- **THEN** 回傳錯誤訊息「不允許存取此路徑」

### Requirement: 更新專案 MCP 工具
MCP Server SHALL 提供 `update_project` 工具讓 AI 助手更新專案資訊。

#### Scenario: 更新專案基本資訊
- **GIVEN** AI 助手有專案 ID 和要更新的資訊
- **WHEN** 呼叫 `update_project(project_id, name="新名稱", description="新描述")`
- **THEN** 系統更新專案的對應欄位
- **AND** 回傳更新後的專案資訊

#### Scenario: 更新專案狀態
- **GIVEN** AI 助手有專案 ID
- **WHEN** 呼叫 `update_project(project_id, status="completed")`
- **THEN** 系統更新專案狀態
- **AND** status 可選值：planning, in_progress, completed, on_hold

#### Scenario: 更新專案日期
- **GIVEN** AI 助手有專案 ID
- **WHEN** 呼叫 `update_project(project_id, start_date="2026-01-01", end_date="2026-06-30")`
- **THEN** 系統更新專案日期

#### Scenario: 專案不存在
- **WHEN** 呼叫 `update_project` 且專案 ID 不存在
- **THEN** 回傳錯誤訊息「專案不存在」

---

### Requirement: 更新里程碑 MCP 工具
MCP Server SHALL 提供 `update_milestone` 工具讓 AI 助手更新里程碑資訊。

#### Scenario: 更新里程碑狀態
- **GIVEN** AI 助手有里程碑 ID
- **WHEN** 呼叫 `update_milestone(milestone_id, status="completed", actual_date="2026-01-15")`
- **THEN** 系統更新里程碑狀態和實際完成日期

#### Scenario: 更新里程碑預計日期
- **GIVEN** AI 助手有里程碑 ID
- **WHEN** 呼叫 `update_milestone(milestone_id, planned_date="2026-02-01")`
- **THEN** 系統更新里程碑預計日期

#### Scenario: 更新里程碑名稱與備註
- **GIVEN** AI 助手有里程碑 ID
- **WHEN** 呼叫 `update_milestone(milestone_id, name="新名稱", notes="備註說明")`
- **THEN** 系統更新里程碑名稱和備註

#### Scenario: 里程碑不存在
- **WHEN** 呼叫 `update_milestone` 且里程碑 ID 不存在
- **THEN** 回傳錯誤訊息「里程碑不存在」

---

### Requirement: 更新專案成員 MCP 工具
MCP Server SHALL 提供 `update_project_member` 工具讓 AI 助手更新成員資訊。

#### Scenario: 更新成員角色
- **GIVEN** AI 助手有成員 ID
- **WHEN** 呼叫 `update_project_member(member_id, role="專案經理")`
- **THEN** 系統更新成員角色

#### Scenario: 更新成員聯絡資訊
- **GIVEN** AI 助手有成員 ID
- **WHEN** 呼叫 `update_project_member(member_id, email="new@email.com", phone="0912345678")`
- **THEN** 系統更新成員聯絡資訊

#### Scenario: 更新成員公司與備註
- **GIVEN** AI 助手有成員 ID
- **WHEN** 呼叫 `update_project_member(member_id, company="新公司", notes="備註")`
- **THEN** 系統更新成員公司和備註

#### Scenario: 成員不存在
- **WHEN** 呼叫 `update_project_member` 且成員 ID 不存在
- **THEN** 回傳錯誤訊息「成員不存在」

---

### Requirement: 新增專案會議 MCP 工具
MCP Server SHALL 提供 `add_project_meeting` 工具讓 AI 助手新增會議記錄。

#### Scenario: 新增會議（僅標題）
- **GIVEN** AI 助手有專案 ID
- **WHEN** 呼叫 `add_project_meeting(project_id, title="週會")`
- **THEN** 系統在該專案新增會議
- **AND** 回傳新增的會議 ID 和資訊

#### Scenario: 新增會議含日期
- **GIVEN** AI 助手有專案 ID 和會議資訊
- **WHEN** 呼叫 `add_project_meeting(project_id, title="設計審查", meeting_date="2026-01-10")`
- **THEN** 系統新增會議並設定日期

#### Scenario: 新增會議含完整記錄
- **GIVEN** AI 助手有專案 ID 和完整會議資訊
- **WHEN** 呼叫 `add_project_meeting(project_id, title="週會", meeting_date="2026-01-07", location="會議室A", content="# 會議內容\n...", attendees="王小明, 李小華")`
- **THEN** 系統新增會議記錄包含完整內容

#### Scenario: 專案不存在
- **WHEN** 呼叫 `add_project_meeting` 且專案 ID 不存在
- **THEN** 回傳錯誤訊息「專案不存在」

---

### Requirement: 更新專案會議 MCP 工具
MCP Server SHALL 提供 `update_project_meeting` 工具讓 AI 助手更新會議記錄。

#### Scenario: 更新會議內容
- **GIVEN** AI 助手有會議 ID
- **WHEN** 呼叫 `update_project_meeting(meeting_id, content="# 更新後的會議內容\n...")`
- **THEN** 系統更新會議內容

#### Scenario: 更新會議時間地點
- **GIVEN** AI 助手有會議 ID
- **WHEN** 呼叫 `update_project_meeting(meeting_id, meeting_date="2026-01-08 10:00", location="線上")`
- **THEN** 系統更新會議時間和地點

#### Scenario: 更新會議標題與參與者
- **GIVEN** AI 助手有會議 ID
- **WHEN** 呼叫 `update_project_meeting(meeting_id, title="新標題", attendees="全員")`
- **THEN** 系統更新會議標題和參與者

#### Scenario: 會議不存在
- **WHEN** 呼叫 `update_project_meeting` 且會議 ID 不存在
- **THEN** 回傳錯誤訊息「會議不存在」

