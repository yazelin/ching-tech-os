# infrastructure Specification

## Purpose
TBD - created by archiving change mount-nas-storage. Update Purpose after archive.
## Requirements
### Requirement: NAS 系統掛載
系統 SHALL 使用 systemd mount unit 掛載 NAS 共享資料夾。

#### Scenario: 服務啟動前自動掛載
- **GIVEN** 系統設定了 NAS 掛載
- **WHEN** `ching-tech-os.service` 啟動
- **THEN** `mnt-nas.mount` 先啟動並掛載 NAS
- **AND** 掛載點為 `/mnt/nas`（可透過環境變數配置）

#### Scenario: 掛載使用憑證檔案
- **GIVEN** 系統需要掛載 NAS
- **WHEN** mount unit 執行掛載
- **THEN** 使用 `/etc/nas-credentials` 檔案中的帳密
- **AND** 憑證檔案權限為 600

#### Scenario: 服務依賴掛載
- **GIVEN** `ching-tech-os.service` 設定了 `Requires=mnt-nas.mount`
- **WHEN** 掛載失敗
- **THEN** 服務不會啟動
- **AND** systemd 日誌顯示掛載失敗原因

#### Scenario: 卸載服務時清理掛載
- **GIVEN** 執行 `uninstall-service.sh`
- **WHEN** 腳本完成
- **THEN** mount unit 被停用並移除
- **AND** 憑證檔案被刪除
- **AND** 掛載點目錄被移除

---

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

