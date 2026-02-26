# Proposal: Configurable Restricted Mode

## Why

受限模式（restricted mode）目前有多處硬編碼的文字模板（歡迎訊息、綁定提示、頻率超限訊息等），無法在不修改程式碼的情況下客製化。當 CTOS 部署給不同產業（如診所衛教、企業客服）時，每次都需要改程式碼才能調整這些文字，不利於平台化推廣。

## What Changes

將受限模式的所有部署相關文字模板從硬編碼改為可配置，利用現有 `ai_agents.settings` JSONB 欄位儲存，讓不同部署只需透過 AI 管理 UI 修改 `bot-restricted` Agent 設定即可客製化。

### 需要配置化的項目

| 項目 | 目前狀態 | 配置方式 |
|------|---------|---------|
| 歡迎訊息（/start + FollowEvent） | `command_handlers.py` 硬編碼 | `agent.settings.welcome_message` |
| 綁定帳號提示（reject 模式） | `identity_router.py` 硬編碼 | `agent.settings.binding_prompt` |
| 每小時超限訊息 | `rate_limiter.py` 硬編碼 | `agent.settings.rate_limit_hourly_msg` |
| 每日超限訊息 | `rate_limiter.py` 硬編碼 | `agent.settings.rate_limit_daily_msg` |
| 免責聲明（自動附加） | 不存在 | `agent.settings.disclaimer` |
| AI 呼叫失敗訊息 | `identity_router.py` 硬編碼 | `agent.settings.error_message` |

### 不改動的項目（已可配置）

- System Prompt → 已在 `ai_agents` 表，可透過 UI 修改
- 工具白名單 → 已在 `ai_agents.tools`，可透過 UI 修改
- Model → 環境變數 `BOT_RESTRICTED_MODEL`
- 頻率限制數值 → 環境變數 `BOT_RATE_LIMIT_HOURLY` / `BOT_RATE_LIMIT_DAILY`
- 公開資料夾 → 環境變數 `LIBRARY_PUBLIC_FOLDERS`

## Capabilities

- **bot-restricted-settings**: 受限模式 Agent 的 settings 配置化，包含文字模板讀取、變數替換、預設值 fallback、免責聲明自動附加

## Impact

- **改動範圍小**：僅修改 4 個檔案的文字讀取邏輯 + 1 個 migration
- **完全向後相容**：未設定 settings 時行為與現在完全相同
- **不需新 UI**：利用現有 AI 管理介面的 Agent 設定頁面
- **不需新表**：利用現有 `ai_agents.settings` JSONB 欄位
