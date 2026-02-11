"""平台無關的 Agent 工具 Prompt 管理

從 linebot_agents.py 抽離的平台無關邏輯。
各平台的 Agent 設定可引用這裡的工具說明 Prompt 區塊。

優先從 SkillManager 載入 prompt，找不到時 fallback 到硬編碼。
"""

import logging

logger = logging.getLogger("bot.agents")

# 嘗試載入 SkillManager
try:
    from ...skills import get_skill_manager
    _HAS_SKILL_MANAGER = True
except (ImportError, ModuleNotFoundError):
    _HAS_SKILL_MANAGER = False


# ============================================================
# 按 App 權限分類的工具說明 Prompt 區塊
# ============================================================

# 專案管理工具說明（對應 app: project-management）
# 此功能已遷移至 ERPNext，以下為 ERPNext 操作指引
PROJECT_TOOLS_PROMPT = """【專案管理】（使用 ERPNext）
專案管理功能已遷移至 ERPNext 系統，請使用 ERPNext MCP 工具操作：

【查詢專案】
- mcp__erpnext__list_documents: 查詢專案列表
  · doctype: "Project"
  · fields: ["name", "project_name", "status", "expected_start_date", "expected_end_date"]
  · filters: 可依狀態過濾，如 '{"status": "Open"}'
- mcp__erpnext__get_document: 取得專案詳情
  · doctype: "Project"
  · name: 專案名稱

【任務管理】（對應原本的里程碑）
- mcp__erpnext__list_documents: 查詢專案任務
  · doctype: "Task"
  · filters: '{"project": "專案名稱"}'
- mcp__erpnext__create_document: 新增任務
  · doctype: "Task"
  · data: {"subject": "任務名稱", "project": "專案名稱", "status": "Open"}

【專案操作範例】
1. 查詢所有進行中的專案：
   mcp__erpnext__list_documents(doctype="Project", filters='{"status":"Open"}')
2. 查詢特定專案的任務：
   mcp__erpnext__list_documents(doctype="Task", filters='{"project":"專案名稱"}')
3. 更新任務狀態為完成：
   mcp__erpnext__update_document(doctype="Task", name="TASK-00001", data='{"status":"Completed"}')

【直接操作 ERPNext】
若需要更複雜的操作，請直接在 ERPNext 系統操作：http://ct.erp"""

# 物料/庫存管理工具說明（對應 app: inventory）
# 此功能已遷移至 ERPNext，以下為 ERPNext 操作指引
INVENTORY_TOOLS_PROMPT = """【物料/庫存管理】（使用 ERPNext）
物料與庫存管理功能已遷移至 ERPNext 系統，請使用 ERPNext MCP 工具操作：

【查詢物料】
- mcp__erpnext__list_documents: 查詢物料列表
  · doctype: "Item"
  · fields: ["item_code", "item_name", "item_group", "stock_uom"]
  · filters: 可依類別過濾，如 '{"item_group": "零件"}'
- mcp__erpnext__get_document: 取得物料詳情
  · doctype: "Item"
  · name: 物料代碼

【查詢庫存】
- mcp__erpnext__get_stock_balance: 查詢即時庫存
  · item_code: 物料代碼（可選）
  · warehouse: 倉庫名稱（可選）
- mcp__erpnext__get_stock_ledger: 查詢庫存異動記錄
  · item_code: 物料代碼（可選）
  · warehouse: 倉庫名稱（可選）
  · limit: 回傳筆數（預設 50）

【庫存異動】
- mcp__erpnext__create_document: 建立 Stock Entry
  · doctype: "Stock Entry"
  · data: 包含 stock_entry_type、items 等欄位
  · stock_entry_type 常用值：
    - "Material Receipt"：收料入庫
    - "Material Issue"：發料出庫
    - "Material Transfer"：倉庫間調撥

【廠商/客戶管理】
⭐ 首選工具（一次取得完整資料，支援別名搜尋）：
- mcp__erpnext__get_supplier_details: 查詢廠商完整資料
  · keyword: 關鍵字搜尋（支援別名，如「健保局」、「104人力銀行」）
  · 回傳：名稱、地址、電話、傳真、聯絡人
- mcp__erpnext__get_customer_details: 查詢客戶完整資料
  · keyword: 關鍵字搜尋（支援別名）
  · 回傳：名稱、地址、電話、傳真、聯絡人

進階操作：
- mcp__erpnext__list_documents: 查詢列表（doctype: "Supplier" 或 "Customer"）
- mcp__erpnext__create_document: 新增廠商/客戶

【操作範例】
1. 查詢庫存：
   mcp__erpnext__get_stock_balance(item_code="CTOS-ABC123")
2. 查詢物料清單：
   mcp__erpnext__list_documents(doctype="Item", fields='["item_code","item_name","stock_uom"]')
3. 收料入庫：
   mcp__erpnext__create_document(doctype="Stock Entry", data='{"stock_entry_type":"Material Receipt","items":[{"item_code":"CTOS-ABC123","qty":10,"t_warehouse":"Stores - 擎添工業"}]}')

【直接操作 ERPNext】
若需要更複雜的操作（如採購單、批號管理），請直接在 ERPNext 系統操作：http://ct.erp"""

# 知識庫工具說明（對應 app: knowledge-base）
KNOWLEDGE_TOOLS_PROMPT = """【知識庫】
- search_knowledge: 搜尋知識庫（輸入關鍵字，回傳標題列表）
  · 傳入 ctos_user_id 可搜尋個人知識（從【對話識別】取得）
  · 若未傳入，只能搜尋全域知識
- get_knowledge_item: 取得知識庫文件完整內容（輸入 kb_id，如 kb-001）
- update_knowledge_item: 更新知識庫文件，可更新：
  · title（標題）、content（內容）、category（分類）
  · type（類型：note/spec/guide）
  · topics（主題標籤列表）、projects（關聯專案列表）
  · roles（適用角色列表）、level（層級：beginner/intermediate/advanced）
  · scope（範圍：global 全域/personal 個人）- 傳入 ctos_user_id 可修改為個人知識
- delete_knowledge_item: 刪除知識庫文件
- add_note: 新增筆記到知識庫（自動判斷範圍）
  · 傳入 line_user_id、ctos_user_id（從【對話識別】取得）
  · 個人聊天且已綁定帳號 → 個人知識（只有自己能編輯）
  · 未綁定帳號 → 全域知識

【知識庫附件】
- add_note_with_attachments: 新增筆記並加入附件（自動判斷範圍）
  · attachments: NAS 路徑列表
  · 傳入 line_user_id、ctos_user_id（從【對話識別】取得）
  · 範圍判斷同 add_note
- add_attachments_to_knowledge: 為現有知識新增附件（輸入 kb_id、attachments，可選 descriptions 設定描述）
- get_knowledge_attachments: 查詢知識庫的附件列表（索引、檔名、說明）
- read_knowledge_attachment: 讀取知識庫附件的內容（文字檔案如 json/yaml/md/txt 會返回內容）
  · kb_id: 知識 ID
  · attachment_index: 附件索引（預設 0）
  · max_chars: 最大字元數（預設 15000）
  · 若知識內容提到「參考附件」或有附件，用此工具讀取附件內容
  · ⚠️ 重要：不要指定 max_chars，使用預設值即可！指定更大的值會導致 token 超限錯誤
- update_knowledge_attachment: 更新附件說明（輸入 kb_id、attachment_index、description）"""

# 檔案管理工具說明（對應 app: file-manager）
FILE_TOOLS_PROMPT = """【NAS 共用檔案】
- search_nas_files: 搜尋 NAS 共享檔案（搜尋範圍包含：專案資料、線路圖）
  · keywords: 多個關鍵字用逗號分隔（AND 匹配，大小寫不敏感）
  · file_types: 檔案類型過濾，如 pdf,xlsx,dwg
  · 範例：search_nas_files(keywords="亦達,layout", file_types="pdf")
  · 結果路徑格式：shared://projects/... 或 shared://circuits/...
  · ⚠️ 注意：查找「最近的圖片」或「剛才的圖」請用 get_message_attachments，不要用此工具
- get_nas_file_info: 取得 NAS 檔案詳細資訊（大小、修改時間）
- prepare_file_message: 準備檔案訊息（推薦使用）
  · file_path: 檔案完整路徑（從 search_nas_files 取得）
  · 圖片（jpg/png/gif 等）< 10MB 會直接顯示在回覆中
  · 其他檔案會以連結形式顯示
  · 重要：工具返回的 [FILE_MESSAGE:...] 標記必須原封不動包含在回應中，系統會自動處理
  · 注意：圖片/檔案會顯示在文字下方，請用 👇 而非 👆

【PDF 轉圖片】
- convert_pdf_to_images: 將 PDF 轉換為圖片（方便在 Line 中預覽）
  · pdf_path: PDF 檔案路徑（用戶上傳的 /tmp/bot-files/... 或 NAS 路徑）
  · pages: 要轉換的頁面
    - "0"：只查詢頁數，不轉換
    - "1"：只轉換第 1 頁
    - "1-3"：轉換第 1 到 3 頁
    - "all"：轉換全部（預設）
  · output_format: png（預設）或 jpg
  · dpi: 解析度，預設 150
  · 回傳 JSON 包含 total_pages、converted_pages、images（圖片路徑陣列）

【PDF 轉圖片使用流程】
1. 用戶上傳 PDF 並要求轉圖片時：
   - 先用 convert_pdf_to_images(pdf_path="...", pages="0") 查詢頁數
   - 若只有 1 頁：直接 convert_pdf_to_images(pdf_path="...", pages="1") 轉換
   - 若有多頁：詢問用戶「這份 PDF 共 X 頁，要轉換哪幾頁？」
2. 用戶回覆要轉換的範圍後，根據回覆設定 pages 參數
3. 轉換完成後，對每張圖片呼叫 prepare_file_message 發送
4. 若用戶明確說「轉成圖片」或「全部」，可直接轉換不用詢問
5. NAS 上的 PDF 轉換：先用 search_nas_files 找到 PDF，再轉換"""

# 基礎工具說明（不需特定權限）
BASE_TOOLS_PROMPT = """【對話附件管理】
- get_message_attachments: 查詢對話中的附件（圖片、檔案），可指定 days 天數範圍
  · 用於查找「最近的圖片」、「剛才生成的圖」、「之前傳的檔案」等
  · 比 search_nas_files 更快，且會自動過濾該對話的附件
- summarize_chat: 取得群組聊天記錄摘要

【分享連結】
- create_share_link: 產生公開分享連結（不顯示在回覆中，只給連結）
  · resource_type: "nas_file"、"knowledge"、"project" 或 "project_attachment"
  · resource_id: 檔案路徑、知識ID、專案UUID 或 附件UUID
  · expires_in: 1h/24h/7d（預設 24h）"""

# AI 文件生成工具說明（對應 app: ai-assistant）
AI_DOCUMENT_TOOLS_PROMPT = """【AI 文件/簡報生成】
- generate_md2ppt: 儲存 MD2PPT 簡報並建立分享連結（可線上編輯並匯出 PPTX）
  · markdown_content: 已格式化的 MD2PPT markdown（必填，必須以 --- 開頭）
  · ⚠️ 你必須先根據下方格式規範產生完整 markdown，再傳入此工具
  · 回傳：分享連結 url 和 4 位數密碼 password
- generate_md2doc: 儲存 MD2DOC 文件並建立分享連結（可線上編輯並匯出 Word）
  · markdown_content: 已格式化的 MD2DOC markdown（必填，必須以 --- 開頭）
  · ⚠️ 你必須先根據下方格式規範產生完整 markdown，再傳入此工具
  · 回傳：分享連結 url 和 4 位數密碼 password

⚠️ 內容品質要求：
- 每頁包含重點功能 + 實際案例或延伸用法，內容要充實
- 必須混合使用多種 layout（impact、two-column、grid、center），禁止整份都用同一種
- 有數據比較時善用圖表（chart-bar、chart-pie）

【MD2PPT 格式規範】
格式結構：
1. 全域 Frontmatter（開頭必須有）：--- title/author/bg/transition ---
   theme 可選：amber, midnight, academic, material
2. 分頁：=== 前後必須有空行
3. 每頁 Frontmatter：layout/bg/mesh 等
4. Layout 選項與適用場景：
   · default — 標準頁面
   · impact — 強調頁（開場、重點結論，大標題+副標題）
   · center — 置中頁（過場、章節分隔）
   · grid — 網格（搭配 columns: 2，並列比較）
   · two-column — 雙欄（功能+案例、問題+方案）
   · quote — 引言頁（金句、客戶評價）
   · alert — 警告/重點提示頁
5. 雙欄語法（:: right :: 前後必須有空行）：
   ### 左欄標題
   左欄內容

   :: right ::

   ### 右欄標題
   右欄內容
6. 圖表（::: 前後必須有空行，JSON 雙引號）：
   ::: chart-bar { "title": "季度營收", "showValues": true }

   | 季度 | 營收 |
   | :--- | :--- |
   | Q1 | 150 |
   | Q2 | 200 |

   :::
   類型：chart-bar, chart-line, chart-pie, chart-area
7. Mesh 背景：bg: mesh + mesh: { colors: [...], seed: 數字 }
配色：科技藍=midnight+["#0F172A","#1E40AF","#3B82F6"]、溫暖橙=amber+["#FFF7ED","#FB923C","#EA580C"]、清新綠=material+["#ECFDF5","#10B981","#047857"]、極簡灰=academic+["#F8FAFC","#94A3B8","#475569"]、電競紫=midnight+["#111827","#7C3AED","#DB2777"]
設計原則：
- 重點頁用 mesh/鮮明色、資訊頁用淺色(#F8FAFC)/深色(#1E293B)
- 不要每頁 mesh（只在開場、過場、結尾用）
- ⚠️ 10+頁簡報至少用 3 種以上不同 layout，禁止全部用同一種
- 資訊頁用 two-column/grid，重點用 impact，有數據用 chart

【MD2DOC 格式規範】
格式結構：
1. Frontmatter（必須）：--- title/author/header:true/footer:true ---
2. 標題：只用 H1-H3，H4+ 改用 **粗體**
3. 目錄：[TOC] + 章節列表
4. 提示區塊：> [!TIP] / > [!NOTE] / > [!WARNING]
5. 程式碼區塊標註語言，:no-ln 隱藏行號
6. 行內：**粗體**、*斜體*、<u>底線</u>、【按鈕】、[Ctrl]+[S]、『書名』
設計原則：H1 大章節/H2 小節/H3 細項、善用 Callouts 標注重點、程式碼標註語言

【文件/簡報使用流程】
1. 根據用戶需求和上方格式規範產生完整 markdown
2. 傳入 generate_md2ppt/generate_md2doc 的 markdown_content 參數
3. 回覆連結和密碼

【意圖判斷】
- 「做簡報」「投影片」「PPT」→ generate_md2ppt
- 「寫文件」「做報告」「說明書」「SOP」→ generate_md2doc"""

# AI 圖片生成工具說明（對應 app: ai-assistant）
AI_IMAGE_TOOLS_PROMPT = """【AI 圖片生成】
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
· ❌ 錯誤：用 Read 看圖後回覆「已完成」← 用戶看不到圖！"""


# 列印工具說明（對應 app: printer）
PRINTER_TOOLS_PROMPT = """【列印功能】
列印分兩步驟，先轉換路徑再列印：

步驟 1 - 準備檔案（ching-tech-os 工具）：
- prepare_print_file: 將虛擬路徑轉換為絕對路徑，Office 文件自動轉 PDF
  · file_path: 檔案路徑（必填）
    - 虛擬路徑：ctos://knowledge/attachments/report.pdf、shared://projects/...
    - 絕對路徑：/mnt/nas/ctos/...
  · 回傳：可列印的絕對路徑

步驟 2 - 實際列印（printer-mcp 工具）：
- mcp__printer__print_file: 將檔案送至印表機列印
  · file_path: 步驟 1 回傳的絕對路徑（必填）
  · printer: 印表機名稱（可選，預設使用系統預設）
  · copies: 份數（可選，預設 1）
  · page_size: 紙張大小（可選，A3/A4/A5/B4/B5/Letter/Legal）
  · orientation: 方向（可選，portrait/landscape）
  · color_mode: 色彩模式（可選，gray/color，預設 gray。除非用戶要求彩色列印，否則一律用 gray）
- mcp__printer__list_printers: 查詢可用印表機
- mcp__printer__printer_status: 查詢印表機狀態
- mcp__printer__cancel_job: 取消列印工作

⚠️ 重要：不要跳過步驟 1 直接呼叫 printer-mcp！
  虛擬路徑（ctos://、shared://）必須先經過 prepare_print_file 轉換。
  只有當你已經有絕對路徑（/mnt/nas/...）時才能直接用 printer-mcp。

【支援的檔案格式】
- 直接列印：PDF、純文字（.txt, .log, .csv）、圖片（PNG, JPG, JPEG, GIF, BMP, TIFF, WebP）
- 自動轉 PDF：Office 文件（.docx, .xlsx, .pptx, .doc, .xls, .ppt, .odt, .ods, .odp）

【列印使用情境】
1. 用戶說「把知識庫的報告印出來」
   → search_knowledge("報告") 找到檔案路徑
   → prepare_print_file(file_path="ctos://knowledge/...")
   → mcp__printer__print_file(file_path="回傳的絕對路徑")
2. 用戶說「印 3 份 A3 橫式」
   → prepare_print_file(file_path=...)
   → mcp__printer__print_file(file_path=..., copies=3, page_size="A3", orientation="landscape")
3. 用戶說「列出印表機」
   → mcp__printer__list_printers()（不需要步驟 1）"""


# ============================================================
# 動態 Prompt 生成函數
# ============================================================

# App ID 與 Prompt 區塊的對應
APP_PROMPT_MAPPING: dict[str, str] = {
    "project-management": PROJECT_TOOLS_PROMPT,
    "inventory-management": INVENTORY_TOOLS_PROMPT,
    "knowledge-base": KNOWLEDGE_TOOLS_PROMPT,
    "file-manager": FILE_TOOLS_PROMPT,
    "ai-assistant": AI_IMAGE_TOOLS_PROMPT + "\n\n" + AI_DOCUMENT_TOOLS_PROMPT,
    "printer": PRINTER_TOOLS_PROMPT,
}


async def generate_tools_prompt(
    app_permissions: dict[str, bool],
    is_group: bool = False,
) -> str:
    """根據使用者權限動態生成工具說明 prompt

    優先從 SkillManager 載入，找不到 skill 時 fallback 到硬編碼。

    Args:
        app_permissions: 使用者的 App 權限設定（app_id -> bool）
        is_group: 是否為群組對話（群組使用精簡版）

    Returns:
        組合後的工具說明 prompt
    """
    # 優先使用 SkillManager
    if _HAS_SKILL_MANAGER:
        try:
            sm = get_skill_manager()
            result = await sm.generate_tools_prompt(app_permissions, is_group)
            if result:
                return result
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"SkillManager 載入失敗，使用 fallback: {e}")

    # 嘗試注入 Script Tools prompt
    script_prompt = await _generate_script_tools_prompt(app_permissions)

    # Fallback: 硬編碼 prompt
    sections: list[str] = []

    # 基礎工具（不需特定權限）
    sections.append(BASE_TOOLS_PROMPT)

    # 根據權限添加各功能模組的工具說明
    for app_id, prompt_section in APP_PROMPT_MAPPING.items():
        if app_permissions.get(app_id, False):
            sections.append(prompt_section)

    result = "\n\n".join(sections)

    # 附加 Script Tools prompt
    if script_prompt:
        result += "\n\n" + script_prompt

    return result


async def _generate_script_tools_prompt(
    app_permissions: dict[str, bool],
) -> str:
    """根據使用者權限生成 Script Tools prompt"""
    if not _HAS_SKILL_MANAGER:
        return ""

    try:
        sm = get_skill_manager()
        skills = await sm.get_skills_for_user(app_permissions)

        lines = []
        for skill in skills:
            if not skill.scripts:
                continue
            scripts_info = await sm.get_scripts_info(skill.name)
            if not scripts_info:
                continue

            lines.append(f"\n{skill.name}:")
            for s in scripts_info:
                desc = s["description"] or f"執行 {skill.name} 的腳本 {s['name']}"
                lines.append(f"  - {s['name']}: {desc}")
            lines.append(
                f'  用法：run_skill_script(skill="{skill.name}", '
                f'script="<script_name>", input="...")'
            )

        if not lines:
            return ""

        return (
            "【Script Tools】\n"
            "以下 skill 提供可執行的 script，使用 run_skill_script 工具呼叫："
            + "\n".join(lines)
        )
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"生成 Script Tools prompt 失敗: {e}")
        return ""


def generate_usage_tips_prompt(
    app_permissions: dict[str, bool],
    is_group: bool = False,
) -> str:
    """根據使用者權限動態生成使用說明 prompt

    Args:
        app_permissions: 使用者的 App 權限設定
        is_group: 是否為群組對話

    Returns:
        使用說明 prompt
    """
    tips: list[str] = []

    # 專案相關流程（已遷移至 ERPNext）
    if app_permissions.get("project-management", False):
        tips.extend([
            "1. 專案管理已遷移至 ERPNext，使用 mcp__erpnext__list_documents(doctype='Project') 查詢專案",
            "2. 使用 mcp__erpnext__list_documents(doctype='Task', filters='{\"project\":\"專案名稱\"}') 查詢任務",
            "3. 複雜操作請引導用戶直接在 ERPNext 系統操作：http://ct.erp",
        ])

    # 知識庫相關流程
    if app_permissions.get("knowledge-base", False):
        tips.extend([
            f"{len(tips)+1}. 查詢知識庫時，先用 search_knowledge 找到文件 ID，再用 get_knowledge_item 取得完整內容",
            f"{len(tips)+1}. 用戶要求「記住」或「記錄」某事時，使用 add_note 新增筆記，傳入 line_user_id 和 ctos_user_id",
            f"{len(tips)+1}. 用戶要求修改或更新知識時，使用 update_knowledge_item",
            f"{len(tips)+1}. 用戶要求將圖片加入知識庫時，先用 get_message_attachments 查詢附件，再用 add_note_with_attachments 加入",
        ])

    # 庫存相關流程（已遷移至 ERPNext）
    if app_permissions.get("inventory-management", False):
        tips.extend([
            f"{len(tips)+1}. 庫存管理已遷移至 ERPNext，使用 mcp__erpnext__get_stock_balance 查詢庫存",
            f"{len(tips)+1}. 使用 mcp__erpnext__list_documents(doctype='Item') 查詢物料清單",
            f"{len(tips)+1}. 收料/發料請引導用戶在 ERPNext 建立 Stock Entry：http://ct.erp",
        ])

    # 檔案相關流程
    if app_permissions.get("file-manager", False):
        tips.extend([
            f"{len(tips)+1}. 用戶要求找專案檔案時，用 search_nas_files 搜尋，找到後用 prepare_file_message 準備發送",
        ])

    if not tips:
        return ""

    return "使用工具的流程：\n" + "\n".join(tips)


# ============================================================
# 硬編碼工具白名單（fallback 用）
# ============================================================

_FALLBACK_TOOLS: dict[str | None, list[str]] = {
    # requires_app=None（base，所有人都有）
    None: ["Read"],
    # 各 app 對應的外部 MCP 工具
    "ai-assistant": [
        "mcp__nanobanana__generate_image",
        "mcp__nanobanana__edit_image",
        "mcp__nanobanana__restore_image",
    ],
    "printer": [
        "mcp__printer__print_file",
        "mcp__printer__list_printers",
        "mcp__printer__printer_status",
        "mcp__printer__cancel_job",
        "mcp__printer__print_test_page",
    ],
    "inventory-management": [
        "mcp__erpnext__list_documents",
        "mcp__erpnext__get_document",
        "mcp__erpnext__create_document",
        "mcp__erpnext__update_document",
        "mcp__erpnext__delete_document",
        "mcp__erpnext__submit_document",
        "mcp__erpnext__cancel_document",
        "mcp__erpnext__run_report",
        "mcp__erpnext__get_count",
        "mcp__erpnext__get_list_with_summary",
        "mcp__erpnext__run_method",
        "mcp__erpnext__search_link",
        "mcp__erpnext__list_doctypes",
        "mcp__erpnext__get_doctype_meta",
        "mcp__erpnext__get_stock_balance",
        "mcp__erpnext__get_stock_ledger",
        "mcp__erpnext__get_item_price",
        "mcp__erpnext__make_mapped_doc",
        "mcp__erpnext__get_party_balance",
        "mcp__erpnext__get_supplier_details",
        "mcp__erpnext__get_customer_details",
        "mcp__erpnext__upload_file",
        "mcp__erpnext__upload_file_from_url",
        "mcp__erpnext__list_files",
        "mcp__erpnext__download_file",
        "mcp__erpnext__get_file_url",
    ],
    "project-management": [
        "mcp__erpnext__list_documents",
        "mcp__erpnext__get_document",
        "mcp__erpnext__create_document",
        "mcp__erpnext__update_document",
        "mcp__erpnext__delete_document",
        "mcp__erpnext__submit_document",
        "mcp__erpnext__cancel_document",
        "mcp__erpnext__run_report",
        "mcp__erpnext__get_count",
        "mcp__erpnext__get_list_with_summary",
        "mcp__erpnext__run_method",
        "mcp__erpnext__search_link",
        "mcp__erpnext__list_doctypes",
        "mcp__erpnext__get_doctype_meta",
        "mcp__erpnext__make_mapped_doc",
        "mcp__erpnext__upload_file",
        "mcp__erpnext__upload_file_from_url",
        "mcp__erpnext__list_files",
        "mcp__erpnext__download_file",
        "mcp__erpnext__get_file_url",
    ],
}


async def get_tools_for_user(
    app_permissions: dict[str, bool],
) -> list[str]:
    """根據使用者權限動態產生外部 MCP 工具白名單

    優先從 SkillManager 載入，失敗時 fallback 到硬編碼列表。
    回傳的是「外部 MCP 工具」（如 nanobanana、printer、erpnext）和
    特殊工具（如 Read），不包含 ching-tech-os 內建 MCP 工具。

    Args:
        app_permissions: 使用者的 App 權限設定（app_id -> bool）

    Returns:
        去重後的工具名稱列表
    """
    # 優先使用 SkillManager
    if _HAS_SKILL_MANAGER:
        try:
            sm = get_skill_manager()
            tools = await sm.get_tool_names(app_permissions)
            if tools:
                # 去重（多個 skill 可能有重複工具）
                return list(dict.fromkeys(tools))
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"SkillManager 取得工具列表失敗，使用 fallback: {e}")

    # Fallback: 硬編碼工具列表
    tools: list[str] = []
    for app_id, app_tools in _FALLBACK_TOOLS.items():
        # 基底工具 (app_id=None) 任何人都有，其他工具則需對應權限
        if app_id is None or app_permissions.get(app_id, False):
            tools.extend(app_tools)
    # 去重
    return list(dict.fromkeys(tools))


async def get_mcp_servers_for_user(
    app_permissions: dict[str, bool],
) -> set[str] | None:
    """根據使用者權限取得需要載入的 MCP server 集合

    優先從 SkillManager 載入，失敗時回傳 None（載入全部）。

    Args:
        app_permissions: 使用者的 App 權限設定（app_id -> bool）

    Returns:
        需要載入的 MCP server 名稱集合，None 表示載入全部（fallback）
    """
    if _HAS_SKILL_MANAGER:
        try:
            sm = get_skill_manager()
            servers = await sm.get_required_mcp_servers(app_permissions)
            if servers:
                return servers
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"SkillManager 取得 MCP servers 失敗，將載入全部: {e}")
    return None
