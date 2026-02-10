import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  // 專案根目錄即 frontend/
  root: '.',

  // 開發伺服器設定
  server: {
    port: 5173,
    open: false,
  },

  build: {
    // 輸出至 frontend/dist
    outDir: 'dist',
    emptyOutDir: true,

    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
    },

    // 保守策略：產出相容性較佳的格式
    target: 'es2020',
    // 不做程式碼分割，合併為單一 bundle 以簡化首次部署
    cssCodeSplit: false,
  },

  // 將 CDN 外部相依排除在 bundle 之外（它們透過 <script> 標籤載入）
  // Vite 預設不會處理非 module 的 <script>，因此這裡僅作為文件說明
  optimizeDeps: {
    exclude: ['marked', 'socket.io-client', '@xterm/xterm'],
  },
});
