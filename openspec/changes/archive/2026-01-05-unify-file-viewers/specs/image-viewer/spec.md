# image-viewer Specification

## Purpose
圖片檢視器模組，提供圖片瀏覽、縮放、平移等功能。

## ADDED Requirements

### Requirement: 圖片檢視器視窗
系統 SHALL 提供獨立的圖片檢視器模組。

#### Scenario: 開啟圖片檢視器
- **WHEN** 呼叫 `ImageViewerModule.open(filePath, filename)`
- **THEN** 開啟圖片檢視器視窗
- **AND** 載入並顯示指定圖片
- **AND** 視窗標題顯示檔案名稱

#### Scenario: 關閉圖片檢視器
- **WHEN** 呼叫 `ImageViewerModule.close()` 或點擊視窗關閉按鈕
- **THEN** 關閉圖片檢視器視窗

---

### Requirement: 圖片縮放功能
圖片檢視器 SHALL 提供縮放功能讓使用者檢視圖片細節。

#### Scenario: 放大圖片
- **GIVEN** 圖片檢視器已開啟
- **WHEN** 點擊放大按鈕或使用滾輪向上
- **THEN** 圖片放大顯示
- **AND** 縮放比例顯示在工具列

#### Scenario: 縮小圖片
- **GIVEN** 圖片檢視器已開啟
- **WHEN** 點擊縮小按鈕或使用滾輪向下
- **THEN** 圖片縮小顯示
- **AND** 縮放比例顯示在工具列

#### Scenario: 縮放範圍限制
- **GIVEN** 圖片檢視器已開啟
- **THEN** 縮放範圍限制在 10% 至 500% 之間

#### Scenario: 適合視窗大小
- **GIVEN** 圖片檢視器已開啟
- **WHEN** 點擊「適合視窗」按鈕
- **THEN** 圖片自動縮放至適合視窗大小
- **AND** 保持圖片比例

#### Scenario: 重設為原始大小
- **GIVEN** 圖片已被縮放
- **WHEN** 點擊「100%」按鈕
- **THEN** 圖片恢復原始大小

---

### Requirement: 圖片平移功能
圖片檢視器 SHALL 支援圖片平移，讓使用者檢視放大後的圖片各區域。

#### Scenario: 拖曳平移
- **GIVEN** 圖片已放大超過視窗大小
- **WHEN** 使用者按住滑鼠並拖曳
- **THEN** 圖片隨滑鼠移動平移
- **AND** 可檢視圖片的任意區域

---

### Requirement: 圖片資訊顯示
圖片檢視器 SHALL 在狀態列顯示圖片資訊。

#### Scenario: 顯示圖片資訊
- **GIVEN** 圖片檢視器已開啟並載入圖片
- **THEN** 狀態列顯示檔案名稱
- **AND** 狀態列顯示圖片尺寸（寬 x 高）
- **AND** 狀態列顯示目前縮放比例
