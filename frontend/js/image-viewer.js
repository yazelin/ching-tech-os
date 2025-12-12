/**
 * ChingTech OS - Image Viewer Module
 * Displays images with zoom and pan functionality
 */

const ImageViewerModule = (function() {
  'use strict';

  // State
  let windowId = null;
  let currentPath = null;
  let currentFilename = null;
  let zoom = 100;
  let panX = 0;
  let panY = 0;
  let isPanning = false;
  let startX = 0;
  let startY = 0;
  let imageLoaded = false;
  let naturalWidth = 0;
  let naturalHeight = 0;

  const MIN_ZOOM = 10;
  const MAX_ZOOM = 500;
  const ZOOM_STEP = 25;

  /**
   * Get auth token
   */
  function getToken() {
    return localStorage.getItem('chingtech_token');
  }

  /**
   * Open image viewer
   * @param {string} filePath - Full path to the image file
   * @param {string} filename - Display filename
   */
  function open(filePath, filename) {
    currentPath = filePath;
    currentFilename = filename;
    zoom = 100;
    panX = 0;
    panY = 0;
    imageLoaded = false;

    // Check if already open
    const existing = WindowModule.getWindowByAppId('image-viewer');
    if (existing) {
      WindowModule.closeWindow(existing.windowId);
    }

    windowId = WindowModule.createWindow({
      title: filename,
      appId: 'image-viewer',
      icon: 'file-image',
      width: 800,
      height: 600,
      content: renderContent(),
      onClose: handleClose,
      onInit: handleInit
    });
  }

  /**
   * Close image viewer
   */
  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
    }
  }

  /**
   * Handle window close
   */
  function handleClose() {
    windowId = null;
    currentPath = null;
    currentFilename = null;
    imageLoaded = false;
  }

  /**
   * Handle window init
   */
  function handleInit(windowEl, wId) {
    // Set windowId here since createWindow calls onInit before returning
    windowId = wId;
    bindEvents(windowEl);
    loadImage();
  }

  /**
   * Render content
   */
  function renderContent() {
    return `
      <div class="viewer image-viewer">
        <div class="viewer-toolbar">
          <button class="viewer-toolbar-btn" id="imgBtnZoomOut" title="縮小">
            <span class="icon">${getIcon('zoom-out')}</span>
          </button>
          <span class="viewer-zoom-level" id="imgZoomLevel">100%</span>
          <button class="viewer-toolbar-btn" id="imgBtnZoomIn" title="放大">
            <span class="icon">${getIcon('zoom-in')}</span>
          </button>
          <div class="viewer-toolbar-divider"></div>
          <button class="viewer-toolbar-btn" id="imgBtnFit" title="適合視窗">
            <span class="icon">${getIcon('fit-screen')}</span>
          </button>
          <button class="viewer-toolbar-btn" id="imgBtnOriginal" title="原始大小">
            <span class="icon">${getIcon('file-image')}</span>
          </button>
        </div>
        <div class="viewer-content image-viewer-content" id="imgViewerContent">
          <div class="image-viewer-loading">
            <span class="icon">${getIcon('file-image')}</span>
            <span>載入中...</span>
          </div>
        </div>
        <div class="viewer-statusbar">
          <span id="imgStatusInfo">-</span>
          <span id="imgStatusSize">-</span>
        </div>
      </div>
    `;
  }

  /**
   * Bind events
   */
  function bindEvents(windowEl) {
    // Toolbar buttons
    windowEl.querySelector('#imgBtnZoomOut').addEventListener('click', () => setZoom(zoom - ZOOM_STEP));
    windowEl.querySelector('#imgBtnZoomIn').addEventListener('click', () => setZoom(zoom + ZOOM_STEP));
    windowEl.querySelector('#imgBtnFit').addEventListener('click', fitToWindow);
    windowEl.querySelector('#imgBtnOriginal').addEventListener('click', () => setZoom(100));

    // Content area for panning
    const content = windowEl.querySelector('#imgViewerContent');
    content.addEventListener('mousedown', handlePanStart);
    // 使用 passive: false 因為 handleWheel 需要呼叫 preventDefault()
    content.addEventListener('wheel', handleWheel, { passive: false });

    // Global events for panning
    document.addEventListener('mousemove', handlePanMove);
    document.addEventListener('mouseup', handlePanEnd);
  }

  /**
   * Load image
   */
  function loadImage() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const content = windowEl.querySelector('#imgViewerContent');

    const img = new Image();
    img.onload = () => {
      imageLoaded = true;
      naturalWidth = img.naturalWidth;
      naturalHeight = img.naturalHeight;

      content.innerHTML = '';
      img.id = 'imgViewerImage';
      content.appendChild(img);

      // Fit to window initially
      fitToWindow();

      // Update status
      updateStatus();
    };

    img.onerror = () => {
      content.innerHTML = `
        <div class="image-viewer-error">
          <span class="icon">${getIcon('information')}</span>
          <span>無法載入圖片</span>
        </div>
      `;
    };

    // Determine the URL to fetch
    let fetchUrl;
    if (currentPath.startsWith('/api/') || currentPath.startsWith('http://') || currentPath.startsWith('https://')) {
      // Direct URL - use as is
      fetchUrl = currentPath;
    } else if (currentPath.startsWith('/data/')) {
      // Static file path - use directly without auth
      img.src = currentPath;
      return;
    } else {
      // NAS file path - use NAS API
      fetchUrl = `/api/nas/file?path=${encodeURIComponent(currentPath)}`;
    }

    // Add authorization header via fetch and create blob URL
    fetch(fetchUrl, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    })
    .then(response => {
      if (!response.ok) throw new Error('載入失敗');
      return response.blob();
    })
    .then(blob => {
      img.src = URL.createObjectURL(blob);
    })
    .catch(error => {
      content.innerHTML = `
        <div class="image-viewer-error">
          <span class="icon">${getIcon('information')}</span>
          <span>${error.message}</span>
        </div>
      `;
    });
  }

  /**
   * Set zoom level
   */
  function setZoom(newZoom) {
    zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));
    updateImage();
    updateZoomDisplay();
  }

  /**
   * Fit image to window
   */
  function fitToWindow() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl || !imageLoaded) return;

    const content = windowEl.querySelector('#imgViewerContent');
    const contentRect = content.getBoundingClientRect();

    const scaleX = (contentRect.width - 40) / naturalWidth;
    const scaleY = (contentRect.height - 40) / naturalHeight;
    const scale = Math.min(scaleX, scaleY, 1);

    zoom = Math.round(scale * 100);
    panX = 0;
    panY = 0;
    updateImage();
    updateZoomDisplay();
  }

  /**
   * Update image transform
   */
  function updateImage() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const img = windowEl.querySelector('#imgViewerImage');
    if (!img) return;

    const scale = zoom / 100;
    img.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
  }

  /**
   * Update zoom display
   */
  function updateZoomDisplay() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    windowEl.querySelector('#imgZoomLevel').textContent = `${zoom}%`;
  }

  /**
   * Update status bar
   */
  function updateStatus() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    windowEl.querySelector('#imgStatusInfo').textContent = currentFilename;
    windowEl.querySelector('#imgStatusSize').textContent = `${naturalWidth} x ${naturalHeight} px`;
  }

  /**
   * Handle pan start
   */
  function handlePanStart(e) {
    if (e.button !== 0) return; // Left click only

    const windowEl = document.getElementById(windowId);
    if (!windowEl || !imageLoaded) return;

    isPanning = true;
    startX = e.clientX - panX;
    startY = e.clientY - panY;

    const content = windowEl.querySelector('#imgViewerContent');
    content.classList.add('dragging');
  }

  /**
   * Handle pan move
   */
  function handlePanMove(e) {
    if (!isPanning) return;

    panX = e.clientX - startX;
    panY = e.clientY - startY;
    updateImage();
  }

  /**
   * Handle pan end
   */
  function handlePanEnd() {
    if (!isPanning) return;

    isPanning = false;

    const windowEl = document.getElementById(windowId);
    if (windowEl) {
      const content = windowEl.querySelector('#imgViewerContent');
      content.classList.remove('dragging');
    }
  }

  /**
   * Handle mouse wheel zoom
   */
  function handleWheel(e) {
    e.preventDefault();

    const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
    setZoom(zoom + delta);
  }

  // Public API
  return {
    open,
    close
  };
})();
