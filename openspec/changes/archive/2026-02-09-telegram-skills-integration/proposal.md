## Why

Telegram bot 和 Line bot 的工具白名單（nanobanana、printer、erpnext 等）都是在 handler 裡硬編碼的，與已建好的 Skills 架構（`skills/` 目錄下 7 個 skill YAML）完全脫節。目前 SkillManager 只用於生成 prompt 文字，工具列表仍靠複製貼上維護，新增或修改工具時必須同時改多個檔案，容易遺漏。

## What Changes

- 在 `bot/agents.py` 新增 `get_tools_for_user()` 函式，從 SkillManager 動態產生工具白名單（含 fallback）
- 重構 Telegram handler (`bot_telegram/handler.py`) 的工具列表組裝，移除硬編碼，改用 `get_tools_for_user()`
- 同步重構 Line bot handler (`linebot_ai.py`) 的工具列表組裝，與 Telegram 保持一致
- Skills YAML 補齊缺少的工具定義（對齊目前硬編碼的完整工具列表）

## Capabilities

### New Capabilities

_無新 capability — 此變更為內部重構。_

### Modified Capabilities

- `bot-platform`: 工具白名單從硬編碼改為由 SkillManager 動態產生，新增 `get_tools_for_user()` 共用函式
- `mcp-tools`: Skills YAML 中的 tools 列表補齊，確保與目前硬編碼的工具清單一致

## Impact

- **程式碼**：`bot/agents.py`、`bot_telegram/handler.py`、`linebot_ai.py`、多個 `skills/*/skill.yaml`
- **行為**：對外行為不變，工具白名單內容維持相同（只是來源從硬編碼變為 YAML 定義）
- **風險**：若 SkillManager 載入失敗，需有 fallback 機制確保不中斷服務
