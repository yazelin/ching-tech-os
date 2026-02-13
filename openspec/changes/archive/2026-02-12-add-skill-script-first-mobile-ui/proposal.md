# Proposal: Skill Script-First 與手機操作精簡

## Why

目前 skill 系統雖已支援 Hub 安裝與 script runner，但仍有三個痛點：

1. **內建 skills 綁定專案程式碼目錄**：不利於獨立維護與跨專案複用  
2. **MCP 依賴偏高**：大量流程仍直接暴露 MCP tool，skill 模組化不足  
3. **手機操作層級過深**：Skill 管理在小螢幕下仍有過多切換與彈窗

## What Changes

1. **外部 Skill 根目錄標準化**  
   - 新增外部根目錄：`~/SDD/skill`（可設定覆寫）  
   - 內建 skills 拆分為可獨立發佈/同步的 skill 套件  

2. **Script-First 工具策略**  
   - 新增規範：優先以 `scripts/*.py|*.sh` 實作 skill 能力  
   - 僅保留跨系統必要能力使用 MCP（例如 ERPNext、印表機）  
   - 同功能同時存在時，預設優先 script，MCP 作為備援  

3. **手機端 Skill 管理 UI 精簡**  
   - Skill 管理改為單欄堆疊流程：列表 → 詳情 → 操作  
   - 高頻操作統一在底部固定操作列（安裝/更新/啟用）  
   - 低頻設定收斂至底部抽屜，降低切頁與模態框數量  

4. **穩定性與驗證機制**  
   - 建立 script/mcp 對照矩陣與回歸測試清單  
   - 以功能等價為準則逐步替換，確保既有功能不中斷  

## Impact

- 影響 capabilities：`skill-management`、`bot-platform`、`mobile-app-layout`
- 會新增遷移腳本與設定項（skill root path、routing policy）
- 不直接改變業務功能語意，重點在執行路徑與操作體驗優化

## Risk

- script 化過程可能出現工具行為差異，需要分階段比對  
- 外部 skill 目錄權限與部署流程需明確規範  
- 手機 UI 精簡需避免犧牲進階管理能力
