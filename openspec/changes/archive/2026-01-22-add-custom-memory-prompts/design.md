## Context

Line Bot 目前使用統一的 Agent Prompt（linebot-personal 和 linebot-group），無法針對特定群組或個人進行客製化。使用者希望能讓 AI 「記住」某些特定的偏好或規則，例如：
- 群組 A：「回報專案進度時，客戶新增的項目要標註 ⭐客戶新增」
- 群組 B：「專案名稱用代號 P001 表示」
- 個人：「我習慣用表格格式看資料」

這些記憶需要：
1. 持久保存（不會因對話重置而消失）
2. 自動套用到後續對話
3. 可透過對話或 Web UI 管理

## Goals / Non-Goals

**Goals:**
- 支援群組和個人兩種範圍的自訂記憶
- 透過 Line 對話可以新增、修改、刪除記憶（AI 自動判斷如何整理）
- 透過 CTOS Web App 可以管理記憶
- 記憶自動整合到 AI prompt 中

**Non-Goals:**
- 不支援跨群組共享記憶（每個群組獨立）
- 不支援角色層級的記憶（如「所有 PM 都套用」）

## Decisions

### 1. 資料模型設計

採用兩張獨立的表格，分別儲存群組記憶和個人記憶：

```sql
-- 群組記憶
CREATE TABLE line_group_memories (
    id UUID PRIMARY KEY,
    line_group_id UUID NOT NULL REFERENCES line_groups(id) ON DELETE CASCADE,
    title VARCHAR(128) NOT NULL,           -- 記憶標題（AI 自動產生）
    content TEXT NOT NULL,                  -- 記憶內容（會加入 prompt）
    is_active BOOLEAN DEFAULT true,         -- 是否啟用
    created_by UUID REFERENCES line_users(id), -- 建立者（Line 用戶）
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 個人記憶
CREATE TABLE line_user_memories (
    id UUID PRIMARY KEY,
    line_user_id UUID NOT NULL REFERENCES line_users(id) ON DELETE CASCADE,
    title VARCHAR(128) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**決策理由：**
- 分開兩張表格較直觀，避免複雜的多型態設計
- `title` 欄位由 AI 自動產生，方便使用者在 UI 中識別
- `is_active` 欄位支援暫時停用而不刪除
- `created_by` 記錄群組記憶的建立者，供稽核用
- 不設條數限制，讓使用者自由管理

### 2. Prompt 整合方式

在 `build_system_prompt()` 中，於現有 prompt 末尾加入記憶區塊：

```
【自訂記憶】
以下是此對話的自訂記憶，請在回應時遵循這些規則：
1. 列出專案進度時，客戶新增的項目標註「⭐客戶新增」
2. 使用表格格式呈現清單資料

請自然地遵循上述規則，不需要特別提及或確認。
```

**決策理由：**
- 放在 prompt 末尾確保記憶內容被看到
- 使用編號列表清楚呈現多條記憶
- 明確指示 AI 「自然遵循」而非特別提及

### 3. MCP 工具設計

新增以下 MCP 工具，讓 AI 自行判斷如何整理記憶：

```python
# 新增記憶（AI 自動產生標題）
add_memory(
    content: str,         # 記憶內容
    title: str?,          # 標題（可選，AI 會自動產生合適的標題）
    line_group_id: str?,  # 群組 ID（群組對話時提供）
    line_user_id: str?,   # 用戶 ID（個人對話時提供）
) -> str

# 查詢記憶
get_memories(
    line_group_id: str?,
    line_user_id: str?,
) -> str

# 更新記憶（AI 判斷要整合或修改）
update_memory(
    memory_id: str,       # 記憶 ID
    title: str?,          # 新標題
    content: str?,        # 新內容
    is_active: bool?,     # 是否啟用
) -> str

# 刪除記憶
delete_memory(
    memory_id: str,       # 記憶 ID
) -> str
```

**AI 自動整理邏輯：**
- 用戶說「記住 XXX」→ AI 呼叫 `add_memory`，自動產生合適的標題
- 用戶說「修改記憶 XXX」→ AI 先用 `get_memories` 查詢，再用 `update_memory` 更新
- 用戶說「不要再 XXX」→ AI 判斷是否要刪除或更新現有記憶
- 相似的記憶由 AI 判斷是否要整合成一條

**決策理由：**
- 標題由 AI 自動產生，降低使用者負擔
- AI 可以智慧判斷是新增、更新還是整合記憶
- 工具名稱使用 `memory` 而非 `prompt`，對使用者更直觀

### 4. Web App 設計

在 CTOS 中新增「Line Bot 記憶管理」App：

```
+----------------------------------+
| 記憶管理                          |
+----------------------------------+
| [群組] [個人]                     |  <- 分頁切換
+----------------------------------+
| ▼ 專案討論群                      |  <- 群組下拉選單
+----------------------------------+
| □ 客戶新增標註                    |  <- 記憶列表
|   列出進度時標註 ⭐客戶新增        |
|                      [編輯][刪除] |
+----------------------------------+
| □ 表格格式                        |
|   用表格呈現清單                   |
|                      [編輯][刪除] |
+----------------------------------+
|                       [+ 新增]   |
+----------------------------------+
```

**決策理由：**
- 分頁切換群組/個人記憶
- 勾選框控制啟用/停用
- 列表顯示標題和內容預覽
- 編輯使用彈出視窗
- 新增時用戶可自行輸入標題和內容

### 5. 對話中的使用方式

使用者可以用自然語言要求 AI 管理記憶，AI 自動判斷如何處理：

```
用戶：「記住：列出專案進度時，客戶新增的要特別標註」
AI：好的，我已經記住了！
   （AI 自動產生標題「專案進度客戶標註」並儲存內容）

用戶：「以後客戶新增的用 🌟 標示」
AI：好的，我已經更新記憶設定，改用 🌟 標示客戶新增項目。
   （AI 判斷這是修改現有記憶，自動更新）

用戶：「列出我設定的記憶」
AI：您目前有以下記憶設定：
    1. 專案進度客戶標註：列出進度時客戶新增標 🌟

用戶：「不要再標註客戶新增了」
AI：好的，已刪除相關的記憶設定。
```

## Risks / Trade-offs

### 記憶內容可能與系統 prompt 衝突
- **風險**：使用者設定的記憶可能與系統規則矛盾
- **緩解**：在 prompt 中明確說明「自訂記憶是偏好設定，系統安全規則優先」

### 群組記憶的權限控制
- **風險**：任何群組成員都能修改群組記憶
- **決定**：V1 不做權限控制（與現有專案成員操作一致），後續可依需求加入

### AI 判斷錯誤
- **風險**：AI 可能誤判用戶意圖（如誤刪記憶）
- **緩解**：AI 操作後會回報結果，用戶可以糾正；Web UI 提供完整管理功能

## Migration Plan

1. 建立新資料表（不影響現有功能）
2. 修改 `build_system_prompt()` 載入記憶（記憶為空時不影響）
3. 新增 MCP 工具（漸進式啟用）
4. 更新 linebot prompt 說明記憶管理功能
5. 新增 Web App（獨立功能）

## Open Questions

- Q: 是否需要支援「匯入/匯出」記憶功能？
  A: V1 不需要，後續可依需求加入

- Q: 群組管理員是否可以清除所有成員的記憶？
  A: V1 不需要，任何成員都能管理群組記憶
