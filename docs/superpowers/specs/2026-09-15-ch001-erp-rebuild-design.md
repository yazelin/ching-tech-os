# 舊 ERP 歷史資料匯復與查核設計

日期：2026-09-15
狀態：待實作；範圍與定位由 yazelin 拍板（2026-09-15）
上位規格：`2026-09-12-ai-native-erp-design.md`（本規格是**平行**的獨立系統，不擴充它）
資料來源盤點：`docs/ch001-export-inventory.md`

## 一、這是什麼，不是什麼

舊 ERP（鼎新 e-Go）要退場。整庫傾印 `CH001_export` 是唯一的歷史資料來源，
不會再更新。同事另建的新 ERP（`192.168.11.6:8000`）從零開始，可能參考這裡
建起來的樣子。

**這套東西是給同事確認資料內容正確無誤用的查核工具，不是 CTOS 要拿來營運的系統。**
（yazelin，2026-09-15）

設計目標因此不是「好用」，是**好查、好比對、好證明**。落下來的取捨：

| 不做 | 為什麼 |
|---|---|
| 建立／修改／刪除的 service 函式 | 沒有人會在裡面建東西 |
| `erp_audit` 稽核 | 沒有寫入就沒有稽核對象 |
| 唯讀 trigger | 不開寫入路徑，不必擋 |
| uuid 主鍵、`created_by`／`updated_at`／`deleted_at` | 查核用不上，反而擋路 |
| MCP 工具 | 選配，不列在必要範圍 |
| 稅務申報、BOM、多公司、多幣別 | 來源沒有或不在查核範圍 |

**真正的資產是「鼎新 197 張無欄名資料表 → 人看得懂的現代 schema」這份對照與轉換。**
那件事不管誰建系統都得做一次，做對了就永久有效。CTOS 這套只是它的第一個消費者，
同事的版本是第二個。所以轉換層必須獨立於 CTOS（第四節）。

### 隔離：獨立的 PostgreSQL schema

全部資料放 `ch001` schema，不進 CTOS 既有的 `public`。

1. 不污染 CTOS 的正式表（`parties`／`items`／`purchase_orders` 等維持原樣）。
2. 給同事的唯讀帳號只授 `ch001` 的 `USAGE` 與 `SELECT`，碰不到使用者、
   知識庫、AI 紀錄。
3. 這版不要了就 `DROP SCHEMA ch001 CASCADE`，一句話，沒有殘留。
4. 不需要動 CTOS 的 alembic 主線；`ch001` 的 DDL 是獨立的 `.sql`，
   由匯入器負責建立。

## 二、決定（yazelin，2026-09-15）

1. 在 CTOS 完整匯復鼎新的資料，做到會計與票據。
2. 完整搬進來可以查帳。
3. 匯出的內容不要有漏 —— 已驗收，118,946 張傳票借貸 100% 平衡。
4. 這套是給同事確認資料正確用的，不是我們要用的。
5. 同事那邊從零開始，可能參考我們建起來的樣子。
6. 科目餘額：即時算與月結快照都要，加對帳。
7. 中間格式用 JSONL ＋ schema 文件。
8. 階段 1 驗完後把對照與中間格式交付給同事。
9. 同事用唯讀檢視頁，並開唯讀資料庫帳號給他直連。

## 二之二、部署現況（2026-09-15）

階段 1 已在 `.11` 上線。yazelin 授權執行。

| 項目 | 值 |
|---|---|
| 容器 | `ch001-db`（`postgres:16-alpine`）、`ch001-viewer`（查核頁），皆 `restart: unless-stopped` |
| Port | 資料庫 `5436`（5432–5435 已被 CTOS、jaba、billing 佔用）、查核頁 `8092` |
| 查核頁 | `http://192.168.11.11:8092`，HTTP Basic 登入 |
| 工作目錄 | `~/ch001-work/`　**刻意不放在 `ching-tech-os` 工作樹裡** |
| 資料 | 19 張表、707,971 列、171 MB |
| 唯讀帳號 | `ch001_viewer`，密碼在 `~/ch001-work/.env`（權限 600，不進版控） |

`ching-tech-os` 的工作樹全程未動（不 pull、不 build、不 checkout）；腳本以
`scp` 傳到獨立目錄執行。`.11` 沒有 `python3-venv`，改用 `~/.local/bin/uv run
--with psycopg2-binary`（`uv` 不在非互動 shell 的 PATH，要用絕對路徑）。

正式機上的驗收，與本機排練完全一致：

```
借貸平衡          118,946/118,946　借方合計 8,502,130,448.00　差額 0
進貨 單頭==明細     47,127/47,127
數量 × 單價==金額   130,350/130,350
表 19 張、171 MB、有中文註解的欄位 349
```

負控制（唯讀帳號真的寫不進去，不是只有「沒人去寫」）：

- 讀 `ch001.tpadga` → 673 家廠商
- `INSERT` → `cannot execute INSERT in a read-only transaction`
- `CREATE TABLE` → `cannot execute CREATE TABLE in a read-only transaction`
- 用同一組帳密連 CTOS 的 5432 → `password authentication failed`（兩邊完全隔離）

階段 2 的查核頁也已上線（2026-09-16 收尾）：表清單按模組分組、搜尋任一欄位、
單頭鑽明細。欄位中文名讀資料庫的 `COMMENT`，與 `ch001_columns.py` 是同一份來源。
未認出語意的欄位顯示原始欄位名並標灰 —— 那是要請使用者指認的部分，不是瑕疵。

收尾時修掉的三個問題（都是實際操作才會踩到的）：

- 語意規則的順序：電話規則 `[\d()\-\s#]{8,}` 會先吃掉 8 位數的日期與 14 位的
  傳票總號，把它們標成「電話／傳真」。改成日期優先，且電話必須含分隔符或是
  09 開頭的手機；郵遞區號限定 3 或 5 碼，免得把會計科目 `1101` 當成郵遞區號。
  **標錯比不標更糟 —— 使用者會相信標籤。**
- 複合鍵鑽取：會計傳票的主鍵是 (類別, 總號)，只用第一欄當網址會抓到一整批
  同類別的傳票。網址改用 `~` 串接多欄。
- 表頭重複：未認出的欄位會上下印同一個名字兩遍（中文位置也印欄位名）。

收掉的方式：`cd ~/ch001-work && docker compose down -v`，volume 一起刪，
CTOS 不受影響。

## 三、來源的讀法（已定案，不要重新發明）

細節見 `docs/ch001-export-inventory.md`，三件必須遵守：

1. **一律用 `scripts/ch001_reader.py`**。不可 `decode(...).split("|")` —— Big5
   中文字的低位元組可能是 `0x7C`（即 `|`），先解碼再切分會**靜默**錯位。
2. **分錄表是 `KJSNHB`**（借方貸方分兩欄，100% 平衡），不是 `KJSNFB`
   （單邊 `±1` 乘金額，只平 87.24%）。
3. **已知瑕疵不得靜默丟棄**：銷貨明細 1 筆單號欄被打成中文備註、
   會計傳票 2 筆分錄無單頭、1 筆單頭無分錄。挑掉並記進 `manifest.json`，
   且要出現在 `--dry-run` 輸出裡。

## 四、中間格式（交付給同事的東西）

轉換層不 import 任何 `ching_tech_os` 的東西，輸出中性格式：

- `<表名>.jsonl` — 一列一個 JSON 物件，鍵即 schema 欄位名。
- `schema.json` — 每個欄位的型別、可否為空、主鍵、外鍵指向。
- `manifest.json` — 來源表、筆數、產生時間、跳過的瑕疵逐筆記錄。

不綁資料庫，同事用 PostgreSQL、MySQL 或別的都讀得動。金額一律字串
（避免浮點誤差），日期一律 `YYYY-MM-DD`，NULL 就是 JSON `null`。

## 五、資料模型

**主鍵直接用來源的鍵**，不生 uuid。同事要驗資料時會拿鼎新的單號來查
（`PC209001010001`、傳票 `(2, 20900101000001)`、廠商 `SX0001`），
主鍵就該是那個鍵。三件事同時變簡單：他查得到、兩邊逐欄對得起來、
匯入天然冪等（主鍵衝突就是重複）。

每張表只多一個 `imported_at TIMESTAMPTZ`，其餘欄位全部來自來源。

### 主檔

| 表 | 來源 | 主鍵 |
|---|---|---|
| `parties` | `TPADGA`（廠商）＋`TPADFA`（客戶） | `code` |
| `party_contacts` | `CRMIKG` | `(party_code, seq)` |
| `items` | `TPADEA` | `code` |
| `item_groups` | `TPADED` | `code` |
| `warehouses` | `TPADDA` | `code` |

廠商與客戶同一張表、用 `is_supplier`／`is_customer` 兩個旗標，
因為舊系統的代號前綴（`SM`／`SF`／`CM`／`CF`）已經把兩者分開，
不會撞鍵。

### 採購進貨與庫存

| 表 | 來源 | 主鍵 |
|---|---|---|
| `purchase_orders` / `purchase_order_lines` | `DCSHDA` / `DCSHDB` | `po_no` / `(po_no, line_no)` |
| `goods_receipts` / `goods_receipt_lines` | `JSKJDA` / `JSKJDB` | `gr_no` / `(gr_no, line_no)` |
| `goods_returns` | `JSKJFA` | `gn_no` |
| `stock_movements` | `JSKLNA` | `(doc_type, doc_no, line_no)` |

### 銷貨與發票

| 表 | 來源 | 主鍵 |
|---|---|---|
| `sales_orders` / `sales_order_lines` | `JSKKEA` / `JSKKEB` | `so_no` / `(so_no, line_no)` |
| `sales_returns` | `JSKKFA` | `sr_no` |
| `quotations` | `DCSIAA` | `quote_no` |
| `invoices` / `invoice_lines` | `JSKJIA`（進項）／`JSKKGA`（銷項） | `(direction, invoice_no)` |

`direction` 是 `in`／`out`，兩邊欄位幾乎相同，查「這家的所有發票」不必 union。

### 會計

| 表 | 來源 | 主鍵 |
|---|---|---|
| `gl_accounts` | `KJSNAA`→`BA`→`CA`→`DA` | `code` |
| `gl_vouchers` | `KJSNFA` | `(voucher_type, voucher_no)` |
| `gl_voucher_lines` | **`KJSNHB`** | `(voucher_type, voucher_no, line_no)` |
| `gl_period_balances` | `KJSNHA` | `(account_code, period)` |

科目四層平鋪成一張表加 `parent_code`，`level` 保留原層級
（類 9 → 大類 35 → 中類 67 → 科目 289）。

**`debit` 與 `credit` 分兩欄**，直接對應來源，不做 `signed_amount` 轉換 ——
轉換會讓借貸平衡這個驗證失去意義，而它是這批資料唯一的硬指標。

### 應收應付與票據

| 表 | 來源 | 主鍵 |
|---|---|---|
| `receivables` / `payables` | `YSFGAA`＋`YSFGEA` / `YSFGNA`＋`YSFGRA` | `doc_no` |
| `payments` | `YSFGDA`（收）／`YSFGQA`（付） | `(direction, payment_no)` |
| `payment_allocations` | `YSFGCA` / `YSFGPA` | `(direction, payment_no, seq)` |
| `notes_receivable` / `notes_payable` | `PJMPAA` / `PJMPIA` | `note_no` |

收付款與沖銷拆兩張：一張收款單可沖多筆應收
（`YSFGCA` 18,482 列對 `YSFGDA` 5,658 列，確實是一對多）。

## 六、三個查核出口

查核工具的價值全在這一節。沒有這些，資料進來了也證明不了什麼。

### 1. 唯讀資料庫帳號

同事從 `192.168.11.6` 直連 `.11` 的 PostgreSQL，只授 `ch001` schema 的
`USAGE` ＋ `SELECT`。

**這是對正式機的變更，不由 agent 執行**：規格只寫出該下什麼、
開哪個網段，實際執行等 yazelin 授權或自己做。附一份 `ch001_readonly.sql`
（`CREATE ROLE` ＋ `GRANT`，密碼留佔位）與 `pg_hba` 需要加的那一行。

### 2. 唯讀檢視頁（ctos-web）

不做 CRUD，四種畫面：

- **表清單** — 每張表的中文名、筆數、來源鼎新表名、最後匯入時間。
- **原始列檢視** — 逐列瀏覽、翻頁、依主鍵搜尋。讓他跟鼎新畫面逐欄對照。
- **鑽取** — 單號點進去看明細；傳票點進去看分錄；廠商點進去看它的進貨、
  發票、應付。
- **對帳報表** — 見下。

### 3. 對帳報表（他在鼎新有得比的數字）

- **試算表** — 某期間各科目借貸合計與餘額，底部合計必須相等。
- **科目明細帳** — 某科目某期間的每一筆分錄，可回推到來源單據。
- **進銷存** — 某期間某品號的期初、進、銷、期末。
- **廠商／客戶對帳單** — 某往來對象的應收應付與收付款沖銷。
- **與 ERPNext 的差異報告** — 419 客戶／665 廠商的交叉比對，
  列出只在一邊有的、統編不一致的。

報表同時輸出 CSV，他要拿去 Excel 比對也行。

## 七、轉換與匯入

三支腳本，中間隔著中間格式：

| 腳本 | 做什麼 | 依賴 CTOS |
|---|---|---|
| `ch001_transform.py` | `CH001_export` → 中間格式。語意翻譯：欄位位置換欄位名、單頭明細接起來、瑕疵挑掉記進 manifest | 否 |
| `ch001_load.py` | 中間格式 → `ch001` schema。建表、批次 COPY | 只依賴連線字串 |
| `ch001_dump.py` | `ch001` schema → 中間格式。換系統時帶走資料，也是匯入的迴圈驗證 | 只依賴連線字串 |

`ch001_transform.py` 純函式為主、不連資料庫，測試不需要 DB。它的輸出就是
階段 1 之後要交給同事的東西。

載入用 `COPY`，不用逐筆 INSERT —— `gl_voucher_lines` 31 萬筆、
`stock_movements` 16 萬筆，逐筆會跑到天亮。

## 八、階段

每支 implement → review → fix → re-review → CI 綠 → 合併。
**後端合併即停，不自行部署 .11。**

排法的原則（yazelin，2026-09-15）：**盡快讓會計、採購、業務三種人各自拿到
一塊自己最熟的資料去親手驗**，而不是等全部灌完才給看。他們看一眼就知道欄位
對不對，比繼續推論準得多；推不準的欄位由他們指出來再修。

已定案的 13 張表正好覆蓋這三塊，所以階段 1 就能讓三種人同時開工。

| # | 內容 | 匯入列數 | 誰來驗 |
|---|---|---:|---|
| 1 | `ch001` schema ＋ transform／load ＋ **主檔、進貨、銷貨、會計** | 約 60 萬 | 建好即可開工 |
| 2 | 唯讀檢視頁（表清單、原始列、單號搜尋、單頭鑽明細）＋ 唯讀 DB 帳號 | 0 | 會計／採購／業務 |
| 3 | 依三方回饋修欄位定案，補對帳報表（試算表、科目明細帳、進銷存） | 0 | 三方複驗 |
| 4 | 庫存異動與餘額、採購單、進貨退出、銷貨退回 | 約 35 萬 | 採購 |
| 5 | 發票、應收應付、收付款、票據 | 約 18 萬 | 會計 |
| 6 | 其餘單據（報價、訂單、借出入、調撥、盤點） | 剩餘 | 視需要 |

階段 1 的表（全部已定案欄位）：

- 主檔：`TPADGA` 廠商、`TPADFA` 客戶、`TPADEA` 商品、`CRMIKG` 聯絡人、
  `TPADDA` 倉庫、`TPADED` 商品分類、`TPADAA` 部門、`TPADBA` 使用者
- 採購：`JSKJDA`／`JSKJDB` 進貨單
- 業務：`JSKKEA`／`JSKKEB` 銷貨單
- 會計：`KJSNAA`–`KJSNDA` 科目、`KJSNFA` 傳票、`KJSNHB` 分錄、`KJSNHA` 月結

欄位推不出來的一律**原樣保留**（欄位名用 `JDB047` 這種原始名稱，型別照推斷），
不猜、不丟。使用者驗的時候看得到它的值，有人認得出來就補一條定案。

MCP 工具與 CRUD **不做**。這套是查核工具，見第一節。

## 九、驗收

每個階段除了單元測試，都要跑：

1. `scripts/ch001_verify.py --src <目錄>` 五項全過（階段 5 後為六項，含餘額對帳）。
2. **筆數對帳**：DB 實際列數 == 來源列數 − 已知瑕疵筆數，差額必須為 0。
3. **重跑冪等**：同一份來源跑第二次，資料庫內容逐表 checksum 不變。
4. **迴圈等價**：`transform` → `load` → `dump` 產出的中間格式，
   與第一步的中間格式逐表比對應等價（唯一允許的差異是 `imported_at`）。
   這一項是「資料沒被鎖死」的證明。
5. 階段 5 額外：`SUM(debit) == SUM(credit) == 8,502,130,448.00`。
   這是硬指標，對不上就是匯入有問題。
6. 階段 5 額外：`gl_period_balances` 與從 `gl_voucher_lines` 即時聚合的結果
   逐（科目, 期間）相符。不相符就是失敗 —— 沒有這項，雙軌遲早分家。

## 十、假設（換一種就會做出不同東西）

1. 舊系統造字（42 處）維持 Unicode 私用區佔位，不還原字形。
   要還原得跟原系統要造字檔，是另一件事。
2. 幣別只有 TWD（`TPADGA` 第 20 欄實測只有一個值）。
3. 人事薪資（`CMSMV`、`PALMT`、`PALML`–`PALMV` 等）不進 `ch001`。
4. `TPABYA` 等系統設定表不進 `ch001`。
5. 資料只進不出到同事的系統；他要用就拿中間格式自己灌。

## 十一、待拍板

1. 品號要不要沿用舊碼。（影響階段 1；沿用則兩邊天然對得起來）
2. 唯讀 DB 帳號開給哪個網段、什麼時候開。（對正式機的變更）
3. `CH001_export` 那個共享槽含員工薪資與勞健保資料，建議來源端移出。
