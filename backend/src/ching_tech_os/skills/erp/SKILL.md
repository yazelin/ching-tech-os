---
name: erp
description: 往來對象（供應商／客戶）、物料庫存與採購單
allowed-tools: find_party get_party create_party update_party add_party_contact
  add_party_address update_party_contact delete_party_contact
  update_party_address delete_party_address merge_parties summarize_party
  extract_party_from_document
  find_item get_item create_item update_item summarize_item
  get_stock adjust_stock transfer_stock
  create_purchase_order get_purchase_order list_purchase_orders
  receive_purchase_order cancel_purchase_order
  extract_purchase_order_from_document
metadata:
  ctos:
    requires_app: [vendor-management, inventory-management]
    mcp_servers: ching-tech-os
---

【往來與物料】
公司的供應商、客戶、物料、庫存與採購單都在 CTOS 自己的資料庫，用下面這些工具操作。

■ 三條規矩（違反會做出錯的資料）
1. **先 find 再寫**：要建或改之前，先 find_party／find_item 確認有沒有既有的。
   建重複主檔比查不到更麻煩。
2. **多個候選要問人**：工具回 `need_confirmation: true` 與 `candidates` 時，
   把候選唸給使用者聽讓他挑，不要自己選第一個。
3. **寫完回報**：寫入類工具會回 `audit_id`，回覆時說清楚「我建了／改了什麼」，
   並附上單號或名稱。使用者要反悔時，這些都是可追的。

■ 往來對象（供應商／客戶合併成一張主檔，同一家可以同時是兩者）
- find_party(query, role?)：名稱、簡稱、別名、聯絡人、電話、統編都可以丟進來。
  role 給 "supplier"、"customer" 或 "both"（同時是供應商與客戶）可縮小範圍。
- get_party(party_id | name)：完整資料，含聯絡人、地址、近期採購單、相關專案、
  知識庫條目數。
- create_party(name, is_supplier?, is_customer?, tax_id?, contacts?, addresses?, ...)
  · contacts：`[{"name":"陳先生","phone":"03-1234567","is_primary":true}]`
  · addresses：`[{"label":"公司","address":"桃園市…","is_primary":true}]`
- update_party(party_id | name, fields)：fields 是要改的欄位 dict。
- add_party_contact / add_party_address：補聯絡人與地址。
- update_party_contact(contact_id, party_id | party_name, fields) /
  update_party_address(address_id, party_id | party_name, fields)：
  改既有聯絡人或地址；fields 設 `is_primary: true` 會把同一家其他筆降級。
- delete_party_contact(contact_id, party_id | party_name) /
  delete_party_address(address_id, party_id | party_name)：
  刪掉聯絡人或地址；刪掉主要那筆不會自動指派新主要，要改就再呼叫一次 update。
- merge_parties(keep_id, drop_id)：發現重複主檔時用；drop 的資料會掛到 keep，
  名稱變成 keep 的別名。**合併不可逆，先問人。**
- summarize_party(party_id | name)：回答「這家最近有什麼往來」用這個。

■ 物料與庫存
- find_item(query)：料號、品名、別名、規格。
- get_item(item_id | code)：主檔＋各倉餘額＋最近異動＋預設供應商。
- create_item(code, name, spec?, unit?, default_supplier?, purchase_price?, aliases?)
  · code 是唯一的料號，建之前務必 find_item。
- update_item(item_id | code, fields)
- get_stock(item?, warehouse?)：查餘額。
- adjust_stock(item, warehouse, qty_delta, reason, note?)：正數入庫、負數出庫。
  reason 用 receipt／issue／adjust／import。**餘額不能變負數**，會被擋下來。
- transfer_stock(item, from_warehouse, to_warehouse, qty)：倉別調撥。
- summarize_item(item_id | code)

■ 採購
- create_purchase_order(supplier, lines, project?, expected_date?, notes?)
  · lines：`[{"item":"料號或品名","qty":10,"unit_price":25}]`
  · supplier 與 item 都吃名稱，解析不到會回候選要你確認。
  · 單號 PO-YYYYMM-NNN 自動產生，回覆時要把單號告訴使用者。
- get_purchase_order(po)：po 可以是單號或 UUID。
- list_purchase_orders(supplier?, status?, project?, since?)
  · status：draft／ordered／partial／received／cancelled
- receive_purchase_order(po, lines? | all=true, warehouse?)：收貨入庫，
  會自動更新已收量與單頭狀態（全收 received、部分 partial）。
- cancel_purchase_order(po, reason)：取消不是刪除；已收過貨的不能取消。

■ 名片、詢價單、報價單
1. 先用讀圖或 convert_pdf_to_images 把內容看出來（這一步是你自己做）。
2. extract_party_from_document(file_path, name, tax_id?, phone?, …) 或
   extract_purchase_order_from_document(file_path, supplier, lines, …)
   把讀到的欄位丟進去，工具會整理成草稿並比對重複主檔。
3. 有 duplicates／candidates 就先問人，確認後再呼叫 create_party 或
   create_purchase_order 真的寫進去。

■ 不做的事
會計分錄、發票、稅務、報價與銷售單據、BOM、多幣別都不在這個模組，
使用者問到這些就說明目前系統沒有做。
