## 1. Docker 設定

- [x] 1.1 修改 `docker/docker-compose.yml` - 新增 code-server 服務
  - image: codercom/code-server:latest
  - 掛載專案目錄
  - 掛載 SSH key 和 gitconfig
  - 設定 port 8443
- [x] 1.2 新增 code-server volume 用於持久化設定和擴充功能

## 2. 啟動腳本

- [x] 2.1 修改 `scripts/start.sh` - 確保 code-server 隨 docker compose 啟動
- [x] 2.2 新增等待 code-server 就緒的檢查

## 3. 前端整合

- [x] 3.1 新增 `frontend/js/code-editor.js` - 編輯器視窗模組
  - 使用 iframe 嵌入 code-server
  - 支援視窗開啟/關閉
- [x] 3.2 新增 `frontend/css/code-editor.css` - 編輯器樣式
  - iframe 全尺寸填滿視窗
  - 移除 iframe 邊框
- [x] 3.3 修改 `frontend/js/desktop.js` - 新增 code-editor case
- [x] 3.4 修改 `frontend/index.html` - 引入 code-editor 模組

## 4. 測試與驗證

- [x] 4.1 測試 docker compose 啟動 code-server
- [x] 4.2 測試直接瀏覽器存取 localhost:8443
- [x] 4.3 測試 Taskbar 點擊開啟編輯器視窗
- [x] 4.4 測試 iframe 中 code-server 正常運作
- [x] 4.5 測試 Git 操作（commit, push）使用正確身份
