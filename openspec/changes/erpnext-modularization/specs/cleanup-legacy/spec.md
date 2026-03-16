# Spec: 清理 ERPNext 遺留碼

## 概述

刪除主系統中已被 ERPNext MCP 取代的舊業務邏輯，以及 share/main 中引用這些服務的死碼分支。

## 刪除檔案

| 檔案 | 行數 | 說明 |
|------|------|------|
| `services/project.py` | ~1,158 | 舊專案管理邏輯，零 API route，資料表已不存在 |
| `services/inventory.py` | 大量 | 舊物料庫存邏輯，零引用 |
| `services/vendor.py` | — | 舊廠商管理邏輯，零引用 |
| `models/project.py` | ~367 | 舊專案資料模型（Project、Milestone 等） |

## 清理死碼分支

### services/share.py

移除 `resource_type` 為 `"project"` 和 `"project_attachment"` 的處理分支：
- `get_public_resource()` 中的 project/project_attachment 分支
- `get_project_attachment_info()` 函式
- 其他引用 project 的條件分支

### api/share.py

移除 `download_shared_file()` 中的 `project_attachment` 分支：
- `from ..services.project import get_attachment_content, ProjectError`
- `elif resource_type == "project_attachment":` 區塊
- `except ProjectError` 處理

### main.py

移除 `short_share_url()` 中的 project OG 標籤分支：
- `elif resource_type == "project":` 區塊
- `from .services import project_service`

## 清理 agents.py 硬編碼

### 移除的常數

- `PROJECT_TOOLS_PROMPT` — 專案管理 ERPNext 操作指引
- `INVENTORY_TOOLS_PROMPT` — 物料庫存 ERPNext 操作指引

### 移除的映射項目

- `APP_PROMPT_MAPPING["project-management"]`
- `APP_PROMPT_MAPPING["inventory-management"]`
- `_FALLBACK_TOOLS["project-management"]`
- `_FALLBACK_TOOLS["inventory-management"]`

## 清理 modules.py

- 移除 `erpnext` builtin 模組定義（含 `app_ids: ["project-management", "inventory-management", "vendor-management"]`）

## 清理 .mcp.json

- 移除 `.mcp.json` 和 `.mcp.json.example` 中的 erpnext server 設定

## 驗證

- 資料庫確認無 `project`、`project_attachments` 資料表
- 資料庫確認無 `resource_type = 'project'` 或 `'project_attachment'` 的分享連結
- `services/inventory.py`、`services/vendor.py` 零引用
- 刪除後服務正常啟動、無 import error
