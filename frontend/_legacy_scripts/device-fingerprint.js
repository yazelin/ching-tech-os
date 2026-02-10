/**
 * 裝置指紋產生器
 *
 * 結合多種裝置特徵產生唯一指紋，用於識別登入裝置
 */

const DeviceFingerprint = {
  /**
   * 產生裝置指紋
   * @returns {Promise<Object>} 裝置資訊物件
   */
  async generate() {
    const components = await this.collectComponents();
    const fingerprint = this.hash(JSON.stringify(components));

    return {
      fingerprint,
      device_type: this.getDeviceType(),
      browser: this.getBrowserInfo(),
      os: this.getOSInfo(),
      screen_resolution: this.getScreenResolution(),
      timezone: this.getTimezone(),
      language: navigator.language || navigator.userLanguage,
    };
  },

  /**
   * 收集裝置特徵
   */
  async collectComponents() {
    return {
      userAgent: navigator.userAgent,
      language: navigator.language,
      platform: navigator.platform,
      hardwareConcurrency: navigator.hardwareConcurrency || 0,
      deviceMemory: navigator.deviceMemory || 0,
      screenResolution: this.getScreenResolution(),
      timezone: this.getTimezone(),
      timezoneOffset: new Date().getTimezoneOffset(),
      sessionStorage: this.hasSessionStorage(),
      localStorage: this.hasLocalStorage(),
      indexedDB: this.hasIndexedDB(),
      cookieEnabled: navigator.cookieEnabled,
      colorDepth: screen.colorDepth,
      pixelRatio: window.devicePixelRatio || 1,
      touchSupport: this.getTouchSupport(),
      canvas: await this.getCanvasFingerprint(),
      webgl: this.getWebGLFingerprint(),
    };
  },

  /**
   * 取得螢幕解析度
   */
  getScreenResolution() {
    return `${screen.width}x${screen.height}`;
  },

  /**
   * 取得時區
   */
  getTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
      return '';
    }
  },

  /**
   * 檢查 sessionStorage
   */
  hasSessionStorage() {
    try {
      sessionStorage.setItem('test', '1');
      sessionStorage.removeItem('test');
      return true;
    } catch {
      return false;
    }
  },

  /**
   * 檢查 localStorage
   */
  hasLocalStorage() {
    try {
      localStorage.setItem('test', '1');
      localStorage.removeItem('test');
      return true;
    } catch {
      return false;
    }
  },

  /**
   * 檢查 IndexedDB
   */
  hasIndexedDB() {
    return !!window.indexedDB;
  },

  /**
   * 取得觸控支援資訊
   */
  getTouchSupport() {
    return {
      maxTouchPoints: navigator.maxTouchPoints || 0,
      touchEvent: 'ontouchstart' in window,
      touchPoints: navigator.msMaxTouchPoints || 0,
    };
  },

  /**
   * 取得 Canvas 指紋
   */
  async getCanvasFingerprint() {
    try {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = 200;
      canvas.height = 50;

      // 繪製文字
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = '#f60';
      ctx.fillRect(125, 1, 62, 20);
      ctx.fillStyle = '#069';
      ctx.font = '11pt Arial';
      ctx.fillText('ChingTech OS', 2, 15);
      ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
      ctx.font = '18pt Arial';
      ctx.fillText('ChingTech OS', 4, 45);

      // 取得資料 URL
      return canvas.toDataURL().slice(-50);
    } catch {
      return '';
    }
  },

  /**
   * 取得 WebGL 指紋
   */
  getWebGLFingerprint() {
    try {
      const canvas = document.createElement('canvas');
      const gl =
        canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) return '';

      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
      if (debugInfo) {
        return {
          vendor: gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL),
          renderer: gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL),
        };
      }
      return {
        vendor: gl.getParameter(gl.VENDOR),
        renderer: gl.getParameter(gl.RENDERER),
      };
    } catch {
      return '';
    }
  },

  /**
   * 取得裝置類型
   */
  getDeviceType() {
    const ua = navigator.userAgent.toLowerCase();

    if (
      /mobile|android|iphone|ipod|blackberry|iemobile|opera mini/i.test(ua)
    ) {
      return 'mobile';
    }
    if (/ipad|tablet|playbook|silk/i.test(ua)) {
      return 'tablet';
    }
    return 'desktop';
  },

  /**
   * 取得瀏覽器資訊
   */
  getBrowserInfo() {
    const ua = navigator.userAgent;
    let browser = 'Unknown';
    let version = '';

    if (ua.indexOf('Firefox') > -1) {
      browser = 'Firefox';
      version = ua.match(/Firefox\/(\d+)/)?.[1] || '';
    } else if (ua.indexOf('Edg') > -1) {
      browser = 'Edge';
      version = ua.match(/Edg\/(\d+)/)?.[1] || '';
    } else if (ua.indexOf('Chrome') > -1) {
      browser = 'Chrome';
      version = ua.match(/Chrome\/(\d+)/)?.[1] || '';
    } else if (ua.indexOf('Safari') > -1) {
      browser = 'Safari';
      version = ua.match(/Version\/(\d+)/)?.[1] || '';
    } else if (ua.indexOf('Opera') > -1 || ua.indexOf('OPR') > -1) {
      browser = 'Opera';
      version = ua.match(/(?:Opera|OPR)\/(\d+)/)?.[1] || '';
    }

    return version ? `${browser} ${version}` : browser;
  },

  /**
   * 取得作業系統資訊
   */
  getOSInfo() {
    const ua = navigator.userAgent;
    let os = 'Unknown';

    if (ua.indexOf('Windows NT 10') > -1) {
      os = 'Windows 10/11';
    } else if (ua.indexOf('Windows NT 6.3') > -1) {
      os = 'Windows 8.1';
    } else if (ua.indexOf('Windows NT 6.2') > -1) {
      os = 'Windows 8';
    } else if (ua.indexOf('Windows NT 6.1') > -1) {
      os = 'Windows 7';
    } else if (ua.indexOf('Mac OS X') > -1) {
      const version = ua.match(/Mac OS X (\d+[._]\d+)/)?.[1]?.replace('_', '.');
      os = version ? `macOS ${version}` : 'macOS';
    } else if (ua.indexOf('Linux') > -1) {
      if (ua.indexOf('Ubuntu') > -1) {
        os = 'Ubuntu Linux';
      } else if (ua.indexOf('Android') > -1) {
        const version = ua.match(/Android (\d+)/)?.[1];
        os = version ? `Android ${version}` : 'Android';
      } else {
        os = 'Linux';
      }
    } else if (ua.indexOf('iPhone') > -1 || ua.indexOf('iPad') > -1) {
      const version = ua.match(/OS (\d+)/)?.[1];
      os = version ? `iOS ${version}` : 'iOS';
    }

    return os;
  },

  /**
   * 簡單的字串雜湊函式
   */
  hash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    // 轉換為 16 進位並確保正數
    return Math.abs(hash).toString(16).padStart(8, '0');
  },
};

// 匯出供登入頁面使用
window.DeviceFingerprint = DeviceFingerprint;
