## MODIFIED Requirements

### Requirement: 查詢下載狀態
Skill SHALL 提供 `check_download` script，查詢背景下載的進度與結果。完成時 SHALL 同時回傳虛擬路徑（`ctos_path`）與絕對路徑（`file_path`），使 AI 可直接定位檔案。

#### Scenario: 查詢進行中的下載
- **WHEN** AI 呼叫 `run_skill_script(skill="media-downloader", script="check-download", input='{"job_id":"a1b2c3d4"}')`
- **AND** 下載正在進行中
- **THEN** 系統回傳 `{"status": "downloading", "progress": 45.2, "filename": "video.mp4"}`

#### Scenario: 查詢已完成的下載
- **WHEN** 下載已完成
- **THEN** 系統回傳 `{"status": "completed", "ctos_path": "ctos://...", "file_path": "/mnt/nas/ctos/...", "file_size": 123456789, "filename": "video.mp4"}`
- **AND** `file_path` 為透過 `PathManager.to_filesystem(ctos_path)` 轉換的絕對路徑
- **AND** 若 `file_path` 轉換失敗，回傳結果 SHALL 不包含 `file_path` 欄位但不影響其他欄位

#### Scenario: 查詢不存在的 job
- **WHEN** job_id 不存在或狀態檔遺失
- **THEN** 系統回傳 `{"success": false, "error": "找不到下載任務"}`

#### Scenario: 下載逾時判定
- **WHEN** 狀態檔的 `updated_at` 超過 10 分鐘未更新
- **AND** status 仍為 `downloading`
- **THEN** 系統回傳 `{"status": "failed", "error": "下載逾時（超過 10 分鐘無進度）"}`

---

## MODIFIED Requirements

### Requirement: Skill 定義與權限
Skill SHALL 以 `SKILL.md` 定義 metadata，遵循 Agent Skills 標準。SKILL.md SHALL 包含 AI 行為指引，明確說明路徑使用方式。

#### Scenario: Skill 載入
- **WHEN** 系統啟動或 reload skills
- **THEN** `media-downloader` Skill 被載入
- **AND** 包含 3 個 scripts：`get-video-info`、`download-video`、`check-download`

#### Scenario: 權限控管
- **WHEN** 使用者不具備 `file-manager` app 權限
- **THEN** 系統拒絕執行任何 media-downloader script

#### Scenario: SKILL.md 結構
- **WHEN** 讀取 SKILL.md
- **THEN** frontmatter 包含 `name: media-downloader`、`requires_app: file-manager`、`mcp_servers: ching-tech-os`

#### Scenario: SKILL.md 路徑指引
- **WHEN** AI 讀取 SKILL.md 的 check-download 說明
- **THEN** 說明 SHALL 包含：完成時回傳 `ctos_path` 和 `file_path`
- **AND** 說明 SHALL 指引 AI 在後續操作（如轉逐字稿）中使用 `ctos_path` 作為 `source_path`
- **AND** 說明 SHALL 明確禁止 AI 自行猜測或拼湊路徑
