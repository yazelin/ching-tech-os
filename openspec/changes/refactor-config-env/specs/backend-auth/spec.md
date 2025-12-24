## ADDED Requirements

### Requirement: 環境變數設定
系統 SHALL 從環境變數載入所有敏感和環境相關設定。

#### Scenario: 載入資料庫設定
- **WHEN** 應用程式啟動
- **THEN** 系統從環境變數讀取 `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- **AND** 使用這些設定連線資料庫

#### Scenario: 載入 NAS 設定
- **WHEN** 應用程式啟動
- **THEN** 系統從環境變數讀取 `NAS_HOST`, `NAS_PORT`, `NAS_USER`, `NAS_PASSWORD`, `NAS_SHARE`
- **AND** 使用這些設定進行 NAS 操作

#### Scenario: 載入管理員設定
- **WHEN** 應用程式啟動
- **THEN** 系統從環境變數讀取 `ADMIN_USERNAME`
- **AND** 該帳號登入時可被識別為管理員

#### Scenario: 環境變數缺失時提供預設值
- **WHEN** 某個非必要環境變數未設定
- **THEN** 系統使用預設值
- **AND** 應用程式正常啟動

#### Scenario: 必要環境變數缺失時警告
- **WHEN** 敏感環境變數（如密碼）未設定
- **THEN** 系統在啟動時記錄警告訊息
- **AND** 相關功能可能無法正常運作

---

### Requirement: 環境變數範例檔
專案 SHALL 提供 `.env.example` 範例檔案。

#### Scenario: 範例檔包含所有設定
- **WHEN** 開發者查看 `.env.example`
- **THEN** 檔案列出所有可用的環境變數
- **AND** 每個變數有註解說明用途
- **AND** 不包含實際的敏感值

#### Scenario: 範例檔納入版本控制
- **WHEN** 開發者提交程式碼
- **THEN** `.env.example` 會被提交到版本控制
- **AND** `.env` 不會被提交（在 .gitignore 中）
