## MODIFIED Requirements

### Requirement: 大型附件 NAS 儲存
知識庫 SHALL 將大型附件儲存於 NAS，避免 Git 膨脹。

#### Scenario: 小型附件本機儲存
- **WHEN** 使用者上傳小於 1MB 的圖片
- **THEN** 系統將圖片存放於 `data/knowledge/assets/images/`
- **AND** 圖片隨 Git 追蹤
- **AND** 附件路徑記錄為 `local://knowledge/assets/images/{kb_id}-{filename}`

#### Scenario: 大型附件 NAS 儲存
- **WHEN** 使用者上傳大於或等於 1MB 的附件
- **THEN** 系統將附件存放於 NAS `//192.168.11.50/擎添開發/ching-tech-os/knowledge/attachments/{kb-id}/`
- **AND** 附件不進入 Git
- **AND** 附件路徑記錄為 `ctos://knowledge/attachments/{kb_id}/{filename}`

#### Scenario: NAS 附件引用
- **WHEN** 知識包含 NAS 附件
- **THEN** 元資料 attachments 欄位記錄附件資訊
- **AND** 使用 `ctos://knowledge/attachments/{kb-id}/{filename}` 協定引用

#### Scenario: 顯示 NAS 附件
- **WHEN** 使用者檢視包含 NAS 附件的知識
- **THEN** 前端透過後端 API 代理載入附件
- **AND** 附件正確顯示（圖片、影片等）

#### Scenario: 附件區固定底部顯示
- **WHEN** 使用者檢視知識內容
- **THEN** 附件區固定顯示於內容區底部
- **AND** 無需捲動即可查看附件列表
- **AND** 內容過長時僅內容區捲動，附件區維持可見

#### Scenario: 上傳附件彈出視窗
- **WHEN** 使用者在編輯模式點擊「新增附件」按鈕
- **THEN** 顯示上傳附件彈出視窗
- **AND** 視窗包含檔案選擇器、描述輸入欄位
- **AND** 顯示檔案大小預估與儲存位置提示（本機/NAS）

#### Scenario: 編輯附件元資料
- **WHEN** 使用者點擊附件的編輯按鈕
- **THEN** 顯示附件編輯表單
- **AND** 可修改附件描述文字
- **WHEN** 使用者儲存修改
- **THEN** 系統更新附件元資料（不移動檔案）

#### Scenario: 刪除知識連帶刪除附件
- **WHEN** 使用者確認刪除知識
- **THEN** 系統刪除該知識的所有附件（本機與 NAS）
- **AND** 刪除知識檔案與索引記錄
- **AND** 若 NAS 附件目錄為空則一併刪除

#### Scenario: 公開分享頁面下載附件
- **WHEN** 使用者透過公開分享連結存取知識
- **AND** 知識包含附件
- **THEN** 前端可透過 `/api/public/{token}/attachments/{path}` 下載附件
- **AND** API 支援 `local://knowledge/assets/images/...` 格式（新）
- **AND** API 支援 `local://knowledge/images/...` 格式（舊，向後相容）
- **AND** API 支援 `ctos://knowledge/attachments/...` 格式（NAS）
- **AND** API 正確轉換路徑並回傳檔案內容
