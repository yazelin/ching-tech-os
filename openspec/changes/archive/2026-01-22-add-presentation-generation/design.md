# Design: AI 簡報生成功能

## Context

用戶透過 Line Bot 對話或 Web 介面，用自然語言描述簡報需求，系統自動生成 PowerPoint 簡報。此功能需要整合現有的 AI 服務、NAS 檔案系統，並新增簡報生成模組。

### 限制條件
- 使用現有的 Claude API 整合
- 簡報檔案需儲存於 NAS 以便分享
- MCP 工具需支援 Line Bot 對話流程

## Goals / Non-Goals

### Goals
- 用戶可透過自然語言描述生成簡報
- 支援多種簡報風格（專業、休閒、創意、極簡）
- 自動從 Pexels 配圖
- 簡報儲存於 NAS 並可透過 Line Bot 分享

### Non-Goals
- 不支援編輯已生成的簡報（MVP 階段）
- 不支援自訂模板上傳（未來擴充）
- 不支援 PDF 匯出（使用者可自行轉換）

## Decisions

### 1. 使用 Claude API 生成簡報大綱
- **決定**: 使用現有 Claude API 整合，不額外引入 Gemini
- **原因**: 系統已有 Claude 整合，減少依賴和維護成本
- **實作**: 透過 prompt 讓 Claude 輸出 JSON 格式的大綱結構

### 2. 使用 python-pptx 生成 PowerPoint
- **決定**: 使用 python-pptx 函式庫
- **原因**: 成熟穩定、純 Python、無需 Office 安裝
- **替代方案**: LibreOffice CLI（複雜度高）、Google Slides API（需額外帳號）

### 3. 使用 Pexels API 配圖
- **決定**: 使用 Pexels 免費圖庫 API
- **原因**: 免費、無浮水印、商用友好
- **注意**: 商用需標註圖片來源

### 4. 檔案儲存於 NAS
- **決定**: 簡報儲存於 `/mnt/nas/projects/ai-presentations/`
- **原因**: 便於分享、與現有檔案系統整合
- **清理策略**: 定期清理超過 30 天的檔案（手動或排程）

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Line Bot / Web                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 MCP Server (mcp_server.py)                   │
│                                                              │
│  generate_presentation(topic, num_slides, style, images)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              PresentationService (presentation_service.py)   │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ _generate_outline │  │ _fetch_pexels    │                 │
│  │   (Claude API)    │  │   (Pexels API)   │                 │
│  └──────────────────┘  └──────────────────┘                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ _create_slide (python-pptx)                           │   │
│  │  - _create_title_slide                                │   │
│  │  - _create_content_slide                              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    NAS Storage                               │
│           /mnt/nas/projects/ai-presentations/                │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **用戶請求**: "幫我做一份介紹 AI 應用的簡報，7 頁"
2. **MCP 工具呼叫**: `generate_presentation(topic="AI 應用", num_slides=7)`
3. **生成大綱**: Claude API 回傳 JSON 結構的簡報大綱
4. **配圖**: 根據每頁的 `image_keyword` 從 Pexels 下載圖片
5. **生成簡報**: python-pptx 建立 .pptx 檔案
6. **儲存**: 儲存至 NAS
7. **回傳**: 回傳檔案路徑，可用 `prepare_file_message` 發送給用戶

## Claude Prompt 設計

```
請為以下主題生成一份 {num_slides} 頁的簡報大綱，風格為 {style}。

主題：{topic}

請用 JSON 格式回傳，結構如下：
{
    "title": "簡報標題",
    "slides": [
        {
            "type": "title",  // title, content, two_column, image_focus
            "title": "標題",
            "subtitle": "副標題（選填）",
            "content": ["重點1", "重點2", "重點3"],
            "image_keyword": "搜尋圖片的關鍵字（英文）",
            "speaker_notes": "講者備註"
        }
    ]
}

第一頁必須是 title 類型。
每頁 content 最多 5 個重點。
image_keyword 用於搜尋圖庫，請用英文。

只回傳 JSON，不要其他文字。
```

## Risks / Trade-offs

| 風險 | 緩解措施 |
|------|---------|
| Claude 回傳非 JSON 格式 | 加入重試機制和 JSON 解析容錯 |
| Pexels API 配額限制 | 實作快取，相同關鍵字重用圖片 |
| 簡報檔案累積佔用空間 | 定期清理策略，檔名含時間戳 |
| 圖片下載失敗 | 容錯處理，跳過配圖繼續生成 |

## Open Questions

- 是否需要支援使用者上傳的圖片？（建議 Phase 2）
- 是否需要支援自訂公司模板？（建議 Phase 2）
- 是否需要支援圖表生成（matplotlib）？（建議 Phase 2）
