# Design: Gemini 模型自動 Fallback

## Context
- nanobanana MCP 使用 `gemini-3-pro-image-preview` 模型
- 該模型為預覽版，Google 資源有限，高負載時會 hang 住
- 2026 年 1 月 Google 加強風控，導致更頻繁的超時
- `gemini-2.5-flash-image` 測試穩定，回應時間 4-6 秒

## Goals / Non-Goals
**Goals:**
- 提高圖片生成成功率
- 當 Pro 模型不可用時自動切換到 Flash
- 讓使用者知道目前使用的是哪個服務

**Non-Goals:**
- 不修改 nanobanana MCP 套件本身
- 不改變 Pro 模型優先的策略（品質優先）

## Decisions

### 1. 直接呼叫 Gemini API 而非重啟 MCP
**決定**：建立獨立的 Gemini API 呼叫函數

**原因**：
- nanobanana MCP 透過環境變數設定模型，無法動態切換
- 重啟 MCP server 太慢且複雜
- 直接呼叫 API 更快速、可控

### 2. Fallback 順序
```
1. nanobanana (gemini-3-pro-image-preview) - 品質最好
   ↓ timeout 或 error
2. 直接 API (gemini-2.5-flash-image) - 穩定快速
   ↓ 失敗
3. Hugging Face FLUX - 最後備用
```

### 3. 觸發條件
- nanobanana timeout（output 為空）
- nanobanana 503/overloaded 錯誤
- nanobanana quota/limit 錯誤

### 4. 使用者通知訊息
```
Pro 成功：（不顯示額外訊息）
Flash fallback：「圖片已生成（使用快速模式）」
Hugging Face fallback：「圖片已生成（使用備用服務）」
全部失敗：「⚠️ 圖片生成服務暫時無法使用...」
```

## Architecture

```
linebot_ai.py
     │
     ├─→ Claude CLI + nanobanana MCP
     │        │
     │        ↓ (timeout/error)
     │
     └─→ image_fallback.py
              │
              ├─→ generate_with_gemini_flash()
              │        │
              │        ↓ (失敗)
              │
              └─→ generate_with_huggingface()
```

## File Structure
```
services/
├── image_fallback.py      # 新增：統一 fallback 邏輯
├── linebot_ai.py          # 修改：整合 fallback
└── huggingface_image.py   # 修改：只保留 HF 生成函數
```

## API Reference

### Gemini generateContent API
```python
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent

Request:
{
  "contents": [{"parts": [{"text": "prompt"}]}],
  "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
}

Response:
{
  "candidates": [{
    "content": {
      "parts": [
        {"text": "description"},
        {"inlineData": {"mimeType": "image/png", "data": "base64..."}}
      ]
    }
  }]
}
```

## Risks / Trade-offs
- **風險**：Gemini Flash 品質可能不如 Pro
  - 緩解：Flash 只作為備用，Pro 優先
- **風險**：直接呼叫 API 需要自行處理錯誤
  - 緩解：完整的錯誤處理和日誌記錄

## Timeout Configuration
| 服務 | 超時時間 | 說明 |
|------|----------|------|
| nanobanana (Pro) | 240 秒 | 從 480 秒降低，正常約 30-60 秒，最慢成功紀錄 406 秒 |
| Gemini Flash | 30 秒 | 正常約 4-6 秒 |
| Hugging Face | 30 秒 | 正常約 10-20 秒 |
| **總計最大** | **300 秒** | 從 480+ 秒大幅降低 |

## Open Questions
- 是否需要讓使用者選擇偏好的模型？（目前：否，自動處理）
