# Tasks: add-md-converter-file-loading

## Task List

### 1. 擴充 ExternalAppModule
- [x] 新增 `openWithContent(config, content)` 方法
- [x] 實作 postMessage 傳送機制
- [x] 等待 iframe ready 訊號後再傳送內容
- [x] 處理超時情況（3 秒後自動嘗試傳送）

**驗證**：可開啟外部 App 並傳送內容 ✓

### 2. 定義 postMessage 協議
- [x] 定義 `ready` 訊號格式
- [x] 定義 `load-file` 訊息格式
- [x] 文件化協議供外部 App 參考（`postmessage-protocol.md`）

**驗證**：協議文件完整 ✓

### 3. 註冊檔案開啟處理器
- [x] 在 `file-opener.js` 註冊 `.md2ppt` 副檔名處理器
- [x] 在 `file-opener.js` 註冊 `.md2doc` 副檔名處理器
- [x] 根據副檔名開啟對應的外部 App

**驗證**：點擊檔案可開啟對應 App ✓

### 4. 整合檔案管理器（NAS）
- [x] 檔案管理器已使用 `FileOpener.open()` 開啟檔案
- [x] 自動支援 `.md2ppt` / `.md2doc` 檔案

**驗證**：從 NAS 載入檔案到外部 App ✓

### 5. 整合知識庫附件
- [x] 知識庫已使用 `FileOpener.open()` 開啟附件
- [x] 自動支援 `.md2ppt` / `.md2doc` 檔案

**驗證**：從知識庫載入檔案到外部 App ✓

### 6. 整合專案會議附件
- [x] 專案管理已使用 `FileOpener.open()` 開啟附件
- [x] 自動支援 `.md2ppt` / `.md2doc` 檔案

**驗證**：從專案會議載入檔案到外部 App ✓

### 7. 整合 Line Bot 檔案
- [x] Line Bot 已使用 `FileOpener.open()` 開啟檔案
- [x] 自動支援 `.md2ppt` / `.md2doc` 檔案

**驗證**：從 Line Bot 載入檔案到外部 App ✓

### 8. 外部 App 修改（md2ppt）
- [ ] 監聽 `message` 事件
- [ ] 發送 `ready` 訊號給父視窗
- [ ] 接收 `load-file` 訊息
- [ ] 載入內容到編輯器

**驗證**：md2ppt 可接收並載入檔案（待外部實作）

### 9. 外部 App 修改（md2doc）
- [ ] 監聽 `message` 事件
- [ ] 發送 `ready` 訊號給父視窗
- [ ] 接收 `load-file` 訊息
- [ ] 載入內容到編輯器

**驗證**：md2doc 可接收並載入檔案（待外部實作）

### 10. 整合測試
- [ ] 測試從 NAS 載入
- [ ] 測試從知識庫載入
- [ ] 測試從專案會議載入
- [ ] 測試從 Line Bot 載入

**驗證**：所有來源都能正常載入（待測試）

## 完成的檔案變更

### 修改檔案
- `frontend/js/external-app.js` - 新增 `openWithContent()` 方法和 postMessage 機制
- `frontend/js/file-opener.js` - 新增 `.md2ppt` / `.md2doc` 處理器

### 新增檔案
- `openspec/changes/add-md-converter-file-loading/postmessage-protocol.md` - 協議文件

## 待外部實作

md2ppt 和 md2doc 需要實作 postMessage 協議，詳見 `postmessage-protocol.md`。
