# Proposal: add-linebot-md-converter-agents

## Why
使用者經常需要將大量內容轉換為簡報或文件格式。目前 LineBot AI 無法直接產生符合 MD2PPT/MD2DOC 格式的內容，使用者必須手動在 CTOS 中建立和編輯。

此功能讓 LineBot AI 能夠：
1. 判斷使用者意圖（是否需要產生簡報/文件）
2. 呼叫專門的 Agent 產生正確格式的內容
3. 儲存並產生帶密碼保護的分享連結
4. 讓使用者無需登入 CTOS 即可在 MD2PPT/MD2DOC 中開啟編輯

## What Changes

### 1. 新增 MCP Tools
- `generate_presentation`: 產生 MD2PPT 格式的簡報內容
- `generate_document`: 產生 MD2DOC 格式的文件內容

### 2. 擴充現有分享 API
- 擴充 `public_share_links` 資料表，新增密碼欄位
- 修改 `POST /api/share` 支援可選的密碼參數
- 修改 `GET /api/public/{token}` 支援密碼驗證
- 新增 CORS 支援讓外部網站可存取

### 3. 修改 MD2PPT/MD2DOC
- 支援 `?shareToken=xxx` URL 參數
- 啟動時若有 shareToken，顯示密碼輸入框
- 驗證成功後載入內容

### 4. 新增專門 System Prompts
- MD2PPT Agent Prompt: 包含 AI_GENERATION_GUIDE.md 的格式規範
- MD2DOC Agent Prompt: 包含 AI_GENERATION_GUIDE.md 的格式規範

## Background

### MD2PPT 格式重點
- 全域設定：theme (amber/midnight/academic/material), transition, title, author
- 分頁符號：`===` 前後必須有空行
- 頁面配置：layout (default/impact/center/grid/two-column/quote/alert)
- Mesh 背景只用於標題頁和重點頁，內容頁用純色
- 圖表語法：`::: chart-xxx { JSON }` 前後必須有空行
- 雙欄語法：`:: right ::` 前後必須有空行

### MD2DOC 格式重點
- Frontmatter：title, author, header, footer
- 只支援 H1, H2, H3 標題
- `[TOC]` 放在 Frontmatter 後
- Callouts：只支援 TIP, NOTE, WARNING
- 對話語法：`角色 ::"` 然後換行接內容

## Goals
1. LineBot 使用者能透過對話產生專業簡報和文件
2. 產生的內容 100% 相容 MD2PPT/MD2DOC 格式
3. 分享連結有密碼保護，過期自動刪除
4. 使用者可直接在 MD2PPT/MD2DOC 網站開啟編輯

## Non-Goals
- 不實作檔案版本控制
- 不實作多人協作編輯
- 不整合到 CTOS 知識庫（分享連結獨立於知識庫）

## Approach

### 流程圖
```
使用者傳訊息 → LineBot AI 判斷意圖
                    ↓
              需要產生簡報/文件?
                    ↓ 是
              呼叫 MCP Tool (generate_presentation / generate_document)
                    ↓
              專門 Agent 產生內容
                    ↓
              建立分享連結 (POST /api/public/share)
                    ↓
              回傳連結給使用者
                    ↓
使用者點擊連結 → MD2PPT/MD2DOC 網站
                    ↓
              輸入存取密碼
                    ↓
              驗證通過，載入內容
```

### 分享連結格式
```
https://md-2-ppt-evolution.vercel.app/?shareToken=abc123
```

### 密碼驗證流程
1. MD2PPT 偵測到 `shareToken` 參數
2. 顯示密碼輸入對話框
3. 用戶輸入密碼
4. MD2PPT 呼叫 `GET /api/public/share/{token}?password=xxx`
5. 後端驗證密碼，成功則回傳內容
6. MD2PPT 載入內容到編輯器

### 安全性考量
- 密碼為 6 位隨機數字，方便 Line 使用者輸入
- 分享連結預設 24 小時過期
- 錯誤密碼嘗試次數限制（5 次後鎖定）
- 內容取得後可選擇刪除分享連結

## Impact
- 後端：新增 2 個 MCP Tools，1 個公開 API 路由，1 個資料表
- 前端：無變更（MD2PPT/MD2DOC 是外部專案）
- 外部專案：MD2PPT、MD2DOC 需新增 shareToken 處理邏輯

## Related
- `md-converter-apps` spec - 外部應用程式整合
- `md-converter-file-loading` spec - 檔案載入協議
- `line-bot` spec - LineBot 整合
- `mcp-tools` spec - MCP 工具定義
