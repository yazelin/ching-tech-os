## ADDED Requirements

### Requirement: 圖書館支援影片資料分類
圖書館歸檔工具 `archive_to_library` SHALL 支援「影片資料」作為合法的大分類。

#### Scenario: 歸檔影片到圖書館
- **WHEN** AI 呼叫 `archive_to_library(source_path="ctos://linebot/videos/...", category="影片資料", filename="教學影片.mp4")`
- **THEN** 系統將影片複製到 `shared://library/影片資料/教學影片.mp4`

#### Scenario: 影片資料分類可用
- **WHEN** 查詢 `LIBRARY_CATEGORIES` 白名單
- **THEN** 包含 `"影片資料"` 項目
