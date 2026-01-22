# Tasks: 新增 AI 簡報生成功能

## 1. 環境設定
- [x] 1.1 在 `pyproject.toml` 新增 `python-pptx` 依賴（已存在）
- [x] 1.2 在 `.env` 新增 `PEXELS_API_KEY` 環境變數
- [x] 1.3 建立 NAS 輸出目錄（透過 SMB 動態建立）

## 2. 後端服務實作
- [x] 2.1 建立 `services/presentation.py`
  - [x] 2.1.1 實作 `generate_outline()` 方法（Claude CLI 生成大綱）
  - [x] 2.1.2 實作 `create_title_slide()` 方法（標題頁）
  - [x] 2.1.3 實作 `create_content_slide()` 方法（內容頁）
  - [x] 2.1.4 實作 `fetch_pexels_image()` 方法（Pexels 配圖）
  - [x] 2.1.5 實作 `generate_huggingface_image()` 方法（Hugging Face AI 配圖）
  - [x] 2.1.6 實作 `generate_nanobanana_image()` 方法（nanobanana/Gemini AI 配圖）
  - [x] 2.1.7 實作 `fetch_image()` 方法（統一圖片取得介面）
  - [x] 2.1.8 實作 `generate_presentation()` 主流程（支援 outline_json 直接傳入大綱）

## 3. API 端點實作
- [x] 3.1 建立 `api/presentation.py`
- [x] 3.2 實作 `POST /api/presentation/generate` 端點
- [x] 3.3 在 `main.py` 註冊路由
- [x] 3.4 支援 `image_source` 參數（pexels/huggingface/nanobanana）

## 4. MCP 工具整合
- [x] 4.1 在 `mcp_server.py` 新增 `generate_presentation` 工具
- [x] 4.2 工具參數：`topic`、`num_slides`、`style`、`include_images`、`image_source`、`outline_json`
- [x] 4.3 整合 `create_share_link` 產生分享連結（在回應中提示）

## 5. Line Bot 整合優化
- [x] 5.1 移除 nanobanana 重試機制（只呼叫一次）
- [x] 5.2 保留 Hugging Face fallback（nanobanana 失敗時自動切換）

## 6. 測試
- [x] 6.1 測試模組載入（Python import 驗證）
- [ ] 6.2 測試 API 端點（需要啟動服務）
- [ ] 6.3 測試 MCP 工具（需要啟動服務）
- [ ] 6.4 測試 Line Bot 對話生成簡報（需要啟動服務）
