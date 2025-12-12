# text-viewer Specification

## Purpose
TBD - created by archiving change add-markdown-rendering-unified. Update Purpose after archive.
## Requirements
### Requirement: TextViewer Display Mode
文字讀取器 SHALL 支援多種顯示模式，讓使用者能以最適合的方式檢視檔案內容。

#### Scenario: 顯示模式切換介面
- **WHEN** TextViewer 視窗開啟
- **THEN** 工具列顯示顯示模式切換按鈕
- **AND** 按鈕包含：原始文字、Markdown、JSON、YAML、XML

#### Scenario: 自動選擇預設模式
- **GIVEN** 開啟 `.md` 或 `.markdown` 檔案
- **THEN** 預設使用 Markdown 預覽模式
- **GIVEN** 開啟 `.json` 檔案
- **THEN** 預設使用 JSON 格式化模式
- **GIVEN** 開啟 `.yaml` 或 `.yml` 檔案
- **THEN** 預設使用 YAML 格式化模式
- **GIVEN** 開啟 `.xml`、`.html`、`.svg` 檔案
- **THEN** 預設使用 XML 格式化模式
- **GIVEN** 開啟其他文字檔案
- **THEN** 預設使用原始文字模式

#### Scenario: 手動切換顯示模式
- **WHEN** 使用者點擊顯示模式按鈕
- **THEN** 內容以所選模式重新渲染
- **AND** 當前模式按鈕顯示選中狀態

---

### Requirement: TextViewer Markdown Preview
文字讀取器 SHALL 支援 Markdown 預覽模式。

#### Scenario: Markdown 渲染
- **WHEN** 使用者選擇 Markdown 模式
- **THEN** 系統使用 marked.js 渲染檔案內容
- **AND** 套用統一的 Markdown 樣式
- **AND** 標題、列表、代碼塊、引用、表格等元素正確顯示

#### Scenario: Markdown 主題適配
- **WHEN** 使用者切換暗色/亮色主題
- **THEN** Markdown 渲染樣式自動更新
- **AND** 代碼塊、引用等元素的背景與文字顏色正確切換

---

### Requirement: TextViewer JSON Formatting
文字讀取器 SHALL 支援 JSON 格式化顯示。

#### Scenario: JSON 格式化成功
- **GIVEN** 檔案內容為有效的 JSON
- **WHEN** 使用者選擇 JSON 模式
- **THEN** 系統解析並美化 JSON 內容
- **AND** 顯示適當的縮排（2 空格）
- **AND** 套用語法色彩（字串、數字、布林、null、鍵名）

#### Scenario: JSON 格式化失敗
- **GIVEN** 檔案內容非有效的 JSON
- **WHEN** 使用者選擇 JSON 模式
- **THEN** 系統顯示原始文字內容
- **AND** 狀態列顯示錯誤訊息「無效的 JSON 格式」

#### Scenario: JSON 主題適配
- **WHEN** 使用者切換暗色/亮色主題
- **THEN** JSON 語法色彩自動更新
- **AND** 字串、數字、布林等元素顏色正確切換

---

### Requirement: TextViewer YAML Formatting
文字讀取器 SHALL 支援 YAML 格式化顯示。

#### Scenario: YAML 格式化
- **WHEN** 使用者選擇 YAML 模式
- **THEN** 系統對 YAML 內容套用語法色彩
- **AND** 鍵名、字串、數字、布林、null、註解使用不同顏色
- **AND** 保留原始縮排結構

#### Scenario: YAML 主題適配
- **WHEN** 使用者切換暗色/亮色主題
- **THEN** YAML 語法色彩自動更新

---

### Requirement: TextViewer XML Formatting
文字讀取器 SHALL 支援 XML 格式化顯示。

#### Scenario: XML 格式化成功
- **GIVEN** 檔案內容為有效的 XML
- **WHEN** 使用者選擇 XML 模式
- **THEN** 系統解析並美化 XML 內容
- **AND** 顯示適當的縮排
- **AND** 套用語法色彩（標籤、屬性、屬性值、文字內容）

#### Scenario: XML 格式化失敗
- **GIVEN** 檔案內容非有效的 XML
- **WHEN** 使用者選擇 XML 模式
- **THEN** 系統顯示原始文字內容
- **AND** 狀態列顯示錯誤訊息「無效的 XML 格式」

#### Scenario: XML 主題適配
- **WHEN** 使用者切換暗色/亮色主題
- **THEN** XML 語法色彩自動更新

---

### Requirement: TextViewer Raw Mode
文字讀取器 SHALL 保留原始文字顯示模式。

#### Scenario: 原始文字顯示
- **WHEN** 使用者選擇原始文字模式
- **THEN** 系統以 `<pre>` 標籤顯示未經處理的檔案內容
- **AND** 保留所有空白字元與換行

#### Scenario: 原始文字主題適配
- **WHEN** 使用者切換暗色/亮色主題
- **THEN** 原始文字區域背景與文字顏色正確切換

