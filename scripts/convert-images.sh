#!/usr/bin/env bash
# =============================================================
# 影像壓縮批次腳本
# 將 frontend/assets/images/ 中的大型 PNG 轉換為 WebP 格式
# 參考：docs/optimizations/images-compression.md
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE_DIR="${ROOT_DIR}/frontend/assets/images"
BACKUP_DIR="${IMAGE_DIR}/.backup-originals"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# --- 前置檢查 ---
command -v cwebp >/dev/null 2>&1 || { echo "❌ 需要安裝 cwebp: sudo apt install webp"; exit 1; }
command -v magick >/dev/null 2>&1 || command -v convert >/dev/null 2>&1 || { echo "❌ 需要安裝 ImageMagick: sudo apt install imagemagick"; exit 1; }

# ImageMagick 指令相容性（magick 或 convert）
MAGICK_CMD="magick"
command -v magick >/dev/null 2>&1 || MAGICK_CMD="convert"

echo "=========================================="
echo "  影像壓縮腳本 — ${TIMESTAMP}"
echo "=========================================="
echo ""

# --- 顯示原始檔案大小 ---
echo "📊 原始檔案大小："
for f in "${IMAGE_DIR}/logo.png" "${IMAGE_DIR}/wallpaper.png"; do
  if [ -f "$f" ]; then
    echo "  $(basename "$f"): $(du -h "$f" | cut -f1)"
  fi
done
echo ""

# --- Dry-run 模式 ---
if [ "${1:-}" = "--dry-run" ]; then
  echo "🔍 Dry-run 模式：僅顯示將執行的操作"
  echo ""
  echo "將執行以下轉換："
  echo "  1. logo.png → logo.webp (1024×1024, quality 80)"
  echo "  2. logo.png → logo-512.webp (512×512, quality 80)"
  echo "  3. logo.png → logo-optimized.png (512×512, 無損最佳化)"
  echo "  4. wallpaper.png → wallpaper.webp (原尺寸, quality 75)"
  echo "  5. wallpaper.png → wallpaper-mobile.webp (672×384, quality 75)"
  echo ""
  echo "備份目錄：${BACKUP_DIR}/${TIMESTAMP}/"
  exit 0
fi

# --- 建立備份 ---
echo "📦 建立原始檔案備份..."
mkdir -p "${BACKUP_DIR}/${TIMESTAMP}"
cp "${IMAGE_DIR}/logo.png" "${BACKUP_DIR}/${TIMESTAMP}/"
cp "${IMAGE_DIR}/wallpaper.png" "${BACKUP_DIR}/${TIMESTAMP}/"
echo "  備份完成：${BACKUP_DIR}/${TIMESTAMP}/"
echo ""

# --- 轉換 logo.png ---
echo "🔄 轉換 logo.png..."
# 512×512 WebP
${MAGICK_CMD} "${IMAGE_DIR}/logo.png" -resize 512x512 /tmp/logo-512-${TIMESTAMP}.png
cwebp -q 80 /tmp/logo-512-${TIMESTAMP}.png -o "${IMAGE_DIR}/logo-512.webp" 2>/dev/null
echo "  ✔ logo-512.webp (512×512)"

# 1024×1024 WebP
cwebp -q 80 "${IMAGE_DIR}/logo.png" -o "${IMAGE_DIR}/logo.webp" 2>/dev/null
echo "  ✔ logo.webp (1024×1024)"

# 最佳化 PNG fallback
${MAGICK_CMD} "${IMAGE_DIR}/logo.png" -resize 512x512 -strip -define png:compression-level=9 "${IMAGE_DIR}/logo-optimized.png"
echo "  ✔ logo-optimized.png (512×512, 無損)"

# 清理暫存
rm -f /tmp/logo-512-${TIMESTAMP}.png

# --- 轉換 wallpaper.png ---
echo "🔄 轉換 wallpaper.png..."
cwebp -q 75 "${IMAGE_DIR}/wallpaper.png" -o "${IMAGE_DIR}/wallpaper.webp" 2>/dev/null
echo "  ✔ wallpaper.webp (原尺寸)"

# 行動裝置版本
${MAGICK_CMD} "${IMAGE_DIR}/wallpaper.png" -resize 672x384 /tmp/wallpaper-mobile-${TIMESTAMP}.png
cwebp -q 75 /tmp/wallpaper-mobile-${TIMESTAMP}.png -o "${IMAGE_DIR}/wallpaper-mobile.webp" 2>/dev/null
echo "  ✔ wallpaper-mobile.webp (672×384)"

# 清理暫存
rm -f /tmp/wallpaper-mobile-${TIMESTAMP}.png

# --- 輸出結果 ---
echo ""
echo "📊 轉換結果："
echo "=========================================="
for f in "${IMAGE_DIR}"/*.webp "${IMAGE_DIR}/logo-optimized.png"; do
  [ -f "$f" ] && echo "  $(basename "$f"): $(du -h "$f" | cut -f1)"
done
echo "=========================================="
echo ""
echo "⚠️  請手動驗證影像品質後，再更新前端程式碼中的引用路徑。"
echo "📝 回滾指令：cp ${BACKUP_DIR}/${TIMESTAMP}/* ${IMAGE_DIR}/"
echo ""
echo "💡 下一步：更新 HTML 中的 <img> 為 <picture> 標籤"
echo "   參考：docs/optimizations/images-compression.md"
