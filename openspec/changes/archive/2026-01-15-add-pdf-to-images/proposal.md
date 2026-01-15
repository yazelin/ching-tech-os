# Change: Line Bot PDF 轉圖片功能

## Why
用戶經常需要在 Line 上查看 CAD 工程圖（PDF 格式），但 Line 對 PDF 的預覽支援不佳。將 PDF 轉換成圖片可以讓用戶直接在 Line 中預覽工程圖，大幅提升使用體驗。

## What Changes
- 新增 MCP 工具 `convert_pdf_to_images`，將 PDF 檔案轉換為圖片
- Line Bot 支援接收用戶上傳的 PDF，並根據請求轉換為圖片
- Line Bot 支援將 NAS 上的 PDF 轉換為圖片
- Line Bot 支援將專案附件中的 PDF 轉換為圖片
- 轉換後的圖片儲存到 NAS，並透過 Line Bot 發送給用戶
- 使用現有的 **PyMuPDF** 套件進行 PDF 轉換（已安裝）
- 修改 `get_project_attachments` 回傳 storage_path，讓 AI 可取得附件路徑

## Impact
- Affected specs: `line-bot`、`mcp-tools`
- Affected code:
  - `backend/src/ching_tech_os/services/document_reader.py` - 新增轉圖片函式
  - `backend/src/ching_tech_os/services/mcp_server.py` - 新增 MCP 工具
  - `backend/src/ching_tech_os/services/linebot_agents.py` - 更新 prompt 說明
