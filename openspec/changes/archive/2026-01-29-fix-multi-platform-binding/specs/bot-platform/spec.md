# bot-platform spec delta

## MODIFIED Requirements

### Requirement: 多平台獨立綁定
系統 MUST 允許同一 CTOS 帳號同時綁定多個平台（Line、Telegram），各平台綁定獨立運作。

#### Scenario: 已綁定 Line 後綁定 Telegram
- Given: CTOS 用戶已綁定 Line
- When: 用戶產生 Telegram 綁定驗證碼並在 Telegram Bot 發送
- Then: Telegram 綁定成功，Line 綁定不受影響

#### Scenario: 已綁定 Telegram 後綁定 Line
- Given: CTOS 用戶已綁定 Telegram
- When: 用戶產生 Line 綁定驗證碼並在 Line Bot 發送
- Then: Line 綁定成功，Telegram 綁定不受影響

### Requirement: 平台獨立解除綁定
解除綁定 API MUST 接受平台類型參數，只解除指定平台的綁定。

#### Scenario: 解除 Line 綁定不影響 Telegram
- Given: CTOS 用戶同時綁定 Line 和 Telegram
- When: 用戶解除 Line 綁定
- Then: Line 綁定解除，Telegram 綁定不受影響

#### Scenario: 解除 Telegram 綁定不影響 Line
- Given: CTOS 用戶同時綁定 Line 和 Telegram
- When: 用戶解除 Telegram 綁定
- Then: Telegram 綁定解除，Line 綁定不受影響
