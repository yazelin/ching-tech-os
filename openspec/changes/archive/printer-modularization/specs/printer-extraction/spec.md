# Spec: Printer 模組搬遷至 extends/

## 概述

將 Printer 相關的 Skill、MCP server 設定、Agent Prompt 從主系統移至 `extends/printer/`，使其成為可選的外部模組。

## 目標結構

```
extends/printer/
├── contributes.yaml          # MCP server 宣告
└── skills/
    └── printer/
        └── SKILL.md          # 列印 Skill（從 backend 搬過來）
```

## 搬遷項目

### 搬到 extends/printer/

| 來源 | 目標 | 說明 |
|------|------|------|
| `backend/src/ching_tech_os/skills/printer/SKILL.md` | `extends/printer/skills/printer/SKILL.md` | Skill 定義，內容不變 |
| `.mcp.json.example` 中的 printer 設定 | `extends/printer/contributes.yaml` | 轉為 YAML 格式 |

### 從主系統移除

| 檔案 | 移除內容 |
|------|---------|
| `bot/agents.py` | `PRINTER_TOOLS_PROMPT` 常數 |
| `bot/agents.py` | `APP_PROMPT_MAPPING["printer"]` |
| `bot/agents.py` | `_FALLBACK_TOOLS["printer"]` |
| `modules.py` | `docs-tools.app_ids` 中的 `"printer"` |
| `.mcp.json.example` | `printer` server 設定 |
| `backend/src/ching_tech_os/skills/printer/` | 整個目錄（已搬到 extends） |

### 保留在主系統

| 檔案 | 內容 | 原因 |
|------|------|------|
| `services/mcp/presentation_tools.py` | `prepare_print_file` 工具 | 屬於 ching-tech-os MCP server，負責路徑轉換 |
| `services/permissions.py` | `"printer": True` 權限定義 | App 權限是主系統功能 |
| `services/permissions.py` | `"prepare_print_file": "printer"` 工具權限映射 | 同上 |

## Skill 載入路徑

搬遷後，Printer Skill 的載入方式改變：

- **之前**：SkillManager 從 `backend/src/ching_tech_os/skills/printer/` 載入（內建 skill）
- **之後**：主系統啟動時掃描 `extends/printer/`，將 `skills/` 目錄註冊到 SkillManager

需確認 `extends/*/skills/` 的 Skill 載入是否已由現有的 `contributes.yaml` 機制支援，或需要擴充。

## 驗證方式

1. 啟用 extends/printer 後，Line Bot 中說「列出印表機」→ 應正常回應
2. 不啟用 extends/printer 時，AI 不應看到任何 printer 相關的 prompt 和工具
3. `prepare_print_file` MCP 工具仍可用（它屬於 ching-tech-os server，不受影響）
