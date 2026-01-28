## ADDED Requirements

### Requirement: AI 圖片生成模型資訊顯示
AI 助理 SHALL 根據 nanobanana MCP 的回應，在圖片生成完成後告知用戶實際使用的模型。

#### Scenario: 使用 Pro 模型成功
- **WHEN** nanobanana 回應 `modelUsed` 為 `gemini-3-pro-image-preview`
- **AND** `usedFallback` 為 `false`
- **THEN** AI 回覆不特別標註模型（預設高品質）

#### Scenario: 使用 Flash 模型（fallback）
- **WHEN** nanobanana 回應 `modelUsed` 為 `gemini-2.5-flash-image`
- **AND** `usedFallback` 為 `true`
- **THEN** AI 回覆標註「（快速模式）」或類似說明
- **AND** 讓用戶了解圖片可能與預期有差異

#### Scenario: 使用 FLUX 備用服務
- **WHEN** nanobanana MCP 完全失敗（timeout 或錯誤）
- **AND** 系統 fallback 到 Hugging Face FLUX
- **THEN** AI 回覆標註「（備用服務）」
- **AND** 說明可能需要較長時間或品質有所不同

---

### Requirement: 簡化圖片生成 Fallback 機制
圖片生成服務 SHALL 採用兩層 fallback 架構。

#### Scenario: 第一層 - nanobanana MCP
- **WHEN** 用戶請求生成圖片
- **THEN** 系統優先使用 nanobanana MCP
- **AND** nanobanana 內部自動處理 Gemini Pro → Flash 的 fallback

#### Scenario: 第二層 - FLUX 備用
- **WHEN** nanobanana MCP 完全失敗（timeout、API 錯誤、無回應）
- **THEN** 系統 fallback 到 Hugging Face FLUX
- **AND** 記錄 fallback 原因

#### Scenario: 移除重複的 Gemini Flash 層
- **WHEN** 系統處理圖片生成 fallback
- **THEN** 不再直接呼叫 Gemini Flash API
- **AND** Gemini 相關的 fallback 由 nanobanana MCP 內部處理
