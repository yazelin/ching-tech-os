# project-management Spec Delta

## ADDED Requirements

### Requirement: 會議內容 Markdown 渲染
專案管理模組 SHALL 在會議詳情中正確渲染 Markdown 格式的會議內容。

#### Scenario: 會議內容 Markdown 渲染
- **WHEN** 使用者查看會議詳情
- **THEN** 會議內容使用 marked.js 渲染 Markdown
- **AND** 套用完整的 Markdown 樣式

#### Scenario: 會議內容樣式元素
- **GIVEN** 會議內容包含 Markdown 格式
- **THEN** 以下元素正確顯示：
  - 標題（h1-h6）
  - 列表（有序、無序）
  - 代碼塊（行內代碼、多行代碼）
  - 引用
  - 表格
  - 連結
  - 水平線

#### Scenario: 會議內容主題適配
- **WHEN** 使用者切換暗色/亮色主題
- **THEN** 會議內容的 Markdown 渲染樣式自動更新
- **AND** 代碼塊、引用、表格等元素的背景與文字顏色正確切換

#### Scenario: 無會議內容
- **GIVEN** 會議沒有內容
- **WHEN** 使用者查看會議詳情
- **THEN** 顯示「無會議內容」提示文字
