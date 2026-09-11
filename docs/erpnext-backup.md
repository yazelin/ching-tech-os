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

## 匯入（ERPNext → 往來與物料模組）

`scripts/erpnext_import.py` 把備份的 doctype JSON 匯進 migration 030 建的資料表
（規格 `docs/superpowers/specs/2026-09-12-ai-native-erp-design.md` 第六節）。
寫入一律經過 `services/erp*.py` 與 `services/project.py`，所以每一筆都留稽核，
`erp_audit.via = "import"`、`actor_user_id` 是 `--actor-user-id` 指定的執行者。

```bash
cd backend
# 先空跑看統計（會讀資料庫比對，但不寫）
uv run python ../scripts/erpnext_import.py \
    --src /mnt/nas/ctos/erpnext-backup/$(cat /mnt/nas/ctos/erpnext-backup/LATEST)/doctypes \
    --dry-run

# 真的匯（--db-name 覆寫 DB_NAME，其餘連線參數照 config.py 的 env 取法）
uv run python ../scripts/erpnext_import.py \
    --src /mnt/nas/ctos/erpnext-backup/20260912/doctypes \
    --actor-user-id 1 --report ~/logs/erpnext-import-report.json
```

參數：`--src`（doctypes 目錄）、`--dry-run`、`--only parties|items|stock|purchase_orders|projects`
（可複選）、`--db-name`、`--actor-user-id`、`--internal-contact-threshold`、`--report`。

### 兩道過濾

- **內部人員的 Contact**：ERPNext 把擎添自家業務也掛成往來對象的聯絡人，
  一個人最多掛到 260 家。掛在 `--internal-contact-threshold`（預設 20）家以上
  **且 phone／mobile／email 全空**的，整筆跳過不建 `party_contacts`，
  報告記在 `contacts_skipped_internal` 並列出人名與掛載數。
  有聯絡方式的即使掛很多家也照掛，只在 `contacts_fanout_top` 點名。
  不擋的話這些人名會進 `party_contacts.name` 的 trgm 索引，
  用人名 `resolve_party` 會一次跳出幾百個候選。
- **測試資料**：任何 doctype 的主鍵、顯示名稱或指到主檔的參照欄位以
  `_MCP_TEST_` 開頭的都跳過，報告記在 `skipped_test_records`（依 doctype 分）。

### 對應規則

| 來源 | 目的地 | 備註 |
|------|--------|------|
| Supplier ＋ Customer | `parties` | 名稱正規化後同名的併成一筆，`is_supplier`／`is_customer` 都設 |
| Contact／Address | `party_contacts`／`party_addresses` | 依 Dynamic Link 掛，沒有 link 的略過並計數 |
| Item ＋ Item Price（`buying=1`） | `items` | `lead_time_days` → `lead_days`，Item Default 的預設供應商 → `default_supplier_id` |
| Warehouse（非群組倉） | `warehouses` | `warehouse_name` 當 `code` |
| Bin | `stock_movements(reason='import')` | 走 `adjust_stock`，補「目標餘額 − 現有餘額」 |
| Purchase Order | `purchase_orders` | 保留 ERPNext 單號；草稿（`docstatus=0`）不匯；`received_qty` 直接帶入，不產生庫存異動 |
| Project／Task | `projects`／`tasks` | 以專案名稱去重 |

名稱正規化：去掉 ERPNext 的流水碼前綴（`SM9001 - `）、全形轉半形、去空白、
去「股份有限公司／有限公司／公司」尾綴。所以
`SM9001 - 某某企業有限公司` 與 `CM9001 - 某某企業有限公司` 會併成同一家。

### 失敗處理

- `--actor-user-id` 在開始寫之前先對 `users` 驗一次，對不上就直接結束（exit 2），
  不會寫到一半才被外鍵擋下來。
- **單筆失敗不中斷整批**：那一筆記進報告的 `errors`（doctype、name、錯誤摘要）後繼續跑。
  有任何 errors 時行程的 exit code 是 1。
- `import-report.json` 在 `finally` 寫出來。已經開始匯的區塊爆掉時，各桶的計數
  會留在報告裡，看得出資料庫被寫了多少；如果是讀來源就失敗（找不到目錄、JSON 壞掉），
  報告只有空桶——不過那時候也還沒寫進資料庫。

### 冪等

以 `source_ref` 當 key（`Supplier:<name>`、`Customer:<name>`、`Item:<item_code>`），
採購單用 `po_no`，倉庫用 `code`，專案用名稱——都是唯一鍵且由來源名稱決定。
已存在的只更新「有值且真的變了」的欄位，`aliases` 只加不減，布林旗標只從 false 變 true。
庫存做的是差額調整，差為 0 就不寫。所以重跑第二次的報告會全部落在 `unchanged`。

### 要人看過的兩個清單

- `merge_review`：合併組裡的成員**去公司尾綴之前名稱就不一樣**
  （「某某有限公司」對上「某某股份有限公司」）。多半是同一家，但也可能是兩個法人，
  腳本照併，列出來讓人眼看過。
- `unresolved.party_conflicts`：同一組的來源 token 分別對到**兩筆以上既有 party**
  （上一次匯入時還沒併在一起）。腳本只更新第一筆、不自己猜，
  要人去跑 `merge_parties` 把它們併起來。

### 正式機執行需授權

匯入會在正式庫產生大量寫入與稽核。**在正式機跑之前要先取得負責人授權**，
流程：先在測試庫跑一次（`--db-name`），把 `import-report.json` 給負責人看過，
確認建立／更新筆數與「無法解析」清單都合理，才在正式機執行。

## 已知限制

- API 使用者沒讀取權限的 doctype（目前只有 BOM，0 筆）在 manifest 記 `skipped: HTTP 403`，資料仍在 SQL dump 裡。
- 子表（Item Default 等）不獨立匯出，已含在父文件的 JSON。
- 匯入的模糊解析（`resolve_party`／`resolve_item`）只在 `source_ref` 沒命中時才用；
  真實備份裡 Item Default 的 `default_supplier` 全部是空的，所以那條路在實測中沒被觸發。
