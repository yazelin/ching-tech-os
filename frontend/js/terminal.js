/**
 * ChingTech OS - Terminal Application
 * Web-based terminal with PTY backend support
 */

const TerminalApp = (function() {
  'use strict';

  const APP_ID = 'terminal';

  // Store multiple terminal instances
  const instances = new Map();
  let instanceCounter = 0;

  /**
   * 從 CSS 變數讀取顏色值
   * @param {string} varName - CSS 變數名稱 (包含 --)
   * @returns {string} 顏色值
   */
  function getCSSVar(varName) {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  }

  /**
   * 從 CSS 變數建立 xterm 主題
   * @returns {Object} xterm 主題配置
   */
  function getTerminalTheme() {
    return {
      background: getCSSVar('--terminal-bg'),
      foreground: getCSSVar('--terminal-fg'),
      cursor: getCSSVar('--terminal-cursor'),
      cursorAccent: getCSSVar('--terminal-cursor-accent'),
      selectionBackground: getCSSVar('--terminal-selection'),
      black: getCSSVar('--terminal-black'),
      red: getCSSVar('--terminal-red'),
      green: getCSSVar('--terminal-green'),
      yellow: getCSSVar('--terminal-yellow'),
      blue: getCSSVar('--terminal-blue'),
      magenta: getCSSVar('--terminal-magenta'),
      cyan: getCSSVar('--terminal-cyan'),
      white: getCSSVar('--terminal-white'),
      brightBlack: getCSSVar('--terminal-bright-black'),
      brightRed: getCSSVar('--terminal-bright-red'),
      brightGreen: getCSSVar('--terminal-bright-green'),
      brightYellow: getCSSVar('--terminal-bright-yellow'),
      brightBlue: getCSSVar('--terminal-bright-blue'),
      brightMagenta: getCSSVar('--terminal-bright-magenta'),
      brightCyan: getCSSVar('--terminal-bright-cyan'),
      brightWhite: getCSSVar('--terminal-bright-white')
    };
  }

  /**
   * Terminal instance class
   */
  class TerminalInstance {
    constructor(windowId) {
      this.windowId = windowId;
      this.sessionId = null;
      this.terminal = null;
      this.fitAddon = null;
      this.webLinksAddon = null;
      this.resizeObserver = null;
      this.connected = false;
    }

    /**
     * Initialize xterm.js terminal
     * @param {HTMLElement} container
     */
    init(container) {
      // Create terminal instance with theme from CSS variables
      this.terminal = new Terminal({
        cursorBlink: true,
        cursorStyle: 'block',
        fontFamily: '"JetBrainsMono NF", "JetBrainsMono Nerd Font", "FiraCode Nerd Font", "JetBrains Mono", "Fira Code", "Cascadia Code", Menlo, Monaco, "Courier New", monospace',
        fontSize: 14,
        lineHeight: 1.2,
        theme: getTerminalTheme()
      });

      // Load addons
      this.fitAddon = new FitAddon.FitAddon();
      this.webLinksAddon = new WebLinksAddon.WebLinksAddon();

      this.terminal.loadAddon(this.fitAddon);
      this.terminal.loadAddon(this.webLinksAddon);

      // Open terminal in container
      this.terminal.open(container);

      // Initial fit
      setTimeout(() => this.fit(), 0);

      // Setup resize observer
      this.resizeObserver = new ResizeObserver(() => {
        this.fit();
      });
      this.resizeObserver.observe(container);

      // Handle input
      this.terminal.onData(data => {
        if (this.sessionId && this.connected) {
          SocketClient.emit('terminal:input', {
            session_id: this.sessionId,
            data: data
          });
        }
      });

      // Setup socket event handlers
      this.setupSocketHandlers();

      // Check for recoverable sessions or create new
      this.checkAndConnect();
    }

    /**
     * Check for recoverable sessions and show dialog if found
     */
    async checkAndConnect() {
      this.terminal.write('檢查連線狀態...\r\n');

      try {
        // Check for detached sessions
        const response = await SocketClient.emitWithAck('terminal:list', {});
        const sessions = response.sessions || [];

        if (sessions.length > 0) {
          // Show reconnect dialog
          this.showReconnectDialog(sessions);
        } else {
          // No sessions to recover, create new
          this.createSession();
        }
      } catch (e) {
        // If list fails, just create new session
        this.createSession();
      }
    }

    /**
     * Show reconnect dialog
     * @param {Array} sessions - Available sessions to reconnect
     */
    showReconnectDialog(sessions) {
      const windowEl = document.getElementById(this.windowId);
      if (!windowEl) return;

      // Create overlay
      const overlay = document.createElement('div');
      overlay.className = 'terminal-reconnect-overlay';

      // Format session time
      const formatTime = (isoString) => {
        const date = new Date(isoString);
        return date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
      };

      // Format cwd for display (shorten home path)
      const formatCwd = (cwd) => {
        if (!cwd) return '未知';
        const home = '/home/';
        if (cwd.startsWith(home)) {
          const rest = cwd.slice(home.length);
          const slashIdx = rest.indexOf('/');
          if (slashIdx > 0) {
            return '~' + rest.slice(slashIdx);
          }
          return '~';
        }
        return cwd;
      };

      overlay.innerHTML = `
        <div class="terminal-reconnect-dialog">
          <h3>發現未關閉的終端機</h3>
          <p>有 ${sessions.length} 個終端機 session 可以恢復</p>
          <ul class="terminal-session-list">
            ${sessions.map((s, i) => `
              <li class="terminal-session-item" data-session-id="${s.session_id}">
                <div class="terminal-session-info">
                  <div class="terminal-session-cwd"><code>${formatCwd(s.cwd)}</code></div>
                  <div class="terminal-session-time">${formatTime(s.last_activity)}</div>
                </div>
                <span class="icon">${typeof getIcon !== 'undefined' ? getIcon('arrow-right') : '→'}</span>
              </li>
            `).join('')}
          </ul>
          <div class="terminal-reconnect-actions">
            <button class="btn btn-secondary" data-action="new">建立新的</button>
          </div>
        </div>
      `;

      // Add to terminal container
      const terminalApp = windowEl.querySelector('.terminal-app');
      terminalApp.appendChild(overlay);

      // Handle session item click
      overlay.querySelectorAll('.terminal-session-item').forEach(item => {
        item.addEventListener('click', () => {
          const sessionId = item.dataset.sessionId;
          overlay.remove();
          this.reconnectSession(sessionId);
        });
      });

      // Handle button clicks
      overlay.querySelector('[data-action="new"]').addEventListener('click', () => {
        overlay.remove();
        this.createSession();
      });
    }

    /**
     * Reconnect to existing session
     * @param {string} sessionId
     */
    async reconnectSession(sessionId) {
      this.terminal.write('正在恢復 session...\r\n');

      try {
        const response = await SocketClient.emitWithAck('terminal:reconnect', {
          session_id: sessionId
        });

        if (response.success) {
          this.sessionId = response.session_id;
          this.connected = true;
          this.updateStatusIndicator();
          this.terminal.write('\x1b[32mSession 已恢復！\x1b[0m\r\n');
          // Store session ID
          sessionStorage.setItem(`terminal_session_${this.windowId}`, this.sessionId);
          // Send resize to sync terminal size
          this.fit();
        } else {
          this.terminal.write(`\x1b[33mSession 已過期，建立新的連線...\x1b[0m\r\n`);
          this.createSession();
        }
      } catch (e) {
        this.terminal.write(`\x1b[31m恢復失敗: ${e.message}\x1b[0m\r\n`);
        this.createSession();
      }
    }

    /**
     * Setup Socket.IO event handlers
     */
    setupSocketHandlers() {
      // Output handler
      SocketClient.on('terminal:output', (data) => {
        if (data.session_id === this.sessionId) {
          this.terminal.write(data.data);
        }
      });

      // Error handler
      SocketClient.on('terminal:error', (data) => {
        if (data.session_id === this.sessionId) {
          this.terminal.write(`\r\n\x1b[31mError: ${data.error}\x1b[0m\r\n`);
        }
      });

      // Closed handler
      SocketClient.on('terminal:closed', (data) => {
        if (data.session_id === this.sessionId) {
          this.terminal.write('\r\n\x1b[33mSession ended.\x1b[0m\r\n');
          this.connected = false;
          this.updateStatusIndicator();
        }
      });
    }

    /**
     * Create a new terminal session
     */
    async createSession() {
      this.terminal.write('Connecting...\r\n');

      try {
        const response = await SocketClient.emitWithAck('terminal:create', {
          cols: this.terminal.cols,
          rows: this.terminal.rows
        });

        if (response.success) {
          this.sessionId = response.session_id;
          this.connected = true;
          this.updateStatusIndicator();
          // Store session ID for potential reconnect
          sessionStorage.setItem(`terminal_session_${this.windowId}`, this.sessionId);
        } else {
          this.terminal.write(`\r\n\x1b[31mFailed to create session: ${response.error}\x1b[0m\r\n`);
        }
      } catch (e) {
        this.terminal.write(`\r\n\x1b[31mConnection error: ${e.message}\x1b[0m\r\n`);
      }
    }

    /**
     * Fit terminal to container
     */
    fit() {
      if (this.fitAddon && this.terminal) {
        try {
          this.fitAddon.fit();
          // Send resize to server
          if (this.sessionId && this.connected) {
            SocketClient.emit('terminal:resize', {
              session_id: this.sessionId,
              cols: this.terminal.cols,
              rows: this.terminal.rows
            });
          }
        } catch (e) {
          // Ignore fit errors during initialization
        }
      }
    }

    /**
     * Update status indicator in status bar
     */
    updateStatusIndicator() {
      const windowEl = document.getElementById(this.windowId);
      if (!windowEl) return;

      const statusDot = windowEl.querySelector('.status-dot');
      if (statusDot) {
        statusDot.classList.toggle('connected', this.connected);
        statusDot.classList.toggle('disconnected', !this.connected);
      }

      const statusText = windowEl.querySelector('.terminal-status-text');
      if (statusText) {
        statusText.textContent = this.connected ? '已連線' : '已斷線';
      }
    }

    /**
     * Cleanup and destroy instance
     */
    destroy() {
      // Close session
      if (this.sessionId && this.connected) {
        SocketClient.emit('terminal:close', {
          session_id: this.sessionId
        });
      }

      // Remove session storage
      sessionStorage.removeItem(`terminal_session_${this.windowId}`);

      // Cleanup resize observer
      if (this.resizeObserver) {
        this.resizeObserver.disconnect();
      }

      // Dispose terminal
      if (this.terminal) {
        this.terminal.dispose();
      }
    }
  }

  /**
   * Build window content HTML
   * @returns {string}
   */
  function buildWindowContent() {
    return `
      <div class="terminal-app">
        <div class="terminal-container"></div>
        <div class="terminal-status-bar">
          <div class="terminal-status-left">
            <div class="terminal-status-indicator">
              <span class="status-dot"></span>
              <span class="terminal-status-text">連線中...</span>
            </div>
          </div>
          <div class="terminal-status-right">
            <span class="terminal-size"></span>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Initialize terminal in window
   * @param {string} windowId
   */
  function initTerminal(windowId) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const container = windowEl.querySelector('.terminal-container');
    if (!container) return;

    // Create instance
    const instance = new TerminalInstance(windowId);
    instances.set(windowId, instance);

    // Initialize
    instance.init(container);

    // Update size display
    if (instance.terminal) {
      instance.terminal.onResize(({ cols, rows }) => {
        const sizeDisplay = windowEl.querySelector('.terminal-size');
        if (sizeDisplay) {
          sizeDisplay.textContent = `${cols}x${rows}`;
        }
      });
    }
  }

  /**
   * Open terminal application
   */
  function open() {
    instanceCounter++;
    const instanceId = instanceCounter;

    // Create window
    const windowId = WindowModule.createWindow({
      title: `終端機${instanceCounter > 1 ? ` (${instanceCounter})` : ''}`,
      appId: APP_ID,
      icon: 'console',
      width: 800,
      height: 500,
      content: buildWindowContent(),
      onInit: (windowEl, wId) => {
        initTerminal(wId);
      },
      onClose: (wId) => {
        const instance = instances.get(wId);
        if (instance) {
          instance.destroy();
          instances.delete(wId);
        }
      }
    });

    return windowId;
  }

  /**
   * Close all terminal instances
   */
  function closeAll() {
    for (const [windowId, instance] of instances) {
      instance.destroy();
      WindowModule.closeWindow(windowId);
    }
    instances.clear();
  }

  // Public API
  return {
    open,
    closeAll
  };
})();
