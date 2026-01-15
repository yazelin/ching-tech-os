/**
 * ChingTech OS - Text Viewer Module
 * 支援多種顯示模式：原始文字、Markdown 預覽、JSON/YAML/XML 格式化
 */

const TextViewerModule = (function() {
  'use strict';

  // 狀態
  let windowId = null;
  let currentPath = null;
  let currentFilename = null;
  let content = '';
  let lineCount = 0;
  let displayMode = 'raw'; // 'raw', 'markdown', 'json', 'yaml', 'xml'
  let formatError = null;

  // 顯示模式設定
  const DISPLAY_MODES = [
    { id: 'raw', label: '原始', icon: 'file-document' },
    { id: 'markdown', label: 'Markdown', icon: 'markdown' },
    { id: 'json', label: 'JSON', icon: 'code-json' },
    { id: 'yaml', label: 'YAML', icon: 'code-braces' },
    { id: 'xml', label: 'XML', icon: 'code-tags' }
  ];

  /**
   * 取得認證 token
   */
  function getToken() {
    return localStorage.getItem('chingtech_token');
  }

  /**
   * 根據副檔名取得預設顯示模式
   * @param {string} filename
   * @returns {string}
   */
  function getDefaultMode(filename) {
    if (!filename) return 'raw';
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

  /**
   * 開啟文字檢視器
   * @param {string} filePath - 檔案完整路徑
   * @param {string} filename - 顯示的檔案名稱
   */
  function open(filePath, filename) {
    currentPath = filePath;
    currentFilename = filename;
    content = '';
    lineCount = 0;
    formatError = null;
    displayMode = getDefaultMode(filename);

    // 檢查是否已開啟
    const existing = WindowModule.getWindowByAppId('text-viewer');
    if (existing) {
      WindowModule.closeWindow(existing.windowId);
    }

    windowId = WindowModule.createWindow({
      title: filename,
      appId: 'text-viewer',
      icon: 'file-document',
      width: 800,
      height: 600,
      content: renderContent(),
      onClose: handleClose,
      onInit: handleInit
    });
  }

  /**
   * 關閉文字檢視器
   */
  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
    }
  }

  /**
   * 處理視窗關閉
   */
  function handleClose() {
    windowId = null;
    currentPath = null;
    currentFilename = null;
    content = '';
    lineCount = 0;
    displayMode = 'raw';
    formatError = null;
  }

  /**
   * 處理視窗初始化
   */
  function handleInit(windowEl, wId) {
    windowId = wId;
    bindToolbarEvents();
    loadFile();
  }

  /**
   * 綁定工具列事件
   */
  function bindToolbarEvents() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    // 綁定顯示模式按鈕
    windowEl.querySelectorAll('.txt-mode-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const mode = btn.dataset.mode;
        if (mode && mode !== displayMode) {
          setDisplayMode(mode);
        }
      });
    });
  }

  /**
   * 設定顯示模式
   * @param {string} mode
   */
  function setDisplayMode(mode) {
    displayMode = mode;
    formatError = null;
    updateModeButtons();
    renderFileContent();
    updateStatus();
  }

  /**
   * 更新模式按鈕狀態
   */
  function updateModeButtons() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    windowEl.querySelectorAll('.txt-mode-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === displayMode);
    });
  }

  /**
   * 渲染視窗內容
   */
  function renderContent() {
    const modeButtons = DISPLAY_MODES.map(mode => `
      <button class="txt-mode-btn ${mode.id === displayMode ? 'active' : ''}"
              data-mode="${mode.id}"
              title="${mode.label}">
        <span class="icon">${getIcon(mode.icon)}</span>
        <span class="txt-mode-label">${mode.label}</span>
      </button>
    `).join('');

    return `
      <div class="viewer text-viewer">
        <div class="txt-toolbar">
          <div class="txt-toolbar-label">顯示模式：</div>
          <div class="txt-mode-group">
            ${modeButtons}
          </div>
        </div>
        <div class="txt-error-bar" id="txtErrorBar" style="display: none;">
          <span class="icon">${getIcon('alert')}</span>
          <span class="txt-error-text" id="txtErrorText"></span>
        </div>
        <div class="viewer-content text-viewer-content" id="txtViewerContent">
          <div class="text-viewer-loading">
            <span class="icon">${getIcon('file-document')}</span>
            <span>載入中...</span>
          </div>
        </div>
        <div class="viewer-statusbar">
          <span id="txtStatusInfo">${currentFilename}</span>
          <span id="txtStatusMode">${getModeLabel(displayMode)}</span>
          <span id="txtStatusLines">-</span>
        </div>
      </div>
    `;
  }

  /**
   * 取得模式標籤
   * @param {string} mode
   * @returns {string}
   */
  function getModeLabel(mode) {
    const m = DISPLAY_MODES.find(d => d.id === mode);
    return m ? m.label : '原始';
  }

  /**
   * 載入檔案內容
   */
  async function loadFile() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const contentEl = windowEl.querySelector('#txtViewerContent');

    try {
      // 決定要 fetch 的 URL
      let fetchUrl;
      let fetchOptions = {};
      const basePath = window.API_BASE || '';

      if (currentPath.startsWith('/api/')) {
        // API URL - add base path for sub-path deployment
        fetchUrl = `${basePath}${currentPath}`;
        fetchOptions = { headers: { 'Authorization': `Bearer ${getToken()}` } };
      } else if (currentPath.startsWith('http://') || currentPath.startsWith('https://')) {
        // Absolute URL - use as is
        fetchUrl = currentPath;
        fetchOptions = { headers: { 'Authorization': `Bearer ${getToken()}` } };
      } else if (currentPath.startsWith('/data/')) {
        fetchUrl = currentPath;
      } else {
        // Use PathUtils for unified path handling
        fetchUrl = PathUtils.toApiUrl(currentPath);
        fetchOptions = { headers: { 'Authorization': `Bearer ${getToken()}` } };
      }

      const response = await fetch(fetchUrl, fetchOptions);

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '載入失敗' }));
        throw new Error(error.detail || '載入失敗');
      }

      content = await response.text();
      lineCount = content.split('\n').length;

      // 渲染內容
      renderFileContent();
      updateStatus();

    } catch (error) {
      contentEl.innerHTML = `
        <div class="text-viewer-error">
          <span class="icon">${getIcon('information')}</span>
          <span>${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染檔案內容（根據顯示模式）
   */
  function renderFileContent() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const contentEl = windowEl.querySelector('#txtViewerContent');
    const errorBar = windowEl.querySelector('#txtErrorBar');
    const errorText = windowEl.querySelector('#txtErrorText');

    // 隱藏錯誤提示
    errorBar.style.display = 'none';
    formatError = null;

    let html = '';

    // 處理空白檔案
    if (content === '' || content === null || content === undefined) {
      html = `<pre class="text-viewer-empty"><span class="text-viewer-empty-hint">（檔案內容為空）</span></pre>`;
    } else {
      switch (displayMode) {
        case 'markdown':
          html = renderMarkdownContent();
          break;
        case 'json':
          html = renderJsonContent();
          break;
        case 'yaml':
          html = renderYamlContent();
          break;
        case 'xml':
          html = renderXmlContent();
          break;
        case 'raw':
        default:
          html = `<pre>${escapeHtml(content)}</pre>`;
          break;
      }
    }

    contentEl.innerHTML = html;

    // 顯示錯誤提示（如果有）
    if (formatError) {
      errorText.textContent = formatError;
      errorBar.style.display = 'flex';
    }
  }

  /**
   * 渲染 Markdown 內容
   * @returns {string}
   */
  function renderMarkdownContent() {
    if (typeof marked !== 'undefined') {
      try {
        const rendered = marked.parse(content);
        return `<div class="txt-markdown-preview markdown-rendered">${rendered}</div>`;
      } catch (e) {
        formatError = 'Markdown 解析錯誤';
        return `<pre>${escapeHtml(content)}</pre>`;
      }
    }
    formatError = 'Markdown 解析器不可用';
    return `<pre>${escapeHtml(content)}</pre>`;
  }

  /**
   * 渲染 JSON 內容
   * @returns {string}
   */
  function renderJsonContent() {
    try {
      const obj = JSON.parse(content);
      const formatted = JSON.stringify(obj, null, 2);
      const highlighted = syntaxHighlightJson(formatted);
      return `<pre class="formatted-data">${highlighted}</pre>`;
    } catch (e) {
      formatError = `無效的 JSON 格式：${e.message}`;
      return `<pre>${escapeHtml(content)}</pre>`;
    }
  }

  /**
   * JSON 語法色彩渲染
   * @param {string} json - 格式化後的 JSON 字串
   * @returns {string}
   */
  function syntaxHighlightJson(json) {
    // 先轉義 HTML
    const escaped = escapeHtml(json);

    // 使用正則表達式添加語法色彩
    return escaped
      // 鍵名（在冒號之前的引號字串）
      .replace(/("[\w\u4e00-\u9fa5]+")(\s*:)/g, '<span class="fd-key">$1</span>$2')
      // 字串值（不在冒號之前的引號字串）
      .replace(/:(\s*)("(?:[^"\\]|\\.)*")/g, ':$1<span class="fd-string">$2</span>')
      // 數字
      .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="fd-number">$1</span>')
      // 布林值
      .replace(/:\s*(true|false)/g, ': <span class="fd-boolean">$1</span>')
      // null
      .replace(/:\s*(null)/g, ': <span class="fd-null">$1</span>');
  }

  /**
   * 渲染 YAML 內容
   * @returns {string}
   */
  function renderYamlContent() {
    const highlighted = syntaxHighlightYaml(content);
    return `<pre class="formatted-data">${highlighted}</pre>`;
  }

  /**
   * YAML 語法色彩渲染
   * @param {string} yaml
   * @returns {string}
   */
  function syntaxHighlightYaml(yaml) {
    const escaped = escapeHtml(yaml);
    const lines = escaped.split('\n');

    return lines.map(line => {
      // 註解
      if (/^\s*#/.test(line)) {
        return `<span class="fd-comment">${line}</span>`;
      }

      // 鍵值對
      const kvMatch = line.match(/^(\s*)([^:#]+)(:)(.*)$/);
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
        // 字串
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

  /**
   * 渲染 XML 內容
   * @returns {string}
   */
  function renderXmlContent() {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(content, 'text/xml');

      // 檢查解析錯誤
      const parseError = doc.querySelector('parsererror');
      if (parseError) {
        formatError = '無效的 XML 格式';
        return `<pre>${escapeHtml(content)}</pre>`;
      }

      // 格式化 XML
      const formatted = formatXmlNode(doc.documentElement, 0);
      return `<pre class="formatted-data">${formatted}</pre>`;
    } catch (e) {
      formatError = `XML 解析錯誤：${e.message}`;
      return `<pre>${escapeHtml(content)}</pre>`;
    }
  }

  /**
   * 遞迴格式化 XML 節點
   * @param {Node} node
   * @param {number} level
   * @returns {string}
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

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return '';
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

  /**
   * 轉義 HTML 特殊字元
   * @param {string} text
   * @returns {string}
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * 更新狀態列
   */
  function updateStatus() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    windowEl.querySelector('#txtStatusInfo').textContent = currentFilename;
    windowEl.querySelector('#txtStatusMode').textContent = getModeLabel(displayMode);
    windowEl.querySelector('#txtStatusLines').textContent = `${lineCount} 行`;
  }

  /**
   * 取得檔案內容
   */
  function getContent() {
    return content;
  }

  // 公開 API
  return {
    open,
    close,
    getContent
  };
})();
