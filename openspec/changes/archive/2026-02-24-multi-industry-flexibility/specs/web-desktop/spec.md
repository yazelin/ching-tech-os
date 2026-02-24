## MODIFIED Requirements

### Requirement: 桌面圖示權限控制
桌面 SHALL 從後端 API 動態取得應用清單，取代前端靜態 `applications` 陣列。停用模組的 App SHALL 不出現在桌面。

#### Scenario: 登入後從 API 載入應用清單
- **WHEN** 使用者登入成功進入桌面
- **THEN** `desktop.js` SHALL 呼叫 `GET /api/config/apps` 取得可用應用清單
- **THEN** 桌面 SHALL 依回傳清單渲染應用圖示

#### Scenario: 顯示有權限的應用程式
- **WHEN** API 回傳應用清單
- **THEN** SHALL 結合使用者個人 app 權限進一步過濾
- **THEN** 只顯示使用者有權限的應用

#### Scenario: 管理員看到所有啟用模組的應用程式
- **WHEN** 登入使用者為管理員
- **THEN** SHALL 顯示所有啟用模組的應用（不受個人權限限制）

#### Scenario: API 失敗 fallback
- **WHEN** `/api/config/apps` 請求失敗（網路錯誤、伺服器異常）
- **THEN** SHALL fallback 到前端內建的靜態 `applications` 清單
- **THEN** 桌面 SHALL 正常顯示，不因 API 失敗而空白

#### Scenario: Skill 擴充 App 動態載入
- **WHEN** API 回傳的應用項目包含 `loader` 欄位
- **THEN** 使用者點擊該 App 時，`desktop.js` SHALL 動態載入 `loader.src` 指定的 JS 檔案
- **THEN** 若有 `css` 欄位，SHALL 先載入 CSS 再載入 JS

#### Scenario: 開啟無權限應用程式提示
- **WHEN** 透過 URL 或程式碼嘗試開啟使用者無權限的 App
- **THEN** SHALL 顯示「無權限」提示，不開啟視窗
