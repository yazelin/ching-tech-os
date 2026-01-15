# Proposal: 統一路徑管理器

## 問題描述

目前系統中的路徑處理散落在各處，格式不統一，導致：

1. **路徑格式混亂**：至少有 8 種以上的路徑格式在系統中流通
2. **轉換邏輯重複**：`mcp_server.py`、`share.py`、`knowledge.py` 等都有各自的路徑轉換
3. **難以維護**：新增功能時需要在多處處理路徑，容易遺漏
4. **前後端不一致**：後端儲存格式、API 回傳格式、前端期望格式各不相同

### 目前路徑格式清單

| 來源 | 格式 | 範例 |
|-----|------|------|
| 知識庫本機附件 | `../assets/{type}/{file}` | `../assets/images/kb-001-demo.png` |
| 知識庫 NAS 附件 | `nas://knowledge/attachments/{id}/{file}` | `nas://knowledge/attachments/kb-001/large.pdf` |
| 專案本機附件 | `{project_id}/{file}` | `550e8400.../doc.xlsx` |
| 專案 NAS 附件 | `nas://projects/attachments/{id}/{file}` | `nas://projects/attachments/xxx/doc.pdf` |
| Line Bot 檔案 | `{scope}/{type}s/{date}/{id}.{ext}` | `groups/C123/images/2026-01-05/abc.jpg` |
| search_nas_files 回傳 | `/{project}/{file}` | `/亦達光學/layout.pdf` |
| AI 生成圖片 | `/tmp/.../nanobanana-output/{file}` | `/tmp/xxx/nanobanana-output/abc.jpg` |
| 系統暫存 | `/tmp/linebot-files/{file}` | `/tmp/linebot-files/msg123_doc.pdf` |
| 實際掛載路徑 | `/mnt/nas/{mount}/{path}` | `/mnt/nas/ctos/linebot/files/...` |
| 前端 API 路徑 | `/api/{module}/{action}/{path}` | `/api/knowledge/attachments/...` |

### 路徑轉換邏輯散落位置

- `backend/src/ching_tech_os/services/mcp_server.py` - `resolve_nas_path()`
- `backend/src/ching_tech_os/services/share.py` - `validate_nas_file_path()`
- `backend/src/ching_tech_os/services/knowledge.py` - 附件路徑處理
- `backend/src/ching_tech_os/services/project.py` - 專案附件路徑
- `backend/src/ching_tech_os/services/linebot.py` - `generate_nas_path()`
- `frontend/js/file-manager.js` - `toSystemMountPath()`
- `frontend/js/knowledge-base.js` - 附件路徑正規化

## 提案目標

建立統一的路徑管理器（PathManager），提供：

1. **統一的路徑格式**：定義標準的內部路徑表示法
2. **集中的轉換邏輯**：所有路徑轉換都透過 PathManager
3. **清晰的路徑類型**：明確區分不同用途的路徑
4. **前後端一致性**：統一 API 回傳格式和前端處理

### 預期效益

- 減少重複程式碼
- 降低新功能開發時的路徑處理負擔
- 方便未來擴展（影片、音樂等新檔案類型）
- 提高程式碼可讀性和可維護性

## 範圍

- 後端路徑管理器設計與實作
- 前端路徑工具函式
- 現有程式碼重構（逐步遷移）
- API 回傳格式標準化

## 非目標

- 變更現有資料庫儲存格式（維持向後相容）
- 變更 NAS 目錄結構
- 變更環境變數設定

## 初步想法

### 標準路徑格式

```
ctos://{domain}/{path}

範例：
- ctos://knowledge/attachments/kb-001/file.pdf
- ctos://projects/attachments/xxx/doc.xlsx
- ctos://linebot/files/groups/C123/images/2026-01-05/abc.jpg
- ctos://nas/projects/亦達光學/layout.pdf
- ctos://temp/linebot-files/msg123_doc.pdf
```

### PathManager 介面

```python
class PathManager:
    # 解析路徑
    def parse(path: str) -> ParsedPath

    # 轉換為實際檔案系統路徑
    def to_filesystem(path: str) -> str

    # 轉換為 API 路徑
    def to_api(path: str) -> str

    # 轉換為儲存格式（資料庫）
    def to_storage(path: str) -> str

    # 從舊格式轉換
    def from_legacy(path: str) -> str
```

## 需要進一步討論

1. 標準路徑格式的設計（`ctos://` 協議？還是其他方式？）
2. 向後相容策略（如何處理現有資料）
3. 遷移計畫（一次性重構 vs 逐步遷移）
4. 前端是否也需要 PathManager？

## 相關文件

- `backend/src/ching_tech_os/config.py` - 現有路徑設定
- `docs/smb-nas-architecture.md` - NAS 架構設計
