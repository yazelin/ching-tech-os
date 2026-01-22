# Design: 簡報設計師 AI Agent

## Context

目前簡報生成功能使用 9 種預設風格（professional、casual、creative 等），雖然配色專業，但設計較為單調，缺乏：
- 裝飾元素（底線、形狀）
- 版面變化（標題位置、圖片位置）
- 根據內容智慧調整的能力

用戶希望 AI 能像專業設計師一樣，根據簡報的「內容」、「對象」、「場景」來決定最適合的視覺設計。

## Goals / Non-Goals

### Goals
- 讓 AI 能根據情境智慧設計簡報風格
- 支援更豐富的視覺元素（裝飾、版面變化）
- 設計規格存入 CTOS 系統，可透過後台調整
- 保持向下相容，原有功能不受影響

### Non-Goals
- 不實作複雜的動畫效果
- 不支援自訂圖片模板
- 不實作即時預覽功能（Phase 3）

## Decisions

### Decision 1: design_json 規格

設計師輸出的 JSON 結構：

```json
{
  "design": {
    "colors": {
      "background": "#0D1117",
      "background_gradient": null,
      "title": "#58A6FF",
      "subtitle": "#A371F7",
      "text": "#C9D1D9",
      "bullet": "#38A169",
      "accent": "#F97316"
    },
    "typography": {
      "title_font": "Noto Sans TC",
      "title_size": 44,
      "title_bold": true,
      "body_font": "Noto Sans TC",
      "body_size": 20,
      "body_bold": false
    },
    "layout": {
      "title_align": "left",
      "title_position": "top",
      "content_columns": 1,
      "image_position": "right",
      "image_size": "medium"
    },
    "decorations": {
      "title_underline": true,
      "title_underline_color": "#58A6FF",
      "title_underline_width": 3,
      "accent_bar_left": false,
      "accent_bar_color": "#A371F7",
      "page_number": true,
      "page_number_position": "bottom-right"
    }
  },
  "slides": [
    {
      "type": "title",
      "title": "簡報標題",
      "subtitle": "副標題",
      "image_keyword": "technology abstract"
    },
    {
      "type": "content",
      "title": "第一章",
      "content": ["重點1", "重點2", "重點3"],
      "image_keyword": "business meeting",
      "layout_override": null
    }
  ]
}
```

**Rationale**:
- 將設計規格與內容分離，便於獨立調整
- 支援每頁覆寫版面設定（`layout_override`）
- 所有顏色使用 hex code，便於 AI 生成和解析

### Decision 2: 設計師 Prompt 架構

設計師 prompt 需要考量的因素：

| 因素 | 影響 | 範例 |
|------|------|------|
| 內容類型 | 整體風格 | 技術文件→極簡；行銷→創意 |
| 簡報對象 | 正式程度 | 客戶→專業；內部→輕鬆 |
| 展示場景 | 背景色/字體大小 | 投影→深色大字；螢幕→明亮 |
| 品牌調性 | 配色方向 | 科技→藍紫；環保→綠色 |
| 頁數 | 資訊密度 | 少頁→內容豐富；多頁→精簡 |

**Prompt 輸入**:
```
內容摘要：[知識庫內容/主題描述]
簡報對象：[客戶/內部/投資人/技術團隊...]
展示場景：[投影/線上會議/列印/平板...]
品牌/產業：[科技/製造/環保/奢華...]
頁數限制：[5頁]
特殊需求：[用戶額外要求]
```

**Prompt 輸出**: 完整的 design_json

### Decision 3: 字型相容性

由於 PowerPoint 在不同系統上的字型支援不同，採用以下策略：

| 優先級 | 中文字型 | 英文字型 | 說明 |
|--------|----------|----------|------|
| 1 | Noto Sans TC | Noto Sans | 跨平台開源字型 |
| 2 | 微軟正黑體 | Arial | Windows 預設 |
| 3 | PingFang TC | Helvetica | macOS 預設 |

設計師可指定字型，但 python-pptx 會自動 fallback 到系統可用字型。

### Decision 4: 裝飾元素實作

| 元素 | 實作方式 | 備註 |
|------|----------|------|
| 標題底線 | Shape (Line) | 在標題下方加入線條 |
| 側邊裝飾條 | Shape (Rectangle) | 在左側加入色塊 |
| 頁碼 | TextBox | 在指定位置加入文字 |
| 漸層背景 | Background Fill Gradient | python-pptx 支援 |

### Decision 5: 向下相容

- `generate_presentation(style="tech")` → 使用預設風格（現有行為）
- `generate_presentation(design_json=...)` → 使用設計師輸出
- 兩者互斥，`design_json` 優先

## Risks / Trade-offs

| 風險 | 影響 | 緩解 |
|------|------|------|
| AI 設計品質不穩定 | 輸出風格可能不協調 | 設計 prompt 包含設計原則限制 |
| 字型不存在 | 顯示異常 | 實作 fallback 機制 |
| design_json 格式錯誤 | 生成失敗 | 嚴格的 JSON 驗證 + 預設值 |
| Prompt 調整需重啟 | 迭代慢 | Prompt 存資料庫，可即時更新 |

## Migration Plan

1. **Phase 2.1**: 實作 design_json 解析 + 擴展 python-pptx
2. **Phase 2.2**: 建立設計師 prompt + agent
3. **Phase 2.3**: 整合到 Line Bot 流程
4. **Rollback**: 移除 design_json 參數即可回退到 Phase 1

## Open Questions

1. 是否需要讓用戶在 CTOS 前端手動調整設計？（Phase 3？）
2. 是否需要支援企業 CI（Corporate Identity）設定？
3. 是否需要支援簡報模板（預設 design_json）？
