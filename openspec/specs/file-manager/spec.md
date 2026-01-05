# file-manager Specification

## Purpose
TBD - created by archiving change add-file-manager. Update Purpose after archive.
## Requirements
### Requirement: 檔案管理視窗
系統 SHALL 提供檔案管理視窗，讓使用者瀏覽和管理 NAS 上的檔案。

#### Scenario: 開啟檔案管理
- Given 使用者已登入並在桌面
- When 雙擊「檔案管理」圖示或從 Taskbar 開啟
- Then 開啟檔案管理視窗
- And 顯示使用者有權限的共享資料夾列表

#### Scenario: 進入資料夾
- Given 檔案管理視窗已開啟
- When 雙擊資料夾
- Then 進入該資料夾並顯示內容
- And 導航列更新目前路徑

#### Scenario: 返回上層資料夾
- Given 使用者位於某資料夾內
- When 點擊「上一層」按鈕
- Then 返回父資料夾
- And 更新檔案列表和導航列

#### Scenario: 顯示檔案資訊
- Given 檔案管理視窗顯示檔案列表
- Then 每個項目顯示圖示、名稱、大小（檔案）、修改日期
- And 資料夾顯示資料夾圖示
- And 檔案根據類型顯示對應圖示

#### Scenario: 多選檔案
- Given 檔案管理視窗已開啟
- When 使用者按住 Ctrl 並點擊多個檔案
- Then 多個檔案被選取
- And 狀態列顯示選取數量

#### Scenario: 範圍選取
- Given 檔案管理視窗已開啟且已選取一個檔案
- When 使用者按住 Shift 並點擊另一個檔案
- Then 兩個檔案之間的所有項目被選取

---

### Requirement: 檔案預覽面板
系統 SHALL 在檔案管理視窗右側提供快速預覽面板。

#### Scenario: 雙擊開啟檔案
- **GIVEN** 檔案管理視窗已開啟
- **WHEN** 雙擊支援的檔案類型（圖片、文字、PDF）
- **THEN** 呼叫 `FileOpener.open()` 開啟對應的檢視器
> 原本直接呼叫各 Viewer，改為統一使用 FileOpener

### Requirement: 檔案操作
系統 SHALL 提供基本的檔案操作功能。

#### Scenario: 上傳檔案
- Given 使用者位於某資料夾內
- When 點擊「上傳」按鈕並選擇本機檔案
- Then 檔案上傳至目前資料夾
- And 重新整理檔案列表顯示新檔案
- And 顯示上傳成功提示

#### Scenario: 下載檔案
- Given 使用者選取了一個檔案
- When 點擊「下載」或從右鍵選單選擇下載
- Then 檔案下載到使用者本機
- And 瀏覽器顯示下載進度/完成

#### Scenario: 刪除檔案
- Given 使用者選取了一個或多個檔案
- When 點擊「刪除」並確認
- Then 檔案從 NAS 刪除
- And 檔案列表移除該項目
- And 顯示刪除成功提示

#### Scenario: 刪除非空資料夾
- Given 使用者選取了一個非空的資料夾
- When 點擊「刪除」
- Then 顯示警告對話框提示將遞迴刪除所有內容
- When 使用者確認
- Then 資料夾及其所有內容從 NAS 刪除

#### Scenario: 批次刪除
- Given 使用者多選了多個檔案或資料夾
- When 點擊「刪除」並確認
- Then 所有選取的項目被刪除
- And 顯示刪除成功提示

#### Scenario: 重命名
- Given 使用者選取了一個檔案或資料夾
- When 點擊「重命名」並輸入新名稱
- Then 項目重命名
- And 檔案列表更新顯示新名稱

#### Scenario: 建立資料夾
- Given 使用者位於某資料夾內
- When 點擊「新增資料夾」並輸入名稱
- Then 在目前位置建立新資料夾
- And 檔案列表顯示新資料夾

---

### Requirement: 檔案搜尋
系統 SHALL 提供檔案搜尋功能，讓使用者在目前路徑下搜尋檔案和資料夾。

#### Scenario: 執行搜尋
- Given 使用者位於某資料夾內
- When 在搜尋框輸入關鍵字並按 Enter
- Then 系統遞迴搜尋目前路徑下的檔案和資料夾
- And 顯示符合條件的結果列表
- And 結果包含名稱、完整路徑、類型

#### Scenario: 使用萬用字元搜尋
- Given 使用者在搜尋框
- When 輸入「*.py」或「test*」等萬用字元模式
- Then 系統搜尋符合模式的檔案名稱
- And 顯示所有符合的結果

#### Scenario: 從搜尋結果導航
- Given 搜尋結果已顯示
- When 雙擊搜尋結果中的資料夾
- Then 導航至該資料夾
- And 清除搜尋狀態
- When 雙擊搜尋結果中的檔案
- Then 導航至該檔案所在的資料夾

#### Scenario: 清除搜尋
- Given 搜尋結果已顯示
- When 點擊清除按鈕或按 Escape
- Then 清除搜尋結果
- And 回到正常檔案瀏覽模式

---

