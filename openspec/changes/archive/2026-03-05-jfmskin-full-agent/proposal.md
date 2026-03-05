## Why

杰膚美目前只有衛教受限模式 Agent（`jfmskin-edu`），已綁定帳號的診所人員無法透過 Bot 使用完整功能。需要建立 `jfmskin-full` Agent 並在 DB 中註冊，讓已綁定用戶可以查詢 HIS 資料（預約、病患、處方）和使用知識庫等完整功能。

## What Changes

- 在 `ensure_default_linebot_agents()` 中新增 jfmskin-full Agent 的 seed 邏輯（從 `extends/his/clients/jfmskin/agents/jfmskin-full.md` 讀取 prompt）
- 建立通用的 extends Agent seed 機制：掃描 `extends/*/clients/*/agents/*.md`，自動建立或更新 Agent
- 確保 jfmskin-full Agent 在 DB 中正確建立（model、tools、prompt）

## Capabilities

### New Capabilities
- `extends-agent-seed`: 從 extends/ 子模組的 clients/ 目錄自動 seed Agent 到資料庫的機制

### Modified Capabilities
（無）

## Impact

- **後端**：`services/linebot_agents.py`（新增 extends agent seed 邏輯）
- **資料庫**：`ai_agents` + `ai_prompts` 表新增記錄（jfmskin-full）
- **現有功能**：不影響，jfmskin-edu 和其他 Agent 不受影響
