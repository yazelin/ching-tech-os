# 影像壓縮優化計畫

> **狀態：** 提案（尚未執行）
> **建立日期：** 2025-07
> **目標：** 減少 `frontend/assets/images/` 中大型影像的檔案大小，提升前端載入效能。

---

## 一、影像資產盤點

### 大型影像（優先處理）

| 檔案路徑 | 尺寸 (px) | 色彩模式 | 目前大小 | 問題說明 |
|---|---|---|---|---|
| `frontend/assets/images/logo.png` | 1024×1024 | RGB 8-bit | **1,100,693 bytes (1.1 MB)** | 過大；PNG 未壓縮最佳化，作為 logo 不需要此解析度 |
| `frontend/assets/images/wallpaper.png` | 1344×768 | RGB 8-bit | **743,288 bytes (726 KB)** | 可轉 WebP 大幅縮小；桌布用途可接受有損壓縮 |

### 小型影像（暫不處理）

| 檔案路徑 | 尺寸 (px) | 目前大小 | 備註 |
|---|---|---|---|
| `frontend/assets/images/favicon-64.png` | 64×64 | 3,312 bytes (3.3 KB) | 已夠小 |
| `frontend/assets/images/favicon-32.png` | 32×32 | 1,148 bytes (1.2 KB) | 已夠小 |
| `frontend/assets/images/favicon-16.png` | 16×16 | 409 bytes | 已夠小 |
| `frontend/assets/images/logo.svg` | 向量 | 3,400 bytes | SVG 向量，無需壓縮 |
| `frontend/assets/images/wallpaper-breathing.svg` | 向量 | 5,200 bytes | SVG 向量，無需壓縮 |
| `frontend/assets/images/wallpaper-static.svg` | 向量 | 3,200 bytes | SVG 向量，無需壓縮 |

---

## 二、壓縮建議方案

### 2.1 `logo.png`（1.1 MB → 預估 ~60–80 KB）

| 項目 | 說明 |
|---|---|
| **目前格式** | PNG, 1024×1024, RGB |
| **建議格式** | WebP（有損） + 保留 PNG fallback（無損壓縮） |
| **建議尺寸** | 主要用途縮至 512×512（大多數 UI 場景足夠）；保留 1024 版本供高解析度 |
| **建議品質** | WebP quality 80（視覺無明顯差異） |
| **預估壓縮後大小** | WebP 512×512 ~30–50 KB；WebP 1024×1024 ~60–80 KB |
| **預估節省** | 約 **93–97%** 檔案大小 |

#### 轉換指令

```bash
# 方法 A：使用 cwebp（Google WebP 工具）
# 1024×1024 版本
cwebp -q 80 frontend/assets/images/logo.png -o frontend/assets/images/logo.webp

# 512×512 縮圖版本（需先用 ImageMagick 縮放）
magick frontend/assets/images/logo.png -resize 512x512 /tmp/logo-512.png
cwebp -q 80 /tmp/logo-512.png -o frontend/assets/images/logo-512.webp

# 方法 B：使用 ImageMagick 一步完成
magick frontend/assets/images/logo.png -resize 512x512 -quality 80 frontend/assets/images/logo.webp

# 方法 C：同時產生最佳化 PNG fallback（無損壓縮）
magick frontend/assets/images/logo.png -resize 512x512 -strip -define png:compression-level=9 frontend/assets/images/logo-optimized.png
```

### 2.2 `wallpaper.png`（726 KB → 預估 ~50–100 KB）

| 項目 | 說明 |
|---|---|
| **目前格式** | PNG, 1344×768, RGB |
| **建議格式** | WebP（有損）；桌布屬裝飾性質，適合有損壓縮 |
| **建議尺寸** | 維持 1344×768（桌布需全尺寸）；另產 672×384 低解析版供行動裝置 |
| **建議品質** | WebP quality 75（桌布容許更高壓縮率） |
| **預估壓縮後大小** | WebP 1344×768 ~50–100 KB；低解析版 ~20–40 KB |
| **預估節省** | 約 **86–93%** 檔案大小 |

#### 轉換指令

```bash
# 方法 A：使用 cwebp
cwebp -q 75 frontend/assets/images/wallpaper.png -o frontend/assets/images/wallpaper.webp

# 行動裝置低解析版
magick frontend/assets/images/wallpaper.png -resize 672x384 /tmp/wallpaper-mobile.png
cwebp -q 75 /tmp/wallpaper-mobile.png -o frontend/assets/images/wallpaper-mobile.webp

# 方法 B：使用 ImageMagick 一步完成
magick frontend/assets/images/wallpaper.png -quality 75 frontend/assets/images/wallpaper.webp
```

---

## 三、整體影響預估

| 檔案 | 壓縮前 | 壓縮後（預估） | 節省 |
|---|---|---|---|
| `logo.png` → `logo.webp` (512×512) | 1.1 MB | ~40 KB | ~1.06 MB |
| `wallpaper.png` → `wallpaper.webp` | 726 KB | ~75 KB | ~651 KB |
| **合計** | **1.8 MB** | **~115 KB** | **~1.7 MB (約 94%)** |

---

## 四、批次轉換腳本範例

> ⚠️ **此腳本僅供參考，尚未執行。** 執行前請確認已安裝 `cwebp` 和 `imagemagick`。

```bash
#!/usr/bin/env bash
# =============================================================
# 影像壓縮批次腳本 — 僅供計畫參考，請勿在未審閱前直接執行
# =============================================================
set -euo pipefail

IMAGE_DIR="frontend/assets/images"
BACKUP_DIR="frontend/assets/images/.backup-originals"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# --- 前置檢查 ---
command -v cwebp >/dev/null 2>&1 || { echo "❌ 需要安裝 cwebp: sudo apt install webp"; exit 1; }
command -v magick >/dev/null 2>&1 || { echo "❌ 需要安裝 ImageMagick: sudo apt install imagemagick"; exit 1; }

# --- 建立備份 ---
echo "📦 建立原始檔案備份..."
mkdir -p "${BACKUP_DIR}/${TIMESTAMP}"
cp "${IMAGE_DIR}/logo.png" "${BACKUP_DIR}/${TIMESTAMP}/"
cp "${IMAGE_DIR}/wallpaper.png" "${BACKUP_DIR}/${TIMESTAMP}/"
echo "✅ 備份完成：${BACKUP_DIR}/${TIMESTAMP}/"

# --- 轉換 logo.png ---
echo "🔄 轉換 logo.png..."
# 產生 512×512 WebP
magick "${IMAGE_DIR}/logo.png" -resize 512x512 /tmp/logo-512.png
cwebp -q 80 /tmp/logo-512.png -o "${IMAGE_DIR}/logo-512.webp"
# 產生 1024×1024 WebP
cwebp -q 80 "${IMAGE_DIR}/logo.png" -o "${IMAGE_DIR}/logo.webp"
# 產生最佳化 PNG fallback
magick "${IMAGE_DIR}/logo.png" -resize 512x512 -strip -define png:compression-level=9 "${IMAGE_DIR}/logo-optimized.png"
echo "✅ logo 轉換完成"

# --- 轉換 wallpaper.png ---
echo "🔄 轉換 wallpaper.png..."
cwebp -q 75 "${IMAGE_DIR}/wallpaper.png" -o "${IMAGE_DIR}/wallpaper.webp"
# 行動裝置版本
magick "${IMAGE_DIR}/wallpaper.png" -resize 672x384 /tmp/wallpaper-mobile.png
cwebp -q 75 /tmp/wallpaper-mobile.png -o "${IMAGE_DIR}/wallpaper-mobile.webp"
echo "✅ wallpaper 轉換完成"

# --- 輸出結果 ---
echo ""
echo "📊 轉換結果："
echo "================================================"
for f in "${IMAGE_DIR}"/*.webp "${IMAGE_DIR}/logo-optimized.png"; do
  [ -f "$f" ] && echo "  $(basename "$f"): $(du -h "$f" | cut -f1)"
done
echo "================================================"
echo ""
echo "⚠️  請手動驗證影像品質後，再更新前端程式碼中的引用路徑。"
echo "📝 回滾指令：cp ${BACKUP_DIR}/${TIMESTAMP}/* ${IMAGE_DIR}/"
```

---

## 五、前端程式碼引用更新

轉換完成後，需更新以下檔案中的影像引用：

| 檔案 | 目前引用 | 更新為 |
|---|---|---|
| `frontend/public.html` | `logo.png` / `wallpaper.png` | 使用 `<picture>` 標籤提供 WebP + PNG fallback |

### `<picture>` 標籤範例

```html
<!-- Logo -->
<picture>
  <source srcset="/assets/images/logo-512.webp" type="image/webp">
  <img src="/assets/images/logo.png" alt="Ching Tech OS Logo" width="512" height="512">
</picture>

<!-- Wallpaper -->
<picture>
  <source srcset="/assets/images/wallpaper.webp" type="image/webp">
  <img src="/assets/images/wallpaper.png" alt="Wallpaper" width="1344" height="768">
</picture>
```

---

## 六、回滾方法

若壓縮後發現品質問題，可透過以下方式回滾：

### 方法 A：從備份還原

```bash
# 批次腳本會自動建立備份到 .backup-originals/ 目錄
cp frontend/assets/images/.backup-originals/<TIMESTAMP>/logo.png frontend/assets/images/
cp frontend/assets/images/.backup-originals/<TIMESTAMP>/wallpaper.png frontend/assets/images/
```

### 方法 B：從 Git 還原

```bash
# 還原單一檔案
git checkout HEAD~1 -- frontend/assets/images/logo.png
git checkout HEAD~1 -- frontend/assets/images/wallpaper.png

# 或還原整個影像目錄
git checkout HEAD~1 -- frontend/assets/images/
```

### 方法 C：移除 WebP 並回到純 PNG

```bash
# 刪除所有 WebP 檔案
rm frontend/assets/images/*.webp
rm frontend/assets/images/logo-optimized.png

# 將前端程式碼中的 <picture> 標籤改回 <img>
```

---

## 七、工具安裝指南

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y webp imagemagick

# macOS (Homebrew)
brew install webp imagemagick

# 驗證安裝
cwebp -version
magick -version
```

---

## 八、後續建議

1. **CI/CD 整合**：在建置流程中加入影像大小檢查，防止未來新增過大影像。
2. **自動化格式偵測**：可使用 `sharp` (Node.js) 或 `Pillow` (Python) 在建置時自動產生 WebP。
3. **CDN 整合**：若部署至 CDN，可啟用自動影像轉換（如 Cloudflare Image Resizing）。
4. **漸進式載入**：考慮加入模糊佔位圖（blur placeholder）提升感知效能。
