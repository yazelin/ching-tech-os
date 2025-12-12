# 前端開發指南

## 概覽

ChingTech OS 前端採用純 HTML5/CSS3/JavaScript（無框架），使用 IIFE（Immediately Invoked Function Expression）模式封裝各功能模組。

## 技術棧

| 技術 | 用途 |
|------|------|
| HTML5 | 語義化標籤結構 |
| CSS3 | CSS Variables、Flexbox、Grid |
| JavaScript (ES6+) | 模組化開發 |
| Socket.IO Client | 即時通訊（終端機、AI） |
| xterm.js | 終端機模擬器 |
| marked.js | Markdown 渲染 |

## 專案結構

```
frontend/
├── index.html          # 桌面主頁
├── login.html          # 登入頁面
├── css/
│   ├── main.css        # 設計系統、CSS 變數、基礎元件
│   ├── login.css       # 登入頁面
│   ├── header.css      # Header Bar
│   ├── desktop.css     # 桌面區域
│   ├── taskbar.css     # Taskbar/Dock
│   ├── window.css      # 視窗系統
│   ├── ai-assistant.css
│   ├── file-manager.css
│   ├── terminal.css
│   ├── knowledge-base.css
│   ├── code-editor.css
│   ├── project-management.css
│   ├── message-center.css
│   ├── settings.css
│   ├── user-profile.css
│   └── viewer.css      # 圖片/文字檢視器
├── js/
│   ├── icons.js        # SVG 圖示庫
│   ├── api-client.js   # REST API 客戶端
│   ├── socket-client.js # Socket.IO 客戶端
│   ├── login.js        # 登入模組
│   ├── header.js       # Header 模組
│   ├── desktop.js      # 桌面模組
│   ├── taskbar.js      # Taskbar 模組
│   ├── window.js       # 視窗管理
│   ├── theme.js        # 主題切換
│   ├── notification.js # 通知系統
│   ├── ai-assistant.js
│   ├── file-manager.js
│   ├── terminal.js
│   ├── knowledge-base.js
│   ├── code-editor.js
│   ├── project-management.js
│   ├── message-center.js
│   ├── settings.js
│   ├── user-profile.js
│   ├── image-viewer.js
│   ├── text-viewer.js
│   ├── matrix-rain.js  # 登入頁 Matrix 效果
│   └── device-fingerprint.js # 裝置指紋
└── assets/
    ├── icons/          # 應用程式圖示
    └── images/         # Logo、背景、Favicon
```

## IIFE 模組模式

所有 JavaScript 模組使用 IIFE 封裝，避免全域命名空間污染：

```javascript
const ModuleName = (function() {
  'use strict';

  // 私有變數
  let privateVar = null;

  // 私有函式
  function privateFunction() {
    // ...
  }

  // 公開函式
  function publicFunction() {
    // ...
  }

  // 初始化
  function init() {
    // DOM Ready 後的初始化邏輯
  }

  // 公開 API
  return {
    init,
    publicFunction
  };
})();

// 頁面載入後初始化
document.addEventListener('DOMContentLoaded', () => {
  ModuleName.init();
});
```

## 模組說明

### 核心模組

| 模組 | 檔案 | 說明 |
|------|------|------|
| APIClient | `api-client.js` | REST API 封裝，Session Token 管理 |
| SocketClient | `socket-client.js` | Socket.IO 連線管理 |
| WindowManager | `window.js` | 視窗建立、拖曳、縮放、聚焦 |
| ThemeManager | `theme.js` | 主題切換（亮色/暗色） |
| NotificationManager | `notification.js` | Toast 通知 |

### 桌面模組

| 模組 | 檔案 | 說明 |
|------|------|------|
| HeaderModule | `header.js` | 系統時間、使用者資訊、登出 |
| DesktopModule | `desktop.js` | 桌面圖示管理、應用程式啟動 |
| TaskbarModule | `taskbar.js` | Dock 圖示、運行指示器、視窗選單 |

### 應用程式模組

| 模組 | 檔案 | 說明 |
|------|------|------|
| FileManager | `file-manager.js` | NAS 檔案瀏覽、上傳、下載 |
| TerminalApp | `terminal.js` | PTY 終端機（xterm.js） |
| AIAssistant | `ai-assistant.js` | AI 對話介面（Markdown 渲染） |
| KnowledgeBase | `knowledge-base.js` | 知識庫管理 |
| CodeEditor | `code-editor.js` | code-server 整合 |
| ProjectManagement | `project-management.js` | 專案管理 |
| MessageCenter | `message-center.js` | 訊息中心 |
| Settings | `settings.js` | 系統設定 |
| ImageViewer | `image-viewer.js` | 圖片檢視器（縮放、拖曳） |
| TextViewer | `text-viewer.js` | 文字檢視器（Markdown/JSON/YAML/XML） |

## 新增應用程式

### 1. 建立 CSS 檔案

```css
/* frontend/css/my-app.css */
.my-app-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.my-app-content {
  flex: 1;
  padding: var(--spacing-md);
  overflow: auto;
}
```

### 2. 建立 JS 模組

```javascript
/* frontend/js/my-app.js */
const MyApp = (function() {
  'use strict';

  function createContent() {
    const container = document.createElement('div');
    container.className = 'my-app-container';
    container.innerHTML = `
      <div class="my-app-content">
        <!-- 應用程式內容 -->
      </div>
    `;
    return container;
  }

  function open(windowElement) {
    const contentArea = windowElement.querySelector('.window-content');
    contentArea.innerHTML = '';
    contentArea.appendChild(createContent());
  }

  return { open };
})();
```

### 3. 在 index.html 引入

```html
<!-- CSS -->
<link rel="stylesheet" href="css/my-app.css">

<!-- JS -->
<script src="js/my-app.js"></script>
```

### 4. 在 desktop.js 註冊

```javascript
// applications 陣列
{ id: 'my-app', name: '我的應用', icon: 'mdi-application' }

// openApp 函式
case 'my-app':
  MyApp.open(windowElement);
  break;
```

### 5. 在 taskbar.js 註冊（選用）

```javascript
// 若要顯示在 Taskbar
{ id: 'my-app', name: '我的應用', icon: 'mdi-application', pinned: true }
```

## API 呼叫

使用 `APIClient` 模組進行 REST API 呼叫：

```javascript
// GET 請求
const data = await APIClient.get('/api/knowledge');

// POST 請求
const result = await APIClient.post('/api/knowledge', {
  title: '標題',
  content: '內容'
});

// PUT 請求
await APIClient.put(`/api/knowledge/${id}`, updatedData);

// DELETE 請求
await APIClient.delete(`/api/knowledge/${id}`);
```

## Socket.IO 使用

```javascript
// 取得 Socket 實例
const socket = SocketClient.getSocket();

// 發送事件
socket.emit('terminal:input', { sessionId, data });

// 監聽事件
socket.on('terminal:output', (data) => {
  // 處理輸出
});
```

## SVG 圖示

使用 `icons.js` 中的 `getIcon()` 函式取得 SVG 圖示：

```javascript
// 在 JS 中
const iconSvg = getIcon('mdi-folder');
element.innerHTML = `<span class="icon">${iconSvg}</span>`;

// 在 HTML 中使用 data-icon 屬性，由 icons.js 自動替換
<span class="icon" data-icon="mdi-folder"></span>
```

## 主題切換

```javascript
// 切換主題
ThemeManager.setTheme('light'); // 或 'dark'

// 取得當前主題
const currentTheme = ThemeManager.getTheme();

// 監聽主題變更
ThemeManager.onThemeChange((theme) => {
  // 更新 UI
});
```

## 視窗管理

```javascript
// 建立視窗
const windowElement = WindowManager.create({
  title: '我的應用',
  icon: 'mdi-application',
  width: 800,
  height: 600,
  appId: 'my-app'
});

// 關閉視窗
WindowManager.close(windowElement);

// 聚焦視窗
WindowManager.focus(windowElement);

// 最小化視窗
WindowManager.minimize(windowElement);
```

## TextViewer 顯示模式

TextViewer 支援多種顯示模式，根據副檔名自動選擇：

| 模式 | 副檔名 | 功能 |
|------|--------|------|
| 原始文字 | 其他 | 純文字顯示 |
| Markdown | `.md`, `.markdown` | 使用 marked.js 渲染 |
| JSON | `.json` | 解析、格式化、語法色彩 |
| YAML | `.yaml`, `.yml` | 語法色彩標記 |
| XML | `.xml`, `.html`, `.svg` | 解析、格式化、語法色彩 |

使用方式：

```javascript
// 開啟文字檢視器
TextViewerModule.open('/path/to/file.md', 'file.md');
```

## Markdown 渲染

系統提供通用的 `.markdown-rendered` CSS 類別，支援暗色/亮色主題：

```javascript
// 使用 marked.js 渲染
const html = marked.parse(markdownText);

// 套用樣式
element.innerHTML = `<div class="markdown-rendered">${html}</div>`;
```

支援的 Markdown 元素：
- 標題（h1-h6）
- 段落、列表
- 代碼塊、行內代碼
- 引用區塊
- 表格
- 連結、圖片
- 水平分隔線

## 注意事項

### CSS 變數使用

所有樣式應使用 `main.css` 中定義的 CSS 變數：

```css
/* 正確 */
.my-element {
  background: var(--bg-surface);
  color: var(--color-text-primary);
  border: 1px solid var(--border-light);
}

/* 避免硬編碼顏色 */
.my-element {
  background: #1a1a1a;  /* 不要這樣做 */
}
```

### 下拉選單樣式

必須同時為 `<select>` 和 `<option>` 定義樣式：

```css
.my-select {
  background: var(--bg-surface);
  color: var(--color-text-primary);
}

/* 重要：必須為 option 定義樣式 */
.my-select option {
  background-color: var(--color-background);
  color: var(--color-text-primary);
}
```

### 模態框

- 使用 `var(--bg-overlay-dark)` 作為遮罩背景
- 模態框本體使用不透明背景（如 `var(--modal-bg)`）

## 除錯

- 使用瀏覽器開發者工具（F12）
- Console 日誌會顯示 API 錯誤
- 網路面板可檢視 API 請求/回應
- Socket.IO 連線狀態在 Console 中輸出
