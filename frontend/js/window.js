/**
 * ChingTech OS - Window Module
 * Handles window management: create, close, minimize, drag, focus
 */

const WindowModule = (function() {
  'use strict';

  // Window state
  let windows = {};
  let windowOrder = [];
  let baseZIndex = 100;
  let windowIdCounter = 0;

  // State change callbacks
  let stateChangeCallbacks = [];

  // Drag state
  let dragState = {
    isDragging: false,
    windowId: null,
    startX: 0,
    startY: 0,
    offsetX: 0,
    offsetY: 0
  };

  // Resize state
  let resizeState = {
    isResizing: false,
    windowId: null,
    direction: null,
    startX: 0,
    startY: 0,
    startWidth: 0,
    startHeight: 0,
    startLeft: 0,
    startTop: 0
  };

  /**
   * Generate unique window ID
   * @returns {string}
   */
  function generateWindowId() {
    return `window-${++windowIdCounter}`;
  }

  /**
   * Create a new window
   * @param {Object} options - Window options
   * @param {string} options.title - Window title
   * @param {string} options.appId - Application ID
   * @param {string} options.icon - Window icon name
   * @param {number} options.width - Window width (default: 800)
   * @param {number} options.height - Window height (default: 600)
   * @param {string} options.content - Window content HTML
   * @param {Function} options.onClose - Close callback
   * @param {Function} options.onInit - Init callback (called with window element)
   * @returns {string} Window ID
   */
  function createWindow(options) {
    const {
      title = 'Untitled',
      appId = 'app',
      icon = 'information',
      width = 800,
      height = 600,
      content = '',
      onClose = null,
      onInit = null
    } = options;

    const windowId = generateWindowId();
    const desktopArea = document.querySelector('.desktop-area');
    if (!desktopArea) return null;

    // Calculate center position
    const desktopRect = desktopArea.getBoundingClientRect();
    const x = Math.max(20, (desktopRect.width - width) / 2);
    const y = Math.max(20, (desktopRect.height - height) / 2);

    // Create window element
    const windowEl = document.createElement('div');
    windowEl.className = 'window';
    windowEl.id = windowId;
    windowEl.dataset.appId = appId;
    windowEl.style.width = `${width}px`;
    windowEl.style.height = `${height}px`;
    windowEl.style.left = `${x}px`;
    windowEl.style.top = `${y}px`;

    windowEl.innerHTML = `
      <div class="window-titlebar">
        <div class="window-titlebar-left">
          <span class="window-icon icon">${getIcon(icon)}</span>
          <span class="window-title">${title}</span>
        </div>
        <div class="window-titlebar-right">
          <button class="window-btn window-btn-minimize" title="最小化">
            <span class="icon">${getIcon('minus')}</span>
          </button>
          <button class="window-btn window-btn-maximize" title="最大化">
            <span class="icon">${getIcon('window-maximize')}</span>
          </button>
          <button class="window-btn window-btn-close" title="關閉">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
      </div>
      <div class="window-content">
        ${content}
      </div>
      <div class="window-resize window-resize-n" data-direction="n"></div>
      <div class="window-resize window-resize-s" data-direction="s"></div>
      <div class="window-resize window-resize-w" data-direction="w"></div>
      <div class="window-resize window-resize-e" data-direction="e"></div>
      <div class="window-resize window-resize-nw" data-direction="nw"></div>
      <div class="window-resize window-resize-ne" data-direction="ne"></div>
      <div class="window-resize window-resize-sw" data-direction="sw"></div>
      <div class="window-resize window-resize-se" data-direction="se"></div>
    `;

    // Add to DOM
    desktopArea.appendChild(windowEl);

    // Store window info
    windows[windowId] = {
      element: windowEl,
      appId: appId,
      title: title,
      onClose: onClose,
      minimized: false,
      maximized: false,
      // Store original position/size for restore
      restoreState: null
    };

    // Update z-index order
    windowOrder.push(windowId);
    updateZIndices();

    // Bind events
    bindWindowEvents(windowId);

    // Call onInit callback
    if (onInit) {
      onInit(windowEl, windowId);
    }

    // Notify state change
    notifyStateChange('open', appId);

    return windowId;
  }

  /**
   * Bind window events
   * @param {string} windowId
   */
  function bindWindowEvents(windowId) {
    const windowInfo = windows[windowId];
    if (!windowInfo) return;

    const windowEl = windowInfo.element;
    const titlebar = windowEl.querySelector('.window-titlebar');
    const closeBtn = windowEl.querySelector('.window-btn-close');
    const minimizeBtn = windowEl.querySelector('.window-btn-minimize');
    const maximizeBtn = windowEl.querySelector('.window-btn-maximize');

    // Focus on click
    windowEl.addEventListener('mousedown', () => {
      focusWindow(windowId);
    });

    // Drag start
    titlebar.addEventListener('mousedown', (e) => {
      if (e.target.closest('.window-btn')) return;
      startDrag(windowId, e);
    });

    // Double-click titlebar to toggle maximize
    titlebar.addEventListener('dblclick', (e) => {
      if (e.target.closest('.window-btn')) return;
      toggleMaximize(windowId);
    });

    // Close button
    closeBtn.addEventListener('click', () => {
      closeWindow(windowId);
    });

    // Minimize button
    minimizeBtn.addEventListener('click', () => {
      minimizeWindow(windowId);
    });

    // Maximize button
    maximizeBtn.addEventListener('click', () => {
      toggleMaximize(windowId);
    });

    // Resize handles
    windowEl.querySelectorAll('.window-resize').forEach(handle => {
      handle.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        startResize(windowId, e, handle.dataset.direction);
      });
    });
  }

  /**
   * Start dragging window
   * @param {string} windowId
   * @param {MouseEvent} e
   */
  function startDrag(windowId, e) {
    const windowInfo = windows[windowId];
    if (!windowInfo) return;

    // If maximized, unmaximize first and adjust position
    if (windowInfo.maximized) {
      const windowEl = windowInfo.element;
      const oldWidth = windowInfo.restoreState ? parseInt(windowInfo.restoreState.width) : 800;

      // Unmaximize
      unmaximizeWindow(windowId);

      // Position window so mouse is centered on titlebar
      const desktopArea = document.querySelector('.desktop-area');
      const desktopRect = desktopArea.getBoundingClientRect();
      const newX = Math.max(0, Math.min(e.clientX - oldWidth / 2, desktopRect.width - oldWidth));
      const newY = e.clientY - desktopRect.top - 20; // 20px from top of titlebar

      windowEl.style.left = `${newX}px`;
      windowEl.style.top = `${Math.max(0, newY)}px`;
    }

    const windowEl = windowInfo.element;
    const rect = windowEl.getBoundingClientRect();

    dragState = {
      isDragging: true,
      windowId: windowId,
      startX: e.clientX,
      startY: e.clientY,
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top
    };

    windowEl.classList.add('dragging');
    document.body.style.userSelect = 'none';
  }

  /**
   * Handle mouse move for dragging and resizing
   * @param {MouseEvent} e
   */
  function handleMouseMove(e) {
    // Handle resize
    if (resizeState.isResizing) {
      handleResizeMove(e);
      return;
    }

    // Handle drag
    if (!dragState.isDragging) return;

    const windowInfo = windows[dragState.windowId];
    if (!windowInfo) return;

    const windowEl = windowInfo.element;
    const desktopArea = document.querySelector('.desktop-area');
    const desktopRect = desktopArea.getBoundingClientRect();

    let newX = e.clientX - dragState.offsetX;
    let newY = e.clientY - dragState.offsetY - desktopRect.top;

    // Constrain to desktop area
    const windowWidth = windowEl.offsetWidth;
    const windowHeight = windowEl.offsetHeight;

    newX = Math.max(0, Math.min(newX, desktopRect.width - windowWidth));
    newY = Math.max(0, Math.min(newY, desktopRect.height - windowHeight));

    windowEl.style.left = `${newX}px`;
    windowEl.style.top = `${newY}px`;
  }

  /**
   * Handle mouse up to end dragging
   */
  function handleMouseUp() {
    // End dragging
    if (dragState.isDragging) {
      const windowInfo = windows[dragState.windowId];
      if (windowInfo) {
        windowInfo.element.classList.remove('dragging');
      }
      dragState.isDragging = false;
      dragState.windowId = null;
    }

    // End resizing
    if (resizeState.isResizing) {
      const windowInfo = windows[resizeState.windowId];
      if (windowInfo) {
        windowInfo.element.classList.remove('resizing');
      }
      resizeState.isResizing = false;
      resizeState.windowId = null;
    }

    document.body.style.userSelect = '';
  }

  /**
   * Start resizing window
   * @param {string} windowId
   * @param {MouseEvent} e
   * @param {string} direction - 'n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se'
   */
  function startResize(windowId, e, direction) {
    const windowInfo = windows[windowId];
    if (!windowInfo) return;

    const windowEl = windowInfo.element;

    resizeState = {
      isResizing: true,
      windowId: windowId,
      direction: direction,
      startX: e.clientX,
      startY: e.clientY,
      startWidth: windowEl.offsetWidth,
      startHeight: windowEl.offsetHeight,
      startLeft: windowEl.offsetLeft,
      startTop: windowEl.offsetTop
    };

    windowEl.classList.add('resizing');
    document.body.style.userSelect = 'none';
    focusWindow(windowId);
  }

  /**
   * Handle resize mouse move
   * @param {MouseEvent} e
   */
  function handleResizeMove(e) {
    if (!resizeState.isResizing) return;

    const windowInfo = windows[resizeState.windowId];
    if (!windowInfo) return;

    const windowEl = windowInfo.element;
    const deltaX = e.clientX - resizeState.startX;
    const deltaY = e.clientY - resizeState.startY;
    const dir = resizeState.direction;

    const minWidth = 300;
    const minHeight = 200;

    // East (right edge)
    if (dir.includes('e')) {
      const newWidth = Math.max(minWidth, resizeState.startWidth + deltaX);
      windowEl.style.width = `${newWidth}px`;
    }

    // West (left edge)
    if (dir.includes('w')) {
      const newWidth = Math.max(minWidth, resizeState.startWidth - deltaX);
      if (newWidth > minWidth) {
        windowEl.style.width = `${newWidth}px`;
        windowEl.style.left = `${resizeState.startLeft + deltaX}px`;
      } else {
        windowEl.style.width = `${minWidth}px`;
      }
    }

    // South (bottom edge)
    if (dir.includes('s')) {
      const newHeight = Math.max(minHeight, resizeState.startHeight + deltaY);
      windowEl.style.height = `${newHeight}px`;
    }

    // North (top edge)
    if (dir.includes('n')) {
      const newHeight = Math.max(minHeight, resizeState.startHeight - deltaY);
      if (newHeight > minHeight) {
        windowEl.style.height = `${newHeight}px`;
        windowEl.style.top = `${resizeState.startTop + deltaY}px`;
      } else {
        windowEl.style.height = `${minHeight}px`;
      }
    }
  }

  /**
   * Focus a window (bring to front)
   * @param {string} windowId
   */
  function focusWindow(windowId) {
    if (!windows[windowId]) return;

    // Remove from current position
    const index = windowOrder.indexOf(windowId);
    if (index > -1) {
      windowOrder.splice(index, 1);
    }

    // Add to end (top)
    windowOrder.push(windowId);
    updateZIndices();

    // Update focus states
    Object.keys(windows).forEach(id => {
      windows[id].element.classList.toggle('focused', id === windowId);
    });
  }

  /**
   * Update z-indices based on window order
   */
  function updateZIndices() {
    windowOrder.forEach((windowId, index) => {
      const windowInfo = windows[windowId];
      if (windowInfo) {
        windowInfo.element.style.zIndex = baseZIndex + index;
      }
    });
  }

  /**
   * Close a window
   * @param {string} windowId
   */
  function closeWindow(windowId) {
    const windowInfo = windows[windowId];
    if (!windowInfo) return;

    const appId = windowInfo.appId;

    // Call onClose callback
    if (windowInfo.onClose) {
      windowInfo.onClose(windowId);
    }

    // Remove from DOM
    windowInfo.element.remove();

    // Remove from state
    delete windows[windowId];
    const index = windowOrder.indexOf(windowId);
    if (index > -1) {
      windowOrder.splice(index, 1);
    }

    // Notify state change
    notifyStateChange('close', appId);
  }

  /**
   * Minimize a window
   * @param {string} windowId
   */
  function minimizeWindow(windowId) {
    const windowInfo = windows[windowId];
    if (!windowInfo) return;

    windowInfo.minimized = true;
    windowInfo.element.classList.add('minimized');
  }

  /**
   * Restore a minimized window
   * @param {string} windowId
   */
  function restoreWindow(windowId) {
    const windowInfo = windows[windowId];
    if (!windowInfo) return;

    windowInfo.minimized = false;
    windowInfo.element.classList.remove('minimized');
    focusWindow(windowId);
  }

  /**
   * Maximize a window
   * @param {string} windowId
   */
  function maximizeWindow(windowId) {
    const windowInfo = windows[windowId];
    if (!windowInfo || windowInfo.maximized) return;

    const windowEl = windowInfo.element;

    // Save current position and size for restore
    windowInfo.restoreState = {
      left: windowEl.style.left,
      top: windowEl.style.top,
      width: windowEl.style.width,
      height: windowEl.style.height
    };

    // Maximize to fill desktop area
    windowEl.style.left = '0';
    windowEl.style.top = '0';
    windowEl.style.width = '100%';
    windowEl.style.height = '100%';

    windowInfo.maximized = true;
    windowEl.classList.add('maximized');

    // Update maximize button icon
    updateMaximizeButtonIcon(windowId);
  }

  /**
   * Restore a maximized window to its previous size
   * @param {string} windowId
   */
  function unmaximizeWindow(windowId) {
    const windowInfo = windows[windowId];
    if (!windowInfo || !windowInfo.maximized) return;

    const windowEl = windowInfo.element;

    // Restore previous position and size
    if (windowInfo.restoreState) {
      windowEl.style.left = windowInfo.restoreState.left;
      windowEl.style.top = windowInfo.restoreState.top;
      windowEl.style.width = windowInfo.restoreState.width;
      windowEl.style.height = windowInfo.restoreState.height;
    }

    windowInfo.maximized = false;
    windowInfo.restoreState = null;
    windowEl.classList.remove('maximized');

    // Update maximize button icon
    updateMaximizeButtonIcon(windowId);
  }

  /**
   * Toggle maximize state
   * @param {string} windowId
   */
  function toggleMaximize(windowId) {
    const windowInfo = windows[windowId];
    if (!windowInfo) return;

    if (windowInfo.maximized) {
      unmaximizeWindow(windowId);
    } else {
      maximizeWindow(windowId);
    }
  }

  /**
   * Update maximize button icon based on state
   * @param {string} windowId
   */
  function updateMaximizeButtonIcon(windowId) {
    const windowInfo = windows[windowId];
    if (!windowInfo) return;

    const maximizeBtn = windowInfo.element.querySelector('.window-btn-maximize');
    if (!maximizeBtn) return;

    const iconSpan = maximizeBtn.querySelector('.icon');
    if (iconSpan) {
      iconSpan.innerHTML = getIcon(windowInfo.maximized ? 'window-restore' : 'window-maximize');
      maximizeBtn.title = windowInfo.maximized ? '還原' : '最大化';
    }
  }

  /**
   * Get window by app ID
   * @param {string} appId
   * @returns {Object|null}
   */
  function getWindowByAppId(appId) {
    for (const windowId of Object.keys(windows)) {
      if (windows[windowId].appId === appId) {
        return { windowId, ...windows[windowId] };
      }
    }
    return null;
  }

  /**
   * Get all windows
   * @returns {Object}
   */
  function getWindows() {
    return { ...windows };
  }

  /**
   * Register a callback for window state changes
   * @param {Function} callback - Called with (eventType, appId) where eventType is 'open' or 'close'
   */
  function onStateChange(callback) {
    if (typeof callback === 'function') {
      stateChangeCallbacks.push(callback);
    }
  }

  /**
   * Notify all state change callbacks
   * @param {string} eventType - 'open' or 'close'
   * @param {string} appId
   */
  function notifyStateChange(eventType, appId) {
    stateChangeCallbacks.forEach(callback => {
      try {
        callback(eventType, appId);
      } catch (e) {
        console.error('State change callback error:', e);
      }
    });
  }

  /**
   * Initialize window module
   */
  function init() {
    // Global mouse events for dragging
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }

  // Public API
  return {
    init,
    createWindow,
    closeWindow,
    focusWindow,
    minimizeWindow,
    restoreWindow,
    maximizeWindow,
    unmaximizeWindow,
    toggleMaximize,
    getWindowByAppId,
    getWindows,
    onStateChange
  };
})();
