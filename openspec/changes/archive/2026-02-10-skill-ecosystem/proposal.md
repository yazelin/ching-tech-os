# Proposal: Skill 生態系統完善

## Why

目前 CTOS 的 Skill 管理存在四個核心問題：

1. **ClawHub 整合用 CLI 子程序**：text parsing 脆弱、搜尋結果缺 metadata、預覽要二次請求
2. **沒有 ENV 管理**：安裝需要 API Key 的 skill 後無法設定環境變數，等於裝了也不能用
3. **權限預設不安全**：`requires_app` 留空 = 所有人可用，外部 skill 不應該預設全開
4. **Printer 硬編碼**：printer-mcp 是硬編碼的 MCP server，應該 skill 化以統一管理

參考：亞澤在 `telegram-copilot-bot` 已實作了更好的版本（REST API + skill-env.json + _meta.json）。

## What Changes

### Phase 1: ClawHub REST API 替換
- 新增 `ClawHubClient` class，用 `httpx.AsyncClient` 直接打 ClawHub REST API
- 端點：`GET /search`, `GET /skills/{slug}`, `GET /skills/{slug}/versions`, `GET /download`
- 搜尋結果一次回傳：slug, name, description, author, latest_version, tags
- 安裝改用 ZIP 下載 + 解壓（含 zip slip 防護、大小限制）
- 安裝後寫 `_meta.json`（slug, version, source, installed_at, checksum）
- 移除 `clawhub` CLI 依賴（`_run_clawhub` helper 移除）
- 前端搜尋結果卡片直接顯示 author + version，不需額外 inspect

### Phase 2: Skill ENV 管理
- 新增 `skill_env` DB table（scope + key + encrypted_value）
- Fernet 加密（`cryptography`），金鑰從 `CTOS_ENV_SECRET` 環境變數讀取
- 兩層 scope：`_global`（全域共用）+ per-skill（覆蓋 global）
- **Write-only pattern**：API 只接受寫入，讀取時回傳 mask（`GEMI****KEY`）
- SKILL.md `metadata.openclaw.requires.env` 宣告需要的 ENV，自動生成設定表單
- Script Runner 的 ENV 注入改 **allowlist 模式**：只注入 skill 宣告的 ENV keys
- 前端：skill 詳情頁新增「環境變數」section，必填項紅色星號，密碼類自動遮罩

### Phase 3: 權限模型改善
- 外部 skill 安裝後預設 `requires_app: "admin"`（全關）
- 內建 skill（無 `_meta.json`）維持現有設定
- 新增信任等級：`builtin`（內建）/ `private`（自己發布）/ `community`（第三方）
- 安裝完成後引導設定權限：「所有人 / 管理員 / 自訂」
- Skill 列表加狀態燈號：🟢 正常 / 🟡 缺設定 / 🔴 錯誤

### Phase 4: Printer Skill 化
- 新增 `printer` skill 目錄（SKILL.md + 設定）
- `metadata.ctos.mcp_servers` 宣告 printer MCP server
- `requires_app: "printer"` 權限控管
- 從硬編碼 MCP 列表中移除 printer
- Migration script：自動遷移，使用者無感

## Capabilities

- 搜尋一次就有完整 skill 資訊（author、version、描述），不用二次 inspect
- 管理員可在 UI 設定 skill 需要的 API Keys，不用手動改環境變數
- ENV 不回傳原文，API write-only，前端永遠 mask
- 外部 skill 預設安全（deny by default），管理員明確開放
- Skill 狀態一目了然：缺什麼設定、誰能用
- Printer 功能可獨立管理、更新、移除

## Impact

- **後端**：新增 `ClawHubClient` class、`skill_env` table + Alembic migration、ENV CRUD API、權限預設改動、printer skill 目錄
- **前端**：搜尋結果卡片升級、ENV 設定 UI、權限引導、狀態燈號
- **依賴變更**：新增 `httpx`、`cryptography`；移除 `clawhub` CLI 運行時依賴
- **向後相容**：
  - 內建 7 個 skill 不受影響（無 `_meta.json` = builtin）
  - 現有 ClawHub 已安裝的 skill 需要手動設定權限（migration 可處理）
  - `install-service.sh` 中的 `clawhub` 安裝步驟可移除（但保留以防需要）
- **安全**：ENV allowlist（非 blocklist）、zip slip 防護、ZIP 大小限制、SSRF 防護（固定 base URL）

## 風險

- ClawHub REST API 文件不完整，需要實際測試確認端點行為
- `cryptography` 套件需要系統 level 依賴（`libffi`），production 需確認
- Printer skill 化需要測試實際列印功能（需公司環境）
