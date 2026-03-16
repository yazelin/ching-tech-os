# Tasks: ERPNext 整合模組化

## 1. 清理遺留 services

- [x] 1.1 刪除 `services/project.py`
- [x] 1.2 刪除 `services/inventory.py`
- [x] 1.3 刪除 `services/vendor.py`
- [x] 1.4 刪除 `models/project.py`
- [x] 1.5 清理 `services/__init__.py` 中的 project_service 匯出（無需修改）

## 2. 清理死碼分支

- [x] 2.1 `services/share.py` — 移除 project/project_attachment 分支和 `get_project_attachment_info()`
- [x] 2.2 `api/share.py` — 移除 `download_shared_file()` 中的 project_attachment 分支和 ProjectError import
- [x] 2.3 `main.py` — 移除 `short_share_url()` 中的 project OG 標籤分支

## 3. 清理 agents.py 硬編碼

- [x] 3.1 移除 `PROJECT_TOOLS_PROMPT`、`INVENTORY_TOOLS_PROMPT` 常數
- [x] 3.2 移除 `APP_PROMPT_MAPPING` 中的 `"project-management"`、`"inventory-management"` 項目
- [x] 3.3 移除 `_FALLBACK_TOOLS` 中的 `"project-management"`、`"inventory-management"` 項目
- [x] 3.4 清理 `generate_usage_tips_prompt()` 中的 project-management、inventory-management 提示

## 4. 清理 modules.py 和 MCP 設定

- [x] 4.1 `modules.py` — 移除 `erpnext` builtin 模組定義
- [x] 4.2 `.mcp.json` — 移除 erpnext server 設定
- [x] 4.3 `.mcp.json.example` — 移除 erpnext server 設定

## 5. 建立 extends/erpnext 模組

- [x] 5.1 建立 `extends/erpnext/contributes.yaml`（module_id: erpnext + MCP server 宣告）
- [x] 5.2 建立 `extends/erpnext/skills/project-mgmt/SKILL.md`（從 PROJECT_TOOLS_PROMPT 轉換）
- [x] 5.3 建立 `extends/erpnext/skills/inventory/SKILL.md`（從 INVENTORY_TOOLS_PROMPT 拆分，保留物料庫存部分）
- [x] 5.4 建立 `extends/erpnext/skills/vendor/SKILL.md`（從 INVENTORY_TOOLS_PROMPT 拆分，廠商客戶部分）
- [x] 5.5 建立 `extends/erpnext/clients/ching-tech/config.yaml`
- [x] 5.6 更新 `.env` 加入 `erpnext` 到 ENABLED_MODULES
- [x] 5.7 更新 `.env.example` 和 `docs/backend.md` 的 erpnext 模組說明（標註需搭配 extends/erpnext）

## 6. 驗證

- [x] 6.1 確認無 import error 且 `extends MCP servers` 包含 erpnext（本地測試通過）
- [x] 6.2 ENABLED_MODULES 控制已在 printer-modularization 中驗證，同機制適用
