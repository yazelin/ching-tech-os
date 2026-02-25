## 1. 建立 research-skill 骨架

- [x] 1.1 建立 `backend/src/ching_tech_os/skills/research-skill/` 與 `scripts/` 目錄
- [x] 1.2 新增 `SKILL.md`（name、description、allowed-tools、requires_app、mcp_servers、scripts 用法）
- [x] 1.3 定義 script 名稱與輸入/輸出契約（`start-research`、`check-research`）

## 2. 實作 start-research（非同步啟動）

- [x] 2.1 建立 `scripts/start-research.py`，解析並驗證輸入（至少 `query`）
- [x] 2.2 實作 job 目錄與 `status.json` 初始化（含 `job_id`、`status`、`progress`、`created_at`）
- [x] 2.3 實作父程序立即回傳 `job_id`，子程序背景執行（searching/fetching/synthesizing）
- [x] 2.4 實作來源蒐集、去重與部分失敗容錯，更新中間狀態與部分結果
- [x] 2.5 實作最終統整輸出（`final_summary` + `sources`）與失敗狀態寫入

## 3. 實作 check-research（進度/結果查詢）

- [x] 3.1 建立 `scripts/check-research.py`，驗證 `job_id` 格式並搜尋狀態檔
- [x] 3.2 回傳進行中狀態（`status`、`progress`、`partial_results`、`sources`）
- [x] 3.3 回傳完成狀態（`completed` + `final_summary` + `sources`）
- [x] 3.4 回傳失敗與不存在任務錯誤（可診斷訊息）
- [x] 3.5 加入 stale job 判定與狀態修正（長時間無更新轉 failed）

## 4. 整合 bot 平台路由

- [x] 4.1 更新 `services/bot/agents.py` 與相關 prompt，使外部研究任務優先走 `run_skill_script(...start-research...)`
- [x] 4.2 保留 `fallback_required` 的受控回退路徑與路由記錄
- [x] 4.3 更新 `services/linebot_agents.py`（必要時）以納入 research-skill 使用指引

## 5. 整合 Line Bot 兩段式互動

- [x] 5.1 更新 `services/linebot_ai.py`：start 成功時回覆受理訊息（含 `job_id` 與查詢方式）
- [x] 5.2 更新 `services/linebot_ai.py`：check 回覆依狀態輸出進度/部分結果/最終統整
- [x] 5.3 確保群組與個人回覆格式一致且符合 mention 規則
- [x] 5.4 確保 reply 失敗時仍可由 push fallback 將關鍵結果送達

## 6. 驗證與回歸

- [x] 6.1 手動驗證個人對話：start 後立即回覆，再 check 取得完成結果
- [x] 6.2 手動驗證群組對話：@AI start/check 流程與 mention 行為
- [x] 6.3 驗證外部來源失敗場景：部分結果可回覆、錯誤可診斷
- [x] 6.4 執行既有後端測試（至少與 bot/skills 相關）確認無回歸
