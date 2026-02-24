## Context

media-downloader 的 `check-download` 完成時只回傳 `ctos_path`（虛擬路徑，如 `ctos://linebot/videos/2026-02-24/a1b2c3d4/video.mp4`）。AI 在後續操作中需要自行猜測或透過額外工具（`get_nas_file_info`、`search_nas_files`）將虛擬路徑轉換為可操作的路徑，但實際觀察到 AI 經常猜錯（用 YouTube ID 而非 job_id 拼路徑），導致找不到已下載的檔案而重複下載。

media-transcription 的 `check-transcription` 已在 commit `1043706` 中實作了相同的改進模式——完成時回傳 `file_path` 絕對路徑，搭配 SKILL.md 指引 AI 直接使用 Read 工具讀取。

## Goals / Non-Goals

**Goals:**
- check-download 完成時提供 `file_path` 絕對路徑，與 check-transcription 一致
- 更新 SKILL.md 明確指引 AI 如何使用下載完成的路徑
- 減少 AI 在「下載→轉逐字稿」串接流程中的工具調用次數與失敗率

**Non-Goals:**
- 不改變 download-video 或 get-video-info 的行為
- 不修改下載流程本身（非同步機制、狀態檔格式等）
- 不新增 API 端點

## Decisions

### 1. 使用 PathManager.to_filesystem() 進行路徑轉換

與 check-transcription 相同做法：在 `check-download.py` 的完成分支中，用 `path_manager.to_filesystem(ctos_path)` 將虛擬路徑轉為絕對路徑。

**理由**：PathManager 是系統既有的路徑轉換服務，已處理各種 zone（ctos://、shared:// 等）。直接復用確保一致性，且 check-transcription 已驗證此模式可靠。

**替代方案**：讓 AI 自行呼叫 `get_nas_file_info` 取得路徑——但這正是目前的做法，AI 經常跳過此步驟直接猜路徑。

### 2. file_path 轉換失敗時靜默降級

與 check-transcription 相同：用 try-except 包裹，失敗時不影響原本的回傳結構（仍有 ctos_path 可用）。

**理由**：`file_path` 是輔助欄位，不應因轉換失敗而導致整個 check-download 報錯。

### 3. SKILL.md 明確指引後續操作的路徑使用

在 SKILL.md 中新增說明：
- 完成時回傳 `ctos_path`（用於歸檔等 CTOS 操作）+ `file_path`（用於直接讀取檔案）
- 指引 AI：後續要轉逐字稿時，用 `ctos_path` 傳給 transcribe 的 `source_path`
- 明確告知 AI **不要自行猜測或拼湊路徑**，必須使用 check-download 回傳的值

## Risks / Trade-offs

- **[風險] PathManager 在 skill subprocess 中的可用性** → check-transcription 已驗證可行，以 lazy import 方式載入，同樣做法即可
- **[風險] 檔名含特殊字元導致路徑問題** → PathManager.to_filesystem() 已處理路徑編碼，且 download-video 本身就會處理特殊字元檔名
