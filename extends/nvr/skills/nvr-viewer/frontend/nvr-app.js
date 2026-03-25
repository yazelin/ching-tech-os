/**
 * NVR 監控畫面 App — 16 路攝影機即時快照檢視
 */
window.NVRViewerApp = (function () {
  'use strict';

  var TOTAL_CHANNELS = 16;
  var REFRESH_INTERVAL = 3000; // 3 秒刷新（降低 NVR 負擔）
  var API_BASE = window.API_BASE || '';

  var windowId = null;
  var refreshTimer = null;
  var selectedChannel = null;
  var recordingChannels = {}; // {channel: {recording, seconds, since}}

  function recDot(channel) {
    var info = recordingChannels[channel];
    if (info && info.recording) {
      var sec = Math.round(info.seconds || 0);
      return '<span class="nvr-rec-dot" title="錄製中 ' + sec + '秒">⏺</span> ';
    }
    return '';
  }

  function fetchRecordingStatus() {
    var headers = {};
    var token = (typeof LoginModule !== 'undefined' && LoginModule.getToken && LoginModule.getToken()) || localStorage.getItem('chingtech_token');
    if (token) headers['Authorization'] = 'Bearer ' + token;

    fetch(API_BASE + '/api/nvr/recording-status', { headers: headers })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.channels) {
          data.channels.forEach(function (ch) {
            recordingChannels[ch.channel] = ch;
          });
          // 更新畫面上的錄製指示（不重建整個 DOM）
          var container = document.getElementById('nvr-content');
          if (container) {
            container.querySelectorAll('.nvr-cell').forEach(function (cell) {
              var chNum = parseInt(cell.getAttribute('data-channel'));
              var label = cell.querySelector('.nvr-cell-label');
              if (label) {
                var info = recordingChannels[chNum];
                var chLabel = 'CH' + (chNum < 10 ? '0' : '') + chNum;
                if (info && info.recording) {
                  label.innerHTML = '<span class="nvr-rec-dot">⏺</span> ' + chLabel;
                } else {
                  label.textContent = chLabel;
                }
              }
            });
          }
        }
      })
      .catch(function () {});
  }

  function getSnapshotUrl(channel) {
    return API_BASE + '/api/nvr/snapshot/' + channel + '?t=' + Date.now();
  }

  function icon(name) {
    return typeof getIcon === 'function' ? '<span class="icon">' + getIcon(name) + '</span>' : '';
  }

  function buildToolbar() {
    var isGrid = selectedChannel === null;
    var title = isGrid ? '16 路監控' : 'CH' + (selectedChannel < 10 ? '0' : '') + selectedChannel;

    var html = '<div class="nvr-toolbar">' +
      '<span class="nvr-toolbar-title">' + icon('video') + ' ' + title + '</span>' +
      '<span class="nvr-toolbar-spacer"></span>' +
      '<span class="nvr-status"><span class="nvr-status-dot"></span>即時</span>';

    if (!isGrid) {
      html += '<button class="nvr-btn" id="nvr-prev">' + icon('chevron-left') + '</button>';
      html += '<button class="nvr-btn" id="nvr-next">' + icon('chevron-right') + '</button>';
      html += '<button class="nvr-btn" id="nvr-back">' + icon('view-grid') + ' 4×4</button>';
    }

    html += '</div>';
    return html;
  }

  function buildGrid() {
    var isGrid = selectedChannel === null;
    var html = '<div class="nvr-grid ' + (isGrid ? 'grid-4x4' : 'grid-single') + '" id="nvr-grid">';

    if (isGrid) {
      for (var ch = 1; ch <= TOTAL_CHANNELS; ch++) {
        html += '<div class="nvr-cell" data-channel="' + ch + '">' +
          '<img src="' + getSnapshotUrl(ch) + '" alt="CH' + (ch < 10 ? '0' : '') + ch + '" onerror="this.style.display=\'none\'">' +
          '<div class="nvr-cell-label">' + recDot(ch) + 'CH' + (ch < 10 ? '0' : '') + ch + '</div>' +
          '</div>';
      }
    } else {
      html += '<div class="nvr-cell" data-channel="' + selectedChannel + '">' +
        '<img src="' + getSnapshotUrl(selectedChannel) + '" alt="CH' + (selectedChannel < 10 ? '0' : '') + selectedChannel + '">' +
        '<div class="nvr-cell-label">' + recDot(selectedChannel) + 'CH' + (selectedChannel < 10 ? '0' : '') + selectedChannel + '</div>' +
        '</div>';
    }

    html += '</div>';
    return html;
  }

  function render() {
    var container = document.getElementById('nvr-content');
    if (!container) return;
    container.innerHTML = buildToolbar() + buildGrid();
    bindEvents();
  }

  function bindEvents() {
    var grid = document.getElementById('nvr-grid');
    if (grid) {
      grid.addEventListener('click', function (e) {
        var cell = e.target.closest('.nvr-cell');
        if (!cell) return;
        var ch = parseInt(cell.getAttribute('data-channel'));
        if (selectedChannel === null) {
          selectedChannel = ch;
        } else {
          selectedChannel = null;
        }
        render();
      });
    }

    var prevBtn = document.getElementById('nvr-prev');
    var nextBtn = document.getElementById('nvr-next');
    var backBtn = document.getElementById('nvr-back');

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

  function refreshImages() {
    var container = document.getElementById('nvr-content');
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
    refreshTimer = setInterval(function () {
      refreshImages();
      fetchRecordingStatus();
    }, REFRESH_INTERVAL);
    fetchRecordingStatus(); // 立即拉一次
  }

  function stopRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  function open() {
    if (windowId && document.getElementById(windowId)) {
      if (typeof WindowModule !== 'undefined') {
        WindowModule.focusWindow(windowId);
      }
      return;
    }

    if (typeof WindowModule === 'undefined') return;

    selectedChannel = null;

    windowId = WindowModule.createWindow({
      title: '監控畫面',
      icon: 'video',
      width: 900,
      height: 700,
      content: '<div id="nvr-content" class="nvr-container"></div>',
      onClose: function () {
        stopRefresh();
        windowId = null;
      },
    });

    render();
    startRefresh();
  }

  return { open: open };
})();
