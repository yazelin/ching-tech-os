/**
 * ChingTech OS - 檔案工具模組
 * 統一的檔案圖示、類型判斷、格式化功能
 */

const FileUtils = (function() {
  'use strict';

  // ============================================================
  // 副檔名分類
  // ============================================================

  const EXTENSIONS = {
    // 圖片
    image: ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'heic', 'ico', 'tiff', 'tif'],
    // 影片
    video: ['mp4', 'webm', 'avi', 'mov', 'mkv', 'm4v', 'wmv', 'flv', '3gp'],
    // 音訊
    audio: ['mp3', 'm4a', 'wav', 'ogg', 'flac', 'aac', 'wma', 'aiff'],
    // PDF
    pdf: ['pdf'],
    // 文件
    document: ['doc', 'docx', 'odt', 'rtf'],
    // 試算表
    spreadsheet: ['xls', 'xlsx', 'ods', 'csv'],
    // 簡報
    presentation: ['ppt', 'pptx', 'odp'],
    // 純文字/Markdown
    text: ['txt', 'md', 'markdown', 'log', 'readme'],
    // 程式碼
    code: ['js', 'ts', 'jsx', 'tsx', 'css', 'scss', 'sass', 'less',
           'html', 'htm', 'xml', 'json', 'yaml', 'yml', 'toml',
           'py', 'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'go', 'rs', 'rb',
           'php', 'sql', 'sh', 'bash', 'zsh', 'ps1', 'bat', 'cmd'],
    // CAD/工程圖
    cad: ['dwg', 'dxf', 'step', 'stp', 'iges', 'igs', 'stl', 'obj', '3ds'],
    // 壓縮檔
    archive: ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'tgz'],
  };

  // ============================================================
  // 圖示映射
  // ============================================================

  const ICON_MAP = {
    // 分類對應圖示
    folder: 'folder',
    image: 'image',
    video: 'video',
    audio: 'audio',
    pdf: 'file-pdf-box',
    document: 'file-document',
    spreadsheet: 'file-excel',
    presentation: 'file-powerpoint',
    text: 'file-document',
    code: 'code-braces',
    cad: 'ruler-square',
    archive: 'folder-zip',
    default: 'file',
  };

  // ============================================================
  // 類型顏色映射（CSS class 用）
  // ============================================================

  const TYPE_COLORS = {
    folder: 'folder',      // 資料夾黃色
    image: 'image',        // 綠色
    video: 'video',        // 紫色
    audio: 'audio',        // 黃色
    pdf: 'pdf',            // 紅色
    document: 'document',  // 藍色
    spreadsheet: 'spreadsheet', // 綠色
    presentation: 'presentation', // 橘色
    text: 'text',          // 灰色
    code: 'code',          // 青色
    cad: 'cad',            // 橘色
    archive: 'archive',    // 棕色
    default: 'default',    // 灰色
  };

  // ============================================================
  // 公開方法
  // ============================================================

  /**
   * 從檔名取得副檔名（小寫）
   * @param {string} filename - 檔案名稱
   * @returns {string} 副檔名（不含點）
   */
  function getExtension(filename) {
    if (!filename || typeof filename !== 'string') return '';
    const parts = filename.split('.');
    if (parts.length < 2) return '';
    return parts.pop().toLowerCase();
  }

  /**
   * 判斷檔案類型分類
   * @param {string} filename - 檔案名稱
   * @param {string} [fileType] - 可選的檔案類型（如 'image', 'video'）
   * @param {boolean} [isDirectory] - 是否為資料夾
   * @returns {string} 類型分類（image, video, audio, pdf, document, code, cad, archive, text, default）
   */
  function getFileCategory(filename, fileType, isDirectory) {
    if (isDirectory) return 'folder';

    // 優先使用副檔名判斷
    const ext = getExtension(filename);
    if (ext) {
      for (const [category, extensions] of Object.entries(EXTENSIONS)) {
        if (extensions.includes(ext)) {
          return category;
        }
      }
    }

    // 備用：使用傳入的 fileType
    if (fileType) {
      const normalizedType = fileType.toLowerCase();
      if (EXTENSIONS[normalizedType]) return normalizedType;
      // 處理一些常見的 MIME type 簡寫
      if (normalizedType === 'file') return 'default';
    }

    return 'default';
  }

  /**
   * 取得檔案對應的圖示名稱
   * @param {string} filename - 檔案名稱
   * @param {string} [fileType] - 可選的檔案類型
   * @param {boolean} [isDirectory] - 是否為資料夾
   * @returns {string} 圖示名稱（對應 icons.js）
   */
  function getFileIcon(filename, fileType, isDirectory) {
    const category = getFileCategory(filename, fileType, isDirectory);
    return ICON_MAP[category] || ICON_MAP.default;
  }

  /**
   * 取得檔案類型的 CSS class（用於顏色）
   * @param {string} filename - 檔案名稱
   * @param {string} [fileType] - 可選的檔案類型
   * @param {boolean} [isDirectory] - 是否為資料夾
   * @returns {string} CSS class 名稱
   */
  function getFileTypeClass(filename, fileType, isDirectory) {
    const category = getFileCategory(filename, fileType, isDirectory);
    return TYPE_COLORS[category] || TYPE_COLORS.default;
  }

  /**
   * 格式化檔案大小
   * @param {number} bytes - 位元組數
   * @returns {string} 格式化後的大小（如 "1.5 MB"）
   */
  function formatFileSize(bytes) {
    if (bytes === null || bytes === undefined) return '-';
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const size = bytes / Math.pow(1024, i);
    return size.toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
  }

  /**
   * 判斷是否為可預覽的文字檔
   * @param {string} filename - 檔案名稱
   * @returns {boolean}
   */
  function isTextFile(filename) {
    const category = getFileCategory(filename);
    return category === 'text' || category === 'code';
  }

  /**
   * 判斷是否為圖片檔
   * @param {string} filename - 檔案名稱
   * @returns {boolean}
   */
  function isImageFile(filename) {
    return getFileCategory(filename) === 'image';
  }

  /**
   * 判斷是否為影片檔
   * @param {string} filename - 檔案名稱
   * @returns {boolean}
   */
  function isVideoFile(filename) {
    return getFileCategory(filename) === 'video';
  }

  /**
   * 判斷是否為音訊檔
   * @param {string} filename - 檔案名稱
   * @returns {boolean}
   */
  function isAudioFile(filename) {
    return getFileCategory(filename) === 'audio';
  }

  /**
   * 判斷是否為 PDF
   * @param {string} filename - 檔案名稱
   * @returns {boolean}
   */
  function isPdfFile(filename) {
    return getFileCategory(filename) === 'pdf';
  }

  /**
   * 取得認證 Token
   * @returns {string}
   */
  function getToken() {
    return (typeof LoginModule !== 'undefined' && LoginModule.getToken?.())
      || localStorage.getItem('chingtech_token')
      || '';
  }

  /**
   * 認證下載檔案
   * 使用 fetch + blob 方式下載，自動帶入認證 token
   * @param {string} url - 下載 URL（可以是相對路徑如 /api/...）
   * @param {string} [filename] - 下載後的檔名（可選，預設從 URL 取得）
   * @returns {Promise<void>}
   */
  async function downloadWithAuth(url, filename) {
    const basePath = window.API_BASE || '';
    const fullUrl = url.startsWith('http') ? url : `${basePath}${url}`;
    const downloadFilename = filename || url.split('/').pop() || 'download';

    try {
      const token = getToken();
      const response = await fetch(fullUrl, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = downloadFilename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error('[FileUtils] 下載失敗:', error);
      if (typeof NotificationModule !== 'undefined') {
        NotificationModule.show({
          title: '下載失敗',
          message: error.message,
          icon: 'alert-circle'
        });
      }
      throw error;
    }
  }

  // 公開 API
  return {
    getExtension,
    getFileCategory,
    getFileIcon,
    getFileTypeClass,
    formatFileSize,
    isTextFile,
    isImageFile,
    isVideoFile,
    isAudioFile,
    isPdfFile,
    downloadWithAuth,
    getToken,
    // 匯出常數供進階使用
    EXTENSIONS,
    ICON_MAP,
  };
})();

// 匯出到全域（如果需要）
if (typeof window !== 'undefined') {
  window.FileUtils = FileUtils;
}
