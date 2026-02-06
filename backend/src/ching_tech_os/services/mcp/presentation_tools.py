"""簡報與文件生成、列印前置處理 MCP 工具

包含：generate_presentation, generate_md2ppt, generate_md2doc, prepare_print_file
以及 MD2PPT/MD2DOC System Prompts 和格式修正函數
"""

import asyncio as _asyncio
import json
import re
import uuid
from pathlib import Path

from .server import mcp, logger, ensure_db_connection, check_mcp_tool_permission

# ============================================================
# MD2PPT / MD2DOC System Prompts
# ============================================================

MD2PPT_SYSTEM_PROMPT = '''你是專業的 MD2PPT-Evolution 簡報設計師。直接輸出 Markdown 代碼，不要包含解釋文字或 ``` 標記。

## 格式結構

### 1. 全域 Frontmatter（檔案開頭必須有）
```
---
title: "簡報標題"
author: "作者"
bg: "#FFFFFF"
transition: fade
---
```
- theme 可選：amber, midnight, academic, material
- transition 可選：slide, fade, zoom, none

### 2. 分頁符號
用 `===` 分隔頁面，前後必須有空行：
```
（前一頁內容）

===

（下一頁內容）
```

### 3. 每頁 Frontmatter（在 === 後）
```
===

---
layout: impact
bg: "#EA580C"
---

# 標題
```

### 4. Layout 選項
- `default`：標準頁面
- `impact`：強調頁（適合重點、開場）
- `center`：置中頁
- `grid`：網格（搭配 `columns: 2`）
- `two-column`：雙欄（用 `:: right ::` 分隔）
- `quote`：引言頁
- `alert`：警告/重點提示頁

### 5. 雙欄語法（two-column 或 grid）
`:: right ::` 前後必須有空行：
```
### 左欄標題
左欄內容

:: right ::

### 右欄標題
右欄內容
```

### 6. 圖表語法
JSON 必須用雙引號，前後必須有空行：
```
::: chart-bar { "title": "標題", "showValues": true }

| 類別 | 數值 |
| :--- | :--- |
| A | 100 |
| B | 200 |

:::
```
圖表類型：chart-bar, chart-line, chart-pie, chart-area

### 7. Mesh 漸層背景
```
---
bg: mesh
mesh:
  colors: ["#4158D0", "#C850C0", "#FFCC70"]
  seed: 12345
---
```

### 8. 背景圖片
```
---
bgImage: "https://images.unsplash.com/..."
---
```

### 9. 備忘錄（演講者筆記）
```
<!-- note:
這是演講者備忘錄，觀眾看不到。
-->
```

### 10. 對話模式
```
User ":: 這是用戶說的話（靠左）

AI ::" 這是 AI 回覆（靠右）

系統 :": 這是系統提示（置中）
```

### 11. 程式碼區塊
```typescript
const hello = "world";
```

## 配色建議

| 風格 | theme | mesh 配色 | 適用場景 |
|------|-------|----------|---------|
| 科技藍 | midnight | ["#0F172A", "#1E40AF", "#3B82F6"] | 科技、AI、軟體 |
| 溫暖橙 | amber | ["#FFF7ED", "#FB923C", "#EA580C"] | 行銷、活動、創意 |
| 清新綠 | material | ["#ECFDF5", "#10B981", "#047857"] | 環保、健康、自然 |
| 極簡灰 | academic | ["#F8FAFC", "#94A3B8", "#475569"] | 學術、報告、正式 |
| 電競紫 | midnight | ["#111827", "#7C3AED", "#DB2777"] | 遊戲、娛樂、年輕 |

## 設計原則

1. **標題/重點頁**（impact/center/quote）→ 用 `bg: mesh` 或鮮明純色
2. **資訊頁**（grid/two-column/default）→ 用淺色純色（#F8FAFC）或深色（#1E293B）
3. **不要每頁都用 mesh**，會視覺疲勞
4. **圖表數據要合理**，數值要有意義

## 完整範例

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
layout: center
bg: mesh
mesh:
  colors: ["#0F172A", "#1E40AF", "#3B82F6"]
---

# 感謝聆聽
## 歡迎提問
'''

MD2DOC_SYSTEM_PROMPT = '''你是專業的 MD2DOC-Evolution 技術文件撰寫專家。直接輸出 Markdown 代碼，不要包含解釋文字或 ``` 標記。

## 格式結構

### 1. Frontmatter（檔案開頭必須有）
```
---
title: "文件標題"
author: "作者名稱"
header: true
footer: true
---
```
- title 和 author 為必填欄位
- header/footer 控制頁首頁尾顯示

### 2. 標題層級
- 只支援 H1 (#)、H2 (##)、H3 (###)
- H4 以下請改用 **粗體文字** 或列表項目

### 3. 目錄（可選）
```
[TOC]
- 第一章 章節名稱 1
- 第二章 章節名稱 2
```

### 4. 提示區塊 (Callouts)
只支援三種類型：
```
> [!TIP]
> **提示標題**
> 提示內容，用於分享小撇步或最佳實踐。

> [!NOTE]
> **筆記標題**
> 筆記內容，用於補充背景知識。

> [!WARNING]
> **警告標題**
> 警告內容，用於重要注意事項。
```

### 5. 對話模式 (Chat Syntax)
```
系統 :": 這是置中的系統訊息。

AI助手 ":: 這是靠左的 AI 回覆，使用 `"::` 語法。

用戶 ::" 這是靠右的用戶訊息，使用 `::"` 語法。
```

### 6. 程式碼區塊
```typescript
// 預設顯示行號，右上角顯示語言名稱
const config = {
  name: "example"
};
```

隱藏行號（適合短設定檔）：
```json:no-ln
{
  "name": "config",
  "version": "1.0.0"
}
```

強制顯示行號：
```bash:ln
npm install
npm run dev
```

### 7. 行內樣式
- **粗體**：`**文字**` → **文字**
- *斜體*：`*文字*` → *文字*
- <u>底線</u>：`<u>文字</u>` → <u>底線</u>
- `行內程式碼`：反引號包覆
- UI 按鈕：`【確定】` → 【確定】
- 快捷鍵：`[Ctrl]` + `[S]` → [Ctrl] + [S]
- 書名/專案名：`『書名』` → 『書名』
- 智慧連結：`[文字](URL)` → 匯出 Word 時自動生成 QR Code

### 8. 表格
```
| 欄位一 | 欄位二 | 欄位三 |
| --- | --- | --- |
| 內容 | 內容 | 內容 |
```

### 9. 列表
- 第一項
- 第二項
  - 巢狀項目（縮排 2 空格）
  - 巢狀項目

### 10. 分隔線
```
---
```

### 11. Mermaid 圖表（可選）
```mermaid
graph TD
    A[開始] --> B{判斷}
    B -- Yes --> C[執行]
    B -- No --> D[結束]
```

## 設計原則

1. **結構清晰**：使用 H1 作為大章節，H2 作為小節，H3 作為細項
2. **善用 Callouts**：重要提示用 TIP，補充說明用 NOTE，警告事項用 WARNING
3. **程式碼標註語言**：所有程式碼區塊都要標註語言（typescript, json, bash, python 等）
4. **表格對齊**：表格內容盡量簡潔，複雜內容用列表呈現

## 完整範例

---
title: "系統操作手冊"
author: "技術團隊"
header: true
footer: true
---

# 系統操作手冊

[TOC]
- 第一章 系統介紹 1
- 第二章 基本操作 2
- 第三章 進階功能 3

## 1. 系統介紹

本系統是專為企業設計的管理平台，提供 **完整的資料管理** 與 *即時監控* 功能。

> [!TIP]
> **快速開始**
> 首次使用請先完成帳號設定，詳見第二章說明。

---

## 2. 基本操作

### 2.1 登入系統

1. 開啟瀏覽器，輸入系統網址
2. 輸入帳號密碼
3. 點擊 【登入】 按鈕

> [!NOTE]
> **帳號格式**
> 帳號格式為 `員工編號@公司代碼`，例如：`A001@acme`

### 2.2 常用快捷鍵

| 功能 | Windows | Mac |
| --- | --- | --- |
| 儲存 | [Ctrl] + [S] | [Cmd] + [S] |
| 搜尋 | [Ctrl] + [F] | [Cmd] + [F] |
| 列印 | [Ctrl] + [P] | [Cmd] + [P] |

---

## 3. 進階功能

### 3.1 API 整合

系統提供 RESTful API，可與外部系統整合：

```typescript
// 取得使用者資料
const response = await fetch('/api/users', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
```

設定檔範例：

```json:no-ln
{
  "apiUrl": "https://api.example.com",
  "timeout": 30000
}
```

> [!WARNING]
> **安全注意**
> API Token 請妥善保管，切勿分享給他人或提交到版本控制系統。

---

### 3.2 常見問題

系統 :": 以下是常見問題的對話範例。

用戶 ::" 我忘記密碼了，該怎麼辦？

客服 ":: 您可以點擊登入頁面的「忘記密碼」連結，系統會發送重設信件到您的註冊信箱。

---

更多資訊請參考『系統管理指南』或聯繫技術支援。
'''


# ============================================================
# 格式修正函數
# ============================================================


def fix_md2ppt_format(content: str) -> str:
    """
    自動修正 MD2PPT 常見格式問題

    修正項目：
    1. === 分頁符前後空行
    2. :: right :: 前後空行
    3. ::: chart-xxx 前後空行
    4. ::: 結束標記前空行
    5. JSON 單引號改雙引號
    6. 無效 theme 替換為 midnight
    7. 無效 layout 替換為 default
    8. 移除 ``` 標記
    """
    # 移除可能的 markdown 標記
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    # 有效的 theme 和 layout 值
    valid_themes = {"amber", "midnight", "academic", "material"}
    valid_layouts = {"default", "impact", "center", "grid", "two-column", "quote", "alert"}

    # 修正 theme 無效值
    def fix_theme(match):
        theme = match.group(1).strip('"\'')
        if theme not in valid_themes:
            return "theme: midnight"
        return match.group(0)

    content = re.sub(r'^theme:\s*(\S+)', fix_theme, content, flags=re.MULTILINE)

    # 修正 layout 無效值
    def fix_layout(match):
        layout = match.group(1).strip('"\'')
        if layout not in valid_layouts:
            return "layout: default"
        return match.group(0)

    content = re.sub(r'^layout:\s*(\S+)', fix_layout, content, flags=re.MULTILINE)

    # 修正圖表 JSON 中的單引號
    def fix_chart_json(match):
        prefix = match.group(1)  # ::: chart-xxx
        json_str = match.group(2)  # { ... }
        if json_str:
            # 嘗試修正單引號
            try:
                json.loads(json_str)
            except json.JSONDecodeError:
                # 嘗試將單引號替換為雙引號
                fixed_json = json_str.replace("'", '"')
                try:
                    json.loads(fixed_json)
                    return f"{prefix} {fixed_json}"
                except json.JSONDecodeError:
                    pass  # 無法修正，保持原樣
        return match.group(0)

    content = re.sub(
        r'^(:::[\s]*chart-\w+)\s*(\{[^}]+\})',
        fix_chart_json,
        content,
        flags=re.MULTILINE
    )

    # 修正空行問題
    lines = content.split('\n')
    result = []

    # 正則模式
    right_col_pattern = re.compile(r'^(\s*)::[\s]*right[\s]*::[\s]*$', re.IGNORECASE)
    page_break_pattern = re.compile(r'^[\s]*===[\s]*$')
    block_end_pattern = re.compile(r'^[\s]*:::[\s]*$')
    chart_start_pattern = re.compile(r'^[\s]*:::[\s]*chart', re.IGNORECASE)
    frontmatter_pattern = re.compile(r'^---\s*$')

    for i, line in enumerate(lines):
        stripped = line.strip()
        is_right_col = right_col_pattern.match(line)
        is_page_break = page_break_pattern.match(line)
        is_block_end = block_end_pattern.match(line)
        is_chart_start = chart_start_pattern.match(line)

        # 這些模式前面需要空行
        if is_right_col or is_page_break or is_block_end or is_chart_start:
            # 確保前面有空行（除非是檔案開頭或前一行是 frontmatter）
            if result and result[-1].strip() != '' and not frontmatter_pattern.match(result[-1]):
                result.append('')
            result.append(line)
        else:
            # 檢查前一行是否是需要後面空行的模式
            if result:
                prev_line = result[-1]
                need_blank = (
                    right_col_pattern.match(prev_line) or
                    page_break_pattern.match(prev_line) or
                    chart_start_pattern.match(prev_line) or
                    block_end_pattern.match(prev_line)
                )
                if need_blank and stripped != '':
                    result.append('')
            result.append(line)

    return '\n'.join(result)


def fix_md2doc_format(content: str) -> str:
    """
    自動修正 MD2DOC 常見格式問題

    修正項目：
    1. 移除 ``` 標記
    2. 確保有 frontmatter
    3. H4+ 標題轉換為粗體
    4. 修正 Callout 格式
    """
    # 移除可能的 markdown 標記
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    # 確保有 frontmatter（如果沒有就加上基本的）
    if not content.strip().startswith("---"):
        content = """---
title: "文件"
author: "AI Assistant"
---

""" + content

    # 修正 H4+ 標題為粗體
    def fix_heading(match):
        level = len(match.group(1))
        text = match.group(2).strip()
        if level >= 4:
            return f"**{text}**"
        return match.group(0)

    content = re.sub(r'^(#{4,})\s+(.+)$', fix_heading, content, flags=re.MULTILINE)

    # 修正 Callout 類型（只允許 TIP, NOTE, WARNING）
    valid_callouts = {"TIP", "NOTE", "WARNING"}

    def fix_callout(match):
        callout_type = match.group(1).upper()
        if callout_type not in valid_callouts:
            # 映射常見的錯誤類型
            mapping = {
                "INFO": "NOTE",
                "IMPORTANT": "WARNING",
                "CAUTION": "WARNING",
                "DANGER": "WARNING",
                "HINT": "TIP",
            }
            fixed_type = mapping.get(callout_type, "NOTE")
            return f"> [!{fixed_type}]"
        return match.group(0)

    content = re.sub(r'>\s*\[!(\w+)\]', fix_callout, content)

    return content


# ============================================================
# MCP 工具定義
# ============================================================


@mcp.tool()
async def generate_presentation(
    topic: str = "",
    num_slides: int = 5,
    theme: str = "uncover",
    include_images: bool = True,
    image_source: str = "pexels",
    outline_json: str | dict | None = None,
    output_format: str = "html",
) -> str:
    """
    生成簡報（HTML 或 PDF，使用 Marp）

    生成的簡報支援 HTML（瀏覽器直接查看）或 PDF（下載列印）格式。

    有兩種使用方式：

    方式一：只給主題，AI 自動生成大綱（較慢，約 30-60 秒）
        generate_presentation(topic="AI 在製造業的應用", num_slides=5)

    方式二：傳入完整大綱 JSON，直接製作簡報（推薦用於知識庫內容）
        1. 先用 search_knowledge / get_knowledge_item 查詢相關知識
        2. 根據知識內容組織大綱 JSON
        3. 呼叫 generate_presentation(outline_json="...")
        4. 用 create_share_link 產生分享連結回覆用戶

    Args:
        topic: 簡報主題（方式一必填，方式二可省略）
        num_slides: 頁數，預設 5 頁（範圍 2-20，方式一使用）
        theme: Marp 內建主題風格，可選：
            - uncover: 深色投影（深灰背景），適合晚間活動、影片風格（預設）
            - gaia: 暖色調（米黃/棕色背景），適合輕鬆場合
            - gaia-invert: 專業藍（深藍背景），適合正式提案、投影展示
            - default: 簡約白（白底黑字），適合技術文件、學術報告
        include_images: 是否自動配圖，預設 True
        image_source: 圖片來源，可選：
            - pexels: 從 Pexels 圖庫下載（預設，快速）
            - huggingface: 使用 Hugging Face FLUX AI 生成
            - nanobanana: 使用 nanobanana/Gemini AI 生成
        outline_json: 直接傳入大綱 JSON 字串，跳過 AI 生成步驟。格式範例：
            {
                "title": "簡報標題",
                "slides": [
                    {"type": "title", "title": "標題", "subtitle": "副標題"},
                    {"type": "content", "title": "第一章", "content": ["重點1", "重點2"], "image_keyword": "factory automation"}
                ]
            }
            type 類型：title（封面）、section（章節分隔）、content（標題+內容）
        output_format: 輸出格式，可選：
            - html: 網頁格式，可直接在瀏覽器查看（預設）
            - pdf: PDF 格式，可下載列印

    Returns:
        包含簡報資訊和 NAS 路徑的回應，可用於 create_share_link
    """
    from ...services.presentation import generate_html_presentation

    # 驗證：必須有 topic 或 outline_json
    if not topic and not outline_json:
        return "❌ 請提供 topic（主題）或 outline_json（大綱 JSON）"

    # 驗證頁數範圍
    if not outline_json:
        if num_slides < 2:
            num_slides = 2
        elif num_slides > 20:
            num_slides = 20

    # 驗證主題
    valid_themes = ["default", "gaia", "gaia-invert", "uncover"]
    if theme not in valid_themes:
        return (
            f"❌ 無效的主題：{theme}\n"
            f"可用主題：\n"
            f"  - gaia（專業藍）：正式提案、投影展示\n"
            f"  - gaia-invert（亮色藍）：列印、螢幕閱讀\n"
            f"  - default（簡約白）：技術文件、學術報告\n"
            f"  - uncover（深色投影）：晚間活動、影片風格"
        )

    # 驗證輸出格式
    valid_formats = ["html", "pdf"]
    if output_format not in valid_formats:
        return f"❌ 無效的輸出格式：{output_format}\n可用格式：html（網頁）、pdf（列印）"

    # 驗證圖片來源
    valid_image_sources = ["pexels", "huggingface", "nanobanana"]
    if image_source not in valid_image_sources:
        return f"❌ 無效的圖片來源：{image_source}\n可用來源：pexels（圖庫）、huggingface（AI）、nanobanana（Gemini）"

    # 將 dict 轉換為 JSON 字串
    import json as _json
    if isinstance(outline_json, dict):
        outline_json = _json.dumps(outline_json, ensure_ascii=False)

    try:
        result = await generate_html_presentation(
            topic=topic or "簡報",
            num_slides=num_slides,
            theme=theme,
            include_images=include_images,
            image_source=image_source,
            outline_json=outline_json,
            output_format=output_format,
        )

        theme_names = {
            "default": "簡約白",
            "gaia": "專業藍",
            "gaia-invert": "亮色藍",
            "uncover": "深色投影",
        }

        image_source_names = {
            "pexels": "Pexels 圖庫",
            "huggingface": "Hugging Face AI",
            "nanobanana": "Gemini AI",
        }

        format_names = {
            "html": "HTML（可直接在瀏覽器查看）",
            "pdf": "PDF（可下載列印）",
        }

        # 產生 NAS 檔案路徑（供 create_share_link 使用）
        nas_file_path = f"ctos://{result['nas_path']}"

        image_info = f"{'有（' + image_source_names.get(image_source, image_source) + '）' if include_images else '無'}"
        theme_display = theme_names.get(theme, theme)
        format_display = format_names.get(output_format, output_format)

        return (
            f"✅ 簡報生成完成！\n\n"
            f"📊 {result['title']}\n"
            f"・頁數：{result['slides_count']} 頁\n"
            f"・主題：{theme_display}\n"
            f"・配圖：{image_info}\n"
            f"・格式：{format_display}\n\n"
            f"📁 NAS 路徑：{nas_file_path}\n\n"
            f"💡 下一步：使用 create_share_link(resource_type=\"nas_file\", resource_id=\"{nas_file_path}\") 產生分享連結"
        )

    except Exception as e:
        logger.error(f"生成簡報失敗: {e}")
        return f"❌ 生成簡報時發生錯誤：{str(e)}\n請稍後重試或調整內容"


@mcp.tool()
async def generate_md2ppt(
    content: str,
    style: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    產生 MD2PPT 格式的簡報內容，並建立帶密碼保護的分享連結

    用戶說「做簡報」「投影片」「PPT」時呼叫此工具。
    與 generate_presentation（Marp HTML/PDF）不同，此工具產生可線上編輯的簡報。

    Args:
        content: 要轉換為簡報的內容或主題
        style: 風格需求（如：科技藍、簡約深色），不填則自動選擇
        ctos_user_id: CTOS 用戶 ID（從對話識別取得）

    Returns:
        分享連結和存取密碼
    """
    from ..claude_agent import call_claude
    from ..share import create_share_link
    from ...models.share import ShareLinkCreate

    await ensure_db_connection()

    # 組合 prompt
    style_hint = f"【風格需求】：{style}\n" if style else ""
    user_prompt = f"{style_hint}【內容】：\n{content}"

    try:
        logger.debug(f"generate_md2ppt: prompt_len={len(user_prompt)}")

        # 呼叫 Claude 產生內容
        response = await call_claude(
            prompt=user_prompt,
            model="sonnet",
            system_prompt=MD2PPT_SYSTEM_PROMPT,
            timeout=180,
        )

        if not response.success:
            logger.warning(f"generate_md2ppt: AI 失敗: {response.error}")
            return f"❌ AI 產生失敗：{response.error}"

        generated_content = response.message.strip()

        # 自動修正格式問題（不驗證、不重試）
        generated_content = fix_md2ppt_format(generated_content)

        # 建立分享連結
        share_data = ShareLinkCreate(
            resource_type="content",
            content=generated_content,
            content_type="text/markdown",
            filename="presentation.md2ppt",
            expires_in="24h",
        )

        share_link = await create_share_link(
            data=share_data,
            created_by="linebot-ai",
        )

        # 產生 MD2PPT 連結
        from ...config import settings
        md2ppt_url = f"{settings.md2ppt_url}/?shareToken={share_link.token}"

        # 同時保存檔案到 NAS，以便加入知識庫附件
        file_id = str(uuid.uuid4())[:8]
        filename = f"presentation-{file_id}.md2ppt"

        # 保存到 ai-generated 目錄
        save_dir = Path(settings.ctos_mount_path) / "linebot" / "files" / "ai-generated"

        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename
        save_path.write_text(generated_content, encoding="utf-8")

        # 產生可用於 add_attachments_to_knowledge 的路徑
        attachment_path = f"ai-generated/{filename}"

        return f"""✅ 簡報產生成功！

🔗 開啟連結：{md2ppt_url}
🔑 存取密碼：{share_link.password}

📎 檔案路徑：{attachment_path}
（可用 add_attachments_to_knowledge 加入知識庫附件）

⏰ 連結有效期限：24 小時
💡 開啟後可直接編輯並匯出為 PPT"""

    except Exception as e:
        logger.error(f"generate_md2ppt 錯誤: {e}")
        return f"❌ 產生簡報時發生錯誤：{str(e)}"


@mcp.tool()
async def generate_md2doc(
    content: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    產生 MD2DOC 格式的文件內容，並建立帶密碼保護的分享連結

    用戶說「寫文件」「做報告」「說明書」「教學」「SOP」時呼叫此工具。

    Args:
        content: 要轉換為文件的內容
        ctos_user_id: CTOS 用戶 ID（從對話識別取得）

    Returns:
        分享連結和存取密碼
    """
    from ..claude_agent import call_claude
    from ..share import create_share_link
    from ...models.share import ShareLinkCreate

    await ensure_db_connection()

    user_prompt = f"請將以下內容轉換為 MD2DOC 格式的文件：\n\n{content}"

    try:
        logger.debug(f"generate_md2doc: prompt_len={len(user_prompt)}")

        # 呼叫 Claude 產生內容
        response = await call_claude(
            prompt=user_prompt,
            model="sonnet",
            system_prompt=MD2DOC_SYSTEM_PROMPT,
            timeout=180,
        )

        if not response.success:
            logger.warning(f"generate_md2doc: AI 失敗: {response.error}")
            return f"❌ AI 產生失敗：{response.error}"

        generated_content = response.message.strip()

        # 自動修正格式問題（不驗證、不重試）
        generated_content = fix_md2doc_format(generated_content)

        # 建立分享連結
        share_data = ShareLinkCreate(
            resource_type="content",
            content=generated_content,
            content_type="text/markdown",
            filename="document.md2doc",
            expires_in="24h",
        )

        share_link = await create_share_link(
            data=share_data,
            created_by="linebot-ai",
        )

        # 產生 MD2DOC 連結
        from ...config import settings
        md2doc_url = f"{settings.md2doc_url}/?shareToken={share_link.token}"

        # 同時保存檔案到 NAS，以便加入知識庫附件
        file_id = str(uuid.uuid4())[:8]
        filename = f"document-{file_id}.md2doc"

        # 保存到 ai-generated 目錄
        save_dir = Path(settings.ctos_mount_path) / "linebot" / "files" / "ai-generated"

        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename
        save_path.write_text(generated_content, encoding="utf-8")

        # 產生可用於 add_attachments_to_knowledge 的路徑
        attachment_path = f"ai-generated/{filename}"

        return f"""✅ 文件產生成功！

🔗 開啟連結：{md2doc_url}
🔑 存取密碼：{share_link.password}

📎 檔案路徑：{attachment_path}
（可用 add_attachments_to_knowledge 加入知識庫附件）

⏰ 連結有效期限：24 小時
💡 開啟後可直接編輯並匯出為 Word"""

    except Exception as e:
        logger.error(f"generate_md2doc 錯誤: {e}")
        return f"❌ 產生文件時發生錯誤：{str(e)}"


# ============================================================
# 列印前置處理工具
# ============================================================

# 需透過 LibreOffice 轉 PDF 的格式
OFFICE_EXTENSIONS = {
    ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt",
    ".odt", ".ods", ".odp",
}

# printer-mcp 可直接列印的格式
PRINTABLE_EXTENSIONS = {
    ".pdf", ".txt", ".log", ".csv",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp",
}

# 允許存取的路徑前綴
ALLOWED_PRINT_PATHS = ("/mnt/nas/", "/tmp/ctos/")


@mcp.tool()
async def prepare_print_file(
    file_path: str,
    ctos_user_id: int | None = None,
) -> str:
    """將虛擬路徑轉換為可列印的絕對路徑，Office 文件會自動轉為 PDF

    【重要】此工具只負責路徑轉換和格式轉換，不會執行列印。
    取得回傳的絕對路徑後，請接著呼叫 printer-mcp 的 print_file 工具進行實際列印。

    列印完整流程：
    1. 呼叫 prepare_print_file 取得絕對路徑
    2. 呼叫 printer-mcp 的 print_file(file_path=回傳的路徑) 進行列印

    file_path 可以是：
    - 虛擬路徑：ctos://knowledge/attachments/report.pdf、shared://projects/...
    - 絕對路徑：/mnt/nas/ctos/...

    支援的檔案格式：
    - 直接可印：PDF、純文字（.txt, .log, .csv）、圖片（PNG, JPG, JPEG, GIF, BMP, TIFF, WebP）
    - 自動轉 PDF：Office 文件（.docx, .xlsx, .pptx, .doc, .xls, .ppt, .odt, .ods, .odp）
    """
    await ensure_db_connection()
    if ctos_user_id:
        allowed, error_msg = await check_mcp_tool_permission("prepare_print_file", ctos_user_id)
        if not allowed:
            return f"❌ {error_msg}"

    # 路徑轉換：虛擬路徑 → 絕對路徑
    try:
        from ..path_manager import path_manager

        if "://" in file_path:
            actual_path = Path(path_manager.to_filesystem(file_path))
        else:
            actual_path = Path(file_path)
    except Exception as e:
        return f"❌ 路徑解析失敗：{str(e)}"

    # 取得實際絕對路徑（解析 symlink）
    try:
        actual_path = actual_path.resolve()
    except Exception:
        pass

    # 安全檢查
    actual_str = str(actual_path)
    if ".." in file_path:
        return "❌ 不允許的路徑（禁止路徑穿越）"

    if not any(actual_str.startswith(prefix) for prefix in ALLOWED_PRINT_PATHS):
        return "❌ 不允許存取此路徑的檔案。僅允許 NAS 和暫存目錄中的檔案。"

    # 檢查檔案存在
    if not actual_path.exists():
        return f"❌ 檔案不存在：{file_path}"

    if not actual_path.is_file():
        return f"❌ 路徑不是檔案：{file_path}"

    # 檢查檔案格式
    ext = actual_path.suffix.lower()

    if ext in PRINTABLE_EXTENSIONS:
        return f"""✅ 檔案已準備好，請使用 printer-mcp 的 print_file 工具列印：

📄 檔案：{actual_path.name}
📂 絕對路徑：{actual_str}

下一步：呼叫 print_file(file_path="{actual_str}")"""

    if ext in OFFICE_EXTENSIONS:
        # Office 文件轉 PDF
        try:
            tmp_dir = Path("/tmp/ctos/print")
            tmp_dir.mkdir(parents=True, exist_ok=True)

            proc_convert = await _asyncio.create_subprocess_exec(
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", str(tmp_dir), str(actual_path),
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
            )
            _, stderr_convert = await proc_convert.communicate()

            if proc_convert.returncode != 0:
                error_msg = stderr_convert.decode().strip() if stderr_convert else "未知錯誤"
                return f"❌ 檔案轉換 PDF 失敗：{error_msg}"

            pdf_name = actual_path.stem + ".pdf"
            tmp_pdf = tmp_dir / pdf_name

            if not tmp_pdf.exists():
                return "❌ 檔案轉換 PDF 後找不到輸出檔案"

            pdf_str = str(tmp_pdf)
            return f"""✅ Office 文件已轉換為 PDF，請使用 printer-mcp 的 print_file 工具列印：

📄 原始檔案：{actual_path.name}
📄 轉換後 PDF：{pdf_name}
📂 絕對路徑：{pdf_str}

下一步：呼叫 print_file(file_path="{pdf_str}")"""

        except FileNotFoundError:
            return "❌ 找不到 libreoffice 指令，無法轉換 Office 文件。"
        except Exception as e:
            return f"❌ 轉換 PDF 時發生錯誤：{str(e)}"

    supported = ", ".join(sorted(PRINTABLE_EXTENSIONS | OFFICE_EXTENSIONS))
    return f"❌ 不支援的檔案格式：{ext}\n支援的格式：{supported}"
