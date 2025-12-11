## 1. 基礎設施

- [x] 1.1 建立 `data/knowledge/entries/` 目錄結構
- [x] 1.2 建立 `data/knowledge/assets/images/` 目錄
- [x] 1.3 建立初始 `data/knowledge/index.json`（空索引）
- [x] 1.4 在 NAS 建立知識庫附件目錄
  - 路徑由環境變數 `KNOWLEDGE_NAS_PATH` 設定
  - 預設：`擎添開發/ching-tech-os/knowledge/attachments/`
- [x] 1.5 建立範例知識檔案（驗證格式）

## 2. 後端 - Config

- [x] 2.1 在 `config.py` 加入知識庫環境變數
  - `KNOWLEDGE_NAS_HOST` - NAS IP（預設 192.168.11.50）
  - `KNOWLEDGE_NAS_SHARE` - NAS 共享名稱（預設「擎添開發」）
  - `KNOWLEDGE_NAS_PATH` - NAS 子路徑（預設 `ching-tech-os/knowledge`）
  - `KNOWLEDGE_NAS_USER` - NAS 帳號（測試帳號）
  - `KNOWLEDGE_NAS_PASSWORD` - NAS 密碼（測試密碼）

## 3. 後端 - Models

- [x] 3.1 建立 `backend/src/ching_tech_os/models/knowledge.py`
  - KnowledgeMetadata (Pydantic model)
  - KnowledgeCreate, KnowledgeUpdate
  - KnowledgeResponse, KnowledgeListResponse
  - TagsResponse
  - HistoryEntry, HistoryResponse

## 4. 後端 - Services

- [x] 4.1 建立 `backend/src/ching_tech_os/services/knowledge.py`
  - `search_knowledge(query, tags)` - ripgrep 全文搜尋 + 標籤過濾
  - `get_knowledge(id)` - 讀取單一知識
  - `create_knowledge(data)` - 建立知識檔案與索引
  - `update_knowledge(id, data)` - 更新知識檔案與索引
  - `delete_knowledge(id)` - 刪除知識檔案與索引
  - `get_all_tags()` - 從索引讀取所有標籤
  - `rebuild_index()` - 重建索引

- [x] 4.2 實作 YAML Front Matter 解析與生成
- [x] 4.3 實作知識 ID 自動分配邏輯
- [x] 4.4 實作 Git 版本歷史功能
  - `get_history(id)` - 使用 `git log --follow`
  - `get_version(id, commit)` - 使用 `git show`
- [x] 4.5 實作 NAS 附件處理
  - 使用環境變數配置的帳號連接 NAS
  - 附件大小判斷（< 1MB 本機，≥ 1MB NAS）
  - NAS 附件路徑：`{KNOWLEDGE_NAS_PATH}/attachments/{kb-id}/`

## 5. 後端 - API

- [x] 5.1 建立 `backend/src/ching_tech_os/api/knowledge.py`
  - `GET /api/knowledge` - 搜尋/列表
  - `GET /api/knowledge/{id}` - 取得單一知識
  - `POST /api/knowledge` - 新增知識
  - `PUT /api/knowledge/{id}` - 更新知識
  - `DELETE /api/knowledge/{id}` - 刪除知識
  - `GET /api/knowledge/tags` - 取得標籤列表
  - `POST /api/knowledge/rebuild-index` - 重建索引
  - `GET /api/knowledge/{id}/history` - 取得版本歷史
  - `GET /api/knowledge/{id}/version/{commit}` - 取得特定版本
  - `POST /api/knowledge/{id}/attachments` - 上傳附件
  - `DELETE /api/knowledge/{id}/attachments/{idx}` - 刪除附件
  - `GET /api/knowledge/attachments/{path}` - 代理 NAS 附件

- [x] 5.2 註冊 Router 到 main.py
- [x] 5.3 附件元資料編輯 API
  - `PATCH /api/knowledge/{id}/attachments/{idx}` - 更新附件描述
  - 僅更新元資料，不移動檔案
- [x] 5.4 刪除知識連帶刪除附件
  - 刪除知識時自動刪除所有相關附件（本機與 NAS）
  - 嘗試刪除 NAS 上的知識目錄

## 6. 前端 - CSS

- [x] 6.1 建立 `frontend/css/knowledge-base.css`
  - 三欄式佈局樣式
  - 搜尋區樣式
  - 列表項目樣式
  - 內容區樣式（Markdown 渲染）
  - 標籤樣式
  - 編輯表單樣式
  - 版本歷史面板樣式
- [x] 6.2 附件區域樣式
  - 附件列表樣式
  - 附件項目樣式（圖示、名稱、大小、位置標籤）
  - 上傳區域樣式（拖放區、進度條）
- [x] 6.3 附件區固定底部佈局
  - 使用 Flexbox 實現固定底部顯示
  - 內容區可捲動，附件區維持可見
  - 附件區最大高度 180px，內部可捲動
- [x] 6.4 上傳附件彈出視窗樣式
  - Modal overlay 使用 `--bg-overlay-dark`
  - Modal 內容使用固定背景色 `#1e1e2e`
  - 表單欄位與按鈕樣式
- [x] 6.5 全域 CSS 變數統一
  - 新增表面與邊框變數到 `main.css`
  - 新增強調色變數到 `main.css`
  - 批次更新所有 CSS 檔案使用全域變數

## 7. 前端 - JavaScript

- [x] 7.1 建立 `frontend/js/knowledge-base.js`
  - `KnowledgeBaseApp` 類別
  - 初始化與 API 整合
  - 搜尋功能實作
  - 標籤過濾實作
  - CRUD 操作實作
  - Markdown 渲染（使用 marked.js 或類似）
  - 版本歷史功能實作

- [x] 7.2 整合到視窗系統
  - 修改 `frontend/js/desktop.js` 啟用知識庫圖示點擊
  - 修改 `frontend/js/window.js` 支援知識庫視窗

- [x] 7.3 附件功能 UI 實作
  - [x] 7.3.1 在知識詳情頁顯示附件列表
    - 顯示附件類型圖示（圖片、影片、文件等）
    - 顯示檔案大小
    - 顯示儲存位置（本機/NAS 標籤）
  - [x] 7.3.2 附件下載/預覽功能
    - 圖片：直接預覽
    - 其他：下載連結
  - [x] 7.3.3 附件上傳 UI
    - 上傳按鈕
    - 拖放上傳區域
    - 上傳進度顯示
  - [x] 7.3.4 附件刪除功能
    - 刪除按鈕
    - 確認對話框
    - 後端 API 呼叫
  - [x] 7.3.5 上傳附件彈出視窗
    - 檔案選擇對話框
    - 描述輸入欄位
    - 檔案大小與儲存位置預估顯示
  - [x] 7.3.6 附件元資料編輯
    - 編輯按鈕與內聯編輯表單
    - PATCH API 呼叫
- [x] 7.4 NotificationModule API 整合
  - 修正所有通知呼叫使用正確的物件格式
  - 格式：`{ title, message, icon }`

## 8. 前端 - HTML

- [x] 8.1 在 `frontend/index.html` 加入必要的第三方庫
  - marked.js（Markdown 渲染）
  - highlight.js（程式碼高亮，選用）

## 9. 測試

- [x] 9.1 建立後端 API 測試 `backend/tests/test_knowledge.py`
- [x] 9.2 手動測試知識 CRUD 流程
- [x] 9.3 測試搜尋功能與標籤過濾
- [x] 9.4 測試 Markdown 渲染與圖片顯示
- [x] 9.5 測試版本歷史功能
- [x] 9.6 測試 NAS 附件上傳與顯示
- [x] 9.7 測試附件元資料編輯功能
- [x] 9.8 測試刪除知識連帶刪除附件
- [x] 9.9 測試上傳附件彈出視窗 UI

## 10. 初始知識整理

從現有專案整理知識作為知識庫初始內容：

### 10.1 RosAGV (`~/RosAGV`)
- [x] 10.1.1 整理 `docs-ai/context/` 背景知識
  - kb-003: RosAGV 專案整體概覽
  - kb-007: RosAGV 技術棧和依賴關係
  - kb-010: AGVC 管理工作空間概覽
- [x] 10.1.2 整理 `docs-ai/knowledge/` 領域知識
  - kb-004: AGV 車型特性和應用場景
  - kb-005: AGV 狀態機架構與流程
  - kb-006: ROS 2 介面設計和協定
  - kb-009: Keyence PLC 通訊協議
- [x] 10.1.3 整理 `docs-ai/operations/` 操作指導
  - kb-008: 核心開發原則
  - kb-011: 故障排除操作指導
- [x] 10.1.4 為每個知識加上元資料（標籤、來源）

### 10.2 ChingTech-OS (`~/SDD/ching-tech-os`)
- [x] 10.2.1 整理專案架構知識
- [x] 10.2.2 整理設計文件知識 (知識庫功能本身即為設計文件)
- [x] 10.2.3 整理開發指引知識 (參考 kb-001 知識庫使用說明)

### 10.3 Jaba (`~/SDD/jaba`)
- [x] 10.3.1 整理專案相關知識
  - kb-012: Jaba 菜單圖片辨識功能設計

### 10.4 Jaba-Line-Bot (`~/SDD/jaba-line-bot`)
- [x] 10.4.1 整理 LINE Bot 相關知識
  - kb-013: Jaba LINE Bot 系統架構

### 10.5 Fish-CV (`~/SDD/fish-cv`)
- [x] 10.5.1 整理電腦視覺相關知識
  - kb-014: Fish-CV YOLO 魚苗偵測訓練手冊

## 11. 文件

- [x] 11.1 建立知識庫使用說明（作為第一個知識條目）
- [x] 11.2 更新 README.md 說明知識庫功能

## 依賴關係

```
1.x → 2.x → 3.x → 4.x → 5.x → 9.1
                        ↓
6.x → 7.x → 8.x → 9.2-9.6

10.x 可在 API 完成後平行進行
```

可平行進行：
- 後端 (3.x-5.x) 與 前端 (6.x-8.x) 可獨立開發
- 測試在對應功能完成後進行
- 初始知識整理 (10.x) 可在 API 完成後開始
