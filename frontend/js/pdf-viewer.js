/**
 * ChingTech OS - PDF Viewer Module
 * 使用 PDF.js 渲染 PDF 文件
 */

const PdfViewerModule = (function() {
  'use strict';

  // 狀態
  let windowId = null;
  let currentPath = null;
  let currentFilename = null;
  let pdfDoc = null;
  let currentPage = 1;
  let totalPages = 0;
  let scale = 1.0;
  let rendering = false;

  const MIN_SCALE = 0.25;
  const MAX_SCALE = 4.0;
  const SCALE_STEP = 0.25;

  // PDF.js 設定
  const PDFJS_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174';
  let pdfjsLoaded = false;

  /**
   * 取得認證 token
   */
  function getToken() {
    return localStorage.getItem('chingtech_token');
  }

  /**
   * 載入 PDF.js 函式庫
   */
  async function loadPdfJs() {
    if (pdfjsLoaded && window.pdfjsLib) return;

    // 載入 PDF.js 主程式
    if (!window.pdfjsLib) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = `${PDFJS_CDN}/pdf.min.js`;
        script.onload = resolve;
        script.onerror = () => reject(new Error('無法載入 PDF.js'));
        document.head.appendChild(script);
      });
    }

    // 設定 worker
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = `${PDFJS_CDN}/pdf.worker.min.js`;
    pdfjsLoaded = true;
  }

  /**
   * 開啟 PDF 檢視器
   * @param {string} filePath - 檔案路徑或 URL
   * @param {string} filename - 顯示的檔案名稱
   */
  async function open(filePath, filename) {
    currentPath = filePath;
    currentFilename = filename;
    currentPage = 1;
    totalPages = 0;
    scale = 1.0;
    pdfDoc = null;

    // 檢查是否已開啟
    const existing = WindowModule.getWindowByAppId('pdf-viewer');
    if (existing) {
      WindowModule.closeWindow(existing.windowId);
    }

    windowId = WindowModule.createWindow({
      title: filename,
      appId: 'pdf-viewer',
      icon: 'file-pdf',
      width: 900,
      height: 700,
      content: renderContent(),
      onClose: handleClose,
      onInit: handleInit
    });
  }

  /**
   * 關閉 PDF 檢視器
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
    pdfDoc = null;
    currentPage = 1;
    totalPages = 0;
  }

  /**
   * 處理視窗初始化
   */
  function handleInit(windowEl, wId) {
    windowId = wId;
    // [Sprint7] 使用 UIHelpers 初始化 loading 狀態
    const loadingContainer = windowEl.querySelector('.pdf-loading-container');
    if (loadingContainer) UIHelpers.showLoading(loadingContainer, { text: '載入 PDF 中…' });
    bindEvents(windowEl);
    loadPdf();
  }

  /**
   * 渲染視窗內容
   */
  function renderContent() {
    return `
      <div class="viewer pdf-viewer">
        <div class="pdf-toolbar">
          <div class="pdf-toolbar-group">
            <button class="pdf-toolbar-btn" id="pdfBtnPrev" title="上一頁" disabled>
              <span class="icon">${getIcon('chevron-left')}</span>
            </button>
            <span class="pdf-page-info">
              <input type="number" id="pdfPageInput" class="pdf-page-input" value="1" min="1">
              <span class="pdf-page-separator">/</span>
              <span id="pdfTotalPages">-</span>
            </span>
            <button class="pdf-toolbar-btn" id="pdfBtnNext" title="下一頁" disabled>
              <span class="icon">${getIcon('chevron-right')}</span>
            </button>
          </div>
          <div class="pdf-toolbar-divider"></div>
          <div class="pdf-toolbar-group">
            <button class="pdf-toolbar-btn" id="pdfBtnZoomOut" title="縮小">
              <span class="icon">${getIcon('zoom-out')}</span>
            </button>
            <span class="pdf-zoom-level" id="pdfZoomLevel">100%</span>
            <button class="pdf-toolbar-btn" id="pdfBtnZoomIn" title="放大">
              <span class="icon">${getIcon('zoom-in')}</span>
            </button>
            <div class="pdf-toolbar-divider"></div>
            <button class="pdf-toolbar-btn" id="pdfBtnFitWidth" title="適合寬度">
              <span class="icon">${getIcon('arrow-expand-horizontal')}</span>
            </button>
            <button class="pdf-toolbar-btn" id="pdfBtnFitPage" title="適合頁面">
              <span class="icon">${getIcon('fit-screen')}</span>
            </button>
          </div>
        </div>
        <div class="pdf-content" id="pdfContent">
          <!-- [Sprint7] 原始: <div class="pdf-loading"><span class="icon">...</span><span>載入 PDF 中...</span></div> -->
          <div class="pdf-loading-container"></div>
        </div>
        <div class="viewer-statusbar">
          <span id="pdfStatusInfo">${currentFilename}</span>
          <span id="pdfStatusZoom">100%</span>
        </div>
      </div>
    `;
  }

  /**
   * 綁定事件
   */
  function bindEvents(windowEl) {
    // 導航按鈕
    windowEl.querySelector('#pdfBtnPrev').addEventListener('click', () => goToPage(currentPage - 1));
    windowEl.querySelector('#pdfBtnNext').addEventListener('click', () => goToPage(currentPage + 1));

    // 頁碼輸入
    const pageInput = windowEl.querySelector('#pdfPageInput');
    pageInput.addEventListener('change', (e) => {
      const page = parseInt(e.target.value, 10);
      if (page >= 1 && page <= totalPages) {
        goToPage(page);
      } else {
        e.target.value = currentPage;
      }
    });
    pageInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.target.blur();
      }
    });

    // 縮放按鈕
    windowEl.querySelector('#pdfBtnZoomOut').addEventListener('click', () => setScale(scale - SCALE_STEP));
    windowEl.querySelector('#pdfBtnZoomIn').addEventListener('click', () => setScale(scale + SCALE_STEP));
    windowEl.querySelector('#pdfBtnFitWidth').addEventListener('click', fitWidth);
    windowEl.querySelector('#pdfBtnFitPage').addEventListener('click', fitPage);

    // 滾輪縮放
    const content = windowEl.querySelector('#pdfContent');
    content.addEventListener('wheel', (e) => {
      if (e.ctrlKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -SCALE_STEP : SCALE_STEP;
        setScale(scale + delta);
      }
    }, { passive: false });
  }

  /**
   * 載入 PDF
   */
  async function loadPdf() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const contentEl = windowEl.querySelector('#pdfContent');

    try {
      // 載入 PDF.js
      await loadPdfJs();

      // 取得 PDF 資料
      const pdfData = await fetchPdf();

      // 載入 PDF 文件
      pdfDoc = await window.pdfjsLib.getDocument({ data: pdfData }).promise;
      totalPages = pdfDoc.numPages;

      // 更新 UI
      updateNavigation();

      // 渲染第一頁
      await renderPage(1);

      // 適合寬度
      fitWidth();

    } catch (error) {
      console.error('[PdfViewer] 載入 PDF 失敗:', error);
      // [Sprint7] 原始: contentEl.innerHTML = '<div class="pdf-error"><span class="icon">...</span><span>無法載入 PDF</span></div>'
      UIHelpers.showError(contentEl, { message: '無法載入 PDF', detail: error.message });
    }
  }

  /**
   * 取得 PDF 資料
   */
  async function fetchPdf() {
    let fetchUrl;
    const basePath = window.API_BASE || '';

    if (currentPath.startsWith('/api/')) {
      fetchUrl = `${basePath}${currentPath}`;
    } else if (basePath && currentPath.startsWith(`${basePath}/api/`)) {
      // 已包含 basePath 的 API URL（子路徑部署），直接使用
      fetchUrl = currentPath;
    } else if (currentPath.startsWith('http://') || currentPath.startsWith('https://')) {
      fetchUrl = currentPath;
    } else {
      // Use PathUtils for unified path handling
      fetchUrl = PathUtils.toApiUrl(currentPath);
    }

    const response = await fetch(fetchUrl, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });

    if (!response.ok) {
      throw new Error('載入失敗');
    }

    return await response.arrayBuffer();
  }

  /**
   * 渲染指定頁面
   */
  async function renderPage(pageNum) {
    if (!pdfDoc || rendering) return;

    rendering = true;
    currentPage = pageNum;

    const windowEl = document.getElementById(windowId);
    if (!windowEl) {
      rendering = false;
      return;
    }

    const contentEl = windowEl.querySelector('#pdfContent');

    try {
      const page = await pdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale: scale });

      // 建立或取得 canvas
      let canvas = contentEl.querySelector('canvas');
      if (!canvas) {
        contentEl.innerHTML = '';
        canvas = document.createElement('canvas');
        canvas.className = 'pdf-canvas';
        contentEl.appendChild(canvas);
      }

      const context = canvas.getContext('2d');

      // 支援高 DPI
      const dpr = window.devicePixelRatio || 1;
      canvas.width = viewport.width * dpr;
      canvas.height = viewport.height * dpr;
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      context.scale(dpr, dpr);

      // 渲染頁面
      await page.render({
        canvasContext: context,
        viewport: viewport
      }).promise;

      // 更新 UI
      updateNavigation();
      updateZoomDisplay();

    } catch (error) {
      console.error('[PdfViewer] 渲染頁面失敗:', error);
    }

    rendering = false;
  }

  /**
   * 跳至指定頁
   */
  function goToPage(pageNum) {
    if (pageNum < 1 || pageNum > totalPages) return;
    renderPage(pageNum);
  }

  /**
   * 設定縮放比例
   */
  function setScale(newScale) {
    scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, newScale));
    renderPage(currentPage);
  }

  /**
   * 適合寬度
   */
  async function fitWidth() {
    if (!pdfDoc) return;

    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const contentEl = windowEl.querySelector('#pdfContent');
    const page = await pdfDoc.getPage(currentPage);
    const viewport = page.getViewport({ scale: 1.0 });

    const containerWidth = contentEl.clientWidth - 40; // 留邊距
    scale = containerWidth / viewport.width;
    scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale));

    renderPage(currentPage);
  }

  /**
   * 適合頁面
   */
  async function fitPage() {
    if (!pdfDoc) return;

    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const contentEl = windowEl.querySelector('#pdfContent');
    const page = await pdfDoc.getPage(currentPage);
    const viewport = page.getViewport({ scale: 1.0 });

    const containerWidth = contentEl.clientWidth - 40;
    const containerHeight = contentEl.clientHeight - 40;

    const scaleX = containerWidth / viewport.width;
    const scaleY = containerHeight / viewport.height;
    scale = Math.min(scaleX, scaleY);
    scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale));

    renderPage(currentPage);
  }

  /**
   * 更新導航 UI
   */
  function updateNavigation() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const prevBtn = windowEl.querySelector('#pdfBtnPrev');
    const nextBtn = windowEl.querySelector('#pdfBtnNext');
    const pageInput = windowEl.querySelector('#pdfPageInput');
    const totalPagesEl = windowEl.querySelector('#pdfTotalPages');

    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
    pageInput.value = currentPage;
    pageInput.max = totalPages;
    totalPagesEl.textContent = totalPages;
  }

  /**
   * 更新縮放顯示
   */
  function updateZoomDisplay() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const zoomPercent = Math.round(scale * 100);
    windowEl.querySelector('#pdfZoomLevel').textContent = `${zoomPercent}%`;
    windowEl.querySelector('#pdfStatusZoom').textContent = `${zoomPercent}%`;
  }

  // 公開 API
  return {
    open,
    close
  };
})();
