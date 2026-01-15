# Proposal: 統一路徑管理器

## 問題描述

目前系統中的路徑處理散落在各處，格式不統一，且**命名容易混淆**。

### 最大問題：`projects` 名稱衝突

```
/mnt/nas/
├── ctos/
│   └── projects/        ← nas://projects/... 指向這裡（CTOS 專案附件）
│
└── projects/            ← search_nas_files 搜尋這裡（公司共用區）
```

兩個完全不同的東西都叫 `projects`，非常容易搞混！

### 目前路徑格式（混亂）

| 格式 | 實際位置 | 問題 |
|-----|---------|-----|
| `nas://knowledge/attachments/...` | `/mnt/nas/ctos/knowledge/attachments/` | nas:// 不直覺 |
| `nas://projects/attachments/...` | `/mnt/nas/ctos/projects/attachments/` | ⚠️ 與共用區混淆 |
| `groups/C123/images/...` | `/mnt/nas/ctos/linebot/files/groups/...` | 相對路徑，不知道根目錄 |
| `../assets/images/...` | 知識庫本機目錄 | 相對路徑 |
| `/亦達光學/layout.pdf` | `/mnt/nas/projects/亦達光學/` | 看起來像絕對路徑 |
| `/tmp/linebot-files/...` | 系統暫存 | 系統路徑外露 |

---

## 提案：統一路徑協議

### 新的路徑格式

使用 **URI 協議格式**，清楚區分不同儲存區域：

| 協議 | 掛載點 | 用途 | 權限 |
|-----|-------|------|-----|
| `ctos://` | `/mnt/nas/ctos/` | CTOS 系統管理的檔案 | 讀寫 |
| `shared://` | `/mnt/nas/projects/` | 公司專案共用區 | 唯讀 |
| `temp://` | `/tmp/ctos/` | 暫存檔案 | 讀寫 |
| `local://` | 應用程式 data 目錄 | 本機小檔案 | 讀寫 |

### 路徑範例對照

| 舊格式 | 新格式 | 說明 |
|-------|-------|------|
| `nas://knowledge/attachments/kb-001/file.pdf` | `ctos://knowledge/kb-001/file.pdf` | 知識庫附件 |
| `nas://projects/attachments/xxx/doc.xlsx` | `ctos://attachments/xxx/doc.xlsx` | 專案附件 |
| `groups/C123/images/2026-01-05/abc.jpg` | `ctos://linebot/groups/C123/images/2026-01-05/abc.jpg` | Line Bot 檔案 |
| `../assets/images/kb-001-demo.png` | `local://knowledge/images/kb-001-demo.png` | 本機小檔案 |
| `/亦達光學/layout.pdf` | `shared://亦達光學/layout.pdf` | 公司共用區 |
| `/tmp/linebot-files/msg123.pdf` | `temp://linebot/msg123.pdf` | 暫存檔 |
| `/tmp/.../nanobanana-output/abc.jpg` | `temp://ai-generated/abc.jpg` | AI 生成暫存 |

### CTOS 目錄結構（簡化）

```
ctos://
├── knowledge/           ← 知識庫附件
│   ├── kb-001/
│   └── kb-002/
├── attachments/         ← 專案附件（改名，避免與 shared:// 混淆）
│   ├── {project-uuid}/
│   └── ...
└── linebot/             ← Line Bot 檔案
    ├── groups/
    ├── users/
    ├── ai-images/
    └── pdf-converted/
```

---

## PathManager 設計

### 核心類別

```python
from enum import Enum
from dataclasses import dataclass

class StorageZone(Enum):
    """儲存區域"""
    CTOS = "ctos"        # CTOS 系統檔案
    SHARED = "shared"    # 公司共用區
    TEMP = "temp"        # 暫存
    LOCAL = "local"      # 本機

@dataclass
class ParsedPath:
    """解析後的路徑"""
    zone: StorageZone    # 儲存區域
    path: str            # 相對路徑
    raw: str             # 原始輸入

class PathManager:
    """統一路徑管理器"""

    def parse(self, path: str) -> ParsedPath:
        """解析路徑，支援新舊格式"""
        pass

    def to_filesystem(self, path: str) -> str:
        """轉換為實際檔案系統路徑"""
        # ctos://linebot/... → /mnt/nas/ctos/linebot/...
        # shared://亦達光學/... → /mnt/nas/projects/亦達光學/...
        pass

    def to_api(self, path: str) -> str:
        """轉換為前端 API 路徑"""
        # ctos://knowledge/kb-001/file.pdf → /api/files/ctos/knowledge/kb-001/file.pdf
        pass

    def to_storage(self, path: str) -> str:
        """轉換為資料庫儲存格式（標準化）"""
        pass

    def from_legacy(self, path: str) -> str:
        """從舊格式轉換"""
        # nas://projects/... → ctos://attachments/...
        # /亦達光學/... → shared://亦達光學/...
        pass
```

### 向後相容

PathManager 會自動識別舊格式並轉換：

```python
path_manager = PathManager()

# 舊格式自動轉換
path_manager.parse("nas://knowledge/attachments/kb-001/file.pdf")
# → ParsedPath(zone=CTOS, path="knowledge/kb-001/file.pdf")

path_manager.parse("/亦達光學/layout.pdf")
# → ParsedPath(zone=SHARED, path="亦達光學/layout.pdf")

path_manager.parse("groups/C123/images/abc.jpg")
# → ParsedPath(zone=CTOS, path="linebot/groups/C123/images/abc.jpg")
```

---

## 前端 PathUtils

```javascript
const PathUtils = {
    // 解析路徑
    parse(path) {
        // 返回 { zone, path, apiUrl }
    },

    // 取得 API URL
    toApiUrl(path) {
        // ctos://knowledge/... → /api/files/ctos/knowledge/...
    },

    // 判斷是否為圖片
    isImage(path) {},

    // 判斷是否為 PDF
    isPdf(path) {},
};
```

---

## 遷移計畫

### Phase 1: 建立 PathManager（不改現有邏輯）
- 新增 `backend/src/ching_tech_os/services/path_manager.py`
- 新增 `frontend/js/path-utils.js`
- 支援新舊格式轉換

### Phase 2: 新功能使用新格式
- 新的 API 回傳標準化路徑
- 新的資料庫欄位使用新格式

### Phase 3: 逐步遷移現有程式碼
- 替換 `mcp_server.py` 的 `resolve_nas_path()`
- 替換 `share.py` 的 `validate_nas_file_path()`
- 替換各處的路徑處理邏輯

### Phase 4: 資料遷移（可選）
- 更新資料庫中的舊路徑格式
- 或保持向後相容，不遷移

---

## 預期效益

1. **命名清晰**：`ctos://` vs `shared://` 不會混淆
2. **格式統一**：所有路徑都是 `{protocol}://{path}` 格式
3. **集中管理**：路徑轉換邏輯只在 PathManager
4. **容易擴展**：未來新增影片、音樂等只需加新的子路徑
5. **前後端一致**：API 回傳和前端處理使用相同格式

---

## 已確定事項

1. ✅ 路徑協議命名：`ctos://`、`shared://`、`temp://`、`local://`
2. ✅ `ctos://linebot/` 保持現狀，不再細分
3. ✅ 前端統一 API endpoint：`/api/files/{zone}/{path}`
4. ✅ 遷移策略：先建立 PathManager，再依序整合其他部份

---

## 相關檔案

**需要重構的檔案：**
- `backend/src/ching_tech_os/services/mcp_server.py` - `resolve_nas_path()`
- `backend/src/ching_tech_os/services/share.py` - `validate_nas_file_path()`
- `backend/src/ching_tech_os/services/knowledge.py` - 附件路徑
- `backend/src/ching_tech_os/services/project.py` - 專案附件
- `backend/src/ching_tech_os/services/linebot.py` - `generate_nas_path()`
- `frontend/js/file-manager.js` - `toSystemMountPath()`
- `frontend/js/knowledge-base.js` - 附件路徑處理

**設定檔：**
- `backend/src/ching_tech_os/config.py` - 掛載點設定
- `.env` - 環境變數
