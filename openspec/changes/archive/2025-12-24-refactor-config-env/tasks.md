# Tasks: Config 環境變數重構與敏感資料清理

## 1. 更新 .env 檔案
- [x] 1.1 新增管理員設定 `ADMIN_USERNAME`
- [x] 1.2 新增資料庫設定 `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- [x] 1.3 新增 NAS 設定 `NAS_HOST`, `NAS_PORT`, `NAS_USER`, `NAS_PASSWORD`, `NAS_SHARE`
- [x] 1.4 新增 Session 設定 `SESSION_TTL_HOURS`
- [x] 1.5 新增路徑設定（可選）

## 2. 重構 config.py
- [x] 2.1 修改所有設定使用 `os.getenv()`
- [x] 2.2 移除硬編碼的敏感資料
- [x] 2.3 統一 NAS 設定（移除重複的 knowledge_nas_*, project_nas_* 等）
- [x] 2.4 加入環境變數缺失時的警告日誌

## 3. 建立 .env.example
- [x] 3.1 建立範例檔案，包含所有環境變數但不含敏感值
- [x] 3.2 加入註解說明各設定用途

## 4. 確認 .gitignore
- [x] 4.1 確認 `.env` 在 .gitignore 中
- [x] 4.2 確認 `.env.example` 不在 .gitignore 中

## 5. 清理 Git 歷史
- [x] 5.1 安裝 git-filter-repo (`pip install git-filter-repo`)
- [x] 5.2 建立敏感字串替換規則檔
- [x] 5.3 執行 git filter-repo 替換歷史中的敏感資料
- [x] 5.4 刪除替換規則檔（包含敏感資料）
- [x] 5.5 Force push 到 GitHub

## 6. 測試驗證
- [x] 6.1 測試 config 載入環境變數
- [ ] 6.2 測試登入功能（需手動驗證）
- [ ] 6.3 測試 NAS 檔案存取（需手動驗證）
- [ ] 6.4 測試 Line Bot webhook（需手動驗證）
- [x] 6.5 確認 Git 歷史中已無敏感資料
