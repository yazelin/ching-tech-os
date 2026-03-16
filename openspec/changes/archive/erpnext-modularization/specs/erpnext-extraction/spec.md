# Spec: ERPNext 模組搬遷至 extends/

## 概述

將 ERPNext 相關的 Prompt、工具白名單、MCP server 設定從主系統移至 `extends/erpnext/`，使其成為可選的外部模組。

## 目標結構

```
extends/erpnext/
├── contributes.yaml              # MCP server 宣告 + module_id
├── skills/
│   ├── project-mgmt/
│   │   └── SKILL.md              # 專案管理（ERPNext Project/Task）
│   ├── inventory/
│   │   └── SKILL.md              # 物料庫存（Item/Stock/Stock Entry）
│   └── vendor/
│       └── SKILL.md              # 廠商客戶（Supplier/Customer）
└── clients/
    └── ching-tech/
        └── config.yaml           # 擎添的 ERPNext 連線資訊（參考用）
```

## contributes.yaml

```yaml
module_id: erpnext

mcp_servers:
  erpnext:
    command: bash
    args: ["-c", "set -a && source ${PROJECT_ROOT}/.env && set +a && uvx erpnext-mcp"]
```

需在 `.env` 的 `ENABLED_MODULES` 加入 `erpnext` 才會啟用。

## Skill 定義

每個 Skill 從 `bot/agents.py` 中對應的 `*_TOOLS_PROMPT` 和 `_FALLBACK_TOOLS` 轉換而來。

### project-mgmt/SKILL.md

- **來源**: `PROJECT_TOOLS_PROMPT` + `_FALLBACK_TOOLS["project-management"]`
- **requires_app**: `project-management`
- **mcp_servers**: `erpnext`
- **allowed_tools**: `mcp__erpnext__list_documents`、`mcp__erpnext__get_document`、`mcp__erpnext__create_document`、`mcp__erpnext__update_document`、`mcp__erpnext__delete_document`、`mcp__erpnext__submit_document`、`mcp__erpnext__cancel_document`、`mcp__erpnext__run_report`、`mcp__erpnext__get_count`、`mcp__erpnext__get_list_with_summary`、`mcp__erpnext__run_method`、`mcp__erpnext__search_link`、`mcp__erpnext__list_doctypes`、`mcp__erpnext__get_doctype_meta`、`mcp__erpnext__make_mapped_doc`、`mcp__erpnext__upload_file`、`mcp__erpnext__upload_file_from_url`、`mcp__erpnext__list_files`、`mcp__erpnext__download_file`、`mcp__erpnext__get_file_url`
- **prompt**: 專案管理 ERPNext 操作指引（查詢專案、任務管理、操作範例）

### inventory/SKILL.md

- **來源**: `INVENTORY_TOOLS_PROMPT` + `_FALLBACK_TOOLS["inventory-management"]`
- **requires_app**: `inventory-management`
- **mcp_servers**: `erpnext`
- **allowed_tools**: 同 project-mgmt 的 erpnext 工具，加上 `mcp__erpnext__get_stock_balance`、`mcp__erpnext__get_stock_ledger`、`mcp__erpnext__get_item_price`、`mcp__erpnext__get_party_balance`、`mcp__erpnext__get_supplier_details`、`mcp__erpnext__get_customer_details`
- **prompt**: 物料庫存 ERPNext 操作指引（查詢物料、庫存異動、廠商客戶）

### vendor/SKILL.md

- **requires_app**: `vendor-management`
- **mcp_servers**: `erpnext`
- **allowed_tools**: `mcp__erpnext__get_supplier_details`、`mcp__erpnext__get_customer_details`、`mcp__erpnext__list_documents`、`mcp__erpnext__get_document`、`mcp__erpnext__create_document`
- **prompt**: 廠商客戶查詢指引（從 INVENTORY_TOOLS_PROMPT 中拆分）

注意：vendor 的 prompt 目前包含在 `INVENTORY_TOOLS_PROMPT` 的「廠商/客戶管理」段落中，需拆分出來。

## 保留在主系統

| 檔案 | 內容 | 原因 |
|------|------|------|
| `services/permissions.py` | `"project-management": True` 等權限定義 | App 權限是主系統框架 |
| `services/permissions.py` | `"vendor-management": True` | 同上 |
| `services/permissions.py` | `"inventory-management": True` | 同上 |

## clients/ 結構

`clients/ching-tech/config.yaml` 為參考用設定，記錄擎添的 ERPNext 連線資訊：

```yaml
# 擎添工業 ERPNext 設定
# 實際連線參數在 .env 中設定（ERPNEXT_URL, ERPNEXT_API_KEY, ERPNEXT_API_SECRET）
erpnext_url: http://ct.erp
```

## 驗證方式

1. 啟用 erpnext 模組後，Line Bot 中說「查詢專案」→ 應使用 ERPNext MCP 回應
2. 不啟用 erpnext 模組時，AI 不應看到任何 ERPNext 相關 prompt 和工具
3. 主系統啟動無 import error
