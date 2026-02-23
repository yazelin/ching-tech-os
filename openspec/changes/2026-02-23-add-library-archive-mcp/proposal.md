# add-library-archive-mcp

## Summary
新增 MCP 工具讓 AI 能將使用者透過 Line/Telegram 上傳的檔案歸檔至擎添圖書館（`shared://library/`）。AI 分析檔案內容後自動分類、重新命名，並複製到圖書館的適當資料夾中。

## Motivation
- 使用者透過 Line/Telegram 上傳的檔案目前只存在 `ctos://linebot/` 區，缺乏有系統的歸檔管道
- 擎添圖書館（`/mnt/nas/library`）已掛載為讀寫 shared mount，但 AI 目前無任何寫入工具
- 希望 AI 能自動建立並維護圖書館的分類結構，方便未來搜尋

## 使用流程

```
使用者 (Line/TG)          AI                              擎添圖書館
─────────────────    ─────────────────────────    ─────────────────────
1. 上傳檔案          (自動儲存至 linebot 區)
2. 「幫我存到圖書館」
                     3. get_message_attachments
                        → 找到檔案路徑
                     4. read_document
                        → 讀取內容分析
                     5. list_library_folders
                        → 瀏覽現有結構
                     6. archive_to_library          → 複製到適當資料夾
                        → 自動分類 + 重新命名
                     7. 回覆歸檔結果
```

## 新增 MCP 工具

### 1. `list_library_folders`
瀏覽圖書館的資料夾結構，讓 AI 了解現有分類以做出歸檔決策。

| 參數 | 類型 | 說明 |
|------|------|------|
| `path` | `str`（可選） | 子路徑，預設為根目錄 |
| `max_depth` | `int`（可選） | 瀏覽深度，預設 2 |

回傳：資料夾樹狀結構（名稱 + 檔案數量）

### 2. `archive_to_library`
將檔案複製到圖書館的指定位置。

| 參數 | 類型 | 說明 |
|------|------|------|
| `source_path` | `str` | 來源檔案路徑（`ctos://linebot/...`） |
| `category` | `str` | 大分類（見下方預設清單） |
| `folder` | `str`（可選） | 主題子資料夾，不存在則自動建立 |
| `filename` | `str` | 新檔名（AI 依內容命名，含副檔名） |

回傳：歸檔後的完整路徑（`shared://library/技術文件/PLC程式/三菱FX5U-使用手冊.pdf`）

## 預設分類結構

```
擎添圖書館/
├── 技術文件/       # 規格書、手冊、datasheet、SOP
├── 產品資料/       # 型錄、報價單、產品目錄
├── 教育訓練/       # 教材、培訓簡報、操作指南
├── 法規標準/       # ISO、CNS、安規、認證文件
├── 設計圖面/       # CAD、線路圖、機構圖
└── 其他/           # 無法分類時的 fallback
```

- 第一層（category）：預定義清單，工具端驗證
- 第二層（folder）：AI 自由命名，隨內容成長
- 檔名：AI 依內容重新命名，格式如 `品牌-產品型號-文件類型.ext`

## 安全限制

1. **寫入範圍限制**：`archive_to_library` 只能寫入 `library_mount_path`，不可寫入其他 shared mount
2. **來源限制**：`source_path` 只接受 CTOS zone（`ctos://linebot/...`）
3. **路徑清理**：filename 和 folder 過濾 `..`、`/` 等特殊字元，防止 path traversal
4. **不覆蓋**：目標檔案已存在時加數字後綴（`-2`、`-3`），不覆蓋
5. **權限控制**：需要 `shared_sources.library: true` 權限
6. **操作方式**：複製（不移動），原始檔案保留在 linebot 區

## Scope
1. **MCP 工具**：新增 `list_library_folders` 和 `archive_to_library` 兩個工具
2. **權限整合**：工具註冊到 `TOOL_APP_MAPPING`，對應 `file-manager` 權限
3. **Prompt 更新**：Agent prompt 加入圖書館歸檔指引和分類規則

## Out of Scope
- 前端 UI（不需要新介面，透過 AI 對話操作）
- 自動觸發歸檔（僅使用者主動要求時觸發）
- 圖書館瀏覽 UI（使用現有檔案管理器即可瀏覽 shared://library/）
- 從 shared 區（projects/circuits）複製檔案到圖書館（本次只支援 ctos 區來源）
