# Change: NAS 掛載方式重構

## Why
目前系統功能（知識庫、專案、Line Bot）每次存取 NAS 都需要透過 `smbprotocol` 建立連線，效能較差且程式碼複雜。改用系統層級的 CIFS 掛載可以：
- 提升效能（連線由系統核心管理）
- 簡化程式碼（直接使用本機檔案操作）
- 提高穩定性（系統自動處理重連）

## What Changes
1. **修改 install-service.sh** - 新增 systemd mount unit 與憑證檔案設定
2. **修改 uninstall-service.sh** - 新增清理掛載相關設定
3. **新增環境變數** - `NAS_MOUNT_PATH` 設定掛載點路徑
4. **新增本機檔案服務** - `LocalFileService` 取代系統功能中的 SMB 操作
5. **重構系統功能** - `knowledge.py`、`project.py`、`linebot.py` 改用本機路徑

## 不受影響的部份
- **檔案總管**（`api/nas.py`）- 繼續使用 SMB + 用戶帳密（保留多用戶權限）
- **登入認證**（`api/auth.py`）- 繼續使用 SMB 驗證用戶帳密

## Impact
- Affected specs: infrastructure（新增）
- Affected code:
  - `scripts/install-service.sh` - 新增掛載設定
  - `scripts/uninstall-service.sh` - 新增清理設定
  - `backend/src/ching_tech_os/config.py` - 新增路徑設定
  - `backend/src/ching_tech_os/services/local_file.py` - 新增服務
  - `backend/src/ching_tech_os/services/knowledge.py` - 改用本機路徑
  - `backend/src/ching_tech_os/services/project.py` - 改用本機路徑
  - `backend/src/ching_tech_os/services/linebot.py` - 改用本機路徑
