/**
 * LazyBg — 延遲載入背景圖片模組
 * 使用 data-bg 屬性標記需要延遲載入背景的元素，
 * 透過 requestIdleCallback 在瀏覽器閒置時載入。
 */
const LazyBg = (() => {
  function applyBg(el) {
    const url = el.dataset.bg;
    if (!url) return;
    const img = new Image();
    img.onload = () => {
      el.style.backgroundImage = `url('${url}')`;
      el.classList.add('lazy-bg--loaded');
    };
    img.src = url;
  }

  function init() {
    const els = document.querySelectorAll('[data-bg]');
    if (!els.length) return;

    const schedule = window.requestIdleCallback || ((cb) => setTimeout(cb, 50));
    schedule(() => {
      els.forEach(applyBg);
    });
  }

  // 自動在 DOMContentLoaded 初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  return { init };
})();
