# Tasks: Gemini 模型自動 Fallback

## 1. 調整超時設定
- [ ] 1.1 將 `linebot_ai.py` 中的 nanobanana 超時從 480 秒降至 240 秒
- [ ] 1.2 設定 Gemini Flash 超時為 30 秒
- [ ] 1.3 設定 Hugging Face 超時為 30 秒

## 2. 建立 Gemini Flash 直接呼叫功能
- [ ] 2.1 建立 `image_fallback.py` 模組
- [ ] 2.2 實作 `generate_image_with_gemini_flash()` 函數
- [ ] 2.3 處理 Gemini API 回應（base64 圖片解碼、儲存）

## 3. 整合 Fallback 機制
- [ ] 3.1 在 `linebot_ai.py` 整合三層 fallback 邏輯
- [ ] 3.2 重構 `huggingface_image.py`，移除 fallback 入口邏輯
- [ ] 3.3 確保 fallback 順序：Pro (240s) → Flash (30s) → Hugging Face (30s)

## 4. 使用者通知
- [ ] 4.1 定義各服務的通知訊息
- [ ] 4.2 在 fallback 觸發時回傳對應訊息給 Line Bot

## 5. 測試與驗證
- [ ] 5.1 測試 Gemini Flash 直接呼叫
- [ ] 5.2 測試 fallback 觸發流程（模擬 Pro 超時）
- [ ] 5.3 測試使用者通知訊息
- [ ] 5.4 驗證總等待時間不超過 300 秒
