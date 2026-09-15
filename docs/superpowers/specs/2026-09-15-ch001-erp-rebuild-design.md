# 舊 ERP 歷史資料在 CTOS 重建（含會計與票據）設計

日期：2026-09-15
狀態：待實作；範圍由 yazelin 拍板（2026-09-15）
上位規格：`2026-09-12-ai-native-erp-design.md`（本規格**擴充**其第一節原則 5 的「不做」清單）
資料來源盤點：`docs/ch001-export-inventory.md`

## 一、背景與決定

舊 ERP（鼎新 Workflow）要退場。整庫傾印 `CH001_export` 是唯一的歷史資料來源，
不會再更新。同事另建的新 ERP（`192.168.11.6:8000`）只做到進貨單與使用者管理，
沒有客戶、沒有會計，短期內接不了這批歷史。

yazelin 的決定（2026-09-15，逐條）：

1. **在 CTOS 重建**，做法沿用 `scripts/erpnext_import.py` 那條管線。
2. **範圍做到會計與票據**，不是只做主檔。
3. **完整搬進來可以查帳**，不是只搬單頭。
4. **匯出的內容不要有漏** —— 已驗收，118,946 張傳票借貸 100% 平衡。
5. **歷史資料唯讀封存**。
6. **科目餘額兩者都要**：即時算為正本、月結快照為快取、加對帳。

這推翻了上位規格原則 5 的「不做會計分錄、發票、報價／銷售單據」。上位規格
同步修訂，理由是當時的判斷基於 ERPNext 只有 1 張銷貨單、0 筆分錄；
`CH001_export` 有 17,649 張銷貨單與 319,121 筆分錄，前提變了。

## 二、來源的讀法（已定案，不要重新發明）

細節見 `docs/ch001-export-inventory.md`，三件必須遵守：

1. **一律用 `scripts/ch001_reader.py`**。不可 `decode(...).split("|")` —— Big5
   中文字的低位元組可能是 `0x7C`（即 `|`），先解碼再切分會**靜默**錯位。
2. **分錄表是 `KJSNHB`**（借方貸方分兩欄，100% 平衡），不是 `KJSNFB`
   （單邊 `±1` 乘金額，只平 87.24%）。
3. **已知瑕疵不得靜默丟棄**：銷貨明細 1 筆單號欄被打成中文備註、
   會計傳票 2 筆分錄無單頭、1 筆單頭無分錄。匯入時記入報告並跳過，
   報告要出現在 `--dry-run` 輸出裡。

## 三、資料模型

既有十張表（migration 030）不動。新增十三張，全部沿用既有慣例：
uuid 主鍵、`created_at`／`updated_at`／`created_by`、軟刪除 `deleted_at`、
寫入同交易寫 `erp_audit`。

### 銷貨與發票（階段 3）

| 表 | 來源 | 重點欄位 |
|---|---|---|
| `sales_orders` | `JSKKEA` | `so_no`（唯一）、`party_id`、`order_date`、`status`、`total_amount`、`source_ref` |
| `sales_order_lines` | `JSKKEB` | `so_id`、`item_id`、`description`、`qty`、`unit_price`、`amount`、`sort_order` |
| `invoices` | `JSKJIA`（進項）／`JSKKGA`（銷項） | `invoice_no`、`direction`（`in`／`out`）、`party_id`、`invoice_date`、`net_amount`、`tax_amount`、`total_amount`、`source_ref` |
| `invoice_lines` | `JSKJIB`／`JSKKGB` | `invoice_id`、`ref_type`、`ref_id`、`amount`、`tax_amount` |

`direction` 用單一表加方向欄而不是拆兩張，因為兩邊欄位幾乎相同，
查「這家廠商的所有發票」也不必 union。

### 會計（階段 4）

| 表 | 來源 | 重點欄位 |
|---|---|---|
| `gl_accounts` | `KJSNAA`→`KJSNBA`→`KJSNCA`→`KJSNDA` | `code`（唯一）、`name`、`name_en`、`parent_id`、`level`（1–4）、`is_leaf`、`direction`（借／貸性質） |
| `gl_vouchers` | `KJSNFA` | `voucher_type`、`voucher_no`、`voucher_date`、`period`（yyyymm）、`summary`、`source_ref`；`(voucher_type, voucher_no)` 唯一 |
| `gl_voucher_lines` | **`KJSNHB`** | `voucher_id`、`line_no`、`account_id`、`sub_account`、`summary`、`debit`、`credit`、`currency`、`ref_doc` |
| `gl_period_balances` | `KJSNHA` | `account_id`、`period`、`debit_total`、`credit_total`、`balance`；`(account_id, period)` 唯一 |

科目四層平鋪成一張表加 `parent_id`，不建四張。鼎新的四層是
類（9）→ 大類（35）→ 中類（67）→ 科目（289），`level` 保留原層級以便對照。

`debit` 與 `credit` **分兩欄**，直接對應來源，不做 `signed_amount` 轉換 ——
轉換會讓「借貸平衡」這個驗證失去意義。

### 應收應付與票據（階段 5）

| 表 | 來源 | 重點欄位 |
|---|---|---|
| `receivables` | `YSFGAA`＋`YSFGEA` | `party_id`、`doc_no`、`doc_date`、`due_date`、`amount`、`settled_amount`、`status` |
| `payables` | `YSFGNA`＋`YSFGRA` | 同上，方向相反 |
| `payments` | `YSFGDA`（收款）／`YSFGQA`（付款） | `direction`、`payment_no`、`party_id`、`payment_date`、`amount`、`method` |
| `payment_allocations` | `YSFGCA`／`YSFGPA` | `payment_id`、`target_type`（`receivable`／`payable`）、`target_id`、`amount` |
| `notes_receivable` | `PJMPAA` | `note_no`、`party_id`、`issue_date`、`due_date`、`amount`、`bank`、`status` |
| `notes_payable` | `PJMPIA` | 同上 |

收付款與沖銷拆成 `payments` ＋ `payment_allocations` 兩張，因為一張收款單
可以沖多筆應收（`YSFGCA` 18,482 列對 `YSFGDA` 5,658 列，確實是一對多）。

## 四、唯讀封存（yazelin 拍板）

歷史資料一律不得編輯或刪除。**不靠 service 層的紀律，用資料庫擋**：

1. 每張歷史表都有 `source_ref TEXT`。來自 `CH001_export` 的列一律非 NULL
   （格式 `CH001:<表名>:<原始鍵>`），CTOS 自己新建的列為 NULL。
2. 每張表加一個 `BEFORE UPDATE OR DELETE` trigger：`OLD.source_ref IS NOT NULL`
   就 `RAISE EXCEPTION`。單一共用 trigger function，各表各自 `CREATE TRIGGER`。
3. service 層在 trigger 之前先給出可讀的錯誤（`ArchivedRecordError`），
   讓 MCP 工具能回「這是舊系統的歷史資料，不能修改」而不是丟 DB 例外。
4. MCP 工具與 REST 的寫入端點對這些列回 409。

**驗收必須有負控制**：把 trigger 移掉之後，那組測試要變紅。只證明「改不動」
不夠，要證明「是 trigger 在擋」。

例外：`stock_balances` 是推導值不是歷史事實，不上鎖。

## 五、科目餘額雙軌（yazelin 拍板）

- **正本**：從 `gl_voucher_lines` 即時聚合。提供
  `gl_account_balance(account_id, period_from, period_to)` service 函式，
  底層是 `SUM(debit) - SUM(credit)`，索引建在 `(account_id, voucher_id)`
  與 `gl_vouchers(period)`。
- **快取**：`gl_period_balances` 直接收 `KJSNHA` 的月結資料（舊系統已經算好，
  2007 起每月每科目），查報表走這張。
- **對帳**：`scripts/ch001_verify.py` 增加一項檢查，對每個
  (科目, 期間) 比對即時聚合與快照。**不相符就 exit 1。**
  這一項是雙軌制的成立條件 —— 沒有它，兩套數字遲早分家。

## 六、匯入器

沿用 `scripts/erpnext_import.py` 的結構，新增 `scripts/ch001_import.py`：

- **門面層照抄**：`Services` 類別綁 service 函式，所以每筆都留 `erp_audit`
  （`via="import"`）。新表要先有對應的 service 函式才能匯。
- **冪等**：`source_ref` 當 key，已存在就只更新真的變了的欄位。重跑收斂。
- **參數**：`--src`、`--dry-run`、`--only <階段>`、`--db-name`、`--actor-user-id`，
  與 ERPNext 匯入器一致。
- **合併 ERPNext**：階段 1 跑完 `CH001` 之後再跑 `erpnext_import.py`。
  兩邊靠舊代號對上（97.3% 的 ERPNext 廠商名稱開頭就是舊代號，
  格式 `SF0001 - 名稱`），不會產生重複。ERPNext 的值較新，覆蓋同名欄位。
- **批次**：`stock_movements` 16 萬筆、`gl_voucher_lines` 31 萬筆，
  要用 `executemany` 分批，單筆 INSERT 會跑到天亮。批次大小先設 1000，
  實測後調。

## 七、階段與 PR 切法

每支 implement → review → fix → re-review → CI 綠 → 合併。**後端合併即停，
不自行部署 .11。** 每個階段結束都是可用狀態。

| # | 內容 | 新表 | 匯入列數 |
|---|---|---|---|
| 1 | 主檔（客戶／廠商／聯絡人／地址／商品／倉庫）＋合併 ERPNext | 0 | 29,886 |
| 2 | 採購進貨＋庫存異動 | 0 | 347,059 |
| 3 | 唯讀封存機制（trigger ＋ service ＋ 負控制測試） | 0 | 0 |
| 4 | 銷貨＋發票 | 4 | 51,400 |
| 5 | 會計科目＋傳票＋月結快照＋對帳 | 4 | 842,795 |
| 6 | 應收應付＋收付款＋票據 | 6 | 123,506 |

階段 3 刻意排在有歷史資料之後、大量單據之前：主檔已經進來了可以驗鎖，
而後面四個階段的表一建立就帶著 trigger，不必回頭補。

MCP 工具與前端畫面**不在本規格**，等資料進來再依實際查詢需求開。
唯一例外是階段 5 結束時要有 `gl_trial_balance`（試算表）工具，
否則「可以查帳」這個目標沒有可驗收的出口。

## 八、驗收

每個階段除了單元測試，都要跑：

1. `scripts/ch001_verify.py --src <目錄>` 五項全過（階段 5 後為六項，含餘額對帳）。
2. 匯入後的**筆數對帳**：DB 實際列數 == 來源列數 − 已知瑕疵筆數，差額必須為 0。
3. 階段 5 額外：DB 裡 `SUM(debit) == SUM(credit) == 8,502,130,448.00`。
   這個數字是硬指標，對不上就是匯入有問題。
4. **重跑冪等**：同一份來源跑第二次，`erp_audit` 不應新增任何 `update` 紀錄。

## 九、假設（換一種就會做出不同東西）

1. 舊系統造字（42 處）維持私用區佔位即可，不需要還原字形。
   → 若要還原，得跟原系統要造字檔，是另一件事。
2. 歷史資料只進 CTOS，不回寫同事的新 ERP。
3. 幣別只有 TWD（來源實測 `TPADGA` 第 20 欄只有一個值）。多幣別不做。
4. 人事薪資（`CMSMV`、`PALMT`、`PALML`–`PALMV` 等）不進 CTOS。
5. `TPABYA` 等系統設定表不進 CTOS。

## 十、待拍板

1. 品號要不要沿用舊碼。沿用則兩邊天然對得起來；重編要一張對照表，
   且須指定誰維護。（影響階段 1）
2. 客戶主檔歸 CTOS 之後，同事的新 ERP 要不要打 CTOS 的 `/api/parties` 取用。
3. `CH001_export` 那個共享槽含員工薪資與勞健保資料，建議來源端移出。
