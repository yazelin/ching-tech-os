# 任務清單

## 階段一：資料庫與後端基礎

### 1. 建立資料庫 migration
- [x] 建立 `public_share_links` 表格
- [x] 欄位：id, token, resource_type, resource_id, created_by, expires_at, access_count, created_at
- [x] token 欄位建立唯一索引
- **驗證**：✅ migration 執行成功，表格已建立

### 2. 建立後端資料模型
- [x] 新增 `models/share.py`
- [x] 定義 Pydantic 模型：
  - `ShareLinkCreate`：建立連結請求
  - `ShareLinkResponse`：連結回應
  - `ShareLinkListResponse`：連結列表
  - `PublicResourceResponse`：公開資源回應
- **驗證**：✅ 模型定義完成

### 3. 實作後端服務層
- [x] 新增 `services/share.py`
- [x] `generate_token()`：產生 6 字元隨機 token
- [x] `create_share_link()`：產生 token、儲存到資料庫
- [x] `get_public_resource()`：驗證 token、取得資源、更新存取次數
- [x] `list_my_links()`：列出使用者的連結
- [x] `revoke_link()`：撤銷連結
- **驗證**：✅ 服務層實作完成

### 4. 實作後端 API
- [x] 新增 `api/share.py`
- [x] 需登入 API：
  - `POST /api/share`：建立連結
  - `GET /api/share`：列出我的連結
  - `DELETE /api/share/{token}`：撤銷連結
- [x] 無需登入 API：
  - `GET /api/public/{token}`：取得公開資源
  - `GET /api/public/{token}/attachments/{path}`：取得公開附件
- [x] 在 `main.py` 註冊路由
- **驗證**：✅ API 測試通過

## 階段二：公開文件頁面

### 5. 建立公開頁面 HTML
- [x] 新增 `public.html`（完全獨立，不依賴 index.html）
- [x] 基本結構：標題區、內容區、附件區、底部資訊
- [x] 引入 marked.js、highlight.js
- **驗證**：✅ 頁面已建立

### 6. 建立公開頁面樣式
- [x] 新增 `css/public.css`（獨立樣式，不引用 main.css）
- [x] 文件檢視器風格設計
- [x] 響應式設計
- [x] 列印樣式優化
- [x] 錯誤頁面樣式
- **驗證**：✅ 樣式完成

### 7. 建立公開頁面邏輯
- [x] 新增 `js/public.js`（獨立模組）
- [x] 從 URL 取得 token
- [x] 呼叫 API 取得資源
- [x] 渲染知識庫內容（Markdown、附件、相關知識）
- [x] 渲染專案內容（描述、里程碑、成員）
- [x] 附件預覽/下載功能
- [x] 列印功能
- [x] 錯誤處理（過期、不存在、已刪除）
- **驗證**：✅ 邏輯實作完成

### 8. 設定短網址路由
- [x] `/s/{token}` 路由已在 FastAPI 中設定
- [x] 處理子路徑部署（透過 public.js 的 getApiBase）
- **驗證**：✅ 短網址路由正常運作

## 階段三：分享對話框（共用組件）

### 9. 建立分享對話框組件
- [x] 新增 `js/share-dialog.js` 共用模組
- [x] 新增 `css/share-dialog.css` 樣式
- [x] 有效期選項：1 小時、6 小時、24 小時（預設）、3 天、7 天、30 天、永久
- [x] 產生連結按鈕
- [x] 連結顯示區 + 一鍵複製
- [x] QR Code 顯示（使用 qrcode-generator）
- [x] 有效期資訊顯示
- **驗證**：✅ 對話框組件完成

### 10. 整合到知識庫
- [x] 在知識庫內容區新增「分享」按鈕
- [x] 點擊彈出分享對話框
- [x] 呼叫 API 產生連結
- **驗證**：✅ 已整合

### 11. 整合到專案管理
- [x] 在專案詳情區新增「分享」按鈕
- [x] 點擊彈出分享對話框
- [x] 呼叫 API 產生連結
- **驗證**：✅ 已整合

## 階段四：分享管理應用程式

### 12. 建立分享管理 App 基礎
- [x] 新增 `js/share-manager.js`
- [x] 新增 `css/share-manager.css`
- [x] 在 `desktop.js` 註冊應用程式
- [x] 在 `index.html` 引入 CSS/JS
- **驗證**：✅ App 已註冊

### 13. 實作分享管理列表
- [x] 呼叫 API 取得連結列表
- [x] 顯示每個連結的資訊：
  - 資源名稱、類型
  - 完整連結
  - 有效期/已過期狀態
  - 存取次數
  - 建立時間
- **驗證**：✅ 列表功能完成

### 14. 實作過濾
- [x] 按資源類型過濾（全部/知識庫/專案）
- [x] 統計資訊顯示（有效/已過期/總數）
- **驗證**：✅ 過濾功能完成

### 15. 實作連結操作
- [x] 複製連結按鈕（一鍵複製完整 URL）
- [x] 開啟連結按鈕
- [x] 撤銷連結按鈕（確認後撤銷）
- [x] 撤銷後即時更新列表
- **驗證**：✅ 操作功能完成

## 階段五：Line Bot 整合

### 16. 新增 MCP 工具
- [x] 在 `mcp_server.py` 新增 `create_share_link` 工具
- [x] 參數：resource_type, resource_id, expires_in_hours
- [x] 回傳完整 URL 和有效期資訊
- **驗證**：✅ MCP 工具已新增

### 17. 更新 Line Bot Prompt
- [x] 在 system prompt 說明 `create_share_link` 工具用法
- [x] 提示 AI 何時使用（用戶要求連結、內容太長時）
- **驗證**：✅ 已在 linebot_ai.py 的 build_system_prompt 中新增工具說明

## 階段六：收尾

### 18. 完善錯誤處理
- [x] 所有錯誤情境有適當提示
- [x] 複製成功的視覺回饋
- [x] 產生連結失敗的提示
- **驗證**：✅ 錯誤處理完成

### 19. 樣式優化
- [x] 與系統設計風格一致
- [x] 暗色主題支援（公開頁面獨立主題）
- **驗證**：✅ 樣式完成

### 20. 測試
- [x] API 端點測試通過
- [x] 路由測試通過
- **驗證**：✅ 基本測試完成
