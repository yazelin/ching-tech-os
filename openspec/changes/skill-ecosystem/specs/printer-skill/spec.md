# Spec: Printer Skill 化

## Purpose
將硬編碼的 printer MCP server 轉為標準 skill 格式，統一管理。

### Requirement: Printer SKILL.md
系統 SHALL 在 `skills/printer/` 建立 SKILL.md：

```yaml
---
name: printer
description: 控制公司印表機 — 列印文件、查詢狀態。需要 CUPS 環境。
allowed-tools: print_document list_printers get_printer_status
license: MIT
compatibility:
  platforms:
    - ching-tech-os
metadata:
  openclaw:
    requires:
      env:
        - name: PRINTER_HOST
          required: false
          description: "印表機 IP（預設使用本機 CUPS）"
  ctos:
    requires_app: "printer"
    mcp_servers: "printer"
---
```

### Requirement: MCP Server 宣告式啟動
SkillManager SHALL 支援從 `metadata.ctos.mcp_servers` 讀取 MCP server 名稱。
MCP server 的實際啟動設定 SHALL 保留在現有的 MCP 設定機制中（不在 SKILL.md 裡寫 command）。
SKILL.md 只宣告「需要哪個 MCP server」，實際啟動由系統管理。

#### Scenario: Skill 宣告 MCP server
WHEN SkillManager 載入一個宣告了 `mcp_servers` 的 skill
THEN 系統在該使用者有對應權限時，才啟動該 MCP server
AND MCP server 的 tools 加入該使用者的 allowed tools

### Requirement: 從硬編碼移除
系統 SHALL 從 MCP server 硬編碼列表中移除 printer 相關設定。
Printer MCP server 的啟動 SHALL 完全由 skill 機制控管。

#### Scenario: 無 printer 權限
WHEN 使用者沒有 `printer` app 權限
THEN printer MCP server 不會被載入
AND `print_document` 等工具不會出現在 allowed tools 中

### Requirement: 遷移
系統 SHALL 提供無感遷移路徑：
- Printer skill 作為內建 skill 預裝
- 現有 printer 權限設定自動繼承
- 使用者不需要手動操作
