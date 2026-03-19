---
name: ai-assistant
description: AI 圖片生成、文件/簡報生成
allowed-tools: mcp__nanobanana__generate_image mcp__nanobanana__edit_image mcp__nanobanana__restore_image
  generate_md2ppt generate_md2doc download_web_image
metadata:
  ctos:
    requires_app: ai-assistant
    mcp_servers: nanobanana ching-tech-os github asana
---

【AI 圖片生成】
- mcp__nanobanana__generate_image: 根據文字描述生成圖片
  · prompt: 圖片描述（必填，使用英文描述效果較好）
    - 圖片風格、內容描述用英文
    - 圖片中若有文字，指定 "text in Traditional Chinese (zh-TW)" 並附上中文內容
    - 範例：「A beautiful sunrise with lotus flowers, with text in Traditional Chinese (zh-TW) saying '早安，祝你順利'」
  · files: 參考圖片路徑陣列（可選，用於以圖生圖）
  · resolution: 固定使用 "1K"
  · 生成後回傳 generatedFiles 陣列
  · ⚠️ 路徑轉換：回傳的 /tmp/.../nanobanana-output/xxx.jpg 要轉成 ai-images/xxx.jpg
  · ⚠️ 禁止自己寫 [FILE_MESSAGE:...] 標記！必須呼叫 prepare_file_message 工具
- mcp__nanobanana__edit_image: 編輯/修改現有圖片
  · file: 要編輯的圖片路徑（必填）
  · prompt: 編輯指示（英文描述）
  · resolution: 固定使用 "1K"

【圖片生成使用情境】
1. 純文字生圖：用戶說「畫一隻貓」
   → generate_image(prompt="a cute cat", resolution="1K")
2. 以圖生圖（用戶上傳的圖）：用戶回覆一張圖說「畫類似風格的狗」
   → 從 [回覆圖片: /tmp/...] 取得路徑
   → generate_image(prompt="a dog in similar style", files=["/tmp/..."], resolution="1K")
3. 編輯用戶上傳的圖：用戶回覆一張圖說「把背景改成藍色」
   → 從 [回覆圖片: /tmp/...] 取得路徑
   → edit_image(file="/tmp/...", prompt="change background to blue", resolution="1K")
4. 編輯剛才生成的圖：用戶說「把剛才那張圖的字改掉」
   → 用 get_message_attachments(days=1, file_type="image") 查找最近的圖片
   → 從結果中找到 ai-images/ 開頭的 NAS 路徑
   → edit_image(file="ai-images/xxx.jpg", prompt="...", resolution="1K")
   → ⚠️ 注意：edit_image 可能會大幅改變圖片，不只是改文字

【圖片發送流程】
1. 生成/編輯完成後，從 generatedFiles 取得路徑
2. 路徑轉換：/tmp/.../nanobanana-output/xxx.jpg → ai-images/xxx.jpg
3. 呼叫 prepare_file_message("ai-images/xxx.jpg")
4. 將回傳內容原封不動包含在回覆中
· ❌ 錯誤：自己寫 [FILE_MESSAGE:/tmp/...] ← 格式錯誤！
· ❌ 錯誤：用 Read 看圖後回覆「已完成」← 用戶看不到圖！

【AI 文件/簡報生成】
- generate_md2ppt: 儲存 MD2PPT 簡報並建立分享連結（可線上編輯並匯出 PPTX）
  · markdown_content: 已格式化的 MD2PPT markdown（必填，必須以 --- 開頭）
  · ⚠️ 你必須先根據下方格式規範產生完整 markdown，再傳入此工具
  · 回傳：分享連結 url 和 4 位數密碼 password
- generate_md2doc: 儲存 MD2DOC 文件並建立分享連結（可線上編輯並匯出 Word）
  · markdown_content: 已格式化的 MD2DOC markdown（必填，必須以 --- 開頭）
  · ⚠️ 你必須先根據下方格式規範產生完整 markdown，再傳入此工具
  · 回傳：分享連結 url 和 4 位數密碼 password

⚠️ 內容品質要求：
- 簡報內容要充實，每頁包含重點功能說明 + 實際使用案例或延伸用法
- 必須混合使用多種 layout（impact、two-column、grid、center），禁止整份簡報都用同一種
- 有數據比較的場景要善用圖表（chart-bar、chart-pie 等）
- 文件內容要結構完整，善用 Callouts 和表格增強可讀性

【MD2PPT 格式規範】
直接產生 Markdown 內容，不要包含 ``` 標記。

格式結構：
1. 全域 Frontmatter（檔案開頭必須有）：
   ---
   title: "簡報標題"
   author: "作者"
   bg: "#FFFFFF"
   transition: fade
   ---
   theme 可選：amber, midnight, academic, material
   transition 可選：slide, fade, zoom, none

2. 分頁符號：用 === 分隔頁面，前後必須有空行：
   （前一頁內容）

   ===

   （下一頁內容）

3. 每頁 Frontmatter（在 === 後，可設定 layout、bg、mesh 等）：
   ===

   ---
   layout: impact
   bg: "#EA580C"
   ---

   # 標題

4. Layout 選項與適用場景：
   · default — 標準頁面，一般內容
   · impact — 強調頁，適合開場、重點結論（大標題 + 副標題）
   · center — 置中頁，適合過場、章節分隔
   · grid — 網格，搭配 columns: 2，適合並列比較
   · two-column — 雙欄，用 :: right :: 分隔左右，適合功能+案例、問題+方案
   · quote — 引言頁，適合金句、客戶評價
   · alert — 警告/重點提示頁

5. 雙欄語法（two-column）— :: right :: 前後必須有空行：
   ### 左欄標題
   左欄內容

   :: right ::

   ### 右欄標題
   右欄內容

6. 圖表語法 — JSON 必須用雙引號，::: 前後必須有空行：
   ::: chart-bar { "title": "季度營收", "showValues": true }

   | 季度 | 營收 |
   | :--- | :--- |
   | Q1 | 150 |
   | Q2 | 200 |
   | Q3 | 280 |
   | Q4 | 350 |

   :::
   類型：chart-bar, chart-line, chart-pie, chart-area
   · 有數據比較時務必使用圖表，讓簡報更專業

7. Mesh 漸層背景：
   ---
   bg: mesh
   mesh:
     colors: ["#4158D0", "#C850C0", "#FFCC70"]
     seed: 12345
   ---

8. 備忘錄：<!-- note: 演講者筆記 -->

配色建議：
| 風格 | theme | mesh 配色 | 適用場景 |
|------|-------|----------|---------|
| 科技藍 | midnight | ["#0F172A","#1E40AF","#3B82F6"] | 科技、AI、軟體 |
| 溫暖橙 | amber | ["#FFF7ED","#FB923C","#EA580C"] | 行銷、活動、創意 |
| 清新綠 | material | ["#ECFDF5","#10B981","#047857"] | 環保、健康、自然 |
| 極簡灰 | academic | ["#F8FAFC","#94A3B8","#475569"] | 學術、報告、正式 |
| 電競紫 | midnight | ["#111827","#7C3AED","#DB2777"] | 遊戲、娛樂、年輕 |

設計原則：
1. 標題/重點頁（impact/center/quote）→ bg: mesh 或鮮明純色
2. 資訊頁（grid/two-column/default）→ 淺色（#F8FAFC）或深色（#1E293B）
3. 不要每頁都用 mesh，會視覺疲勞；建議只在開場、過場、結尾用 mesh
4. 圖表數據要合理，數值要有意義
5. ⚠️ 必須混合多種 layout：一份 10+ 頁簡報至少用 3 種以上不同 layout
6. 資訊密集的頁面用 two-column 或 grid，重點強調用 impact，概覽用 center

完整範例（展示多種 layout 混搭）：
---
title: "產品發表會"
author: "產品團隊"
bg: "#FFFFFF"
transition: fade
---

# 產品發表會
## 創新解決方案 2026

===

---
layout: impact
bg: mesh
mesh:
  colors: ["#0F172A", "#1E40AF", "#3B82F6"]
---

# 歡迎各位
## 今天我們將介紹全新產品線

===

---
layout: grid
columns: 2
bg: "#F8FAFC"
---

# 市場分析

### 現況
- 市場規模持續成長
- 客戶需求多元化
- 競爭日益激烈

### 機會
- 數位轉型趨勢
- AI 技術成熟
- 新興市場開拓

===

---
layout: two-column
bg: "#F8FAFC"
---

# 產品特色

### 核心功能
- 智能分析
- 即時監控
- 自動化流程

:: right ::

### 技術優勢
- 高效能運算
- 安全加密
- 彈性擴展

===

---
layout: grid
columns: 2
bg: "#F8FAFC"
---

# 業績表現

::: chart-bar { "title": "季度營收", "showValues": true }

| 季度 | 營收 |
| :--- | :--- |
| Q1 | 150 |
| Q2 | 200 |
| Q3 | 280 |
| Q4 | 350 |

:::

::: chart-pie { "title": "市場佔比" }

| 區域 | 佔比 |
| :--- | :--- |
| 北區 | 40 |
| 中區 | 35 |
| 南區 | 25 |

:::

===

---
layout: quote
bg: "#1E293B"
---

> 「這個產品讓我們的效率提升了 300%」
> — 某企業客戶

===

---
layout: center
bg: mesh
mesh:
  colors: ["#0F172A", "#1E40AF", "#3B82F6"]
---

# 感謝聆聽
## 歡迎提問

【MD2DOC 格式規範】
直接產生 Markdown 內容，不要包含 ``` 標記。

格式結構：
1. Frontmatter（必須）：
   ---
   title: "文件標題"
   author: "作者"
   header: true
   footer: true
   ---
2. 標題層級：只用 H1(#)、H2(##)、H3(###)，H4 以下改用 **粗體**
3. 目錄（可選）：
   [TOC]
   - 第一章 章節名稱 1
   - 第二章 章節名稱 2
4. 提示區塊（只支援三種）：
   > [!TIP]
   > **提示標題**
   > 提示內容，用於分享小撇步或最佳實踐。

   > [!NOTE]
   > **筆記標題**
   > 筆記內容，用於補充背景知識。

   > [!WARNING]
   > **警告標題**
   > 警告內容，用於重要注意事項。
5. 程式碼區塊：標註語言，:no-ln 隱藏行號，:ln 強制顯示
6. 行內樣式：**粗體**、*斜體*、<u>底線</u>、`行內碼`
   UI 按鈕：【確定】、快捷鍵：[Ctrl]+[S]、書名：『書名』
   智慧連結：[文字](URL) 匯出 Word 時自動生成 QR Code
7. 表格：標準 Markdown 表格語法
8. 分隔線：---
9. Mermaid 圖表（可選）：```mermaid ... ```

設計原則：
1. H1 大章節、H2 小節、H3 細項，結構清晰
2. 重要提示用 TIP，補充用 NOTE，警告用 WARNING
3. 程式碼區塊都要標註語言
4. 表格內容簡潔，複雜內容用列表
5. 善用 Callouts 區塊增強重點內容的可讀性

【文件/簡報使用流程】
1. 用戶要求做簡報/文件時，根據用戶需求和上方格式規範產生完整 markdown 內容
2. 將產生的 markdown 傳入 generate_md2ppt 或 generate_md2doc 的 markdown_content 參數
3. 回覆用戶分享連結和密碼

使用情境：
1. 用戶說「幫我做一份簡報介紹公司產品」
   → 根據 MD2PPT 格式規範產生包含 frontmatter、多頁內容的 markdown
   → 混合使用 impact（開場）、two-column（功能+案例）、grid（比較）、chart（數據）
   → generate_md2ppt(markdown_content="---\ntitle: \"公司產品介紹\"\n...")
2. 用戶說「幫我寫一份設備操作 SOP」
   → 根據 MD2DOC 格式規範產生包含 frontmatter、章節結構的 markdown
   → 善用 Callouts（TIP/WARNING）標注注意事項和操作要點
   → generate_md2doc(markdown_content="---\ntitle: \"設備操作 SOP\"\n...")

【回覆格式】
生成完成後，回覆用戶：
「已為您生成簡報/文件 👇
🔗 連結：{url}
🔑 密碼：{password}

連結有效期限 24 小時，開啟後可直接編輯並匯出。」

【意圖判斷】
- 「做簡報」「投影片」「PPT」「presentation」→ generate_md2ppt
- 「寫文件」「做報告」「說明書」「教學」「SOP」「document」→ generate_md2doc
- 如果不確定，詢問用戶是需要「簡報（投影片）」還是「文件（Word）」
