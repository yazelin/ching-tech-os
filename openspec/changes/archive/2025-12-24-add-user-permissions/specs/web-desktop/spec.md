# web-desktop Specification Delta

## ADDED Requirements

### Requirement: 桌面圖示權限控制

桌面模組 SHALL 根據使用者權限顯示或隱藏應用程式圖示。

#### Scenario: 登入後載入權限
- Given 使用者成功登入
- When 系統載入桌面
- Then 呼叫 `GET /api/user/me` 取得權限資訊
- And 儲存權限資訊到 `window.currentUser`

#### Scenario: 顯示有權限的應用程式
- Given 使用者已登入且權限已載入
- When 桌面渲染應用程式圖示
- Then 只顯示使用者有權限的應用程式圖示
- And 無權限的應用程式圖示不顯示

#### Scenario: 管理員看到所有應用程式
- Given 管理員已登入
- When 桌面渲染應用程式圖示
- Then 顯示所有應用程式圖示

#### Scenario: 開啟無權限應用程式提示
- Given 應用程式圖示被隱藏
- When 使用者透過其他方式嘗試開啟該應用程式
- Then 顯示 toast 通知「您沒有使用 {應用程式名稱} 的權限，請聯繫管理員」

---

### Requirement: 使用者管理介面

系統設定應用程式 SHALL 提供使用者管理分頁供管理員使用。

#### Scenario: 顯示使用者管理分頁
- Given 管理員開啟系統設定
- When 系統設定視窗載入
- Then 顯示「使用者管理」分頁

#### Scenario: 非管理員隱藏使用者管理
- Given 非管理員使用者開啟系統設定
- When 系統設定視窗載入
- Then 不顯示「使用者管理」分頁

#### Scenario: 使用者列表顯示
- Given 管理員點擊「使用者管理」分頁
- When 分頁載入
- Then 顯示使用者列表表格
- And 每列顯示使用者名稱、顯示名稱、最後登入時間、操作按鈕
- And 管理員帳號標記為「🔒 管理員」

#### Scenario: 開啟權限設定對話框
- Given 管理員在使用者管理分頁
- When 點擊某使用者的「設定權限」按鈕
- Then 顯示權限設定對話框
- And 對話框顯示該使用者目前的權限設定

#### Scenario: 權限設定對話框內容
- Given 權限設定對話框已開啟
- When 對話框顯示
- Then 顯示「應用程式權限」區塊，列出所有應用程式勾選框
- And 顯示「知識庫權限」區塊，包含全域知識寫入與刪除勾選框
- And 顯示「取消」和「儲存」按鈕

#### Scenario: 儲存權限設定
- Given 管理員修改了權限設定
- When 點擊「儲存」按鈕
- Then 呼叫 API 更新權限
- And 顯示成功 toast 通知
- And 關閉對話框
- And 更新使用者列表

#### Scenario: 管理員權限不可編輯
- Given 管理員在使用者管理分頁
- When 查看管理員帳號的列
- Then 不顯示「設定權限」按鈕
- And 顯示「🔒 管理員」標記
