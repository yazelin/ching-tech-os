# ai-assistant-ui Spec Delta

## MODIFIED Requirements

### Requirement: AI Assistant Message Display
AI 助手應用程式 SHALL 在右側主區域顯示對話訊息，並支援 Markdown 格式渲染。

#### Scenario: 顯示對話訊息
- **WHEN** 使用者選擇一個對話
- **THEN** 右側主區域顯示該對話的所有訊息
- **AND** 使用者訊息與 AI 回應有明顯的視覺區分

#### Scenario: AI 回應 Markdown 渲染
- **WHEN** AI 回應包含 Markdown 格式
- **THEN** 系統使用 marked.js 渲染 Markdown 內容
- **AND** 標題、列表、代碼塊、引用、表格等元素正確顯示
- **AND** 套用統一的 Markdown 樣式

#### Scenario: 使用者訊息顯示
- **WHEN** 顯示使用者發送的訊息
- **THEN** 訊息以純文字形式顯示（不渲染 Markdown）
- **AND** 換行符號轉換為 `<br>` 標籤

#### Scenario: 訊息主題適配
- **WHEN** 使用者切換暗色/亮色主題
- **THEN** AI 回應的 Markdown 渲染樣式自動更新
- **AND** 代碼塊、引用等元素的背景與文字顏色正確切換

#### Scenario: 訊息捲動
- **WHEN** 對話訊息超出顯示區域
- **THEN** 訊息區域可捲動瀏覽
- **AND** 新訊息自動捲動至可見範圍
