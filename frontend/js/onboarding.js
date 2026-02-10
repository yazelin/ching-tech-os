/**
 * ChingTech OS - Onboarding Module
 * Sprint 5 — 3 步驟 Spotlight 引導
 *
 * 功能：
 *   1. 依序高亮 header-bar → command palette trigger → ai-assistant 桌面圖示
 *   2. 每步驟顯示 tooltip 說明
 *   3. 提供「跳過」與「稍後顯示」按鈕
 *   4. 完成後設定 localStorage 'onboardingSeen' 標記
 *   5. 外部可呼叫 restart() 重新啟動引導
 */

const OnboardingModule = (function () {
  'use strict';

  // ─── 設定 ───
  const STORAGE_KEY = 'onboardingSeen';

  /** @type {Array<{target: string, title: string, body: string}>} */
  const STEPS = [
    {
      target: '.header-bar',
      title: '歡迎來到 ChingTech OS',
      body: '這是系統標題列，包含時鐘、通知鈴鐺與使用者選單。點擊使用者名稱可進入個人資料頁面。'
    },
    {
      target: '.command-palette-trigger',
      title: '快速搜尋指令面板',
      body: '按下 Ctrl+K（Mac: ⌘K）或點擊此按鈕，即可搜尋並快速啟動任何功能或應用程式。'
    },
    {
      target: '[data-app-id="ai-assistant"]',
      title: 'AI 助理',
      body: '點擊桌面上的 AI 助理圖示，即可與智慧助理對話，協助您完成各種任務。'
    }
  ];

  // ─── 狀態 ───
  let currentStep = 0;
  let overlayEl = null;
  let spotlightEl = null;
  let tooltipEl = null;
  let isActive = false;
  let resizeRAF = null;

  // ─── DOM 建構 ───

  /**
   * 建立 overlay + spotlight + tooltip DOM
   */
  function createDOM() {
    // Overlay
    overlayEl = document.createElement('div');
    overlayEl.className = 'onboarding-overlay';
    overlayEl.setAttribute('role', 'dialog');
    overlayEl.setAttribute('aria-modal', 'true');
    overlayEl.setAttribute('aria-label', '新手導覽');

    // SVG 遮罩（半透明 + 挖洞）
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.classList.add('onboarding-mask-svg');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');

    const defs = document.createElementNS(svgNS, 'defs');
    const mask = document.createElementNS(svgNS, 'mask');
    mask.id = 'onboarding-cutout';

    const maskBg = document.createElementNS(svgNS, 'rect');
    maskBg.setAttribute('width', '100%');
    maskBg.setAttribute('height', '100%');
    maskBg.setAttribute('fill', 'white');

    const hole = document.createElementNS(svgNS, 'rect');
    hole.id = 'onboarding-hole';
    hole.setAttribute('rx', '12');
    hole.setAttribute('ry', '12');
    hole.setAttribute('fill', 'black');

    mask.appendChild(maskBg);
    mask.appendChild(hole);
    defs.appendChild(mask);
    svg.appendChild(defs);

    const overlay = document.createElementNS(svgNS, 'rect');
    overlay.setAttribute('width', '100%');
    overlay.setAttribute('height', '100%');
    overlay.setAttribute('fill', 'rgba(0,0,0,0.6)');
    overlay.setAttribute('mask', 'url(#onboarding-cutout)');
    svg.appendChild(overlay);

    overlayEl.appendChild(svg);

    // Spotlight 邊框環
    spotlightEl = document.createElement('div');
    spotlightEl.className = 'onboarding-spotlight';
    overlayEl.appendChild(spotlightEl);

    // Tooltip
    tooltipEl = document.createElement('div');
    tooltipEl.className = 'onboarding-tooltip';
    tooltipEl.setAttribute('data-arrow', 'top');
    overlayEl.appendChild(tooltipEl);

    document.body.appendChild(overlayEl);
  }

  /**
   * 渲染 tooltip 內容
   */
  function renderTooltip(step, index, total) {
    const dotsHTML = Array.from({ length: total }, (_, i) => {
      const cls = i === index ? 'active' : i < index ? 'completed' : '';
      return `<span class="onboarding-dot ${cls}"></span>`;
    }).join('');

    const isLast = index === total - 1;

    tooltipEl.innerHTML = `
      <div class="onboarding-tooltip-step">
        <span class="onboarding-step-dot"></span>
        步驟 ${index + 1} / ${total}
      </div>
      <div class="onboarding-tooltip-title">${step.title}</div>
      <div class="onboarding-tooltip-body">${step.body}</div>
      <div class="onboarding-dots">${dotsHTML}</div>
      <div class="onboarding-actions">
        <button class="onboarding-btn onboarding-btn-link" data-action="skip">跳過導覽</button>
        <div style="display:flex;gap:8px;">
          ${index > 0 ? '<button class="onboarding-btn onboarding-btn-ghost" data-action="prev">上一步</button>' : '<button class="onboarding-btn onboarding-btn-ghost" data-action="later">稍後再看</button>'}
          <button class="onboarding-btn onboarding-btn-primary" data-action="${isLast ? 'done' : 'next'}">
            ${isLast ? '開始使用 🚀' : '下一步'}
          </button>
        </div>
      </div>
    `;

    // 按鈕事件
    tooltipEl.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', handleAction);
    });
  }

  // ─── 定位邏輯 ───

  /**
   * 取得目標元素並定位 spotlight + tooltip
   */
  function positionSpotlight() {
    const step = STEPS[currentStep];
    const targetEl = document.querySelector(step.target);

    if (!targetEl) {
      // [Sprint8] UIHelpers: 目標不存在時記錄警告
      console.warn(`[Onboarding] 步驟 ${currentStep + 1} 目標元素未找到: ${step.target}`);
      // 目標不存在，跳至下一步
      if (currentStep < STEPS.length - 1) {
        currentStep++;
        showStep();
      } else {
        finish();
      }
      return;
    }

    const rect = targetEl.getBoundingClientRect();
    const pad = 8; // spotlight 外擴 padding

    const x = rect.left - pad;
    const y = rect.top - pad;
    const w = rect.width + pad * 2;
    const h = rect.height + pad * 2;

    // Spotlight 邊框
    spotlightEl.style.left = `${x}px`;
    spotlightEl.style.top = `${y}px`;
    spotlightEl.style.width = `${w}px`;
    spotlightEl.style.height = `${h}px`;

    // SVG 遮罩挖洞
    const hole = document.getElementById('onboarding-hole');
    if (hole) {
      hole.setAttribute('x', x);
      hole.setAttribute('y', y);
      hole.setAttribute('width', w);
      hole.setAttribute('height', h);
    }

    // Tooltip 定位
    positionTooltip(rect);
  }

  /**
   * 根據目標位置決定 tooltip 放置方向
   */
  function positionTooltip(targetRect) {
    const tooltipW = 340;
    const gap = 16;
    const vpH = window.innerHeight;
    const vpW = window.innerWidth;

    // 預設放在目標下方
    let top = targetRect.bottom + gap;
    let left = targetRect.left + targetRect.width / 2 - tooltipW / 2;
    let arrow = 'top';

    // 如果下方空間不足，放到上方
    if (top + 240 > vpH) {
      top = targetRect.top - gap - 240;
      arrow = 'bottom';
    }

    // 水平邊界保護
    if (left < 12) left = 12;
    if (left + tooltipW > vpW - 12) left = vpW - tooltipW - 12;

    tooltipEl.style.top = `${top}px`;
    tooltipEl.style.left = `${left}px`;
    tooltipEl.setAttribute('data-arrow', arrow);
  }

  // ─── 步驟控制 ───

  function showStep() {
    const step = STEPS[currentStep];
    renderTooltip(step, currentStep, STEPS.length);

    // 先隱藏 tooltip 做動畫
    tooltipEl.classList.remove('visible');

    requestAnimationFrame(() => {
      positionSpotlight();
      // 延遲讓 transition 生效
      requestAnimationFrame(() => {
        tooltipEl.classList.add('visible');
      });
    });
  }

  function handleAction(e) {
    const action = e.currentTarget.dataset.action;

    switch (action) {
      case 'next':
        if (currentStep < STEPS.length - 1) {
          currentStep++;
          showStep();
        }
        break;

      case 'prev':
        if (currentStep > 0) {
          currentStep--;
          showStep();
        }
        break;

      case 'done':
        finish();
        break;

      case 'skip':
        finish();
        break;

      case 'later':
        close();
        // 不設定 localStorage，下次仍顯示
        break;
    }
  }

  /**
   * 完成引導，標記已看過
   */
  function finish() {
    localStorage.setItem(STORAGE_KEY, 'true');
    close();
  }

  /**
   * 關閉 overlay
   */
  function close() {
    if (!isActive) return;
    isActive = false;

    overlayEl.classList.remove('active');
    tooltipEl.classList.remove('visible');

    window.removeEventListener('resize', handleResize);
    window.removeEventListener('keydown', handleKeydown);

    // 等 transition 結束再移除 DOM
    setTimeout(() => {
      if (overlayEl && overlayEl.parentNode) {
        overlayEl.parentNode.removeChild(overlayEl);
      }
      overlayEl = null;
      spotlightEl = null;
      tooltipEl = null;
    }, 350);
  }

  // ─── 事件處理 ───

  function handleResize() {
    if (resizeRAF) cancelAnimationFrame(resizeRAF);
    resizeRAF = requestAnimationFrame(() => {
      if (isActive) positionSpotlight();
    });
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      finish();
    } else if (e.key === 'ArrowRight' || e.key === 'Enter') {
      if (currentStep < STEPS.length - 1) {
        currentStep++;
        showStep();
      } else {
        finish();
      }
    } else if (e.key === 'ArrowLeft') {
      if (currentStep > 0) {
        currentStep--;
        showStep();
      }
    }
  }

  // ─── 公開 API ───

  /**
   * 啟動引導（僅在未看過時自動呼叫）
   */
  function start() {
    if (isActive) return;

    currentStep = 0;
    isActive = true;

    createDOM();

    // 確保 DOM 渲染後顯示
    requestAnimationFrame(() => {
      overlayEl.classList.add('active');
      showStep();
    });

    window.addEventListener('resize', handleResize);
    window.addEventListener('keydown', handleKeydown);
  }

  /**
   * 重新啟動引導（從 user menu 呼叫）
   */
  function restart() {
    localStorage.removeItem(STORAGE_KEY);
    if (isActive) close();
    // 小延遲讓 close 動畫完成
    setTimeout(start, 400);
  }

  /**
   * 檢查是否已看過
   */
  function hasSeen() {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  }

  /**
   * 初始化 — 若未看過則延遲顯示
   */
  function init() {
    if (!hasSeen()) {
      // 延遲 1.5 秒讓桌面渲染完成
      setTimeout(start, 1500);
    }
  }

  return {
    init,
    start,
    restart,
    hasSeen
  };
})();
