# Change: 新增程式編輯器 (code-server)

## Why
目前 Ching-Tech OS 缺少程式編輯器功能。使用 code-server 可以提供完整的 VS Code 體驗，包含程式碼編輯、檔案瀏覽、內建終端機、擴充功能支援等。

## What Changes

### Docker 整合
- 新增 code-server 容器到 docker-compose.yml
- 掛載專案目錄作為工作目錄
- 掛載使用者 SSH key 供 Git 使用
- 設定環境變數密碼認證

### 前端整合
- 在桌面視窗中嵌入 code-server (iframe)
- Taskbar 圖示點擊開啟編輯器視窗
- 視窗支援最大化以獲得最佳編輯體驗

### 啟動腳本更新
- start.sh 同時啟動 PostgreSQL 和 code-server

## Impact
- 新增 spec: `code-editor`
- 修改: `docker/docker-compose.yml` - 新增 code-server 服務
- 修改: `scripts/start.sh` - 更新啟動流程
- 新增: `frontend/js/code-editor.js` - 編輯器視窗模組
- 新增: `frontend/css/code-editor.css` - 編輯器樣式
- 修改: `frontend/js/desktop.js` - 新增 code-editor case

## Configuration
- code-server port: 8443
- 工作目錄: 專案根目錄
- 認證: 環境變數 `CODE_PASSWORD` (預設: changeme)
- Git: 使用主機的 ~/.ssh 和 ~/.gitconfig
