## Context
Line Bot 收到圖片/檔案訊息時，會將檔案下載並儲存到 NAS，路徑記錄在 `line_files` 表中。當 AI 要將這些內容加入知識庫時，需要能夠引用這些已儲存的檔案。

現有架構：
- Line 訊息儲存：`line_messages` 表
- Line 檔案儲存：`line_files` 表（記錄 NAS 路徑）
- 知識庫附件：可存於本機（`data/knowledge/assets/`）或 NAS（`nas://knowledge/attachments/`）
- 暫存：圖片/檔案會快取到 `/tmp/linebot_images/` 和 `/tmp/linebot_files/`

問題：
- 對話歷史預設只載入 20 則訊息，用戶若要引用較早的圖片，AI 看不到
- AI 需要有工具查詢更長時間範圍的附件記錄

## Goals / Non-Goals
**Goals:**
- AI 能透過 MCP 工具查詢訊息相關的附件（圖片、檔案等）
- AI 能在建立知識庫筆記時一併加入附件
- AI 能為現有知識庫新增附件
- 附件從 Line Bot NAS 複製到知識庫 NAS（或本機）

**Non-Goals:**
- 不處理影片或大型檔案的串流播放
- 不實作附件編輯或刪除功能（已有現成 API）
- 不改變現有知識庫 UI

## Decisions

### 1. 附件來源識別
**Decision:** 使用 `line_files.nas_path` 作為附件來源，透過訊息 UUID 關聯。

**Alternatives considered:**
- 直接傳 base64 圖片內容：效能差，不適合大檔案
- 傳 Line message_id 重新下載：浪費網路資源，且 Line 內容有時效性

### 2. MCP 工具設計
**Decision:** 新增 `add_note_with_attachments` 工具，接受附件路徑列表。

參數設計：
```python
async def add_note_with_attachments(
    title: str,
    content: str,
    attachments: list[str],  # NAS 路徑列表
    category: str = "note",
    topics: list[str] | None = None,
    project: str | None = None,
) -> str
```

**Alternatives considered:**
- 修改現有 `add_note` 增加可選參數：可能造成向後相容問題
- 使用單一 attachment 參數：不夠彈性，無法處理多附件場景

### 3. 附件複製策略
**Decision:** 從 Line Bot NAS 路徑複製到知識庫儲存區，小於 1MB 存本機，大於等於 1MB 存 NAS。

複製流程：
1. 從 Line Bot NAS 讀取檔案（`smb://192.168.11.50/擎添開發/ching-tech-os/linebot/{path}`）
2. 判斷大小後存到知識庫儲存區
3. 更新知識庫 metadata 的 attachments 欄位

### 4. 查詢訊息附件工具
**Decision:** 新增 `get_message_attachments` MCP 工具，讓 AI 能查詢對話中的附件。

```python
async def get_message_attachments(
    line_user_id: str | None = None,
    line_group_id: str | None = None,
    days: int = 7,           # 預設 7 天，可查更長時間
    file_type: str | None = None,  # 可過濾：image, file, video, audio
    limit: int = 20,
) -> str
```

返回格式範例：
```
找到 3 個附件（最近 7 天）：

1. [圖片] 2026-01-05 14:30
   NAS 路徑：groups/xxx/images/2026-01-05/abc123.jpg
   描述：（圖控系統畫面）

2. [圖片] 2026-01-04 10:15
   NAS 路徑：groups/xxx/images/2026-01-04/def456.png
   描述：（水切爐畫面）
```

### 5. 附件儲存策略（複製 vs 移動 vs 符號連結）
**Decision:** 採用「複製」策略，將檔案從 Line Bot NAS 區複製到知識庫 NAS 區。

**Rationale:**
- Line Bot 檔案可能被後續清理機制刪除
- 知識庫附件需要永久保存
- 兩個區域的生命週期不同，複製較安全

**Alternatives considered:**
- 移動檔案：Line Bot 檔案記錄會失效，其他功能可能受影響
- 符號連結：NAS 不一定支援，且跨目錄連結複雜
- 直接引用原始路徑：生命週期不一致，可能導致知識庫附件失效

## Risks / Trade-offs
- **儲存空間重複**：附件會複製一份到知識庫儲存區
  - Mitigation：知識庫附件依大小決定儲存位置，符合現有策略
- **NAS 連線失敗**：Line Bot NAS 或知識庫 NAS 連線失敗
  - Mitigation：錯誤處理，返回清楚的錯誤訊息

## Migration Plan
無需資料遷移，此為新增功能。

## Open Questions
- 是否需要限制單次新增附件數量？建議暫設上限 10 個。
