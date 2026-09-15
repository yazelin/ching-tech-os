#!/usr/bin/env python3
"""主檔欄位的人工定案，供 `ch001_schema.py` 併入輸出。

自動推導（畫面標籤、可驗證規則、外鍵、ERPNext 交叉驗證）涵蓋所有表，
但主檔有些欄位規則驗不出來（簡稱、聯絡人、備註），需要人工判定。
**每一條都附依據與等級**，讓讀的人自己決定信到什麼程度：

- `verified` — 有硬證據（檢查碼、值域全覆蓋、交叉驗證高命中）
- `inferred` — 有間接證據（子字串關係、格式分佈、填充率對比）
- `guess`    — 只依同類系統慣例，**請自行確認**

格式：(表, 欄位) -> (中文名, 依據說明, 等級)
"""

COLUMNS: dict[tuple[str, str], tuple[str, str, str]] = {
    # ---- TPADGA 廠商主檔（673 列 × 58 欄）----
    ("TPADGA", "DGA001"): ("廠商代號", "唯一鍵；對 ERPNext 廠商名稱前綴命中 89.2%", "verified"),
    ("TPADGA", "DGA002"): ("簡稱", "95.7% 是 DGA003 的子字串；平均長 2.2 對 9.1", "verified"),
    ("TPADGA", "DGA003"): ("全名", "正規化後對 ERPNext supplier_name 命中 90.6%", "verified"),
    ("TPADGA", "DGA004"): ("廠商類型", "值域 100% 落在 TPADGC（廠商類型表，6 列）", "verified"),
    ("TPADGA", "DGA005"): ("統一編號", "411/411 通過台灣統編檢查碼；對 ERPNext tax_id 命中 91.7%", "verified"),
    ("TPADGA", "DGA007"): ("負責業務員", "值域 100% 落在 TPADBA（使用者資料）", "verified"),
    ("TPADGA", "DGA008"): ("聯絡人一", "95.7% 符合人名格式；與 DGA009/010 三欄同型", "inferred"),
    ("TPADGA", "DGA009"): ("聯絡人二", "70.7% 符合人名格式", "inferred"),
    ("TPADGA", "DGA010"): ("聯絡人三", "59.2% 符合人名格式", "inferred"),
    ("TPADGA", "DGA011"): ("電話", "填充 94%，電話格式；三個電話欄中填充最高", "inferred"),
    ("TPADGA", "DGA012"): ("電話二", "填充 4%，電話格式", "inferred"),
    ("TPADGA", "DGA013"): ("傳真", "填充 76%，電話格式；依同類系統慣例排在電話之後", "guess"),
    ("TPADGA", "DGA014"): ("email", "90.8% 含 @ 且符合 email 格式", "verified"),
    ("TPADGA", "DGA015"): ("備註", "內容雜項（營業時間、替代聯絡方式），無固定格式", "inferred"),
    ("TPADGA", "DGA016"): ("通訊地址郵遞區號", "245/245 是合法台灣郵遞區號；與 DGA017 成對", "verified"),
    ("TPADGA", "DGA017"): ("通訊地址", "338/339 含地址關鍵字；填充 50%", "verified"),
    ("TPADGA", "DGA018"): ("公司地址郵遞區號", "535/536 是合法台灣郵遞區號；填充 80%", "verified"),
    ("TPADGA", "DGA019"): ("公司地址", "645/645 含地址關鍵字；填充 96%，是主要地址", "verified"),
    ("TPADGA", "DGA020"): ("幣別", "唯一值 TWD", "verified"),
    ("TPADGA", "DGA028"): ("帳期天數", "值域 {0, 90, 120}", "inferred"),
    ("TPADGA", "DGA030"): ("付款條件天數", "值域 {0,30,35,60,65,90,95,120,125}", "inferred"),
    ("TPADGA", "DGA050"): ("建檔人", "代號落在 TPADBA；與 DGA051 成對", "verified"),
    ("TPADGA", "DGA051"): ("建檔時間", "時間戳，673 筆全相異", "verified"),
    ("TPADGA", "DGA052"): ("異動人", "代號落在 TPADBA；與 DGA053 成對", "verified"),
    ("TPADGA", "DGA053"): ("最後異動時間", "時間戳", "verified"),

    # ---- TPADFA 客戶主檔（440 列 × 114 欄）：與廠商同型，欄位位置不同 ----
    ("TPADFA", "DFA001"): ("客戶代號", "唯一鍵；對 ERPNext 客戶名稱前綴交叉驗證", "verified"),
    ("TPADFA", "DFA002"): ("簡稱", "與 DFA003 的長度關係同 TPADGA 的簡稱／全名", "inferred"),
    ("TPADFA", "DFA003"): ("全名", "正規化後對 ERPNext customer_name 交叉驗證", "verified"),
    ("TPADFA", "DFA005"): ("統一編號", "通過台灣統編檢查碼", "verified"),

    # ---- TPADEA 商品主檔（25,159 列 × 71 欄）----
    ("TPADEA", "DEA001"): ("品號", "唯一鍵", "verified"),
    ("TPADEA", "DEA002"): ("品名", "舊系統畫面標籤（TPADPB）明載", "verified"),
    ("TPADEA", "DEA003"): ("單位", "22 種值，全中文短字串", "inferred"),
    ("TPADEA", "DEA005"): ("商品分類", "值域 100% 落在 TPADED（商品分類表）", "verified"),
    ("TPADEA", "DEA008"): ("預設倉庫", "值域 100% 落在 TPADDA（倉庫資料）", "verified"),
    ("TPADEA", "DEA010"): ("預設供應商", "值域 99% 落在 TPADGA（廠商資料）", "verified"),
    ("TPADEA", "DEA024"): ("零售價", "舊系統畫面標籤（TPADPB）明載", "verified"),
    ("TPADEA", "DEA025"): ("會員價", "舊系統畫面標籤（TPADPB）明載", "verified"),

    # ---- CRMIKG 聯絡人（3,455 列 × 30 欄）----
    ("CRMIKG", "IKG001"): ("對象類別", "1=客戶（1,331 筆）、3=廠商（2,019 筆），與 IKG002 交叉驗證", "verified"),
    ("CRMIKG", "IKG002"): ("往來對象代號", "97.4% 落在客戶∪廠商代號；由 IKG001 決定指向哪張表", "verified"),
    ("CRMIKG", "IKG005"): ("姓名", "對 ERPNext Contact 姓名命中 86.9%", "verified"),
    ("CRMIKG", "IKG008"): ("行動電話", "電話格式，填充 33%", "inferred"),
    ("CRMIKG", "IKG010"): ("電話", "電話格式，填充 9%", "inferred"),
    ("CRMIKG", "IKG011"): ("公司電話", "電話格式，填充 79%，是主要號碼", "inferred"),
    ("CRMIKG", "IKG012"): ("email", "email 格式", "verified"),
}
