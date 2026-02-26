## 1. Worker 架構與任務生命週期

- [x] 1.1 新增背景 worker 佇列與 job 狀態機（queued/running/completed/failed/canceled）
- [x] 1.2 `start-research` 改為「建立 job + enqueue + 回傳 job_id」，不在主回合同步跑完整研究
- [x] 1.3 worker 啟動策略沿用 `os.fork`，並補齊子程序狀態更新與錯誤收斂

## 2. Worker 內 Claude 研究執行器

- [x] 2.1 建立 worker research executor，於背景呼叫 `call_claude` 執行 research 流程
- [x] 2.2 預設模型固定 `claude-sonnet`（保留後續可擴充覆寫）
- [x] 2.3 受控工具白名單：研究流程可用 WebSearch/WebFetch，避免非必要工具介入
- [x] 2.4 對 WebSearch/WebFetch 局部失敗做降級處理，保留 partial result

## 3. 研究產物與清理機制

- [x] 3.1 標準化落盤 `status.json`、`result.md`、`sources.json`、`tool_trace.json`
- [x] 3.2 `check-research` 回傳擴充欄位（stage/progress/error/result_ctos_path/provider/tool trace 摘要）
- [x] 3.3 新增研究暫存清理機制（策略比照影片下載/轉字幕 skill）
- [x] 3.4 完成產物可供後續知識庫流程引用（例如存入知識庫/歸檔）

## 4. Bot 路徑守衛與提示規則

- [x] 4.1 強化研究路徑守衛：同主題已有 job 時優先 check，不回退同步長回合抓取
- [x] 4.2 `check-research` 失敗時引導重新 `start-research`（新 job），避免直接切回 WebSearch/WebFetch
- [x] 4.3 維持「簡短單點查詢可走 WebSearch」與「多來源研究必走 start/check」分流

## 5. 驗證與交付

- [x] 5.1 單元測試：job lifecycle、worker executor、artifact tracking、清理機制
- [x] 5.2 回歸測試：Line/Telegram research 場景，確認先回 job_id 並可查到完成結果
- [x] 5.3 驗證 ai_logs 可追蹤研究子流程與工具軌跡
- [x] 5.4 完成 OpenSpec apply、更新 tasks 勾選、提交 PR
