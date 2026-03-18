---
name: media-translation
description: 長文翻譯（Gemini，背景執行）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
  openclaw:
    requires:
      env:
        - GEMINI_API_KEY
---

【長文翻譯（Gemini 背景執行）】

將長文（逐字稿、文章等）翻譯成指定語言。使用 Google Gemini 翻譯，背景執行不阻塞。
翻譯流程為非同步：啟動翻譯 → 查詢進度 → 取得翻譯結果。

**可用 scripts：**

1. **translate** — 啟動翻譯（非同步，立即回傳 job ID）
   - `run_skill_script(skill="media-translation", script="translate", input='{"source_path":"ctos://...","caller_context":{...}}')`
   - source_path：要翻譯的檔案路徑（支援 `ctos://`、`shared://` 格式，限 .md/.txt 純文字）
   - 或 text：直接傳入要翻譯的文字（二擇一）
   - 可選參數：
     · target_language：目標語言代碼（如 zh-TW、en），預設自動偵測
     · model：Gemini 模型（預設 gemini-2.5-flash）
   - **必須附帶 caller_context**
   - 限制：檔案 ≤ 2MB，文字 ≤ 500,000 字元

2. **check-translation** — 查詢翻譯進度（同步）
   - `run_skill_script(skill="media-translation", script="check-translation", input='{"job_id":"之前取得的job_id"}')`
   - 回傳翻譯狀態（starting/reading/translating/completed/failed）
   - 翻譯中顯示進度（如「3/12」表示第 3 段，共 12 段）
   - 完成時回傳：file_path（絕對路徑，可用 Read 工具讀取）、ctos_path

**典型使用流程：**
1. 使用者要求翻譯某篇文章或逐字稿
2. 呼叫 translate 啟動翻譯，取得 job_id
3. 告知使用者「翻譯已啟動（job_id: xxxx），完成後會通知你，也可以隨時問我進度」，結束本次回應
4. （系統自動：翻譯完成後 proactive-push 通知使用者）
5. 使用者詢問「翻譯好了嗎？」或「進度如何？」時，用 check-translation 查詢並回報狀態
6. 完成後用 Read 工具讀取 file_path，依使用者需求摘要或回覆全文

**語言偵測邏輯：**
- 未指定 target_language 時自動偵測：
  · 英文/中英夾雜 → 翻譯成繁體中文
  · 繁體中文 → 翻譯成英文

**AI 行為指引：**
- 當使用者要求翻譯長文件（逐字稿、文章、文件）時使用此 skill
- 短文翻譯（幾段話）直接回覆即可，不需要用此 skill
- **嚴禁使用 sleep 等待翻譯完成**。啟動後只需查詢一次進度：
  - 若仍在翻譯中：回覆「翻譯進行中（進度 3/12），你可以稍後再問我」，結束本次回應
  - 若已完成：讀取翻譯結果並回覆
- **務必附帶 caller_context**，否則完成後無法推送通知
- 使用者問「翻譯好了嗎」、「進度」等，用 check-translation 查詢。若使用者沒提供 job_id，從對話歷史中找到之前的 job_id
