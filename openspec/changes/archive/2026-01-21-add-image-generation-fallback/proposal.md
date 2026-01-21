# Change: 新增圖片生成備用服務

## Why

目前 Line Bot 使用 nanobanana (Google Gemini) 生成圖片，經常遇到 503 "model is overloaded" 錯誤。
這是 Google 伺服器端的問題，即使付費也無法完全解決。需要備用方案確保圖片生成服務的可用性。

## What Changes

- 新增 Hugging Face Inference API 整合，使用 FLUX.1-schnell 模型作為備用
- 修改 `linebot_ai.py`：nanobanana 失敗時自動切換到 Hugging Face
- 新增環境變數 `HUGGINGFACE_API_TOKEN` 設定
- 備用服務生成的圖片會標註「使用備用服務生成」

## Impact

- Affected specs: `line-bot`
- Affected code:
  - `backend/src/ching_tech_os/services/linebot_ai.py`
  - `backend/.env`

## 設定需求

需要 Hugging Face API Token：
1. 到 https://huggingface.co/settings/tokens 註冊/登入
2. 建立 Fine-grained token，勾選 "Make calls to Inference Providers"
3. 將 token 加入 `.env`：`HUGGINGFACE_API_TOKEN=hf_xxxxxxxx`

## 服務比較

| 項目 | Gemini (nanobanana) | FLUX.1-schnell (備用) |
|------|---------------------|----------------------|
| 品質 | 優秀 | 優秀（細節更準確） |
| 速度 | 3-4 秒 | 1-4 步生成 |
| 中文支援 | 較好 | 一般 |
| 穩定性 | 常 503 過載 | 較穩定 |
| 授權 | API 使用 | Apache 2.0 可商用 |
| 價格 | $0.039/張 | 免費（額度內） |
