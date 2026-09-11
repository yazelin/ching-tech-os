# ERPNext 備份到 NAS

停用 ERPNext 前的資料搬出（9/10 spec 第五節「獨立一條線」）。2026-09-12 起每天 03:30 跑，與知識庫備份（03:00）錯開。

## 產出

`/mnt/nas/ctos/erpnext-backup/<YYYYmmdd>/`

- `site/`：`bench backup --with-files` 的整站備份（`database.sql.gz`、`files.tar`、`private-files.tar`、`site_config_backup.json`），可整站還原。
- `doctypes/`：業務 doctype 逐筆 JSON（含子表）與 CSV（父層純量欄位），`manifest.json` 記每個 doctype 的筆數與失敗清單。清單在 `scripts/erpnext_export.py` 的 `DEFAULT_DOCTYPES`（往來對象、物料庫存、採購銷售單據、專案、Comment、File 等 41 個）。
- `LATEST`：最新一份的日期（NAS 是 SMB，不能用符號連結）。

保留 30 天；每月 1 日那份永久保留。第一次（2026-09-12）：整站 11 MB、doctype 8 MB、6662 筆、0 失敗。

## 腳本與排程

- 腳本：`/home/ct/scripts/backup-erpnext-to-nas.sh` 與 `/home/ct/scripts/erpnext_export.py`（repo 存底 `scripts/`，改完要同步部署到 `~/scripts/`）。
- 排程：`backup-erpnext.timer`（unit 檔在 `scripts/systemd/`，安裝方式見檔頭註解）。
- 日誌：`~/logs/backup-erpnext.log`。
- 憑證：`erpnext_export.py --env-file` 只讀 `.env` 的 `ERPNEXT_URL`／`ERPNEXT_API_KEY`／`ERPNEXT_API_SECRET`，不 source 整個檔。

## 手動跑

```bash
/home/ct/scripts/backup-erpnext-to-nas.sh
python3 scripts/erpnext_export.py --env-file .env --out ./out --doctypes Supplier Customer
```

## 已知限制

- API 使用者沒讀取權限的 doctype（目前只有 BOM，0 筆）在 manifest 記 `skipped: HTTP 403`，資料仍在 SQL dump 裡。
- 子表（Item Default 等）不獨立匯出，已含在父文件的 JSON。
