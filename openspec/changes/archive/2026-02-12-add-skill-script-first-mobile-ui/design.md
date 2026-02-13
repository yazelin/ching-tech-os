# Design: Skill Script-First 與手機操作精簡

## 1. 目標架構

```text
使用者請求
   │
   ▼
Skill Router
   ├─ Script Path（預設）
   │   └─ run_skill_script -> scripts/*.py|*.sh
   └─ MCP Path（必要時）
       └─ mcp__* tools（ERPNext/Printer 等）
```

## 2. Skill 目錄策略

- **Primary Root**: `~/SDD/skill`
- **Fallback Root**: 專案內建 `backend/src/ching_tech_os/skills`
- 載入順序：external first，同名 skill 由 external 覆蓋內建（需記錄來源）

## 3. 內建 Skill 拆分原則

1. 以任務邊界拆分（例如 `knowledge-search`、`knowledge-attachment`）  
2. 每個 skill 只保留單一責任與最小工具集合  
3. 優先以 script 實作通用邏輯，MCP 僅保留系統整合能力

## 4. Script-First 路由規則

- 同一能力若同時有 script 與 MCP：
  - 預設走 script
  - script 失敗且可重試時，才回退 MCP
- 回退事件需記錄 ai_logs（含原因與路由決策）

## 5. 手機端介面策略

- Skill 頁採單欄模式：
  1. 列表（可搜尋/篩選）
  2. 詳情（狀態、必要設定）
  3. 操作（安裝、更新、權限）
- 行動端固定底部操作列，避免捲動後找不到主動作
- 次要設定收斂為 bottom sheet，減少 modal 疊加

## 6. 相容與驗證

- 建立「舊路徑 vs 新路徑」功能對照矩陣
- 每個拆分 skill 必須通過：
  - 工具可用性檢查
  - 權限檢查
  - 失敗回退檢查（script -> MCP）
- 逐批切換，不一次性替換全部內建 skill
