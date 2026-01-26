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
現有的 `create_share_link` MCP 工具 SHALL 擴充支援 `project_attachment` resource_type，讓 AI 助手產生專案附件的暫時下載連結。

#### Scenario: 為專案附件建立分享連結
- **GIVEN** 專案有一個附件
- **WHEN** 呼叫 `create_share_link(resource_type="project_attachment", resource_id=附件UUID)`
- **THEN** 系統建立公開分享連結
- **AND** 回傳包含下載 URL 的連結資訊

#### Scenario: 透過分享連結下載專案附件
- **GIVEN** 存在一個 `project_attachment` 類型的分享連結
- **WHEN** 使用者訪問 `/s/{token}` 或 `/api/public/{token}/download`
- **THEN** 系統讀取附件內容並回傳檔案

#### Scenario: 專案附件路徑解析
- **GIVEN** 附件 storage_path 為 `nas://linebot/files/...` 或 `nas://projects/...`
- **WHEN** 系統讀取附件內容
- **THEN** 根據路徑前綴選擇對應的檔案服務讀取

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

### Requirement: 發包/交貨管理 MCP 工具
MCP Server SHALL 提供發包/交貨管理工具，讓 AI 助手可以協助使用者管理專案發包期程。

#### Scenario: add_delivery_schedule 工具
- **GIVEN** AI 收到使用者關於新增發包記錄的請求
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **THEN** 工具參數包含：
  - `project_id`：專案 UUID（必填）
  - `vendor`：廠商名稱（必填）
  - `item`：料件名稱（必填）
  - `quantity`：數量與單位（選填，如「2 台」）
  - `order_date`：發包日期（選填，格式 YYYY-MM-DD）
  - `expected_delivery_date`：預計交貨日（選填，格式 YYYY-MM-DD）
  - `status`：狀態（選填，預設 pending）
  - `notes`：備註（選填）
- **AND** 系統建立發包記錄
- **AND** 返回「已新增發包記錄：{廠商} - {料件}」

#### Scenario: update_delivery_schedule 工具
- **GIVEN** AI 收到使用者關於更新發包狀態的請求
- **WHEN** AI 呼叫 `update_delivery_schedule` 工具
- **THEN** 工具參數包含：
  - `project_id`：專案 UUID（必填）
  - `delivery_id`：發包記錄 UUID（選填，直接指定）
  - `vendor`：廠商名稱（選填，用於匹配）
  - `item`：料件名稱（選填，用於匹配）
  - `new_status`：新狀態（選填）
  - `actual_delivery_date`：實際到貨日（選填，格式 YYYY-MM-DD）
  - `expected_delivery_date`：更新預計交貨日（選填）
  - `new_notes`：更新備註（選填）
- **WHEN** 透過 vendor + item 匹配找到唯一記錄
- **THEN** 更新該記錄並返回成功訊息
- **WHEN** 找到多筆匹配記錄
- **THEN** 返回錯誤，列出所有匹配項目請使用者選擇
- **WHEN** 找不到匹配記錄
- **THEN** 返回錯誤，提示無此發包記錄

#### Scenario: get_delivery_schedules 工具
- **GIVEN** AI 收到使用者關於查詢發包狀態的請求
- **WHEN** AI 呼叫 `get_delivery_schedules` 工具
- **THEN** 工具參數包含：
  - `project_id`：專案 UUID（必填）
  - `status`：狀態過濾（選填）
  - `vendor`：廠商過濾（選填）
  - `limit`：最大數量（選填，預設 20）
- **AND** 系統返回格式化的發包列表

---

### Requirement: Line Bot System Prompt 更新
Line Bot 的 system prompt SHALL 說明發包/交貨管理工具的用途。

#### Scenario: Prompt 包含工具說明
- **WHEN** Line Bot AI 收到 system prompt
- **THEN** prompt 包含以下工具說明：
  - `add_delivery_schedule`：新增發包/交貨記錄
  - `update_delivery_schedule`：更新發包狀態或到貨日期
  - `get_delivery_schedules`：查詢發包列表
- **AND** prompt 說明四種狀態的意義：
  - `pending`：待發包
  - `ordered`：已發包
  - `delivered`：已到貨
  - `completed`：已完成

#### Scenario: AI 正確使用工具
- **GIVEN** 使用者說「A 公司的水切爐已經到貨了」
- **WHEN** AI 處理此訊息
- **THEN** AI 應呼叫 `update_delivery_schedule` 工具
- **AND** 設定 `vendor` 為 "A 公司"
- **AND** 設定 `item` 為 "水切爐"
- **AND** 設定 `new_status` 為 "delivered"
- **AND** 設定 `actual_delivery_date` 為當天日期

### Requirement: add_project_link
系統 SHALL 提供 MCP 工具讓 AI 新增專案連結。

#### Scenario: 新增專案連結
Given AI 收到用戶要求新增連結
When AI 呼叫 add_project_link(project_id, title, url, description?)
Then 系統在 project_links 表建立記錄
And 回傳成功訊息包含連結標題

### Requirement: get_project_links
系統 SHALL 提供 MCP 工具讓 AI 查詢專案連結列表。

#### Scenario: 查詢專案連結
Given 專案有連結記錄
When AI 呼叫 get_project_links(project_id)
Then 系統回傳連結列表（標題、URL、描述）

### Requirement: update_project_link
系統 SHALL 提供 MCP 工具讓 AI 更新專案連結資訊。

#### Scenario: 更新連結標題
Given 專案有一個連結
When AI 呼叫 update_project_link(link_id, title="新標題")
Then 系統更新連結標題
And 回傳成功訊息

### Requirement: delete_project_link
系統 SHALL 提供 MCP 工具讓 AI 刪除專案連結。

#### Scenario: 刪除連結
Given 專案有一個連結
When AI 呼叫 delete_project_link(link_id)
Then 系統刪除連結記錄
And 回傳成功訊息

### Requirement: add_project_attachment
系統 SHALL 提供 MCP 工具讓 AI 從 NAS 路徑添加附件到專案。

#### Scenario: 從 Line 附件添加
Given 用戶在 Line 發送了圖片
And AI 用 get_message_attachments 取得 NAS 路徑
When AI 呼叫 add_project_attachment(project_id, nas_path, description?)
Then 系統建立附件記錄（storage_path 使用 nas:// 格式）
And 回傳成功訊息包含檔案名稱

#### Scenario: 從 NAS 檔案添加
Given NAS 上有檔案
And AI 用 search_nas_files 取得路徑
When AI 呼叫 add_project_attachment(project_id, nas_path)
Then 系統建立附件記錄
And 回傳成功訊息

### Requirement: get_project_attachments
系統 SHALL 提供 MCP 工具讓 AI 查詢專案附件列表。

#### Scenario: 查詢專案附件
Given 專案有附件記錄
When AI 呼叫 get_project_attachments(project_id)
Then 系統回傳附件列表（檔名、類型、大小、描述）

### Requirement: update_project_attachment
系統 SHALL 提供 MCP 工具讓 AI 更新專案附件描述。

#### Scenario: 更新附件描述
Given 專案有一個附件
When AI 呼叫 update_project_attachment(attachment_id, description="新描述")
Then 系統更新附件描述
And 回傳成功訊息

### Requirement: delete_project_attachment
系統 SHALL 提供 MCP 工具讓 AI 刪除專案附件。

#### Scenario: 刪除附件
Given 專案有一個附件
When AI 呼叫 delete_project_attachment(attachment_id)
Then 系統刪除附件記錄
And 回傳成功訊息

### Requirement: PDF 轉圖片 MCP 工具
MCP Server SHALL 提供 `convert_pdf_to_images` 工具讓 AI 將 PDF 檔案轉換為圖片。

#### Scenario: 查詢 PDF 頁數（不轉換）
- **GIVEN** AI 需要先知道 PDF 有幾頁
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="0")`
- **THEN** 系統只回傳 PDF 頁數資訊，不進行轉換
- **AND** 回傳格式包含 `total_pages` 和 `converted_pages: 0`

#### Scenario: 單頁 PDF 轉換
- **GIVEN** AI 有單頁 PDF 檔案路徑
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...")`
- **THEN** 系統將該頁轉換為 PNG 圖片
- **AND** 圖片儲存到 NAS 的 `linebot/files/pdf-converted/{date}/{uuid}/` 目錄
- **AND** 回傳轉換結果，包含圖片路徑

#### Scenario: 指定頁面範圍轉換
- **GIVEN** AI 需要轉換特定頁面
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="1-3")`
- **THEN** 系統只轉換第 1、2、3 頁
- **AND** 回傳轉換的圖片路徑列表

#### Scenario: 轉換指定的單頁
- **GIVEN** AI 只需要轉換特定一頁
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="2")`
- **THEN** 系統只轉換第 2 頁

#### Scenario: 轉換多個不連續頁面
- **GIVEN** AI 需要轉換不連續的頁面
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="1,3,5")`
- **THEN** 系統轉換第 1、3、5 頁

#### Scenario: 轉換全部頁面
- **GIVEN** AI 需要轉換全部頁面
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="all")`
- **THEN** 系統轉換所有頁面（最多 max_pages 頁）

#### Scenario: 指定輸出格式
- **GIVEN** AI 需要特定格式的圖片
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", output_format="jpg")`
- **THEN** 系統將 PDF 轉換為 JPG 格式圖片

#### Scenario: 指定解析度
- **GIVEN** AI 需要高解析度圖片
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", dpi=300)`
- **THEN** 系統使用 300 DPI 進行轉換

#### Scenario: PDF 檔案不存在
- **WHEN** 呼叫 `convert_pdf_to_images` 且 PDF 路徑不存在
- **THEN** 回傳錯誤訊息「PDF 檔案不存在」

#### Scenario: 非 PDF 檔案
- **WHEN** 呼叫 `convert_pdf_to_images` 且檔案不是 PDF 格式
- **THEN** 回傳錯誤訊息「檔案不是 PDF 格式」

#### Scenario: 轉換成功回傳格式
- **WHEN** 轉換成功
- **THEN** 回傳 JSON 格式結果：
  - `success`: true
  - `total_pages`: PDF 總頁數
  - `converted_pages`: 實際轉換的頁數
  - `images`: 圖片路徑陣列
  - `message`: 人類可讀的結果描述

#### Scenario: 搭配 prepare_file_message 發送圖片
- **GIVEN** AI 已完成 PDF 轉換
- **WHEN** AI 呼叫 `prepare_file_message` 傳入轉換後的圖片路徑
- **THEN** 系統準備檔案訊息供 Line Bot 發送
- **AND** 用戶可以在 Line 中直接查看圖片

---

### Requirement: PDF 轉換工具參數規格
`convert_pdf_to_images` 工具 SHALL 支援以下參數：

#### Scenario: 工具參數定義
- **WHEN** AI 呼叫 `convert_pdf_to_images` 工具
- **THEN** 工具接受以下參數：
  - `pdf_path`：PDF 檔案路徑（必填）
  - `pages`：要轉換的頁面，預設 "all"
    - "0"：只查詢頁數，不轉換
    - "1"：只轉換第 1 頁
    - "1-3"：轉換第 1 到 3 頁
    - "1,3,5"：轉換第 1、3、5 頁
    - "all"：轉換全部頁面
  - `output_format`：輸出格式，可選 "png"（預設）或 "jpg"
  - `dpi`：解析度，預設 150，範圍 72-600
  - `max_pages`：最大頁數限制，預設 20

---

### Requirement: 專案附件 PDF 轉換支援
`get_project_attachments` 工具 SHALL 回傳附件的儲存路徑，讓 AI 可以轉換專案附件中的 PDF。

#### Scenario: 查詢專案附件包含路徑
- **GIVEN** 專案有 PDF 附件
- **WHEN** AI 呼叫 `get_project_attachments(project_id="...")`
- **THEN** 回傳結果包含每個附件的 `路徑` 欄位（storage_path）
- **AND** AI 可以使用該路徑呼叫 `convert_pdf_to_images`

#### Scenario: 轉換專案附件 PDF
- **GIVEN** AI 從 `get_project_attachments` 取得 PDF 附件路徑
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="nas://...")`
- **THEN** 系統轉換該 PDF 為圖片
- **AND** AI 可透過 `prepare_file_message` 發送給用戶

### Requirement: 物料查詢 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以查詢物料與庫存。

#### Scenario: AI 查詢物料列表
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 keyword 參數（可選）
- **THEN** 系統返回匹配的物料列表
- **AND** 每個物料顯示名稱、型號、規格、存放庫位、目前庫存、單位

#### Scenario: AI 查詢單一物料詳情
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 item_id 參數
- **THEN** 系統返回該物料的完整資訊
- **AND** 包含型號、存放庫位、近期進出貨記錄摘要

#### Scenario: 查詢庫存不足物料
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 low_stock=true 參數
- **THEN** 系統返回庫存低於最低庫存量的物料列表

---

### Requirement: 物料新增 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以新增物料。

#### Scenario: AI 新增物料
- **WHEN** AI 呼叫 `add_inventory_item` 工具
- **AND** 提供 name 參數（必填）
- **AND** 可選提供 model、specification、unit、category、default_vendor、storage_location、min_stock、notes 參數
- **THEN** 系統建立新物料記錄
- **AND** 初始庫存設為 0
- **AND** 返回建立成功訊息與物料 ID

#### Scenario: 物料名稱重複檢查
- **WHEN** AI 呼叫 `add_inventory_item` 工具
- **AND** 已存在相同名稱的物料
- **THEN** 系統返回錯誤訊息
- **AND** 提示使用不同名稱或更新現有物料

---

### Requirement: 進貨記錄 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以記錄進貨。

#### Scenario: AI 記錄進貨（依物料 ID）
- **WHEN** AI 呼叫 `record_inventory_in` 工具
- **AND** 提供 item_id 和 quantity 參數（必填）
- **AND** 可選提供 vendor、project_id、transaction_date、notes 參數
- **THEN** 系統建立進貨記錄
- **AND** 自動增加該物料庫存
- **AND** 返回進貨成功訊息

#### Scenario: AI 記錄進貨（依物料名稱）
- **WHEN** AI 呼叫 `record_inventory_in` 工具
- **AND** 提供 item_name 和 quantity 參數（必填）
- **THEN** 系統搜尋匹配的物料
- **WHEN** 找到唯一匹配
- **THEN** 建立進貨記錄
- **WHEN** 找到多個匹配
- **THEN** 返回候選清單請使用者確認

#### Scenario: 進貨關聯專案
- **WHEN** AI 呼叫 `record_inventory_in` 工具
- **AND** 提供 project_id 或 project_name 參數
- **THEN** 系統將此進貨記錄關聯到指定專案

---

### Requirement: 出貨記錄 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以記錄出貨。

#### Scenario: AI 記錄出貨（依物料 ID）
- **WHEN** AI 呼叫 `record_inventory_out` 工具
- **AND** 提供 item_id 和 quantity 參數（必填）
- **AND** 可選提供 project_id、transaction_date、notes 參數
- **THEN** 系統建立出貨記錄
- **AND** 自動減少該物料庫存
- **AND** 返回出貨成功訊息

#### Scenario: AI 記錄出貨（依物料名稱）
- **WHEN** AI 呼叫 `record_inventory_out` 工具
- **AND** 提供 item_name 和 quantity 參數（必填）
- **THEN** 系統搜尋匹配的物料
- **WHEN** 找到唯一匹配
- **THEN** 建立出貨記錄
- **WHEN** 找到多個匹配
- **THEN** 返回候選清單請使用者確認

#### Scenario: 出貨庫存不足警告
- **WHEN** AI 呼叫 `record_inventory_out` 工具
- **AND** 出貨數量大於目前庫存
- **THEN** 系統返回警告訊息
- **AND** 仍允許建立記錄（允許負庫存）
- **AND** 提醒用戶庫存將變為負數

---

### Requirement: 庫存調整 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以調整庫存（盤點校正）。

#### Scenario: AI 調整庫存
- **WHEN** AI 呼叫 `adjust_inventory` 工具
- **AND** 提供 item_id 或 item_name 和 new_quantity 參數（必填）
- **AND** 提供 reason 參數（必填，如「盤點調整」、「損耗」）
- **THEN** 系統計算調整差額
- **AND** 建立對應的進貨或出貨記錄
- **AND** 記錄備註說明調整原因
- **AND** 返回調整成功訊息

#### Scenario: 庫存調整記錄
- **WHEN** 系統執行庫存調整
- **THEN** 若新數量 > 目前庫存，建立進貨記錄
- **THEN** 若新數量 < 目前庫存，建立出貨記錄
- **AND** 備註自動加上「[庫存調整] {reason}」前綴

---

### Requirement: 物料管理 Line Bot Prompt
Line Bot 助理 SHALL 包含物料管理功能的使用說明。

#### Scenario: Prompt 包含物料管理工具
- **WHEN** Line Bot 收到物料相關訊息
- **THEN** AI 可識別並使用物料管理工具
- **AND** Prompt 說明包含：
  - query_inventory: 查詢物料/庫存
  - add_inventory_item: 新增物料（支援型號、存放庫位）
  - record_inventory_in: 記錄進貨
  - record_inventory_out: 記錄出貨
  - adjust_inventory: 庫存調整
  - add_inventory_order: 新增訂購記錄
  - update_inventory_order: 更新訂購記錄
  - get_inventory_orders: 查詢訂購記錄

#### Scenario: 物料管理對話範例
- **WHEN** 使用者說「查詢螺絲的庫存」
- **THEN** AI 呼叫 `query_inventory` 並返回結果（包含型號、庫位）
- **WHEN** 使用者說「新增物料 M8 不鏽鋼螺絲，型號 SS304-M8x20，存放在 A-1-3」
- **THEN** AI 呼叫 `add_inventory_item` 並設定 model 和 storage_location
- **WHEN** 使用者說「訂購 M8 螺絲 500 個，預計下週三交貨」
- **THEN** AI 呼叫 `add_inventory_order` 建立訂購記錄

---

### Requirement: 訂購記錄新增 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以新增物料訂購記錄。

#### Scenario: AI 新增訂購記錄（依物料 ID）
- **WHEN** AI 呼叫 `add_inventory_order` 工具
- **AND** 提供 item_id 和 order_quantity 參數（必填）
- **AND** 可選提供 order_date、expected_delivery_date、vendor、project_id、project_name、notes 參數
- **THEN** 系統建立訂購記錄
- **AND** 狀態預設為 pending
- **AND** 返回建立成功訊息

#### Scenario: AI 新增訂購記錄（依物料名稱）
- **WHEN** AI 呼叫 `add_inventory_order` 工具
- **AND** 提供 item_name 和 order_quantity 參數
- **THEN** 系統搜尋匹配的物料
- **WHEN** 找到唯一匹配
- **THEN** 建立訂購記錄
- **WHEN** 找到多個匹配
- **THEN** 返回候選清單請使用者確認

#### Scenario: 訂購關聯專案
- **WHEN** AI 呼叫 `add_inventory_order` 工具
- **AND** 提供 project_id 或 project_name 參數
- **THEN** 系統將此訂購記錄關聯到指定專案

---

### Requirement: 訂購記錄更新 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以更新物料訂購記錄。

#### Scenario: AI 更新訂購狀態
- **WHEN** AI 呼叫 `update_inventory_order` 工具
- **AND** 提供 order_id 和 status 參數
- **THEN** 系統更新訂購記錄狀態
- **AND** 返回更新成功訊息

#### Scenario: AI 更新訂購資訊
- **WHEN** AI 呼叫 `update_inventory_order` 工具
- **AND** 提供 order_id 參數
- **AND** 可選提供 order_quantity、order_date、expected_delivery_date、actual_delivery_date、vendor、project_id、notes 參數
- **THEN** 系統更新訂購記錄對應欄位
- **AND** 返回更新成功訊息

#### Scenario: 設定交貨完成
- **WHEN** AI 呼叫 `update_inventory_order` 工具
- **AND** 設定 status="delivered" 和 actual_delivery_date
- **THEN** 系統更新訂購記錄為已交貨
- **AND** 返回成功訊息並提示可建立進貨記錄

#### Scenario: 訂購記錄不存在
- **WHEN** AI 呼叫 `update_inventory_order` 工具
- **AND** order_id 不存在
- **THEN** 系統返回錯誤訊息「訂購記錄不存在」

---

### Requirement: 訂購記錄查詢 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以查詢物料訂購記錄。

#### Scenario: AI 查詢物料訂購記錄
- **WHEN** AI 呼叫 `get_inventory_orders` 工具
- **AND** 提供 item_id 或 item_name 參數
- **THEN** 系統返回該物料的訂購記錄列表
- **AND** 每筆記錄顯示訂購數量、下單日期、預計交貨日、狀態、廠商、關聯專案

#### Scenario: 依狀態過濾訂購記錄
- **WHEN** AI 呼叫 `get_inventory_orders` 工具
- **AND** 提供 status 參數（pending/ordered/delivered/cancelled）
- **THEN** 系統返回指定狀態的訂購記錄

#### Scenario: 查詢待交貨訂購
- **WHEN** AI 呼叫 `get_inventory_orders` 工具
- **AND** 提供 status="ordered" 參數
- **THEN** 系統返回所有已下單但尚未交貨的訂購記錄
- **AND** 方便追蹤待交貨項目

### Requirement: 生成簡報 MCP 工具
The system SHALL provide a `generate_presentation` MCP tool that generates PowerPoint presentations.

The tool SHALL accept the following parameters:
- `topic`: Presentation topic (required if no outline_json)
- `num_slides`: Number of slides (2-20, default 5)
- `style`: Predefined style name (professional, casual, creative, minimal, dark, tech, nature, warm, elegant)
- `include_images`: Whether to auto-add images (default true)
- `image_source`: Image source (pexels, huggingface, nanobanana)
- `outline_json`: Direct outline JSON to skip AI generation
- `design_json`: Complete design specification from presentation designer (NEW)

When `design_json` is provided:
- The system SHALL use the design specification for colors, typography, layout, and decorations
- The system SHALL ignore the `style` parameter
- The system SHALL extract slides from `design_json.slides` if present

The `design_json` structure SHALL include:
- `design.colors`: Color scheme (background, title, subtitle, text, bullet, accent)
- `design.typography`: Font settings (title_font, title_size, body_font, body_size)
- `design.layout`: Layout settings (title_align, content_columns, image_position)
- `design.decorations`: Decoration settings (title_underline, accent_bar, page_number)
- `slides`: Array of slide definitions

#### Scenario: Generate with design_json
- **WHEN** user calls `generate_presentation` with `design_json` parameter
- **THEN** the system uses the design specification for visual styling
- **AND** the system generates a PowerPoint file with custom colors, fonts, and decorations

#### Scenario: Generate with predefined style (backward compatible)
- **WHEN** user calls `generate_presentation` with `style` parameter only
- **THEN** the system uses the predefined style configuration
- **AND** the behavior remains unchanged from Phase 1

#### Scenario: Invalid design_json format
- **WHEN** user provides malformed `design_json`
- **THEN** the system returns an error message describing the issue
- **AND** the system does not generate a partial presentation

### Requirement: 簡報風格選項
`generate_presentation` 工具 SHALL 支援以下風格選項：
- `professional`（預設）：專業簡潔風格
- `casual`：輕鬆休閒風格
- `creative`：創意活潑風格
- `minimal`：極簡風格

#### Scenario: 使用專業風格
- **WHEN** 呼叫 `generate_presentation(topic="季度報告", style="professional")`
- **THEN** 簡報使用深藍色調、正式字體、簡潔版面

#### Scenario: 使用創意風格
- **WHEN** 呼叫 `generate_presentation(topic="創意提案", style="creative")`
- **THEN** 簡報使用鮮明色彩、活潑版面配置

---

### Requirement: 簡報檔案命名與儲存
系統 SHALL 將生成的簡報儲存至 NAS，並使用結構化的檔名。

#### Scenario: 檔案命名格式
- **WHEN** 生成主題為「AI 應用」的簡報
- **THEN** 檔名格式為 `AI應用_20260122_143052.pptx`（主題_日期_時間）
- **AND** 儲存路徑為 `/mnt/nas/projects/ai-presentations/`

#### Scenario: 檔名包含特殊字元
- **GIVEN** 主題包含特殊字元如「產品/服務介紹」
- **WHEN** 生成簡報
- **THEN** 系統清理檔名中的特殊字元（斜線、冒號等）
- **AND** 產出有效的檔案名稱

### Requirement: 記憶管理 MCP 工具
MCP Server SHALL 提供記憶管理工具，讓 AI 可以在對話中管理記憶。

#### Scenario: add_memory 新增記憶
- **WHEN** AI 呼叫 `add_memory` 工具
- **AND** 提供 content 參數
- **AND** 提供 line_group_id（群組對話）或 line_user_id（個人對話）
- **THEN** 系統建立新的記憶
- **AND** 若未提供 title，系統自動產生合適的標題（取 content 前 20 字或由 AI 判斷）
- **AND** 回傳成功訊息和記憶 ID

#### Scenario: get_memories 查詢記憶
- **WHEN** AI 呼叫 `get_memories` 工具
- **AND** 提供 line_group_id 或 line_user_id
- **THEN** 系統回傳該群組或用戶的所有記憶列表
- **AND** 每筆記憶包含 id、title、content、is_active

#### Scenario: update_memory 更新記憶
- **WHEN** AI 呼叫 `update_memory` 工具
- **AND** 提供 memory_id 參數
- **AND** 提供要更新的欄位（title、content、is_active）
- **THEN** 系統更新該記憶
- **AND** 回傳成功訊息

#### Scenario: delete_memory 刪除記憶
- **WHEN** AI 呼叫 `delete_memory` 工具
- **AND** 提供 memory_id 參數
- **THEN** 系統刪除該記憶
- **AND** 回傳成功訊息

#### Scenario: 記憶不存在
- **WHEN** AI 呼叫 update_memory 或 delete_memory
- **AND** 指定的 memory_id 不存在
- **THEN** 系統回傳錯誤訊息「找不到指定的記憶」

---

### Requirement: 記憶管理 Prompt 說明
Line Bot Agent Prompt SHALL 包含記憶管理工具的使用說明。

#### Scenario: linebot-personal prompt 記憶說明
- **WHEN** 系統組合 linebot-personal Agent 的 prompt
- **THEN** prompt 包含記憶管理工具說明
- **AND** 說明 AI 應如何判斷新增、修改或刪除記憶
- **AND** 說明 AI 應自動產生合適的標題

#### Scenario: linebot-group prompt 記憶說明
- **WHEN** 系統組合 linebot-group Agent 的 prompt
- **THEN** prompt 包含記憶管理工具說明
- **AND** 說明群組記憶適用於該群組的所有對話

#### Scenario: 用戶要求記住某事
- **WHEN** 用戶說「記住 XXX」或「以後 XXX」
- **THEN** AI 應呼叫 add_memory 工具
- **AND** AI 自動產生合適的標題

#### Scenario: 用戶要求修改記憶
- **WHEN** 用戶說「修改記憶 XXX」或「把 XXX 改成 YYY」
- **THEN** AI 應先呼叫 get_memories 查詢現有記憶
- **AND** 找到相關記憶後呼叫 update_memory 更新

#### Scenario: 用戶要求刪除記憶
- **WHEN** 用戶說「忘記 XXX」或「不要再 XXX」
- **THEN** AI 應判斷是否要刪除相關記憶
- **AND** 若需要刪除，先用 get_memories 查詢再呼叫 delete_memory

#### Scenario: 用戶要求列出記憶
- **WHEN** 用戶說「列出記憶」或「我設定了什麼」
- **THEN** AI 應呼叫 get_memories 查詢並列出結果

### Requirement: Generate Presentation Tool
系統 SHALL 提供 MCP Tool 讓 AI Agent 產生 MD2PPT 格式的簡報內容。

#### Scenario: 產生簡報
- **GIVEN** LineBot AI 判斷用戶需要產生簡報
- **WHEN** 呼叫 `generate_presentation` tool 並傳入用戶提供的內容
- **THEN** 使用專門的 MD2PPT Agent prompt 產生符合格式的內容
- **AND** 自動建立帶密碼的分享連結
- **AND** 回傳分享連結 URL 和存取密碼

#### Scenario: 格式驗證
- **GIVEN** AI 產生了簡報內容
- **WHEN** 內容不符合 MD2PPT 格式規範
- **THEN** 嘗試自動修正或重新產生

### Requirement: Generate Document Tool
系統 SHALL 提供 MCP Tool 讓 AI Agent 產生 MD2DOC 格式的文件內容。

#### Scenario: 產生文件
- **GIVEN** LineBot AI 判斷用戶需要產生文件
- **WHEN** 呼叫 `generate_document` tool 並傳入用戶提供的內容
- **THEN** 使用專門的 MD2DOC Agent prompt 產生符合格式的內容
- **AND** 自動建立帶密碼的分享連結
- **AND** 回傳分享連結 URL 和存取密碼

#### Scenario: 格式驗證
- **GIVEN** AI 產生了文件內容
- **WHEN** 內容不符合 MD2DOC 格式規範
- **THEN** 嘗試自動修正或重新產生

### Requirement: MD2PPT Agent Prompt
系統 SHALL 包含專門的 MD2PPT Agent system prompt，確保產生的內容符合格式規範。

#### Scenario: Prompt 內容
- **GIVEN** 需要產生 MD2PPT 內容
- **WHEN** 呼叫 generate_presentation tool
- **THEN** 使用的 prompt 包含：
  - 全域設定規範 (theme, transition, title, author)
  - 分頁符號規範 (`===` 前後空行)
  - 頁面配置規範 (layout 選項)
  - Mesh 背景使用規則
  - 圖表語法規範
  - 雙欄語法規範
  - 嚴選配色盤
  - 自我檢核表

### Requirement: MD2DOC Agent Prompt
系統 SHALL 包含專門的 MD2DOC Agent system prompt，確保產生的內容符合格式規範。

#### Scenario: Prompt 內容
- **GIVEN** 需要產生 MD2DOC 內容
- **WHEN** 呼叫 generate_document tool
- **THEN** 使用的 prompt 包含：
  - Frontmatter 規範 (title, author, header, footer)
  - 標題層級限制 (只支援 H1-H3)
  - TOC 位置規範
  - Callout 語法規範 (TIP, NOTE, WARNING)
  - 對話語法規範
  - 行內樣式轉換表
  - 負面約束清單

