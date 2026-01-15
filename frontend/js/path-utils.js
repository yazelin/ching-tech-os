/**
 * 統一路徑工具
 *
 * 與後端 PathManager 對應的前端路徑處理工具。
 *
 * 路徑協議：
 * - ctos://    → CTOS 系統檔案
 * - shared://  → 公司專案共用區
 * - temp://    → 暫存檔案
 * - local://   → 本機小檔案
 *
 * 範例：
 * - ctos://knowledge/kb-001/file.pdf
 * - ctos://linebot/groups/C123/images/2026-01-05/abc.jpg
 * - shared://亦達光學/layout.pdf
 * - temp://linebot/msg123.pdf
 */

const PathUtils = (function () {
  'use strict';

  /**
   * 儲存區域
   */
  const StorageZone = {
    CTOS: 'ctos', // CTOS 系統檔案
    SHARED: 'shared', // 公司專案共用區
    TEMP: 'temp', // 暫存
    LOCAL: 'local', // 本機
  };

  /**
   * Line Bot 相對路徑前綴
   */
  const LINEBOT_PREFIXES = ['groups/', 'users/', 'ai-images/', 'pdf-converted/'];

  /**
   * 舊格式前綴對應（用於向後相容）
   */
  const LEGACY_PREFIXES = {
    'nas://knowledge/attachments/': { zone: StorageZone.CTOS, newPrefix: 'knowledge/' },
    'nas://knowledge/': { zone: StorageZone.CTOS, newPrefix: 'knowledge/' },
    'nas://projects/attachments/': { zone: StorageZone.CTOS, newPrefix: 'attachments/' },
    'nas://projects/': { zone: StorageZone.CTOS, newPrefix: 'attachments/' },
    'nas://linebot/files/': { zone: StorageZone.CTOS, newPrefix: 'linebot/' },
    'nas://linebot/': { zone: StorageZone.CTOS, newPrefix: 'linebot/' },
    'nas://ching-tech-os/linebot/files/': { zone: StorageZone.CTOS, newPrefix: 'linebot/' },
    '../assets/': { zone: StorageZone.LOCAL, newPrefix: 'knowledge/' },
  };

  /**
   * 圖片副檔名
   */
  const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'];

  /**
   * 解析路徑
   *
   * @param {string} path - 輸入路徑（新格式或舊格式）
   * @returns {{ zone: string, path: string, raw: string }} 解析後的路徑
   */
  function parse(path) {
    if (!path) {
      throw new Error('路徑不可為空');
    }

    // 1. 新格式：{protocol}://...
    for (const zone of Object.values(StorageZone)) {
      const prefix = `${zone}://`;
      if (path.startsWith(prefix)) {
        return {
          zone: zone,
          path: path.slice(prefix.length),
          raw: path,
        };
      }
    }

    // 2. 舊格式：nas://... 或 ../assets/...
    for (const [legacyPrefix, mapping] of Object.entries(LEGACY_PREFIXES)) {
      if (path.startsWith(legacyPrefix)) {
        const relative = path.slice(legacyPrefix.length);
        return {
          zone: mapping.zone,
          path: `${mapping.newPrefix}${relative}`,
          raw: path,
        };
      }
    }

    // 3. Line Bot 相對路徑：groups/..., users/..., ai-images/...
    for (const prefix of LINEBOT_PREFIXES) {
      if (path.startsWith(prefix)) {
        return {
          zone: StorageZone.CTOS,
          path: `linebot/${path}`,
          raw: path,
        };
      }
    }

    // 4. /tmp/... 開頭 → temp://
    if (path.startsWith('/tmp/')) {
      let relative = path.slice(5); // 移除 /tmp/

      // 特殊處理 nanobanana 輸出
      if (relative.includes('nanobanana-output/')) {
        const filename = relative.split('nanobanana-output/').pop();
        return {
          zone: StorageZone.TEMP,
          path: `ai-generated/${filename}`,
          raw: path,
        };
      }

      // 特殊處理 linebot-files
      if (relative.startsWith('linebot-files/')) {
        return {
          zone: StorageZone.TEMP,
          path: `linebot/${relative.slice(14)}`,
          raw: path,
        };
      }

      return {
        zone: StorageZone.TEMP,
        path: relative,
        raw: path,
      };
    }

    // 5. 以 / 開頭但不是系統路徑 → shared://
    // （這是 search_nas_files 回傳的格式）
    if (path.startsWith('/') && !path.startsWith('/tmp/') && !path.startsWith('/mnt/')) {
      return {
        zone: StorageZone.SHARED,
        path: path.slice(1), // 移除開頭的 /
        raw: path,
      };
    }

    // 6. 純相對路徑（無法判斷 zone）→ 預設 CTOS
    return {
      zone: StorageZone.CTOS,
      path: path,
      raw: path,
    };
  }

  /**
   * 轉換為 API URL
   *
   * @param {string} path - 輸入路徑（任何格式）
   * @returns {string} API URL，如 /api/files/ctos/knowledge/kb-001/file.pdf
   */
  function toApiUrl(path) {
    const parsed = parse(path);
    const basePath = window.API_BASE || '';
    return `${basePath}/api/files/${parsed.zone}/${parsed.path}`;
  }

  /**
   * 轉換為標準 URI 格式
   *
   * @param {string} path - 輸入路徑（任何格式）
   * @returns {string} 標準化 URI，如 ctos://knowledge/kb-001/file.pdf
   */
  function toUri(path) {
    const parsed = parse(path);
    return `${parsed.zone}://${parsed.path}`;
  }

  /**
   * 取得檔案副檔名（小寫）
   *
   * @param {string} path - 檔案路徑
   * @returns {string} 副檔名（含點），如 .pdf
   */
  function getExtension(path) {
    if (!path) return '';
    const lastDot = path.lastIndexOf('.');
    if (lastDot === -1) return '';
    return path.slice(lastDot).toLowerCase();
  }

  /**
   * 判斷是否為圖片
   *
   * @param {string} path - 檔案路徑
   * @returns {boolean}
   */
  function isImage(path) {
    const ext = getExtension(path);
    return IMAGE_EXTENSIONS.includes(ext);
  }

  /**
   * 判斷是否為 PDF
   *
   * @param {string} path - 檔案路徑
   * @returns {boolean}
   */
  function isPdf(path) {
    return getExtension(path) === '.pdf';
  }

  /**
   * 判斷是否為影片
   *
   * @param {string} path - 檔案路徑
   * @returns {boolean}
   */
  function isVideo(path) {
    const ext = getExtension(path);
    return ['.mp4', '.webm', '.mov', '.avi', '.mkv'].includes(ext);
  }

  /**
   * 判斷是否為音訊
   *
   * @param {string} path - 檔案路徑
   * @returns {boolean}
   */
  function isAudio(path) {
    const ext = getExtension(path);
    return ['.mp3', '.wav', '.ogg', '.flac', '.m4a'].includes(ext);
  }

  /**
   * 判斷是否為文字檔
   *
   * @param {string} path - 檔案路徑
   * @returns {boolean}
   */
  function isText(path) {
    const ext = getExtension(path);
    return ['.txt', '.md', '.json', '.xml', '.csv', '.log', '.html', '.css', '.js'].includes(ext);
  }

  /**
   * 判斷路徑是否為唯讀
   *
   * @param {string} path - 檔案路徑
   * @returns {boolean} shared:// 區域為唯讀
   */
  function isReadonly(path) {
    const parsed = parse(path);
    return parsed.zone === StorageZone.SHARED;
  }

  /**
   * 取得路徑的儲存區域
   *
   * @param {string} path - 檔案路徑
   * @returns {string} StorageZone 值
   */
  function getZone(path) {
    return parse(path).zone;
  }

  // 公開 API
  return {
    StorageZone,
    parse,
    toApiUrl,
    toUri,
    getExtension,
    isImage,
    isPdf,
    isVideo,
    isAudio,
    isText,
    isReadonly,
    getZone,
  };
})();

// 支援 ES6 模組匯出（如果需要）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = PathUtils;
}
