# Tasks: 新增簡報設計師 AI Agent

## 1. 設計 design_json 規格
- [ ] 1.1 定義 colors 配色結構（背景、標題、強調、內文、項目符號）
- [ ] 1.2 定義 typography 字型結構（字型名稱、大小、粗細）
- [ ] 1.3 定義 layout 版面結構（標題位置、欄數、圖片位置）
- [ ] 1.4 定義 decorations 裝飾結構（底線、裝飾條、頁碼）
- [ ] 1.5 撰寫 design_json JSON Schema 文件

## 2. 設計簡報設計師 Prompt
- [ ] 2.1 研究專業簡報設計原則（配色理論、版面設計、視覺層次）
- [ ] 2.2 撰寫 presentation_designer prompt（輸入：內容、對象、場景 → 輸出：design_json）
- [ ] 2.3 定義設計師考量因素（內容類型、對象、場景、品牌調性）
- [ ] 2.4 測試並優化 prompt 輸出品質

## 3. 建立資料庫記錄
- [ ] 3.1 建立 Alembic migration：新增 presentation_designer prompt
- [ ] 3.2 建立 Alembic migration：新增簡報設計師 ai_agent
- [ ] 3.3 執行 migration 並驗證

## 4. 擴展 python-pptx 製作能力
- [ ] 4.1 支援 design_json 配色參數（包含漸層背景）
- [ ] 4.2 支援字型設定（字型名稱需考慮跨平台相容性）
- [ ] 4.3 實作標題底線裝飾
- [ ] 4.4 實作側邊裝飾條
- [ ] 4.5 實作頁碼顯示
- [ ] 4.6 支援多種版面配置（標題位置、圖片位置變化）

## 5. 整合 MCP 工具
- [ ] 5.1 新增 `design_json` 參數到 `generate_presentation` MCP 工具
- [ ] 5.2 實作 design_json 解析與套用邏輯
- [ ] 5.3 更新 MCP 工具 docstring 說明
- [ ] 5.4 保持向下相容（無 design_json 時使用預設風格）

## 6. 整合 Line Bot AI 流程
- [ ] 6.1 更新 Line Bot prompt，讓 AI 知道可以呼叫設計師
- [ ] 6.2 測試完整流程：用戶請求 → 查詢知識庫 → 呼叫設計師 → 生成簡報
- [ ] 6.3 測試不同場景的設計輸出品質

## 7. 測試與文件
- [ ] 7.1 測試各種內容類型的設計輸出
- [ ] 7.2 測試各種對象/場景的風格選擇
- [ ] 7.3 更新 docs/mcp-server.md 文件
- [ ] 7.4 Archive Phase 1 change（add-presentation-generation）
