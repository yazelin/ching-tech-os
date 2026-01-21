# Tasks

## 1. 環境設定
- [x] 1.1 在 `.env` 新增 `HUGGINGFACE_API_TOKEN` 變數
- [x] 1.2 在 `pyproject.toml` 新增 `huggingface_hub` 依賴

## 2. Hugging Face 整合
- [x] 2.1 建立 `services/huggingface_image.py` 模組
- [x] 2.2 實作 `generate_image_with_flux()` 函式
- [x] 2.3 實作錯誤處理與重試邏輯
- [x] 2.4 實作圖片儲存到 NAS ai-images 目錄

## 3. 備用邏輯整合
- [x] 3.1 新增 `extract_nanobanana_prompt()` 函式提取原始 prompt
- [x] 3.2 修改 `linebot_ai.py` 的 `auto_prepare_generated_images()`
- [x] 3.3 在 nanobanana 失敗時呼叫 Hugging Face 備用服務
- [x] 3.4 標註備用服務生成的圖片（加入提示文字）

## 4. 測試
- [x] 4.1 測試 Hugging Face API 連線 ✓
- [x] 4.2 測試圖片生成並儲存到 NAS ✓
- [ ] 4.3 測試 Line Bot 完整流程（需部署後測試）

## 5. Timeout 優化
- [x] 5.1 將 timeout 從 300 秒改為 120 秒 ✓
- [x] 5.2 新增 timeout 檢測函式 (`check_nanobanana_timeout`) ✓
- [x] 5.3 在 timeout 時觸發備用服務 ✓
