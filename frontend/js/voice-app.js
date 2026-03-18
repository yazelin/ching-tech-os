/**
 * ChingTech OS - Voice Settings Application
 * 語音設定管理（語音角色選擇、試聽、階層式設定）
 */

const VoiceApp = (function() {
  'use strict';

  const APP_ID = 'voice';
  let windowId = null;
  let currentScope = 'user';
  let currentScopeId = '';
  let currentEngine = '';
  let voices = [];
  let configSchema = {};
  let availableEngines = [];
  let currentSettings = null;
  let effectiveSettings = null;
  let audioPlayer = null;
  let scopeData = { is_admin: false, groups: [], agents: [] };

  function showToast(msg, icon) {
    if (typeof NotificationModule !== 'undefined' && NotificationModule.show) {
      NotificationModule.show({ message: msg, icon: icon || 'information' });
    }
  }

  function getIcon(name) {
    if (typeof window.getIcon === 'function') return window.getIcon(name);
    return '';
  }

  function getAuthHeaders() {
    const token = LoginModule?.getToken?.() || localStorage.getItem('chingtech_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }

  // ── API ───────────────────────────────────────────────────

  async function fetchVoices(engine = '') {
    try {
      const params = engine ? `?engine=${engine}` : '';
      const res = await fetch(`/api/voice/voices${params}`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      currentEngine = data.engine || 'edge';
      voices = data.voices || [];
      configSchema = data.config_schema || {};
      availableEngines = data.available_engines || ['edge'];
      return data;
    } catch (e) {
      console.error('載入語音列表失敗:', e);
      showToast('載入語音列表失敗', 'alert-circle');
      return null;
    }
  }

  async function fetchScopes() {
    try {
      const res = await fetch('/api/voice/scopes', { headers: getAuthHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      scopeData = await res.json();
    } catch (e) {
      console.error('載入範圍列表失敗:', e);
    }
  }

  async function fetchSettings() {
    try {
      const params = new URLSearchParams({ scope: currentScope });
      if (currentScopeId) params.set('scope_id', currentScopeId);
      const res = await fetch(`/api/voice/settings?${params}`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      currentSettings = data.current;
      effectiveSettings = data.effective;
      return data;
    } catch (e) {
      console.error('載入語音設定失敗:', e);
      return null;
    }
  }

  async function saveSettings(engine, params) {
    try {
      const res = await fetch('/api/voice/settings', {
        method: 'PUT',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scope: currentScope,
          scope_id: currentScopeId || null,
          tts_engine: engine,
          tts_params: params,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast('語音設定已儲存', 'check');
      return true;
    } catch (e) {
      showToast('儲存失敗: ' + e.message, 'alert-circle');
      return false;
    }
  }

  async function clearSettings() {
    try {
      const res = await fetch('/api/voice/settings', {
        method: 'DELETE',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scope: currentScope,
          scope_id: currentScopeId || null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast('已清除設定，回退到繼承', 'undo');
      return true;
    } catch (e) {
      showToast('清除失敗: ' + e.message, 'alert-circle');
      return false;
    }
  }

  async function previewVoice(engine, params, text) {
    try {
      const res = await fetch('/api/voice/preview', {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ engine, params, text }),
      });
      if (res.status === 429) {
        showToast('試聽冷卻中，請稍後再試', 'timer-sand');
        return null;
      }
      if (res.status === 501) {
        showToast('此引擎尚未實作', 'alert-circle');
        return null;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      return URL.createObjectURL(blob);
    } catch (e) {
      showToast('試聽失敗: ' + e.message, 'alert-circle');
      return null;
    }
  }

  // ── UI 渲染 ─────────────────────────────────────────────

  function buildWindowContent() {
    return `
      <div class="voice-app">
        <div class="voice-app-header">
          <div class="voice-scope-selector"></div>
        </div>
        <div class="voice-app-body">
          <div class="voice-engine-selector"></div>
          <div class="voice-inherit-info"></div>
          <div class="voice-config-form"></div>
          <div class="voice-actions"></div>
        </div>
      </div>
    `;
  }

  function renderScopeSelector(container) {
    const el = container.querySelector('.voice-scope-selector');
    if (!el) return;

    // 建立選項：個人 + 群組列表 + Agent 列表（管理員）
    let options = '<option value="user:">個人設定</option>';

    if (scopeData.groups.length > 0) {
      options += '<optgroup label="群組設定">';
      for (const g of scopeData.groups) {
        const platformIcon = g.platform === 'telegram' ? '✈️' : '💬';
        options += `<option value="group:${g.id}">${platformIcon} ${g.name}</option>`;
      }
      options += '</optgroup>';
    }

    if (scopeData.is_admin && scopeData.agents.length > 0) {
      options += '<optgroup label="Agent 設定">';
      for (const a of scopeData.agents) {
        options += `<option value="agent:${a.id}">🤖 ${a.name}</option>`;
      }
      options += '</optgroup>';
    }

    el.innerHTML = `
      <label class="voice-label">設定範圍</label>
      <select class="voice-select voice-scope-select">
        ${options}
      </select>
    `;

    // 設定當前值
    const select = el.querySelector('.voice-scope-select');
    select.value = `${currentScope}:${currentScopeId}`;

    // 切換時重新載入
    select.addEventListener('change', async () => {
      const [scope, scopeId] = select.value.split(':');
      currentScope = scope;
      currentScopeId = scopeId || '';
      await reloadSettings(container);
    });
  }

  async function reloadSettings(container) {
    await fetchSettings();
    // 引擎可能隨設定不同，重新載入
    const activeEngine = currentSettings?.tts_engine || effectiveSettings?.tts_engine || '';
    if (activeEngine) await fetchVoices(activeEngine);
    renderEngineSelector(container);
    renderInheritInfo(container);
    renderConfigForm(container);
  }

  function renderEngineSelector(container) {
    const el = container.querySelector('.voice-engine-selector');
    if (!el) return;

    const activeEngine = currentSettings?.tts_engine || effectiveSettings?.tts_engine || currentEngine;

    const options = availableEngines.map(e => {
      const labels = { edge: 'Edge TTS（免費）', google_cloud: 'Google Cloud TTS', gemini: 'Gemini Native Audio' };
      const label = labels[e] || e;
      return `<option value="${e}" ${e === activeEngine ? 'selected' : ''}>${label}</option>`;
    }).join('');

    el.innerHTML = `
      <label class="voice-label">TTS 引擎</label>
      <select class="voice-select voice-engine-select">
        ${options}
      </select>
    `;

    el.querySelector('.voice-engine-select').addEventListener('change', async (e) => {
      await fetchVoices(e.target.value);
      renderConfigForm(container);
    });
  }

  function renderInheritInfo(container) {
    const el = container.querySelector('.voice-inherit-info');
    if (!el) return;

    if (currentSettings) {
      el.innerHTML = '';
      return;
    }

    if (effectiveSettings) {
      const engineLabel = { edge: 'Edge TTS', google_cloud: 'Google Cloud TTS', gemini: 'Gemini' };
      const eName = engineLabel[effectiveSettings.tts_engine] || effectiveSettings.tts_engine;
      el.innerHTML = `
        <div class="voice-inherit-badge">
          <span class="icon">${getIcon('information')}</span>
          目前繼承自上層設定（${eName}）
        </div>
      `;
    } else {
      el.innerHTML = '';
    }
  }

  function renderConfigForm(container) {
    const el = container.querySelector('.voice-config-form');
    if (!el) return;

    const currentParams = currentSettings?.tts_params || effectiveSettings?.tts_params || {};
    let html = '';

    // 引擎未實作時顯示提示
    if (voices.length === 0 && Object.keys(configSchema).length === 0) {
      el.innerHTML = `
        <div class="voice-inherit-badge">
          <span class="icon">${getIcon('alert-circle')}</span>
          此引擎尚未實作，請選擇其他引擎
        </div>
      `;
      return;
    }

    for (const [key, schema] of Object.entries(configSchema)) {
      const value = currentParams[key] || schema.default || '';
      const label = schema.label || key;

      if (schema.type === 'select') {
        if (voices.length === 0) {
          // 引擎有 schema 但沒有語音列表（尚未實作 list_voices）
          html += `
            <div class="voice-field">
              <label class="voice-label">${label}</label>
              <div class="voice-inherit-badge">
                <span class="icon">${getIcon('alert-circle')}</span>
                此引擎尚未實作，語音角色列表不可用
              </div>
            </div>
          `;
          continue;
        }
        // 下拉選單（用 voices 填充）
        const options = voices.map(v => {
          const selected = v.id === value ? 'selected' : '';
          const genderIcon = v.gender === 'female' ? '♀' : v.gender === 'male' ? '♂' : '';
          return `<option value="${v.id}" ${selected}>${v.name} ${genderIcon}</option>`;
        }).join('');

        html += `
          <div class="voice-field">
            <label class="voice-label">${label}</label>
            <select class="voice-select voice-param" data-key="${key}">
              ${options}
            </select>
          </div>
        `;
      } else if (schema.type === 'slider') {
        const min = schema.min || 0;
        const max = schema.max || 100;
        const step = schema.step || 1;
        const val = value || schema.default || min;

        html += `
          <div class="voice-field">
            <label class="voice-label">${label}: <span class="voice-slider-value">${val}</span></label>
            <input type="range" class="voice-slider voice-param"
              data-key="${key}" min="${min}" max="${max}" step="${step}" value="${val}">
          </div>
        `;
      } else if (schema.type === 'text') {
        html += `
          <div class="voice-field">
            <label class="voice-label">${label}</label>
            <input type="text" class="voice-input voice-param"
              data-key="${key}" value="${value}" placeholder="${schema.placeholder || ''}">
          </div>
        `;
      }
    }

    el.innerHTML = html;

    // 滑桿即時顯示數值
    el.querySelectorAll('.voice-slider').forEach(slider => {
      slider.addEventListener('input', () => {
        const display = slider.parentElement.querySelector('.voice-slider-value');
        if (display) display.textContent = slider.value;
      });
    });
  }

  function renderActions(container) {
    const el = container.querySelector('.voice-actions');
    if (!el) return;

    el.innerHTML = `
      <div class="voice-btn-group">
        <button class="voice-btn voice-btn-preview">
          <span class="icon">${getIcon('play')}</span> 試聽
        </button>
        <button class="voice-btn voice-btn-primary voice-btn-save">
          <span class="icon">${getIcon('content-save')}</span> 儲存
        </button>
        <button class="voice-btn voice-btn-clear">
          <span class="icon">${getIcon('undo')}</span> 清除（回退繼承）
        </button>
      </div>
      <div class="voice-player-area"></div>
    `;

    el.querySelector('.voice-btn-preview').addEventListener('click', handlePreview);
    el.querySelector('.voice-btn-save').addEventListener('click', handleSave);
    el.querySelector('.voice-btn-clear').addEventListener('click', handleClear);
  }

  function getFormParams(container) {
    const params = {};
    container.querySelectorAll('.voice-param').forEach(el => {
      const key = el.dataset.key;
      const value = el.type === 'range' ? parseFloat(el.value) : el.value;
      if (key && value !== '') params[key] = value;
    });
    return params;
  }

  function getSelectedEngine(container) {
    const select = container.querySelector('.voice-engine-select');
    return select ? select.value : currentEngine;
  }

  // ── Event Handlers ──────────────────────────────────────

  async function handlePreview() {
    const container = document.querySelector('.voice-app');
    if (!container) return;

    const engine = getSelectedEngine(container);
    const params = getFormParams(container);
    const playerArea = container.querySelector('.voice-player-area');

    // 停止之前的播放
    if (audioPlayer) {
      audioPlayer.pause();
      audioPlayer = null;
    }

    if (playerArea) {
      playerArea.innerHTML = `<div class="voice-loading">生成中...</div>`;
    }

    const url = await previewVoice(engine, params, '');
    if (!url) {
      if (playerArea) playerArea.innerHTML = '';
      return;
    }

    audioPlayer = new Audio(url);
    audioPlayer.play();

    if (playerArea) {
      playerArea.innerHTML = `
        <div class="voice-playing">
          <span class="icon">${getIcon('volume-high')}</span> 播放中...
        </div>
      `;
      audioPlayer.addEventListener('ended', () => {
        playerArea.innerHTML = '';
        URL.revokeObjectURL(url);
      });
    }
  }

  async function handleSave() {
    const container = document.querySelector('.voice-app');
    if (!container) return;

    const engine = getSelectedEngine(container);
    const params = getFormParams(container);
    const ok = await saveSettings(engine, params);
    if (ok) {
      await fetchSettings();
      renderInheritInfo(container);
    }
  }

  async function handleClear() {
    const ok = await clearSettings();
    if (ok) {
      const container = document.querySelector('.voice-app');
      if (container) {
        await fetchSettings();
        renderInheritInfo(container);
        renderConfigForm(container);
      }
    }
  }

  // ── 初始化 ──────────────────────────────────────────────

  async function initApp(container, wId) {
    windowId = wId;

    // 先載入設定和範圍列表
    await Promise.all([fetchSettings(), fetchScopes()]);

    // 根據設定決定要載入哪個引擎的語音列表
    const activeEngine = currentSettings?.tts_engine || effectiveSettings?.tts_engine || '';
    await fetchVoices(activeEngine);

    renderScopeSelector(container);
    renderEngineSelector(container);
    renderInheritInfo(container);
    renderConfigForm(container);
    renderActions(container);
  }

  function open() {
    const existingWindow = WindowModule.getWindowByAppId(APP_ID);
    if (existingWindow) {
      WindowModule.focusWindow(existingWindow.windowId);
      if (existingWindow.minimized) {
        WindowModule.restoreWindow(existingWindow.windowId);
      }
      return;
    }

    WindowModule.createWindow({
      title: '語音設定',
      appId: APP_ID,
      icon: 'microphone',
      width: 480,
      height: 520,
      content: buildWindowContent(),
      onInit: initApp,
      onClose: () => {
        if (audioPlayer) {
          audioPlayer.pause();
          audioPlayer = null;
        }
        windowId = null;
      }
    });
  }

  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
      windowId = null;
    }
  }

  return { open, close };
})();
window.VoiceApp = VoiceApp;
