# Design: add-library-archive-mcp

## 架構決策

### 決策 1：檔案複製策略

**選擇**：使用 `shutil.copy2` 直接在本地掛載點之間複製

**原因**：
- library 已掛載為讀寫（`/mnt/nas/library`），linebot 檔案也在本地掛載（`/mnt/nas/ctos/linebot/`）
- 本地複製比 SMB 直連快，且不需要額外認證
- 與現有 `copy_linebot_attachment_to_knowledge` 使用相同模式

**不採用**：
- ❌ 透過 SMB API 複製：多此一舉，掛載點已存在
- ❌ 移動檔案：linebot 區的檔案是對話紀錄的一部分，需保留

### 決策 2：分類由 AI 決定，工具不做 AI 推理

**選擇**：`archive_to_library` 工具只負責複製，分類邏輯全部交給 AI Agent prompt

**原因**：
- AI 已經能透過 `read_document` 讀取檔案內容
- 分類規則寫在 prompt 中，調整彈性最大
- 工具保持簡單，只做檔案操作

```
AI Agent prompt（分類規則）    archive_to_library 工具（檔案操作）
───────────────────────────    ─────────────────────────────────
1. read_document 讀取內容      接收：source, category, folder, filename
2. list_library_folders 看結構  驗證：category 合法、路徑安全
3. 決定分類和檔名               執行：建目錄 + copy2
4. 呼叫 archive_to_library     回傳：歸檔結果路徑
```

### 決策 3：category 預定義清單 vs 自由輸入

**選擇**：預定義清單（硬編碼），工具端驗證

**原因**：
- 防止 AI 幻覺亂建大分類（第一層目錄爆炸）
- 第二層 `folder` 自由命名，給 AI 足夠彈性
- 新增分類只需改一個常數，不需改資料庫

```python
LIBRARY_CATEGORIES = [
    "技術文件",    # 規格書、手冊、datasheet、SOP
    "產品資料",    # 型錄、報價單、產品目錄
    "教育訓練",    # 教材、培訓簡報、操作指南
    "法規標準",    # ISO、CNS、安規、認證文件
    "設計圖面",    # CAD、線路圖、機構圖
    "其他",        # 無法分類時的 fallback
]
```

## 工具設計

### `list_library_folders`

```python
@mcp.tool()
async def list_library_folders(
    path: str = "",
    max_depth: int = 2,
    ctos_user_id: int | None = None,
) -> str:
    """瀏覽擎添圖書館的資料夾結構"""
```

**實作邏輯**：
1. 權限檢查（`check_mcp_tool_permission` + `shared_sources.library`）
2. 取得 `library_mount_path`，拼接 `path`
3. 使用 `os.walk` 遍歷到 `max_depth` 層
4. 回傳樹狀結構，包含資料夾名稱和檔案數量

**回傳格式**：
```
擎添圖書館/
├── 技術文件/ (3 個檔案)
│   ├── PLC程式/ (2 個檔案)
│   └── 馬達規格/ (1 個檔案)
├── 產品資料/ (空)
└── 其他/ (1 個檔案)
```

### `archive_to_library`

```python
@mcp.tool()
async def archive_to_library(
    source_path: str,
    category: str,
    filename: str,
    folder: str = "",
    ctos_user_id: int | None = None,
) -> str:
    """將檔案歸檔至擎添圖書館"""
```

**實作邏輯**：

```
1. 權限檢查
   ├── check_mcp_tool_permission("archive_to_library", ctos_user_id)
   └── shared_sources.library 權限

2. 驗證 source_path
   ├── path_manager.parse(source_path)
   ├── zone 必須是 CTOS（只接受 linebot 區的檔案）
   └── path_manager.to_filesystem → 取得實際路徑，確認檔案存在

3. 驗證目標參數
   ├── category 必須在 LIBRARY_CATEGORIES 內
   ├── folder 清理特殊字元（.., /, \）
   └── filename 清理特殊字元，保留副檔名

4. 組合目標路徑
   │  library_mount_path / category / folder / filename
   │
   ├── 若 folder 目錄不存在 → mkdir -p
   └── 若 filename 已存在 → 加後綴 (-2, -3, ...)

5. 執行複製
   └── shutil.copy2(source_fs_path, target_fs_path)

6. 回傳結果
   └── "✅ 已歸檔：shared://library/技術文件/PLC程式/三菱FX5U-使用手冊.pdf"
```

**安全檢查細節**：

```python
# 路徑清理函數
def _sanitize_path_segment(segment: str) -> str:
    """清理路徑片段，防止 path traversal"""
    # 移除 .. 和絕對路徑
    segment = segment.replace("..", "").replace("/", "").replace("\\", "")
    # 移除開頭的 . 和空白
    segment = segment.lstrip(". ")
    # 移除控制字元
    segment = re.sub(r'[\x00-\x1f]', '', segment)
    return segment.strip()
```

**檔名去重邏輯**：
```python
# 如果目標檔案已存在，加數字後綴
stem = Path(filename).stem
suffix = Path(filename).suffix
target = target_dir / filename
counter = 2
while target.exists():
    target = target_dir / f"{stem}-{counter}{suffix}"
    counter += 1
```

## 權限設計

### TOOL_APP_MAPPING 新增

```python
# permissions.py
"list_library_folders": "file-manager",
"archive_to_library": "file-manager",
```

### shared_sources 權限檢查

`archive_to_library` 需要額外檢查 `shared_sources.library` 權限：

```python
# 在工具內部
shared_mounts = await _get_user_shared_mounts(ctos_user_id)
if "library" not in shared_mounts:
    return "錯誤：權限不足：無法存取圖書館"
```

## Prompt 更新

Agent prompt 新增圖書館歸檔指引：

```
## 圖書館歸檔

當使用者要求將檔案歸檔至圖書館時：
1. 用 get_message_attachments 找到檔案路徑
2. 用 read_document 讀取內容，判斷分類
3. 用 list_library_folders 瀏覽現有結構，避免重複建立類似的子資料夾
4. 用 archive_to_library 歸檔，注意：
   - category 必須是：技術文件、產品資料、教育訓練、法規標準、設計圖面、其他
   - folder 用中文命名，簡潔描述主題（如：馬達規格、PLC程式）
   - filename 依內容重新命名，格式：品牌-型號-文件類型.副檔名
   - 若無法判斷內容，使用原始檔名，category 設為「其他」
```

## 檔案結構

新增 / 修改的檔案：

| 檔案 | 變更 |
|------|------|
| `services/mcp/nas_tools.py` | 新增 `list_library_folders`、`archive_to_library` |
| `services/permissions.py` | `TOOL_APP_MAPPING` 新增兩個工具 |
| `services/mcp/server.py` | 確認工具自動註冊（`@mcp.tool` 裝飾器） |
| Agent prompt（migration） | 新增圖書館歸檔指引 |
| `tests/test_library_archive.py` | 新增單元測試 |

## 測試計畫

### 單元測試

1. **`_sanitize_path_segment`**：各種路徑穿越攻擊、特殊字元
2. **`archive_to_library`**：
   - 正常歸檔（source 存在、category 合法）
   - category 不合法 → 錯誤
   - source 不在 CTOS zone → 錯誤
   - source 檔案不存在 → 錯誤
   - 目標檔名重複 → 自動加後綴
   - folder 包含 `..` → 被清理
3. **`list_library_folders`**：
   - 正常列出結構
   - 空目錄 → 回傳空結構
   - 指定 path 子目錄

### 整合測試（手動）

1. 掛載 library → 確認讀寫
2. 透過 Line Bot 上傳檔案 → 要求 AI 歸檔 → 確認檔案出現在 library
3. 搜尋 `search_nas_files` → 確認能搜到圖書館的檔案
