# Design: Line Bot PDF 轉圖片功能

## Context
用戶使用 CAD 軟體繪製工程圖後，通常會輸出成 PDF 格式。在 Line 上查看 PDF 需要下載後用其他 App 開啟，體驗不佳。將 PDF 轉換成圖片可以讓用戶直接在 Line 的對話視窗中預覽。

### 主要使用情境
1. **即時上傳轉換**：用戶在 Line 上傳 PDF，要求 AI 轉成圖片
2. **NAS 檔案轉換**：用戶指定 NAS 上的 PDF 路徑，要求 AI 轉換並發送

### 現有資源
- **PyMuPDF 已安裝**：`pyproject.toml` 中已有 `PyMuPDF>=1.24.0`
- **現有程式碼**：`document_reader.py` 已使用 PyMuPDF 讀取 PDF 文字

## Goals / Non-Goals

### Goals
- 用戶可以在 Line 上傳 PDF 後，透過自然語言請求轉換成圖片
- 用戶可以指定 NAS 上的 PDF 進行轉換
- 轉換後的圖片可以直接在 Line 中預覽
- 支援多頁 PDF，每頁轉換成一張圖片

### Non-Goals
- 不實作 PDF 編輯功能
- 不支援加密 PDF（第一版）
- 不支援即時預覽（先轉換完成再發送）

## Decisions

### Decision 1: 使用 PyMuPDF 進行轉換

**選擇**：使用現有的 PyMuPDF 套件

**原因**：
- **已安裝**：不需要新增任何依賴
- **速度快**：比 pdf2image + poppler 快 3-10 倍
- **無外部依賴**：不需要 poppler 或其他系統套件
- **現有程式碼**：`document_reader.py` 已使用，團隊熟悉

### Decision 2: 擴展 document_reader.py

**選擇**：在 `document_reader.py` 新增 `convert_pdf_to_images()` 函式

**原因**：
- 與現有 PDF 處理邏輯放在一起，便於維護
- 可以複用現有的錯誤處理類別（`PasswordProtectedError` 等）

**實作範例**：
```python
def convert_pdf_to_images(
    file_path: str,
    output_dir: str,
    dpi: int = 150,
    output_format: str = "png",
    max_pages: int = 20
) -> list[str]:
    """
    將 PDF 轉換為圖片

    Returns:
        圖片路徑列表
    """
    with fitz.open(file_path) as doc:
        if doc.needs_pass:
            raise PasswordProtectedError("此文件有密碼保護")

        images = []
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)

        for i, page in enumerate(doc):
            if i >= max_pages:
                break

            pix = page.get_pixmap(matrix=mat)
            output_path = f"{output_dir}/page-{i + 1}.{output_format}"
            pix.save(output_path)
            images.append(output_path)

        return images
```

### Decision 3: 轉換後檔案儲存位置

**選擇**：儲存到 NAS 的 linebot 目錄下

**路徑結構**：
```
/mnt/nas/ctos/linebot/files/pdf-converted/{date}/{uuid}/
├── page-1.png
├── page-2.png
└── ...
```

**原因**：
- 與現有的 Line Bot 檔案儲存邏輯一致
- 可以使用現有的 `prepare_file_message` 機制發送

### Decision 4: MCP 工具設計

**工具名稱**：`convert_pdf_to_images`

**參數**：
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| pdf_path | string | ✓ | PDF 檔案路徑（NAS 或暫存路徑） |
| output_format | string | | 輸出格式：png（預設）、jpg |
| dpi | int | | 解析度：預設 150 |
| pages | string | | 要轉換的頁面，如 "1"、"1-3"、"1,3,5"，預設 "all" |
| max_pages | int | | 最大頁數限制：預設 20 |

**回傳**：
```json
{
  "success": true,
  "total_pages": 5,
  "converted_pages": 3,
  "images": [
    "/mnt/nas/ctos/linebot/files/pdf-converted/2026-01-15/abc123/page-1.png",
    ...
  ],
  "message": "已將第 1-3 頁轉換為圖片（共 5 頁）"
}
```

### Decision 5: 多頁 PDF 互動流程

**原則**：先告知頁數，讓用戶決定要轉換多少頁

**流程**：
1. AI 收到轉換請求時，先呼叫 `convert_pdf_to_images` 但設定 `pages="0"`（只取得頁數資訊）
2. 若 PDF **只有 1 頁**：直接轉換並發送
3. 若 PDF **有多頁**：詢問用戶「這份 PDF 共有 X 頁，要轉換哪幾頁？（如：全部、前 3 頁、第 1 頁）」
4. 用戶回覆後，AI 根據回覆設定 `pages` 參數進行轉換

**原因**：
- CAD 工程圖通常只有 1 頁，可直接轉換
- 多頁文件（如規格書）讓用戶選擇，避免浪費時間和空間
- 提升用戶體驗，給予控制權

### Decision 6: 專案附件 PDF 轉換支援

**問題**：用戶可能想轉換專案管理中的 PDF 附件，但 `get_project_attachments` 原本不回傳路徑

**解決方案**：修改 `get_project_attachments` 回傳 `storage_path` 欄位

**修改後輸出格式**：
```
【工程圖.pdf】
  類型：application/pdf
  大小：1.2 MB
  說明：Layout 設計圖
  路徑：nas://projects/xxx/工程圖.pdf  ← 新增
  ID：abc123
```

**工作流程**：
1. 用戶：「把亦達專案的 layout.pdf 轉成圖片」
2. AI 呼叫 `get_project_attachments` 取得附件列表和路徑
3. AI 使用路徑呼叫 `convert_pdf_to_images(pdf_path="nas://...")`
4. 轉換完成後用 `prepare_file_message` 發送

### Decision 7: 統一 nas:// 路徑處理

**問題**：`read_document` 原本只支援 `/mnt/nas/projects/` 下的路徑，無法讀取專案附件（存放在 `/mnt/nas/ctos/projects/attachments/`）

**解決方案**：擴展 `read_document` 支援 `nas://` 路徑格式

**路徑轉換規則**：
- `nas://linebot/files/...` → `/mnt/nas/ctos/linebot/files/...`
- `nas://projects/attachments/...` → `/mnt/nas/ctos/projects/attachments/...`
- 相對路徑（如 `亦達光學/xxx.pdf`）→ `/mnt/nas/projects/亦達光學/xxx.pdf`

**安全檢查**：擴展為允許 `/mnt/nas/` 下的所有路徑（原本只允許 `/mnt/nas/projects/`）

## Risks / Trade-offs

### Risk 1: 大型 PDF 轉換時間
**風險**：頁數多或解析度高的 PDF 轉換可能耗時較長
**緩解**：
- 設定最大頁數限制（預設 20 頁）
- AI 回覆時先告知「正在轉換中」

### Risk 2: 儲存空間
**風險**：轉換後的圖片會佔用 NAS 空間
**緩解**：
- 可設定定期清理機制（如 7 天後刪除）
- 與現有的 Line Bot 檔案清理機制整合

## Migration Plan
此功能為新增功能，無需資料遷移。

## Open Questions
1. 轉換後的圖片保留多久？是否需要定期清理機制？
2. 是否需要支援指定轉換特定頁面（如只轉換第 1-3 頁）？
