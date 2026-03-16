# Design: ERPNext 整合模組化

## 架構決策

### D1: MCP 合併機制已就緒，直接複用

printer-modularization 已實作 `_load_extends_mcp_servers()` 和 `_build_merged_mcp_json()`，支援 `contributes.yaml` 的 `module_id` + `ENABLED_MODULES` 控制。ERPNext 直接使用相同機制，無需額外開發。

### D2: 先清理再建立，避免衝突

執行順序：先刪除舊 services 和 agents.py 硬編碼 → 再建立 extends/erpnext。避免新舊 prompt 同時存在導致 AI 收到重複指令。

### D3: vendor prompt 從 INVENTORY_TOOLS_PROMPT 拆分

目前「廠商/客戶管理」段落嵌在 `INVENTORY_TOOLS_PROMPT` 中，但對應的是獨立的 `vendor-management` app 權限。拆分為獨立 Skill 讓權限控制更精確。

拆分方式：
- `inventory/SKILL.md` — 保留物料查詢、庫存異動、Stock Entry 相關內容
- `vendor/SKILL.md` — 搬走「廠商/客戶管理」段落（get_supplier_details、get_customer_details）

### D4: generate_usage_tips_prompt 中的 ERPNext 提示一併清理

`bot/agents.py` 的 `generate_usage_tips_prompt()` 函式中有 project-management 和 inventory-management 的使用提示，這些也需移除。Skill 載入後由 SkillManager 的 prompt 機制取代。

### D5: permissions.py 的 app 權限定義保留

`"project-management"`、`"inventory-management"`、`"vendor-management"` 在 `DEFAULT_APP_PERMISSIONS` 中的定義保留。這是主系統的權限框架，Skill 的 `requires_app` 需要這些定義來判斷使用者是否有權限。模組不啟用時，權限存在但無對應 Skill，無害。

### D6: services/__init__.py 的 project_service 匯出

`services/__init__.py` 可能有 `project_service` 的匯出，需一併清理避免 import 時觸發已刪除模組的載入。

## 修改檔案清單

### 刪除

| 檔案 | 說明 |
|------|------|
| `services/project.py` | 舊專案管理邏輯 |
| `services/inventory.py` | 舊物料庫存邏輯 |
| `services/vendor.py` | 舊廠商管理邏輯 |
| `models/project.py` | 舊專案資料模型 |

### 修改

| 檔案 | 動作 |
|------|------|
| `services/share.py` | 移除 project/project_attachment 分支和 get_project_attachment_info() |
| `api/share.py` | 移除 project_attachment 下載分支 |
| `main.py` | 移除 project OG 標籤分支 |
| `services/bot/agents.py` | 移除 PROJECT_TOOLS_PROMPT、INVENTORY_TOOLS_PROMPT、對應映射和 usage tips |
| `modules.py` | 移除 erpnext builtin 定義 |
| `.mcp.json` | 移除 erpnext server 設定 |
| `.mcp.json.example` | 移除 erpnext server 設定 |

### 新增

| 檔案 | 說明 |
|------|------|
| `extends/erpnext/contributes.yaml` | module_id + MCP server 宣告 |
| `extends/erpnext/skills/project-mgmt/SKILL.md` | 專案管理 Skill |
| `extends/erpnext/skills/inventory/SKILL.md` | 物料庫存 Skill |
| `extends/erpnext/skills/vendor/SKILL.md` | 廠商客戶 Skill |
| `extends/erpnext/clients/ching-tech/config.yaml` | 參考用設定 |
