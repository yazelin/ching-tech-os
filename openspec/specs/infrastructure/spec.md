# infrastructure Specification

## Purpose
TBD - created by archiving change mount-nas-storage. Update Purpose after archive.
## Requirements
### Requirement: NAS 系統掛載
系統 SHALL 使用 systemd mount unit 掛載 NAS 共享資料夾，包含多個唯讀共用區掛載點。

#### Scenario: circuits 掛載點建立
- **GIVEN** 安裝腳本執行
- **WHEN** 建立 systemd mount units
- **THEN** 建立 `mnt-nas-circuits.mount` 掛載 `//NAS_HOST/擎添線路圖/圖檔` 到 `/mnt/nas/circuits`
- **AND** 使用唯讀模式（ro）
- **AND** 使用與其他掛載相同的憑證檔案

#### Scenario: 服務依賴 circuits 掛載
- **GIVEN** `ching-tech-os.service` 設定
- **WHEN** 服務啟動
- **THEN** service unit 包含 `Wants=mnt-nas-circuits.mount`
- **AND** circuits 掛載失敗不阻止服務啟動（Wants 而非 Requires）

#### Scenario: circuits 掛載環境變數
- **GIVEN** 系統設定
- **WHEN** 讀取環境變數
- **THEN** `CIRCUITS_MOUNT_PATH` 預設為 `/mnt/nas/circuits`
- **AND** 可透過 `.env` 覆蓋

### Requirement: 本機檔案服務
系統功能 SHALL 透過本機路徑存取 NAS 檔案，取代直接 SMB 連線。

#### Scenario: 知識庫使用本機路徑
- **GIVEN** NAS 已掛載於 `/mnt/nas`
- **WHEN** 知識庫服務存取附件
- **THEN** 使用 `/mnt/nas/ching-tech-os/knowledge/` 路徑
- **AND** 不建立 SMB 連線

#### Scenario: 專案使用本機路徑
- **GIVEN** NAS 已掛載於 `/mnt/nas`
- **WHEN** 專案服務存取附件
- **THEN** 使用 `/mnt/nas/ching-tech-os/projects/` 路徑
- **AND** 不建立 SMB 連線

#### Scenario: Line Bot 使用本機路徑
- **GIVEN** NAS 已掛載於 `/mnt/nas`
- **WHEN** Line Bot 服務存取檔案
- **THEN** 使用 `/mnt/nas/ching-tech-os/linebot/files/` 路徑
- **AND** 不建立 SMB 連線

#### Scenario: 檔案總管保持 SMB 存取
- **GIVEN** 用戶使用檔案總管
- **WHEN** 瀏覽或操作 NAS 檔案
- **THEN** 繼續使用 SMBService 與用戶帳密
- **AND** 保留多用戶權限機制

