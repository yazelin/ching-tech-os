/**
 * ChingTech OS - Matrix Rain Effect
 * 像素風格：正方形格子、無間隔、全畫面佈滿
 */

const MatrixRain = (function() {
  'use strict';

  let canvas, ctx;
  let grid = [];
  let streams = [];
  let brightness = [];
  let isHead = [];
  let cols = 0;
  let rows = 0;
  let animationId = null;
  let lastTime = 0;
  let radialCache = [];

  // 字符集（半形片假名 + 數字 + 符號）
  const chars = 'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜｦﾝ0123456789ABCDEFZ';

  // 設定
  const config = {
    cellSize: 20,          // 正方形格子大小
    interval: 45,
    streamLength: 35,
  };

  /**
   * 取得主題顏色
   */
  function getColors() {
    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';

    if (isDark) {
      // 暗色主題：橘色（強調色）
      return {
        head: '#ea580c',
        headGlow: 'rgba(234, 88, 12, 0.8)',
        text: (alpha) => `rgba(234, 88, 12, ${alpha})`,
      };
    } else {
      // 亮色主題：橘色（強調色）
      return {
        head: '#ea580c',
        headGlow: 'rgba(234, 88, 12, 0.6)',
        text: (alpha) => `rgba(234, 88, 12, ${alpha})`,
      };
    }
  }

  /**
   * 偵測使用者是否偏好減少動態效果
   */
  function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  /**
   * 初始化
   */
  function init() {
    // 尊重使用者的 prefers-reduced-motion 設定
    if (prefersReducedMotion()) {
      return;
    }

    // 監聽設定變化（使用者可能在執行期間切換）
    window.matchMedia('(prefers-reduced-motion: reduce)')
      .addEventListener('change', (e) => {
        if (e.matches) {
          destroy();
        }
      });

    canvas = document.createElement('canvas');
    canvas.id = 'matrix-rain';
    canvas.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 0;
    `;

    const container = document.querySelector('.login-container');
    if (container) {
      container.insertBefore(canvas, container.firstChild);
    } else {
      document.body.appendChild(canvas);
    }

    ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize);

    new MutationObserver(resize).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    lastTime = performance.now();
    animationId = requestAnimationFrame(update);
  }

  /**
   * 調整大小
   */
  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    // 計算格子數（無間隔，完全填滿）
    cols = Math.ceil(canvas.width / config.cellSize);
    rows = Math.ceil(canvas.height / config.cellSize);

    // 預計算徑向亮度（中心暗，四周亮）
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const maxDist = Math.sqrt(centerX * centerX + centerY * centerY);

    grid = [];
    brightness = [];
    isHead = [];
    radialCache = [];

    for (let x = 0; x < cols; x++) {
      grid[x] = [];
      brightness[x] = [];
      isHead[x] = [];
      radialCache[x] = [];

      for (let y = 0; y < rows; y++) {
        grid[x][y] = chars[Math.floor(Math.random() * chars.length)];
        brightness[x][y] = 0;
        isHead[x][y] = false;

        const screenX = x * config.cellSize + config.cellSize / 2;
        const screenY = y * config.cellSize + config.cellSize / 2;
        const dx = screenX - centerX;
        const dy = screenY - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        // 中間亮（100%），四周暗（0%）
        radialCache[x][y] = Math.max(0, 1.0 - (dist / maxDist));
      }
    }

    // 每列一個光流
    streams = [];
    for (let x = 0; x < cols; x++) {
      streams.push({
        col: x,
        row: Math.random() * rows * 2 - rows,
        speed: 0.3 + Math.random() * 0.5,
      });
    }
  }

  /**
   * 更新並繪製
   */
  function update(currentTime) {
    animationId = requestAnimationFrame(update);

    if (currentTime - lastTime < config.interval) return;
    lastTime = currentTime;

    const colors = getColors();

    // 清除畫布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 設定字體（填滿格子）
    const fontSize = config.cellSize;
    ctx.font = `bold ${fontSize}px "MS Gothic", "Noto Sans Mono CJK TC", Consolas, monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // 重置
    for (let x = 0; x < cols; x++) {
      for (let y = 0; y < rows; y++) {
        brightness[x][y] = 0;
        isHead[x][y] = false;
      }
    }

    // 計算光流亮度
    for (const stream of streams) {
      const headRow = Math.floor(stream.row);

      for (let i = 0; i < config.streamLength; i++) {
        const row = headRow - i;
        if (row < 0 || row >= rows) continue;

        let intensity;
        if (i === 0) {
          intensity = 1.0;
          isHead[stream.col][row] = true;
        } else {
          intensity = Math.max(0, 1 - (i / config.streamLength));
        }

        brightness[stream.col][row] = Math.max(brightness[stream.col][row], intensity);
      }

      // 移動
      stream.row += stream.speed;
      if (stream.row - config.streamLength > rows) {
        stream.row = -Math.random() * 15;
        stream.speed = 0.3 + Math.random() * 0.5;
      }
    }

    // 繪製所有格子（全畫面填滿）
    for (let x = 0; x < cols; x++) {
      for (let y = 0; y < rows; y++) {
        const b = brightness[x][y];
        const screenX = x * config.cellSize + config.cellSize / 2;
        const screenY = y * config.cellSize + config.cellSize / 2;
        const radial = radialCache[x][y];
        const char = grid[x][y];

        ctx.save();
        ctx.translate(screenX, screenY);
        ctx.scale(1.8, 1.1);  // 拉伸填滿格子

        if (isHead[x][y]) {
          // 頭部最亮 + 發光/陰影效果
          ctx.globalAlpha = radial;
          ctx.shadowColor = colors.headGlow;
          ctx.shadowBlur = 8;
          ctx.fillStyle = colors.head;
          ctx.fillText(char, 0, 0);
          ctx.shadowBlur = 0;
          ctx.globalAlpha = 1;
        } else if (b > 0) {
          // 尾巴
          ctx.fillStyle = colors.text(b * radial * 0.4);
          ctx.fillText(char, 0, 0);
        } else {
          // 背景字符（很暗）
          ctx.fillStyle = colors.text(radial * 0.08);
          ctx.fillText(char, 0, 0);
        }

        ctx.restore();
      }
    }

    // 隨機更換字符
    for (const stream of streams) {
      if (Math.random() < 0.25) {
        const row = Math.floor(stream.row - Math.random() * config.streamLength);
        if (row >= 0 && row < rows) {
          grid[stream.col][row] = chars[Math.floor(Math.random() * chars.length)];
        }
      }
    }
  }

  function stop() {
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
  }

  function destroy() {
    stop();
    if (canvas && canvas.parentNode) {
      canvas.parentNode.removeChild(canvas);
    }
    window.removeEventListener('resize', resize);
  }

  return { init, stop, destroy };
})();

document.addEventListener('DOMContentLoaded', function() {
  MatrixRain.init();
});
