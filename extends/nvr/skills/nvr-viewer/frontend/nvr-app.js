/**
 * NVR 監控畫面 App — 16 路攝影機即時快照檢視
 */
window.NVRViewerApp = (function () {
  'use strict';

  const TOTAL_CHANNELS = 16;
  const REFRESH_INTERVAL = 2000; // 2 秒刷新
  const API_BASE = window.API_BASE || '';

  let windowId = null;
  let refreshTimer = null;
  let selectedChannel = null; // null = 4x4 網格, number = 單路放大

  function getAuthHeaders() {
    const token = (typeof LoginModule !== 'undefined' && LoginModule.getToken?.()) || localStorage.getItem('chingtech_token');
    return token ? { Authorization: 'Bearer ' + token } : {};
  }

  function getSnapshotUrl(channel) {
    return API_BASE + '/api/nvr/snapshot/' + channel + '?t=' + Date.now();
  }

  function buildGridView() {
    var cells = '';
    for (var ch = 1; ch <= TOTAL_CHANNELS; ch++) {
      cells += '<div class="nvr-cell" data-channel="' + ch + '">' +
        '<img src="' + getSnapshotUrl(ch) + '" alt="CH' + (ch < 10 ? '0' : '') + ch + '" onerror="this.style.display=\'none\'">' +
        '<div class="nvr-cell-label">CH' + (ch < 10 ? '0' : '') + ch + '</div>' +
        '</div>';
    }
    return cells;
  }

  function buildSingleView(channel) {
    return '<div class="nvr-cell" data-channel="' + channel + '">' +
      '<img src="' + getSnapshotUrl(channel) + '" alt="CH' + (channel < 10 ? '0' : '') + channel + '">' +
      '<div class="nvr-cell-label">CH' + (channel < 10 ? '0' : '') + channel + '</div>' +
      '</div>';
  }

  function render() {
    var container = document.getElementById('nvr-app-' + windowId);
    if (!container) return;

    var isGrid = selectedChannel === null;
    var toolbar = '<div class="nvr-toolbar">' +
      '<span class="nvr-toolbar-title">' +
      '<span class="icon">' + (typeof getIcon === 'function' ? getIcon('cctv') : '') + '</span> ' +
      (isGrid ? '16 路監控' : 'CH' + (selectedChannel < 10 ? '0' : '') + selectedChannel) +
      '</span>' +
      '<span class="nvr-toolbar-spacer"></span>' +
      '<span class="nvr-status"><span class="nvr-status-dot"></span>即時</span>';

    if (!isGrid) {
      // 單路模式：上一路 / 下一路 / 返回網格
      toolbar += '<button class="nvr-btn" id="nvr-prev-' + windowId + '">' +
        (typeof getIcon === 'function' ? '<span class="icon">' + getIcon('chevron-left') + '</span>' : '◀') +
        '</button>';
      toolbar += '<button class="nvr-btn" id="nvr-next-' + windowId + '">' +
        (typeof getIcon === 'function' ? '<span class="icon">' + getIcon('chevron-right') + '</span>' : '▶') +
        '</button>';
      toolbar += '<button class="nvr-btn" id="nvr-back-' + windowId + '">' +
        (typeof getIcon === 'function' ? '<span class="icon">' + getIcon('view-grid') + '</span> ' : '') +
        '4×4' +
        '</button>';
    }

    toolbar += '</div>';

    var grid = '<div class="nvr-grid ' + (isGrid ? 'grid-4x4' : 'grid-single') + '" id="nvr-grid-' + windowId + '">' +
      (isGrid ? buildGridView() : buildSingleView(selectedChannel)) +
      '</div>';

    container.innerHTML = toolbar + grid;

    // 綁定事件
    var gridEl = document.getElementById('nvr-grid-' + windowId);
    if (gridEl) {
      gridEl.addEventListener('click', function (e) {
        var cell = e.target.closest('.nvr-cell');
        if (!cell) return;
        var ch = parseInt(cell.getAttribute('data-channel'));
        if (isGrid) {
          selectedChannel = ch;
        } else {
          selectedChannel = null;
        }
        render();
      });
    }

    if (!isGrid) {
      var prevBtn = document.getElementById('nvr-prev-' + windowId);
      var nextBtn = document.getElementById('nvr-next-' + windowId);
      var backBtn = document.getElementById('nvr-back-' + windowId);

      if (prevBtn) prevBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        selectedChannel = selectedChannel > 1 ? selectedChannel - 1 : TOTAL_CHANNELS;
        render();
      });
      if (nextBtn) nextBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        selectedChannel = selectedChannel < TOTAL_CHANNELS ? selectedChannel + 1 : 1;
        render();
      });
      if (backBtn) backBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        selectedChannel = null;
        render();
      });
    }
  }

  function refreshImages() {
    var container = document.getElementById('nvr-app-' + windowId);
    if (!container) return;

    var images = container.querySelectorAll('.nvr-cell img');
    images.forEach(function (img) {
      var cell = img.closest('.nvr-cell');
      var ch = parseInt(cell.getAttribute('data-channel'));
      img.src = getSnapshotUrl(ch);
      img.style.display = '';
    });
  }

  function startRefresh() {
    stopRefresh();
    refreshTimer = setInterval(refreshImages, REFRESH_INTERVAL);
  }

  function stopRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  // === App 生命週期 ===

  function init(wid) {
    windowId = wid;
    selectedChannel = null;

    var container = document.getElementById('nvr-app-' + windowId);
    if (!container) return;

    container.classList.add('nvr-container');
    render();
    startRefresh();
  }

  function destroy() {
    stopRefresh();
  }

  return { init: init, destroy: destroy };
})();
