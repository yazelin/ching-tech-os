# Tasks: NAS 掛載方式重構

## 1. 系統設定
- [x] 1.1 修改 `scripts/install-service.sh` 新增 mount unit 與憑證檔案設定
- [x] 1.2 修改 `scripts/uninstall-service.sh` 新增清理掛載設定
- [x] 1.3 更新 `.env.example` 新增 `NAS_MOUNT_PATH` 說明

## 2. 後端設定
- [x] 2.1 修改 `config.py` 新增 `nas_mount_path` 與本機路徑屬性
- [x] 2.2 新增 `services/local_file.py` 實作 `LocalFileService`

## 3. 重構系統功能
- [x] 3.1 重構 `services/knowledge.py` 改用 `LocalFileService`
- [x] 3.2 重構 `services/project.py` 改用 `LocalFileService`
- [x] 3.3 重構 `services/linebot.py` 改用 `LocalFileService`

## 4. 測試與部署
- [ ] 4.1 手動測試知識庫附件上傳/下載
- [ ] 4.2 手動測試專案附件上傳/下載
- [ ] 4.3 手動測試 Line Bot 附件存取
- [ ] 4.4 重新執行 `install-service.sh` 部署
- [ ] 4.5 確認服務正常運作
