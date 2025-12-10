## ADDED Requirements

### Requirement: NAS 檔案操作 API
系統 SHALL 提供 API 讓登入後的使用者對 NAS 檔案執行讀取、上傳、刪除、重命名、建立資料夾等操作。

#### Scenario: 讀取文字檔內容
- Given 使用者已登入
- When 呼叫 GET /api/nas/file?path=/share/folder/file.txt
- Then 系統回傳檔案內容
- And Content-Type 為 text/plain 或對應的 MIME 類型

#### Scenario: 讀取圖片檔
- Given 使用者已登入
- When 呼叫 GET /api/nas/file?path=/share/folder/image.jpg
- Then 系統回傳圖片二進位資料
- And Content-Type 為 image/jpeg 或對應的 MIME 類型

#### Scenario: 下載檔案
- Given 使用者已登入
- When 呼叫 GET /api/nas/download?path=/share/folder/file.txt
- Then 系統回傳檔案二進位資料
- And Content-Disposition 設定為 attachment
- And 檔案名稱正確編碼

#### Scenario: 上傳檔案
- Given 使用者已登入
- When 呼叫 POST /api/nas/upload 並附帶檔案和目標路徑
- Then 檔案儲存到 NAS 指定位置
- And 回傳成功訊息

#### Scenario: 刪除檔案
- Given 使用者已登入
- When 呼叫 DELETE /api/nas/file?path=/share/folder/file.txt
- Then 檔案從 NAS 刪除
- And 回傳成功訊息

#### Scenario: 刪除資料夾
- Given 使用者已登入且資料夾為空或允許遞迴刪除
- When 呼叫 DELETE /api/nas/file?path=/share/folder
- Then 資料夾從 NAS 刪除
- And 回傳成功訊息

#### Scenario: 重命名檔案或資料夾
- Given 使用者已登入
- When 呼叫 PATCH /api/nas/rename 並提供路徑和新名稱
- Then 項目重命名
- And 回傳成功訊息

#### Scenario: 建立資料夾
- Given 使用者已登入
- When 呼叫 POST /api/nas/mkdir 並提供路徑
- Then 在 NAS 建立新資料夾
- And 回傳成功訊息

#### Scenario: 操作無權限的檔案
- Given 使用者已登入
- When 對無權限的檔案或資料夾執行操作
- Then 系統回傳 403 權限錯誤
- And 顯示「無權限執行此操作」訊息

#### Scenario: 搜尋檔案
- Given 使用者已登入
- When 呼叫 GET /api/nas/search?path=/share&query=*.py&max_depth=3&max_results=100
- Then 系統遞迴搜尋指定路徑下符合條件的檔案和資料夾
- And 回傳結果列表包含 name、path、type
- And 支援萬用字元 * 和 ?

#### Scenario: 搜尋結果限制
- Given 使用者已登入
- When 搜尋結果超過 max_results 限制
- Then 系統回傳前 max_results 筆結果
- And max_depth 限制搜尋深度（預設 3 層，最大 10 層）
- And max_results 限制結果數量（預設 100，最大 500）
