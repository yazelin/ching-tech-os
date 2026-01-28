## ADDED Requirements

### Requirement: Gemini Model Fallback
當主要圖片生成服務（gemini-3-pro-image-preview）不可用時，系統 SHALL 自動切換到備用服務。

#### Scenario: Pro 模型超時時自動切換到 Flash
- **WHEN** nanobanana (gemini-3-pro-image-preview) 超時或無回應
- **THEN** 系統自動使用 gemini-2.5-flash-image 生成圖片
- **AND** 回覆訊息包含「使用快速模式」提示

#### Scenario: Flash 模型也失敗時切換到 Hugging Face
- **WHEN** gemini-2.5-flash-image 也失敗
- **THEN** 系統自動使用 Hugging Face FLUX 生成圖片
- **AND** 回覆訊息包含「使用備用服務」提示

#### Scenario: 所有服務都失敗
- **WHEN** 所有圖片生成服務都失敗
- **THEN** 回覆使用者友善的錯誤訊息
- **AND** 建議使用者稍後再試

### Requirement: Fallback 使用者通知
當使用備用服務生成圖片時，系統 SHALL 在回覆中告知使用者。

#### Scenario: 使用 Flash 模式通知
- **WHEN** 圖片由 gemini-2.5-flash-image 生成
- **THEN** 回覆訊息顯示「圖片已生成（使用快速模式）」

#### Scenario: 使用備用服務通知
- **WHEN** 圖片由 Hugging Face 生成
- **THEN** 回覆訊息顯示「圖片已生成（使用備用服務）」
