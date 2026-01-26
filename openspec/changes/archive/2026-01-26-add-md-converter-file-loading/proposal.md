# Proposal: add-md-converter-file-loading

## Summary
讓使用者可以從 CTOS 各種來源載入 `.md2ppt` 和 `.md2doc` 檔案到對應的外部 App（md2ppt/md2doc），透過 postMessage 傳遞檔案內容。

## Background
md2ppt 和 md2doc 兩個外部 App 已整合到 CTOS 桌面（`add-md-converter-apps`）。現在需要讓這些 App 能夠載入 CTOS 中的檔案內容，實現完整的工作流程。

檔案格式：
- `.md2ppt` - 特定格式的 Markdown 檔案，用於產生 PowerPoint
- `.md2doc` - 特定格式的 Markdown 檔案，用於產生 Word 文件

## Goals
1. 從多種來源載入 `.md2ppt` / `.md2doc` 檔案
2. 自動開啟對應的外部 App
3. 透過 postMessage 傳送檔案內容給 iframe
4. 外部 App 接收並處理檔案內容

## Non-Goals
- 本階段不實作儲存功能（從外部 App 存回 CTOS）
- 不修改檔案格式規範

## 檔案來源

| 來源 | 位置 | 現有 API |
|------|------|----------|
| NAS | 檔案管理器 | `/api/nas/files/{path}` |
| 知識庫附件 | 知識庫 → 項目附件 | `/api/knowledge/attachments/{path}` |
| 專案會議附件 | 專案管理 → 會議記錄附件 | `/api/projects/{id}/meetings/{id}/attachments` |
| Line Bot 檔案 | Line Bot → 對話檔案 | `/api/linebot/files/{id}` |

## Approach

### 1. 前端：檔案開啟處理器
在 `file-opener.js` 註冊 `.md2ppt` 和 `.md2doc` 的開啟處理器：
- 偵測檔案副檔名
- 讀取檔案內容（透過對應的 API）
- 開啟外部 App 視窗
- postMessage 傳送內容

### 2. ExternalAppModule 擴充
新增 `openWithContent(config, content)` 方法：
- 開啟視窗
- 等待 iframe 載入完成
- postMessage 傳送檔案內容

### 3. postMessage 協議
```javascript
// CTOS → 外部 App
{
  type: 'load-file',
  filename: 'example.md2ppt',
  content: '# Markdown 內容...'
}

// 外部 App → CTOS (ready 訊號)
{
  type: 'ready'
}
```

### 4. 外部 App 修改（md2ppt / md2doc）
- 監聽 `message` 事件
- 發送 `ready` 訊號
- 接收檔案內容並載入編輯器

## Impact
- 前端變更：修改 `external-app.js`、`file-opener.js`
- 外部 App 變更：md2ppt、md2doc 需配合實作 postMessage 協議
- 無後端變更
- 無資料庫變更

## Related
- `add-md-converter-apps` - 外部 App 整合（已完成）
- `file-manager` spec - 檔案管理器
- `knowledge-base` spec - 知識庫
