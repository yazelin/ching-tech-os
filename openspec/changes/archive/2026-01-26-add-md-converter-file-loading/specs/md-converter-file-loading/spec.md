# md-converter-file-loading Specification

## Purpose
讓使用者可以從 CTOS 各種來源（NAS、知識庫、專案會議、Line Bot）載入 `.md2ppt` 和 `.md2doc` 檔案到對應的外部 App。

## ADDED Requirements

### Requirement: File Open Handler
系統 SHALL 為 `.md2ppt` 和 `.md2doc` 副檔名註冊檔案開啟處理器。

#### Scenario: 開啟 md2ppt 檔案
- **GIVEN** 使用者在任意檔案來源中
- **WHEN** 點擊 `.md2ppt` 副檔名的檔案
- **THEN** 系統開啟 md2ppt 外部 App
- **AND** 載入檔案內容到 App

#### Scenario: 開啟 md2doc 檔案
- **GIVEN** 使用者在任意檔案來源中
- **WHEN** 點擊 `.md2doc` 副檔名的檔案
- **THEN** 系統開啟 md2doc 外部 App
- **AND** 載入檔案內容到 App

---

### Requirement: PostMessage Protocol
系統 SHALL 使用 postMessage 協議與外部 App 通訊。

#### Scenario: 外部 App 發送 ready 訊號
- **GIVEN** 外部 App iframe 已載入
- **WHEN** App 初始化完成
- **THEN** App 發送 `{ type: 'ready' }` 訊號給父視窗

#### Scenario: CTOS 傳送檔案內容
- **GIVEN** CTOS 收到外部 App 的 ready 訊號
- **WHEN** 有待傳送的檔案內容
- **THEN** CTOS 發送 `{ type: 'load-file', filename, content }` 給 iframe

#### Scenario: 外部 App 接收檔案
- **GIVEN** 外部 App 收到 `load-file` 訊息
- **WHEN** 訊息包含有效的 filename 和 content
- **THEN** App 載入內容到編輯器

---

### Requirement: NAS File Loading
系統 SHALL 支援從 NAS（檔案管理器）載入檔案。

#### Scenario: 從檔案管理器開啟
- **GIVEN** 使用者在檔案管理器中瀏覽 NAS
- **WHEN** 點擊 `.md2ppt` 或 `.md2doc` 檔案
- **THEN** 系統讀取檔案內容
- **AND** 開啟對應外部 App 並載入內容

---

### Requirement: Knowledge Base Attachment Loading
系統 SHALL 支援從知識庫附件載入檔案。

#### Scenario: 從知識庫附件開啟
- **GIVEN** 使用者在知識庫項目的附件列表中
- **WHEN** 點擊 `.md2ppt` 或 `.md2doc` 附件
- **THEN** 系統讀取附件內容
- **AND** 開啟對應外部 App 並載入內容

---

### Requirement: Project Meeting Attachment Loading
系統 SHALL 支援從專案會議附件載入檔案。

#### Scenario: 從專案會議附件開啟
- **GIVEN** 使用者在專案會議記錄的附件列表中
- **WHEN** 點擊 `.md2ppt` 或 `.md2doc` 附件
- **THEN** 系統讀取附件內容
- **AND** 開啟對應外部 App 並載入內容

---

### Requirement: Line Bot File Loading
系統 SHALL 支援從 Line Bot 對話檔案載入。

#### Scenario: 從 Line Bot 檔案開啟
- **GIVEN** 使用者在 Line Bot 對話中
- **WHEN** 點擊 `.md2ppt` 或 `.md2doc` 檔案
- **THEN** 系統讀取檔案內容
- **AND** 開啟對應外部 App 並載入內容

---

## Related Specs
- `add-md-converter-apps` - 外部 App 整合
- `file-manager` - 檔案管理器
- `knowledge-base` - 知識庫
- `project-management` - 專案管理
- `line-bot` - Line Bot
