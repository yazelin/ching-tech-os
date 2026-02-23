## Why

目前 CTOS 支援透過 `download_web_file` 下載一般網頁檔案（PDF、圖片、Office 文件等），但無法下載 YouTube、X (Twitter)、Instagram 等平台的影片內容。這些平台不提供直接的檔案 URL，需要專用的解析工具。

公司內部經常需要存檔產品影片、技術教學、客戶分享的社群媒體內容等，目前只能手動下載再上傳，流程繁瑣。透過整合 [yt-dlp](https://github.com/yt-dlp/yt-dlp)（支援 1000+ 網站的影片下載工具），AI 助手可以直接幫使用者下載影片並歸檔到圖書館。

## What Changes

- 新增 `media-downloader` Skill，以 script-first 架構包裝 yt-dlp
- 實作 `download_video.py` 腳本：解析影片 URL → 下載到 CTOS 暫存區 → 回傳 `ctos://` 路徑
- 支援指定輸出格式（mp4/mp3/best）與品質選項
- 下載完成後可搭配現有 `archive_to_library` 歸檔到圖書館
- 在圖書館分類中新增「影片資料」類別
- 新增 `yt-dlp` 為後端系統依賴（非 Python 套件，透過 pip 或系統安裝）

## Capabilities

### New Capabilities
- `media-downloader`: Skill 封裝 yt-dlp 影片下載能力，包含 `download_video.py` 腳本、SKILL.md 定義、格式/品質選項處理

### Modified Capabilities
- `mcp-tools`: 圖書館分類白名單新增「影片資料」類別（`LIBRARY_CATEGORIES`）

## Impact

- **新依賴**：系統需安裝 `yt-dlp`（可透過 `pip install yt-dlp` 或系統套件管理）
- **Skills 目錄**：新增 `skills/media-downloader/`（native skill）或 `~/SDD/skill/media-downloader/`（external skill）
- **NAS 儲存**：下載的影片暫存於 `ctos://linebot/videos/` 下，歸檔後存於 `shared://library/影片資料/`
- **現有程式碼**：僅需修改 `nas_tools.py` 的 `LIBRARY_CATEGORIES` 白名單
- **權限**：Skill 設定 `requires_app: file-manager`，複用現有檔案管理權限
