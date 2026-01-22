# Tasks: 統一簡報生成功能使用 Marp

## 1. API 修改

- [x] 1.1 更新 `api/presentation.py` 的 import，改用 `generate_html_presentation`
- [x] 1.2 更新 `PresentationRequest` Model：
  - `style` 改名為 `theme`
  - 新增 `output_format` 參數（html/pdf）
  - 移除 `design_json`、`designer_request` 參數
- [x] 1.3 更新 `PresentationResponse` Model：新增 `format` 欄位
- [x] 1.4 更新 API 函數呼叫邏輯

## 2. 測試驗證

- [x] 2.1 測試 REST API `/api/presentation/generate` 是否正常運作
- [x] 2.2 確認輸出格式為 HTML 或 PDF

## 3. 清理

- [x] 3.1 移除 `presentation.py` 中的 PowerPoint 相關程式碼（`generate_presentation` 函數）
- [x] 3.2 移除未使用的 python-pptx import
