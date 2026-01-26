# Proposal: add-md-converter-apps

## Summary
新增 MD2PPT 和 MD2Doc 兩個應用程式到 CTOS 桌面，使用 iframe 整合外部 Vercel 服務。

## Background
使用者需要將 Markdown 轉換為 PowerPoint 簡報和 Word 文件的功能。這兩個工具已經部署在 Vercel 上：
- MD2PPT: https://md-2-ppt-evolution.vercel.app/
- MD2Doc: https://md-2-doc-evolution.vercel.app/

為了提供一致的使用體驗，將這兩個外部服務以 iframe 方式整合進 CTOS 桌面，類似現有的 VSCode (code-editor) 應用程式。

## Goals
1. 在桌面新增 MD2PPT 和 MD2Doc 兩個應用程式圖示
2. 點擊圖示後以視窗內嵌 iframe 方式開啟對應服務
3. 提供載入中狀態和錯誤處理
4. 遵循現有 code-editor 模組的設計模式

## Non-Goals
- 不在此階段實作檔案匯入功能（後續討論）
- 不修改外部 Vercel 服務本身
- 不需要後端 API 支援

## Approach
參考現有 `CodeEditorModule` 的實作模式：

1. **建立通用 iframe 應用程式模組** (`external-app.js`)
   - 可重用的 iframe 視窗工廠函式
   - 支援載入狀態、錯誤處理
   - 可配置 URL、視窗標題、圖示、尺寸

2. **新增桌面應用程式定義**
   - 在 `desktop.js` 的 `applications` 陣列新增兩個應用程式
   - 在 `openApp` 函式新增對應的 case

3. **CSS 樣式**
   - 重用 `code-editor.css` 的 iframe 容器樣式
   - 建立通用的 `external-app.css`

4. **HTML 引入**
   - 在 `index.html` 引入新的 JS 和 CSS 檔案

## Impact
- 前端變更：3 個新檔案，2 個修改檔案
- 無後端變更
- 無資料庫變更
- 無破壞性變更

## Related
- `code-editor` spec - 參考 iframe 整合模式
- `web-desktop` spec - 桌面應用程式管理
