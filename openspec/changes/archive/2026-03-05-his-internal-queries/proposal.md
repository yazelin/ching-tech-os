## Why

底層 HIS 查詢引擎（vision_his.py）已實作完成，但目前只有叫號進度（queue_status）有對應的 Skill script 可供 AI agent 使用。綁定帳號的內部用戶（醫護人員、行政人員）需要透過 LINE Bot 查詢門診統計、藥品消耗、預約狀態等診間內部資訊，需要將底層查詢包裝成 Skill scripts。

## What Changes

- 新增多個 Skill scripts 到 `extends/his/skills/his-integration/scripts/`，供內部 agent（jfmskin-full）透過 `run_skill_script` 呼叫
- 更新 jfmskin-full agent prompt，加入新 scripts 的使用說明
- 所有內部查詢 scripts 需要 `his-integration` 權限（已有，default: false）

預計新增的 scripts：
- `visit_stats`：門診統計（各醫師看診量、期間比較）
- `drug_usage`：藥品消耗查詢（特定藥品使用量、開方統計）
- `appointment_list`：預約總覽（今日/未來預約、依醫師分組）
- `manual_booking_stats`：醫師手動預約統計（從 VISLOG 的 `預2[A]` 操作紀錄統計各醫師手動預約次數）

## Capabilities

### New Capabilities
- `his-internal-scripts`: 內部用 HIS 查詢 Skill scripts 的定義與格式規範

### Modified Capabilities
- `his-query`: 新增 Skill script 呼叫方式的 requirement（底層引擎不變，但需定義 script input/output 格式）

## Impact

- `extends/his/skills/his-integration/scripts/` — 新增 3 個 Python scripts
- `extends/his/clients/jfmskin/agents/jfmskin-full.md` — 更新 prompt 加入新工具說明
- 不影響 jfmskin-edu（未綁定用戶看不到內部資訊）
- 不影響底層引擎（vision_his.py 不需修改）
