---
name: research-skill
description: 外部研究整合（搜尋 + 擷取 + 統整，start/check）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
---

【外部研究整合（start/check）】

當任務需要多來源搜尋、擷取內容並統整時，優先使用此 skill，避免在單一回合長時間同步呼叫 WebSearch/WebFetch 導致超時。

**可用 scripts：**

1. **start-research** — 啟動研究任務（非同步，立即回傳 job ID）
   - `run_skill_script(skill="research-skill", script="start-research", input='{"query":"主題關鍵字"}')`
   - 可選參數：
     - `urls`：先驗證或優先擷取的 URL 陣列
     - `max_results`：搜尋最多來源數（1-10，預設 5）
     - `max_fetch`：實際擷取來源數（1-6，預設 4）
   - 立即回傳 `job_id`，背景程序持續執行。

2. **check-research** — 查詢研究進度與結果
   - `run_skill_script(skill="research-skill", script="check-research", input='{"job_id":"之前取得的job_id"}')`
   - 進行中：回傳 `status`、`progress`、`partial_results`
   - 完成：回傳 `final_summary`、`sources`、`result_ctos_path`

**典型流程：**
1. 先呼叫 `start-research` 啟動任務並取得 `job_id`
2. 先回覆用戶「任務已受理，請稍後查詢」，附上 `job_id`
3. 用戶追問進度時再呼叫 `check-research`
4. 完成後再提供統整內容與來源

**AI 行為指引：**
- 嚴禁在同一回合反覆 `sleep + check` 等待完成，避免超時。
- 研究未完成時回覆目前進度與 `job_id`，引導用戶稍後查詢。
- 完成時請附上來源重點，避免無來源的結論式回覆。
