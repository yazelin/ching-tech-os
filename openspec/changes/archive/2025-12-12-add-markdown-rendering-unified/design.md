# Design: add-markdown-rendering-unified

## 架構概覽

本設計旨在建立統一的內容渲染系統，讓 Markdown、JSON、YAML、XML 等格式化內容在各模組中呈現一致且美觀的視覺效果。

```
┌─────────────────────────────────────────────────────────────────┐
│                      統一渲染系統                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Markdown    │  │  JSON/YAML   │  │    XML       │          │
│  │  Renderer    │  │  Formatter   │  │  Formatter   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └────────────┬────┴────────┬────────┘                   │
│                      ▼             ▼                            │
│              ┌───────────────────────────┐                      │
│              │    統一 CSS 樣式系統       │                      │
│              │  .markdown-rendered       │                      │
│              │  .formatted-data          │                      │
│              └───────────┬───────────────┘                      │
│                          │                                      │
│              ┌───────────┴───────────┐                          │
│              │   CSS 變數 (主題支援)   │                          │
│              │   暗色主題 / 亮色主題   │                          │
│              └───────────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 模組應用

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI 助手        │    │   專案管理       │    │   TextViewer    │
│   訊息顯示       │    │   會議內容       │    │   檔案預覽       │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ Markdown 渲染   │    │ Markdown 渲染   │    │ 模式切換:       │
│                 │    │                 │    │ - Raw           │
│                 │    │                 │    │ - Markdown      │
│                 │    │                 │    │ - JSON          │
│                 │    │                 │    │ - YAML          │
│                 │    │                 │    │ - XML           │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────────────────┴──────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │   統一渲染系統          │
                    └───────────────────────┘
```

## CSS 變數設計

### 主題變數命名規範

```css
/* Markdown 渲染相關 */
--md-heading-color          /* 標題顏色 */
--md-text-color             /* 內文顏色 */
--md-link-color             /* 連結顏色 */
--md-code-bg                /* 行內代碼背景 */
--md-code-color             /* 行內代碼文字 */
--md-pre-bg                 /* 代碼塊背景 */
--md-pre-border             /* 代碼塊邊框 */
--md-blockquote-border      /* 引用邊框 */
--md-blockquote-bg          /* 引用背景 */
--md-table-border           /* 表格邊框 */
--md-table-header-bg        /* 表格標題背景 */
--md-hr-color               /* 水平線顏色 */

/* 格式化資料相關 */
--fd-string-color           /* 字串顏色 */
--fd-number-color           /* 數字顏色 */
--fd-boolean-color          /* 布林值顏色 */
--fd-null-color             /* null 顏色 */
--fd-key-color              /* 鍵名顏色 */
--fd-punctuation-color      /* 標點符號顏色 */
--fd-tag-color              /* XML 標籤顏色 */
--fd-attribute-color        /* XML 屬性顏色 */
--fd-comment-color          /* 註解顏色 */
```

### 暗色主題建議色彩

```css
:root, [data-theme="dark"] {
  /* Markdown */
  --md-heading-color: #e2e8f0;
  --md-text-color: #cbd5e1;
  --md-link-color: #60a5fa;
  --md-code-bg: rgba(139, 92, 246, 0.15);
  --md-code-color: #c4b5fd;
  --md-pre-bg: #1e293b;
  --md-pre-border: #334155;
  --md-blockquote-border: #60a5fa;
  --md-blockquote-bg: rgba(96, 165, 250, 0.1);
  --md-table-border: #334155;
  --md-table-header-bg: #1e293b;
  --md-hr-color: #334155;

  /* 格式化資料 */
  --fd-string-color: #a5d6a7;       /* 淡綠色 */
  --fd-number-color: #90caf9;       /* 淡藍色 */
  --fd-boolean-color: #ce93d8;      /* 淡紫色 */
  --fd-null-color: #ef9a9a;         /* 淡紅色 */
  --fd-key-color: #81d4fa;          /* 天藍色 */
  --fd-punctuation-color: #9e9e9e; /* 灰色 */
  --fd-tag-color: #ef5350;          /* 紅色 */
  --fd-attribute-color: #ffb74d;    /* 橙色 */
  --fd-comment-color: #757575;      /* 深灰色 */
}
```

### 亮色主題建議色彩

```css
[data-theme="light"] {
  /* Markdown */
  --md-heading-color: #1e293b;
  --md-text-color: #334155;
  --md-link-color: #2563eb;
  --md-code-bg: rgba(139, 92, 246, 0.1);
  --md-code-color: #7c3aed;
  --md-pre-bg: #f1f5f9;
  --md-pre-border: #e2e8f0;
  --md-blockquote-border: #2563eb;
  --md-blockquote-bg: rgba(37, 99, 235, 0.05);
  --md-table-border: #e2e8f0;
  --md-table-header-bg: #f8fafc;
  --md-hr-color: #e2e8f0;

  /* 格式化資料 */
  --fd-string-color: #2e7d32;       /* 深綠色 */
  --fd-number-color: #1565c0;       /* 深藍色 */
  --fd-boolean-color: #7b1fa2;      /* 深紫色 */
  --fd-null-color: #c62828;         /* 深紅色 */
  --fd-key-color: #0277bd;          /* 藍色 */
  --fd-punctuation-color: #616161; /* 灰色 */
  --fd-tag-color: #d32f2f;          /* 紅色 */
  --fd-attribute-color: #ef6c00;    /* 橙色 */
  --fd-comment-color: #9e9e9e;      /* 灰色 */
}
```

## 格式化渲染實作

### JSON 格式化函式

```javascript
/**
 * 格式化 JSON 並加上語法色彩
 * @param {string} jsonString - 原始 JSON 字串
 * @returns {{ html: string, error: string|null }} 格式化結果
 */
function formatJson(jsonString) {
  try {
    const obj = JSON.parse(jsonString);
    const formatted = JSON.stringify(obj, null, 2);
    return { html: syntaxHighlightJson(formatted), error: null };
  } catch (e) {
    return { html: escapeHtml(jsonString), error: e.message };
  }
}

/**
 * JSON 語法色彩渲染
 * @param {string} json - 格式化後的 JSON 字串
 * @returns {string} 帶有 HTML 標籤的字串
 */
function syntaxHighlightJson(json) {
  // 轉義 HTML
  json = escapeHtml(json);

  // 套用語法色彩
  return json
    // 字串 (包含鍵名)
    .replace(/"([^"\\]*(\\.[^"\\]*)*)"/g, (match, p1, offset, string) => {
      // 判斷是否為鍵名（後面跟著冒號）
      const isKey = /:\s*$/.test(string.slice(0, string.indexOf(match) + match.length + 1).split('\n').pop() || '');
      if (isKey || string.charAt(string.indexOf(match) + match.length) === ':') {
        return `<span class="fd-key">${match}</span>`;
      }
      return `<span class="fd-string">${match}</span>`;
    })
    // 數字
    .replace(/\b(-?\d+\.?\d*)\b/g, '<span class="fd-number">$1</span>')
    // 布林值
    .replace(/\b(true|false)\b/g, '<span class="fd-boolean">$1</span>')
    // null
    .replace(/\bnull\b/g, '<span class="fd-null">null</span>');
}
```

### YAML 格式化函式

```javascript
/**
 * 格式化 YAML 並加上語法色彩
 * @param {string} yamlString - 原始 YAML 字串
 * @returns {string} 帶有 HTML 標籤的字串
 */
function formatYaml(yamlString) {
  const escaped = escapeHtml(yamlString);
  const lines = escaped.split('\n');

  return lines.map(line => {
    // 註解
    if (/^\s*#/.test(line)) {
      return `<span class="fd-comment">${line}</span>`;
    }

    // 鍵值對
    const kvMatch = line.match(/^(\s*)([^:]+)(:)(.*)$/);
    if (kvMatch) {
      const [, indent, key, colon, value] = kvMatch;
      let coloredValue = value;

      // 布林值
      if (/^\s*(true|false)\s*$/.test(value)) {
        coloredValue = value.replace(/(true|false)/, '<span class="fd-boolean">$1</span>');
      }
      // null
      else if (/^\s*(null|~)\s*$/.test(value)) {
        coloredValue = value.replace(/(null|~)/, '<span class="fd-null">$1</span>');
      }
      // 數字
      else if (/^\s*-?\d+\.?\d*\s*$/.test(value)) {
        coloredValue = value.replace(/(-?\d+\.?\d*)/, '<span class="fd-number">$1</span>');
      }
      // 字串（帶引號）
      else if (/^\s*["'].*["']\s*$/.test(value)) {
        coloredValue = `<span class="fd-string">${value}</span>`;
      }
      // 一般字串
      else if (value.trim()) {
        coloredValue = `<span class="fd-string">${value}</span>`;
      }

      return `${indent}<span class="fd-key">${key}</span><span class="fd-punctuation">${colon}</span>${coloredValue}`;
    }

    // 陣列項目
    if (/^\s*-\s/.test(line)) {
      return line.replace(/^(\s*)(-)(\s)/, '$1<span class="fd-punctuation">$2</span>$3');
    }

    return line;
  }).join('\n');
}
```

### XML 格式化函式

```javascript
/**
 * 格式化 XML 並加上語法色彩
 * @param {string} xmlString - 原始 XML 字串
 * @returns {{ html: string, error: string|null }} 格式化結果
 */
function formatXml(xmlString) {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlString, 'text/xml');

    // 檢查解析錯誤
    const parseError = doc.querySelector('parsererror');
    if (parseError) {
      return { html: escapeHtml(xmlString), error: '無效的 XML 格式' };
    }

    // 美化 XML
    const formatted = formatXmlNode(doc.documentElement, 0);
    return { html: formatted, error: null };
  } catch (e) {
    return { html: escapeHtml(xmlString), error: e.message };
  }
}

/**
 * 遞迴格式化 XML 節點
 * @param {Node} node - XML 節點
 * @param {number} level - 縮排層級
 * @returns {string} 格式化的 HTML
 */
function formatXmlNode(node, level) {
  const indent = '  '.repeat(level);

  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent.trim();
    if (!text) return '';
    return `<span class="fd-string">${escapeHtml(text)}</span>`;
  }

  if (node.nodeType === Node.COMMENT_NODE) {
    return `${indent}<span class="fd-comment">&lt;!--${escapeHtml(node.textContent)}--&gt;</span>\n`;
  }

  let result = `${indent}<span class="fd-punctuation">&lt;</span><span class="fd-tag">${node.tagName}</span>`;

  // 屬性
  for (const attr of node.attributes || []) {
    result += ` <span class="fd-attribute">${attr.name}</span><span class="fd-punctuation">=</span><span class="fd-string">"${escapeHtml(attr.value)}"</span>`;
  }

  // 自閉合標籤
  if (!node.hasChildNodes()) {
    result += `<span class="fd-punctuation">/&gt;</span>\n`;
    return result;
  }

  result += `<span class="fd-punctuation">&gt;</span>`;

  // 子節點
  const children = Array.from(node.childNodes);
  const hasElementChildren = children.some(c => c.nodeType === Node.ELEMENT_NODE);

  if (hasElementChildren) {
    result += '\n';
    for (const child of children) {
      result += formatXmlNode(child, level + 1);
    }
    result += indent;
  } else {
    // 只有文字內容
    const text = node.textContent.trim();
    if (text) {
      result += `<span class="fd-string">${escapeHtml(text)}</span>`;
    }
  }

  result += `<span class="fd-punctuation">&lt;/</span><span class="fd-tag">${node.tagName}</span><span class="fd-punctuation">&gt;</span>\n`;
  return result;
}
```

## TextViewer UI 設計

```
┌─────────────────────────────────────────────────────────────────┐
│ 📄 example.json                                   [─] [□] [×]  │
├─────────────────────────────────────────────────────────────────┤
│ 顯示模式: [原始] [Markdown] [JSON✓] [YAML] [XML]                │
├─────────────────────────────────────────────────────────────────┤
│ {                                                               │
│   "name": "example",                                            │
│   "version": 1.0,                                               │
│   "enabled": true,                                              │
│   "data": null                                                  │
│ }                                                               │
│                                                                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ example.json                                           6 行    │
└─────────────────────────────────────────────────────────────────┘
```

### 模式切換邏輯

```javascript
// 根據副檔名自動選擇預設模式
function getDefaultMode(filename) {
  const ext = filename.split('.').pop().toLowerCase();

  switch (ext) {
    case 'md':
    case 'markdown':
      return 'markdown';
    case 'json':
      return 'json';
    case 'yaml':
    case 'yml':
      return 'yaml';
    case 'xml':
    case 'html':
    case 'xhtml':
    case 'svg':
      return 'xml';
    default:
      return 'raw';
  }
}
```

## 安全考量

### Markdown 渲染安全

```javascript
// 設定 marked.js 安全選項
marked.setOptions({
  headerIds: false,
  mangle: false,
  // 如有需要可加入 sanitizer
});

// 或使用 DOMPurify 進行後處理
function safeMarkdownRender(markdown) {
  const html = marked.parse(markdown);
  // 如果引入 DOMPurify:
  // return DOMPurify.sanitize(html);
  return html;
}
```

### 格式化內容安全

所有使用者輸入或檔案內容在渲染前都需要經過 `escapeHtml()` 處理：

```javascript
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
```

## 效能考量

### 大型檔案處理

```javascript
const MAX_FORMAT_SIZE = 1024 * 1024; // 1MB

function shouldFormat(content) {
  if (content.length > MAX_FORMAT_SIZE) {
    return {
      canFormat: false,
      reason: '檔案過大，建議使用原始文字模式'
    };
  }
  return { canFormat: true };
}
```

### 延遲渲染

對於長內容，可考慮使用 requestAnimationFrame 或 setTimeout 分段渲染：

```javascript
async function renderLargeContent(content, container) {
  const CHUNK_SIZE = 5000; // 每次處理的字元數
  const chunks = [];

  for (let i = 0; i < content.length; i += CHUNK_SIZE) {
    chunks.push(content.slice(i, i + CHUNK_SIZE));
  }

  container.innerHTML = '';

  for (const chunk of chunks) {
    await new Promise(resolve => requestAnimationFrame(resolve));
    const span = document.createElement('span');
    span.innerHTML = processChunk(chunk);
    container.appendChild(span);
  }
}
```
