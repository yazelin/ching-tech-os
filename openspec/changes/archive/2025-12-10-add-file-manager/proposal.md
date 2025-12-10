# Change: 新增檔案管理應用程式

## Why
目前桌面上的「檔案管理」圖示點擊後顯示「功能開發中」。使用者需要能夠瀏覽 NAS 上的目錄和檔案、預覽文字和圖片內容、並執行基本的檔案操作（上傳、刪除、重命名、建立資料夾）。

## What Changes
- 新增檔案管理視窗（File Manager App）
- 後端新增檔案讀取、上傳、刪除、重命名、建立資料夾等 API
- 檔案管理內支援快速預覽（側邊或底部面板）
- 新增獨立的「圖片檢視器」和「文字檢視器」App，可由檔案管理雙擊開啟
- 支援的預覽類型：文字檔（txt, md, json, log 等）、圖片檔（jpg, png, gif, svg）

## Impact
- Affected specs: 新增 `file-manager`，修改 `backend-auth`
- Affected code:
  - `backend/src/ching_tech_os/api/nas.py` - 擴充檔案操作 API
  - `backend/src/ching_tech_os/services/smb.py` - 擴充 SMB 操作方法
  - `frontend/js/file-manager.js` - 新增檔案管理模組
  - `frontend/css/file-manager.css` - 新增樣式
  - `frontend/js/image-viewer.js` - 新增圖片檢視器
  - `frontend/js/text-viewer.js` - 新增文字檢視器
  - `frontend/js/desktop.js` - 修改開啟檔案管理的邏輯

## Technical Notes

### 檔案管理視窗架構
```
┌─────────────────────────────────────────────────────────┐
│ 檔案管理                                      _ □ ✕ │
├─────────────────────────────────────────────────────────┤
│ ← → ↑ 🔄 │ /home/yazelin/文件        │ 📤上傳 📁新增 │ （工具列）
├─────────────────────────────────────────────────────────┤
│                              │                          │
│   📁 資料夾1                  │   [預覽面板 - 右側]      │
│   📁 資料夾2                  │                          │
│   📄 文件.txt   ✓             │   選中檔案的快速預覽      │
│   🖼️ 圖片.jpg   ✓             │   - 圖片：縮圖           │
│   📄 報告.md                  │   - 文字：內容前 N 行    │
│                              │   - 其他：檔案資訊       │
│                              │                          │
├─────────────────────────────────────────────────────────┤
│ 6 個項目 │ 選取 2 個 │ 右鍵：刪除/重命名/下載          │ （狀態列）
└─────────────────────────────────────────────────────────┘
```

### 設計決策
- **預覽面板位置**：右側固定（類似 macOS Finder 欄位檢視）
- **多選支援**：Ctrl+點擊 多選、Shift+點擊 範圍選取
- **刪除邏輯**：非空資料夾遞迴刪除，刪除前顯示警告確認
- **下載功能**：支援將 NAS 檔案下載到本機

### SMB 實作架構
由於 `smbprotocol` Python 套件不支援 NetShareEnum（列出共享），採用混合方式：

| 操作 | 使用工具 | 說明 |
|------|----------|------|
| `list_shares()` | `smbclient -L -g` | 動態列出 NAS 所有共享（subprocess） |
| `browse_directory()` | `smbprotocol` | 瀏覽資料夾內容 |
| `read_file()` | `smbprotocol` | 讀取檔案 |
| `write_file()` | `smbprotocol` | 上傳/寫入檔案 |
| `delete_item()` | `smbprotocol` | 刪除檔案/資料夾 |
| `rename_item()` | `smbprotocol` | 重命名 |
| `create_directory()` | `smbprotocol` | 建立資料夾 |

**注意**：系統需安裝 `smbclient`（samba-client 套件）

### 新增後端 API
| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/nas/file` | 讀取檔案內容（支援文字/二進位） |
| GET | `/api/nas/download` | 下載檔案（回傳 attachment） |
| POST | `/api/nas/upload` | 上傳檔案 |
| DELETE | `/api/nas/file` | 刪除檔案或資料夾（支援遞迴） |
| PATCH | `/api/nas/rename` | 重命名檔案或資料夾 |
| POST | `/api/nas/mkdir` | 建立資料夾 |

### 檔案讀取 API 設計
```python
GET /api/nas/file?path=/share/folder/file.txt
# 回傳：
# - 文字檔：{ "content": "...", "mime_type": "text/plain" }
# - 圖片檔：直接回傳二進位（Content-Type: image/jpeg）
```

### 預覽支援的 MIME 類型
**文字類（內嵌預覽 + 文字檢視器）：**
- text/plain (.txt)
- text/markdown (.md)
- application/json (.json)
- text/csv (.csv)
- text/html (.html)
- 其他 text/* 類型

**圖片類（內嵌預覽 + 圖片檢視器）：**
- image/jpeg (.jpg, .jpeg)
- image/png (.png)
- image/gif (.gif)
- image/svg+xml (.svg)
- image/webp (.webp)

### 獨立 App 開啟方式
- 雙擊檔案 → 根據副檔名判斷類型 → 開啟對應的檢視器 App
- 圖片檢視器：支援縮放、上/下一張
- 文字檢視器：顯示純文字內容、支援語法高亮（選配）

## Dependencies
- 已完成 `add-backend-nas-auth`（NAS 認證和基本瀏覽 API）
- 已有 WindowModule 視窗管理系統
- 系統需安裝 `smbclient`（用於列出 NAS 共享）：`apt install smbclient`

## Out of Scope
- PDF 預覽（需要額外處理）
- Office 文件預覽（docx, xlsx 等）
- 影片/音訊播放
- 檔案搜尋功能
- 拖放上傳
