# 檔案管理應用程式

本文件說明檔案管理（File Manager）的設計與實作。

## 功能概覽

- 瀏覽 NAS 共享資料夾與子目錄
- **搜尋功能**（遞迴搜尋、支援萬用字元）
- 檔案/資料夾的選取（單選、多選、範圍選取）
- 右側預覽面板（圖片縮圖、文字預覽）
- **可調整寬度的分隔線**（拖曳調整預覽面板大小）
- **可編輯的路徑欄**（點擊路徑欄直接輸入路徑）
- 檔案操作：上傳、下載、刪除、重命名、新增資料夾
- 右鍵選單
- 獨立的圖片檢視器與文字檢視器
- **統一的深色主題捲軸樣式**

## 視窗結構

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 檔案管理                                                 [_] [□] [✕]    │
├─────────────────────────────────────────────────────────────────────────┤
│ [←] [→] [↑] [🔄]  │  /home/文件  (點擊可編輯)  │       [上傳] [新增]   │
├────────────────────────────────────────────┬┬───────────────────────────┤
│ 名稱                    大小      修改日期  ││ 預覽                      │
├─────────────────────────────────────────────┤├───────────────────────────┤
│ 📁 資料夾1               -        2025/12/1 ││ ┌───────────────────────┐ │
│ 📁 資料夾2               -        2025/12/5 ││ │                       │ │
│ 📄 文件.txt           1.2 KB     2025/12/10 ││ │    [圖片/文字預覽]    │ │
│ 🖼️ 圖片.jpg            500 KB    2025/12/10 ││ │                       │ │
│ 📄 報告.md             2.5 KB     2025/12/8 ││ └───────────────────────┘ │
│                                             │├───────────────────────────┤
│                                             ││ 圖片.jpg                  │
│                                             ││ 類型: JPG  大小: 500 KB   │
│                                             ││ 修改: 2025/12/10 14:30    │
├─────────────────────────────────────────────┴┴───────────────────────────┤
│ 5 個項目 │ 選取 1 個                                                     │
└─────────────────────────────────────────────────────────────────────────┘
          ↑                                   ↑↑
     檔案列表                            分隔線（可拖曳）
```

### 新版預覽面板佈局

預覽面板分為兩個區域：
1. **上方 - 預覽區 (fm-preview-main)**：顯示圖片縮圖、文字內容或檔案圖示
2. **下方 - 資訊區 (fm-preview-info)**：顯示檔名、類型、大小、修改日期

## 前端檔案

| 檔案 | 說明 |
|------|------|
| `frontend/js/file-manager.js` | FileManagerModule 主模組 |
| `frontend/css/file-manager.css` | 樣式（工具列、列表、預覽、選單、對話框、捲軸） |
| `frontend/js/image-viewer.js` | ImageViewerModule 圖片檢視器 |
| `frontend/js/text-viewer.js` | TextViewerModule 文字檢視器 |
| `frontend/css/viewer.css` | 檢視器共用樣式 |

## FileManagerModule API

### 開啟與關閉

```javascript
// 開啟檔案管理視窗
FileManagerModule.open();

// 關閉視窗
FileManagerModule.close();
```

### 內部狀態

```javascript
{
  windowId: null,           // 視窗 ID
  currentPath: '/',         // 目前路徑
  items: [],                // 目前資料夾的項目列表
  selectedItems: new Set(), // 選取的項目（檔名）
  lastSelectedIndex: -1,    // 上次選取的索引（用於 Shift 範圍選取）
  isEditingPath: false,     // 是否正在編輯路徑
  previewWidth: 300,        // 預覽面板寬度（可拖曳調整）
}
```

## 使用者操作

### 導航

| 操作 | 說明 |
|------|------|
| 雙擊資料夾 | 進入該資料夾 |
| 雙擊檔案 | 開啟對應的檢視器 |
| 點擊「←」 | 上一步（歷史記錄） |
| 點擊「→」 | 下一步（歷史記錄） |
| 點擊「↑」 | 上層資料夾 |
| 點擊「🔄」 | 重新整理 |
| **點擊路徑欄** | 進入編輯模式，可直接輸入路徑 |
| **Enter（路徑編輯中）** | 導航至輸入的路徑 |
| **Esc（路徑編輯中）** | 取消編輯，恢復顯示模式 |

### 選取

| 操作 | 說明 |
|------|------|
| 點擊項目 | 單選（取消其他選取） |
| Ctrl + 點擊 | 多選（切換該項目的選取狀態） |
| Shift + 點擊 | 範圍選取（從上次選取到目前項目） |

### 調整預覽面板大小

1. 將滑鼠移至列表與預覽面板之間的分隔線
2. 滑鼠變成左右箭頭（col-resize）
3. 按住並拖曳可調整預覽面板寬度
4. 最小寬度 200px，最大寬度為視窗寬度的 50%

### 搜尋功能

從目前路徑遞迴搜尋檔案和資料夾。

**使用方式：**
1. 在搜尋框輸入關鍵字
2. 按 Enter 執行搜尋
3. 雙擊結果可導航到該位置
4. 按 Escape 或點擊 × 清除搜尋

**支援萬用字元：**
- `*` 匹配任意字元（如 `*.py` 搜尋所有 Python 檔案）
- `?` 匹配單一字元
- 不輸入萬用字元會自動變成 `*關鍵字*`

**限制：**
- 最大搜尋深度：5 層（可調整，最大 10 層）
- 最大結果數量：100 筆（可調整，最大 500 筆）

**API：**
```
GET /api/nas/search?path=/home&query=*.py&max_depth=5&max_results=100
```

### 右鍵選單

```
┌──────────────┐
│ 📂 開啟       │  ← 資料夾或檔案
│ 📥 下載       │  ← 僅檔案
│ ✏️ 重新命名    │
│ 🗑️ 刪除       │
└──────────────┘
```

## 預覽面板

### 支援的預覽類型

**文字檔**（顯示前 50 行）：
- `.txt`, `.md`, `.json`, `.log`, `.csv`, `.html`, `.css`, `.js`, `.xml`, `.yaml`, `.yml`

**圖片檔**（顯示縮圖）：
- `.jpg`, `.jpeg`, `.png`, `.gif`, `.svg`, `.webp`

**其他檔案**：
- 顯示大型檔案圖示和基本資訊（名稱、類型、大小、修改日期）

### 預覽面板結構

```html
<div class="fm-preview">
  <div class="fm-preview-header">預覽</div>
  <div class="fm-preview-content">
    <!-- 預覽主區域 -->
    <div class="fm-preview-main">
      <!-- 圖片: fm-preview-image > img -->
      <!-- 文字: fm-preview-text -->
      <!-- 圖示: fm-preview-icon-large -->
    </div>
    <!-- 檔案資訊 -->
    <div class="fm-preview-info">
      <div class="fm-preview-filename">檔名</div>
      <div class="fm-preview-meta">
        <div class="fm-preview-meta-item">類型: JPG</div>
        <div class="fm-preview-meta-item">大小: 500 KB</div>
        <div class="fm-preview-meta-item">修改: 2025/12/10</div>
      </div>
    </div>
  </div>
</div>
```

## 檔案操作

### 上傳

1. 點擊工具列「上傳」按鈕
2. 選擇本機檔案
3. POST `/api/nas/upload` (multipart/form-data)
4. 成功後重新整理列表

### 下載

1. 選取檔案 → 右鍵 → 下載
2. 建立隱藏的 `<a>` 元素
3. `href` 指向 `/api/nas/download?path=...`
4. 觸發點擊下載

### 刪除

1. 選取項目 → 右鍵 → 刪除
2. 顯示確認對話框
3. 如果包含非空資料夾，顯示遞迴刪除警告
4. DELETE `/api/nas/file`
5. 成功後重新整理列表

### 重命名

1. 選取項目 → 右鍵 → 重新命名
2. 顯示輸入對話框
3. PATCH `/api/nas/rename`
4. 成功後重新整理列表

### 新增資料夾

1. 點擊工具列「新增資料夾」按鈕
2. 顯示輸入對話框
3. POST `/api/nas/mkdir`
4. 成功後重新整理列表

## 圖片檢視器 (ImageViewerModule)

### 功能

- 顯示圖片
- 縮放：10% ~ 500%（每次 ±25%）
- 滾輪縮放
- 適合視窗大小
- 拖曳平移

### 開啟方式

```javascript
// 從檔案管理雙擊圖片時呼叫
ImageViewerModule.open('/home/文件/photo.jpg', 'photo.jpg');
```

### 視窗結構

```
┌─────────────────────────────────────────┐
│ photo.jpg                    [_] [□] [✕] │
├─────────────────────────────────────────┤
│                                         │
│            [圖片內容]                    │
│                                         │
├─────────────────────────────────────────┤
│ [➖] [100%] [➕] [適合大小]              │  ← 控制列
└─────────────────────────────────────────┘
```

## 文字檢視器 (TextViewerModule)

### 功能

- 顯示純文字內容
- 可捲動
- 顯示行數

### 開啟方式

```javascript
// 從檔案管理雙擊文字檔時呼叫
TextViewerModule.open('/home/文件/readme.txt', 'readme.txt');
```

### 視窗結構

```
┌─────────────────────────────────────────┐
│ readme.txt                   [_] [□] [✕] │
├─────────────────────────────────────────┤
│ 1 │ # README                            │
│ 2 │                                     │
│ 3 │ This is a sample file.              │
│ 4 │ ...                                 │
│                                         │
├─────────────────────────────────────────┤
│ 4 行                                    │  ← 狀態列
└─────────────────────────────────────────┘
```

## CSS 類別

### 主要容器

```css
.file-manager           /* 主容器 */
.fm-toolbar             /* 工具列 */
.fm-main                /* 內容區（列表 + 分隔線 + 預覽） */
.fm-file-list           /* 檔案列表 */
.fm-resizer             /* 可拖曳分隔線 */
.fm-preview             /* 預覽面板 */
.fm-statusbar           /* 狀態列 */
```

### 路徑欄

```css
.fm-path-container      /* 路徑欄容器 */
.fm-path-display        /* 路徑顯示模式 */
.fm-path-input-wrapper  /* 路徑輸入模式容器 */
.fm-path-input          /* 路徑輸入框 */
```

### 列表標頭

```css
.fm-list-header         /* 列表標頭列 */
.fm-list-header-name    /* 名稱欄 */
.fm-list-header-size    /* 大小欄 */
.fm-list-header-date    /* 修改日期欄 */
```

### 項目

```css
.fm-file-item           /* 單一項目 */
.fm-file-item.selected  /* 選取狀態 */
.fm-file-icon           /* 圖示 */
.fm-file-name           /* 檔名 */
.fm-file-size           /* 大小 */
.fm-file-modified       /* 日期 */
```

### 預覽面板

```css
.fm-preview-header      /* 預覽標題 */
.fm-preview-content     /* 預覽內容區 */
.fm-preview-main        /* 預覽主區（圖片/文字） */
.fm-preview-image       /* 圖片預覽容器 */
.fm-preview-text        /* 文字預覽容器 */
.fm-preview-icon-large  /* 大型圖示（非預覽檔案） */
.fm-preview-info        /* 檔案資訊區 */
.fm-preview-filename    /* 檔名 */
.fm-preview-meta        /* 元資料容器 */
.fm-preview-meta-item   /* 元資料項目 */
```

### 分隔線

```css
.fm-resizer             /* 分隔線 */
.fm-resizer:hover       /* 懸停時高亮 */
.fm-resizer.dragging    /* 拖曳中 */
```

### 捲軸（深色主題）

```css
.file-manager ::-webkit-scrollbar           /* 捲軸整體 */
.file-manager ::-webkit-scrollbar-track     /* 捲軸軌道 */
.file-manager ::-webkit-scrollbar-thumb     /* 捲軸滑塊 */
.file-manager ::-webkit-scrollbar-thumb:hover /* 滑塊懸停 */
```

### 右鍵選單

```css
.fm-context-menu        /* 選單容器 */
.fm-context-menu-item   /* 選單項目 */
.fm-context-menu-item:hover /* 懸停狀態 */
.fm-context-menu-divider /* 分隔線 */
```

### 對話框

```css
.fm-dialog-overlay      /* 遮罩 */
.fm-dialog              /* 對話框 */
.fm-dialog-header       /* 標題區 */
.fm-dialog-body         /* 內容區 */
.fm-dialog-footer       /* 按鈕區 */
.fm-dialog-input        /* 輸入框 */
```

## 圖示

使用 `frontend/js/icons.js` 提供的 SVG 圖示：

| 圖示名稱 | 用途 |
|----------|------|
| `folder` | 資料夾 |
| `file` | 一般檔案 |
| `file-document` | 文字檔 |
| `file-image` | 圖片檔 |
| `code-braces` | 程式碼檔 |
| `chevron-left` | 上一步 |
| `chevron-right` | 下一步 |
| `chevron-up` | 上層 |
| `refresh` | 重新整理 |
| `upload` | 上傳 |
| `folder-plus` | 新增資料夾 |
| `download` | 下載 |
| `edit` | 重命名 |
| `delete` | 刪除 |
| `zoom-in` | 放大 |
| `zoom-out` | 縮小 |
| `fit-screen` | 適合大小 |
| `information` | 資訊/錯誤提示 |
| `close` | 關閉 |

## 相關文件

- [SMB/NAS 架構](./smb-nas-architecture.md) - 後端 SMB 連線實作
- `openspec/changes/add-file-manager/proposal.md` - 功能規格
- `openspec/changes/add-file-manager/specs/file-manager/spec.md` - 詳細需求
