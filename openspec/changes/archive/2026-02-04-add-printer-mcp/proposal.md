# Add Printer MCP Integration

## Summary

整合 [yazelin/printer-mcp](https://github.com/yazelin/printer-mcp) 作為外部 MCP Server，讓 AI Agent 可以直接列印檔案。類似 nanobanana 的整合方式，透過 `uvx printer-mcp` 啟動獨立的 MCP Server。

## Motivation

目前系統中 NAS 檔案、Line/Telegram 上傳檔案、AI 生成簡報等都儲存在伺服器上，使用者需要手動下載再列印。整合 printer-mcp 後，AI Agent 可直接將這些檔案送至印表機列印。

## Approach

### 架構概覽

```
使用者（Line/Telegram/Web）
  → AI Agent 收到列印請求
  → 解析檔案路徑（ctos:// / shared:// / nas://）
  → 轉換為實際檔案系統路徑（/mnt/nas/...）
  → 呼叫 printer-mcp 的 print_file 工具
  → CUPS 送出列印工作
```

### 整合方式（類似 nanobanana）

在 `.mcp.json` 新增 printer-mcp server：

```json
{
  "printer": {
    "type": "stdio",
    "command": "uvx",
    "args": ["printer-mcp"]
  }
}
```

### 檔案路徑處理（關鍵問題）

printer-mcp 接受的是**絕對檔案系統路徑**，但系統中的檔案使用虛擬協議路徑：

| 來源 | 虛擬路徑 | 實際路徑 |
|------|---------|---------|
| Line 群組上傳 | `ctos://linebot/files/groups/{gid}/{date}/{file}` | `/mnt/nas/ctos/tenants/{tid}/linebot/files/groups/{gid}/{date}/{file}` |
| Line 私訊上傳 | `ctos://linebot/files/users/{uid}/{date}/{file}` | `/mnt/nas/ctos/tenants/{tid}/linebot/files/users/{uid}/{date}/{file}` |
| Telegram 上傳 | `ctos://linebot/telegram/{cid}/{date}/{file}` | `/mnt/nas/ctos/tenants/{tid}/linebot/telegram/{cid}/{date}/{file}` |
| 知識庫附件 | `ctos://knowledge/{path}` | `/mnt/nas/ctos/tenants/{tid}/knowledge/{path}` |
| AI 簡報 | `ctos://ai-presentations/{file}` | `/mnt/nas/ctos/tenants/{tid}/ai-presentations/{file}` |
| NAS 專案 | `shared://projects/{path}` | `/mnt/nas/projects/{path}` |
| NAS 線路圖 | `shared://circuits/{path}` | `/mnt/nas/circuits/{path}` |

**解決方案**：在 ching-tech-os MCP Server 新增 `print_file` 工具，負責：
1. 接收虛擬路徑或 MCP 工具回傳的路徑
2. 透過 PathManager 轉換為實際絕對路徑
3. 驗證檔案存在且可讀
4. 呼叫系統 CUPS `lp` 指令列印（直接使用 CUPS，不經過 printer-mcp）

**或者**，同時配置 printer-mcp 作為獨立 MCP Server（供 Claude Code 直接使用），並在 ching-tech-os MCP Server 新增包裝工具（供 Line/Telegram Bot 使用）。

### 支援的檔案格式

printer-mcp 支援：PDF、純文字、圖片（PNG, JPG, JPEG, GIF, BMP, TIFF, WebP）

不支援但常見的格式（需轉換）：`.docx`, `.xlsx`, `.pptx` → 需先轉 PDF

### 前置需求

- CUPS 已安裝並設定印表機
- `uvx printer-mcp` 可正常執行

## Scope

- **包含**：
  - ching-tech-os MCP Server 新增 `print_file` 工具（路徑轉換 + 列印）
  - ching-tech-os MCP Server 新增 `list_printers` 工具（查詢可用印表機）
  - `.mcp.json` 新增 printer-mcp 設定（供 Claude Code 直接使用）
  - AI Agent prompt 更新（告知有列印功能）
  - 權限控管（新增「列印」應用權限）

- **不包含**：
  - Office 文件轉 PDF（未來可擴充）
  - 前端列印 UI（未來可擴充）
  - 印表機管理介面

## Risks

1. **CUPS 未安裝/未設定**：需確認生產環境有 CUPS 且已設定印表機
2. **NAS 掛載問題**：若 NAS 未掛載，檔案路徑無法存取
3. **檔案格式限制**：不支援 Office 格式直接列印
