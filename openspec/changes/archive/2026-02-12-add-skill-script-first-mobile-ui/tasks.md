## Tasks

### Phase 1: Skill 路徑與載入基礎
- [x] 新增 external skill root 設定（預設 `~/SDD/skill`）
- [x] SkillManager 支援 external-first 載入順序
- [x] 同名 skill 來源覆蓋規則與日誌

### Phase 2: Script-First 路由
- [x] 定義 script 與 MCP 同功能時的優先規則
- [x] 加入 script 失敗回退 MCP 的條件與紀錄
- [x] 為路由決策新增可觀測欄位（ai_logs / debug logs）

### Phase 3: 內建 Skill 拆分
- [x] 盤點現有內建 skills 的責任邊界
- [x] 將可 script 化能力拆分為獨立 skills（單一責任）
- [x] 僅保留必要 MCP 整合能力

### Phase 4: 手機 UI 精簡
- [x] Skill 管理頁改單欄堆疊流程（列表→詳情→操作）
- [x] 新增底部固定操作列（主要動作）
- [x] 次要設定改為 bottom sheet，減少多層 modal

### Phase 5: 穩定性驗證
- [x] 建立 script/mcp 功能對照矩陣
- [x] 回歸測試核心 skill 流程（權限、安裝、執行、回退）
- [x] 完成 rollout 檢查清單後再切換預設路由
