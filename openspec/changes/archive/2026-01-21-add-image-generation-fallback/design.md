# Design: 圖片生成備用服務

## Context

Line Bot 使用 nanobanana MCP 工具呼叫 Google Gemini 生成圖片，但經常遇到 503 "model is overloaded" 錯誤。
這是 Google 伺服器端容量問題，即使付費升級也無法完全解決。

## Goals / Non-Goals

**Goals:**
- 提供備用圖片生成服務，確保可用性
- 保留 Gemini 作為主要服務（品質較好、中文支援較佳）
- 備用切換對用戶透明，但需告知使用了備用服務

**Non-Goals:**
- 不取代 nanobanana，僅作為備用
- 不實作多服務負載平衡
- 不支援 nanobanana 以外的 MCP 工具備用

## Decisions

### Decision 1: 使用 Hugging Face Inference API + FLUX.1-schnell

**理由:**
- Apache 2.0 開源，可商用
- 免費額度足夠測試和輕量使用
- FLUX 品質在開源模型中排名前列
- API 簡單，整合成本低

**替代方案考慮:**
- Stability AI (DreamStudio): 免費額度少，需付費
- Leonardo.ai: 需要額外註冊，API 複雜
- 自架 Stable Diffusion: 需要 GPU 伺服器，維護成本高

### Decision 2: 在 linebot_ai.py 層級實作備用邏輯

**理由:**
- 可以檢測 nanobanana 的錯誤回應
- 不需要修改 MCP Server
- 可以在回應中加入備用服務提示

**實作位置:**
- `linebot_ai.py:auto_prepare_generated_images()` - 已有 nanobanana 錯誤檢測
- 新增 `services/huggingface_image.py` - 獨立模組方便維護

### Decision 3: 備用觸發條件

僅在以下情況觸發備用：
- nanobanana 回傳 `"overloaded"` 錯誤（503 伺服器過載）
- nanobanana 回傳 `"quota"` 或 `"limit"` 錯誤（429 超過配額）

不觸發備用的情況：
- API key 錯誤（設定問題，需人工處理）
- 其他未知錯誤（可能是 prompt 問題）

## Architecture

```
用戶要求畫圖
    ↓
Claude AI 呼叫 nanobanana MCP
    ↓
nanobanana 呼叫 Gemini API
    ↓
┌─────────────────────────────────┐
│ 成功 → 回傳圖片路徑             │
│                                 │
│ 失敗 (503/429)                  │
│   ↓                             │
│ linebot_ai.py 檢測錯誤          │
│   ↓                             │
│ 呼叫 huggingface_image.py       │
│   ↓                             │
│ Hugging Face API → FLUX.1       │
│   ↓                             │
│ 回傳圖片 + 備用服務提示         │
└─────────────────────────────────┘
```

## API Integration

### Hugging Face Inference API

```python
from huggingface_hub import InferenceClient

client = InferenceClient(token=os.getenv("HUGGINGFACE_API_TOKEN"))

image = client.text_to_image(
    prompt,
    model="black-forest-labs/FLUX.1-schnell",
    guidance_scale=0.0,  # schnell 建議 0
    num_inference_steps=4,  # schnell 只需 1-4 步
)
```

### 錯誤處理

```python
async def generate_with_fallback(prompt: str, original_error: str) -> tuple[str, bool]:
    """
    使用備用服務生成圖片

    Returns:
        (image_path, used_fallback)
    """
    try:
        image = client.text_to_image(prompt, model="black-forest-labs/FLUX.1-schnell")
        path = save_temp_image(image)
        return (path, True)
    except Exception as e:
        logger.error(f"備用服務也失敗: {e}")
        return (None, False)
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Hugging Face 免費額度用完 | 監控使用量，必要時升級或限制備用次數 |
| FLUX 中文支援較差 | 保留 Gemini 作為主要，FLUX 僅備用 |
| 兩個服務都失敗 | 回傳清楚的錯誤訊息，告知用戶稍後再試 |

## Open Questions

- [ ] 是否需要記錄備用服務使用次數？
- [ ] 是否需要限制每日備用服務使用次數？
