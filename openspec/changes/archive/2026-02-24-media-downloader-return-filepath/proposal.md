## Why

media-downloader 的 `check-download` 完成時只回傳 `ctos_path`（虛擬路徑），不提供 `file_path`（絕對路徑）。AI 在後續操作（如轉逐字稿）時無法可靠地定位已下載的檔案，導致重複下載浪費時間和頻寬。

**實際案例**（2026-02-24 AI Log）：使用者 Darron 要求下載 YouTube 影片後轉逐字稿。AI 第一次下載完成後（job `2bd37263`），嘗試轉逐字稿時用了自己猜測的路徑 `ctos://linebot/videos/2026-02-24/DNTsjyLSM0g.mp4`（用 YouTube ID 而非 job_id 組合路徑），導致找不到檔案。AI 接著嘗試 `get_message_attachments`、`search_nas_files` 等 3 種工具搜尋均失敗，最終被迫**重新下載一次**（job `c69bb832`）才取得正確路徑繼續轉錄。

media-transcription 的 `check-transcription` 已在最近的修改中加入 `file_path` 欄位（commit `1043706`），成功解決了同類問題。media-downloader 應跟進同樣的模式。

## What Changes

- `check-download` 完成時新增 `file_path` 欄位（影片檔的絕對路徑，如 `/mnt/nas/ctos/linebot/videos/2026-02-24/a1b2c3d4/video.mp4`），使用 `PathManager.to_filesystem()` 轉換
- `SKILL.md` 更新 AI 行為指引：明確說明完成時回傳 `ctos_path` + `file_path`，指導 AI 在後續操作中使用完整路徑，避免猜測路徑

## Capabilities

### New Capabilities

（無新增 capability）

### Modified Capabilities

- `media-downloader`：check-download 完成時的回傳格式變更——新增 `file_path` 絕對路徑欄位，SKILL.md 新增路徑使用指引

## Impact

- **程式碼**：`backend/src/ching_tech_os/skills/media-downloader/scripts/check-download.py`（新增 file_path 轉換邏輯）
- **Skill 定義**：`backend/src/ching_tech_os/skills/media-downloader/SKILL.md`（更新回傳說明與 AI 行為指引）
- **Spec**：`openspec/specs/media-downloader/spec.md`（更新查詢已完成下載的 scenario）
- **依賴**：使用既有的 `ching_tech_os.services.path_manager`，無新增依賴
- **相容性**：純新增欄位，不影響現有 API 消費者
