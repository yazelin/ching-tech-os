## ADDED Requirements

### Requirement: 圖片生成備用服務
Line Bot AI SHALL 在主要圖片生成服務（nanobanana/Gemini）失敗時，自動切換到備用服務（Hugging Face FLUX）。

#### Scenario: nanobanana 503 過載時切換備用
- **WHEN** nanobanana 回傳 "model is overloaded" 錯誤
- **THEN** 系統自動使用 Hugging Face FLUX.1-schnell 重新生成圖片
- **AND** 在回應中標註「使用備用服務生成」

#### Scenario: nanobanana 429 超過配額時切換備用
- **WHEN** nanobanana 回傳 "quota exceeded" 或 "limit" 錯誤
- **THEN** 系統自動使用 Hugging Face FLUX.1-schnell 重新生成圖片
- **AND** 在回應中標註「使用備用服務生成」

#### Scenario: 備用服務也失敗
- **WHEN** Hugging Face API 也回傳錯誤
- **THEN** 系統回傳清楚的錯誤訊息
- **AND** 告知用戶兩個服務都暫時無法使用，請稍後再試

#### Scenario: API key 錯誤不觸發備用
- **WHEN** nanobanana 回傳 "api key" 相關錯誤
- **THEN** 系統不觸發備用服務
- **AND** 回傳錯誤訊息請用戶聯繫管理員

### Requirement: 備用服務環境設定
系統 SHALL 支援透過環境變數設定 Hugging Face API Token。

#### Scenario: 設定 Hugging Face Token
- **WHEN** `.env` 包含 `HUGGINGFACE_API_TOKEN=hf_xxx`
- **THEN** 系統使用該 token 呼叫 Hugging Face Inference API

#### Scenario: 未設定 Token
- **WHEN** `HUGGINGFACE_API_TOKEN` 環境變數未設定
- **THEN** 系統不啟用備用服務
- **AND** nanobanana 失敗時直接回傳錯誤訊息
