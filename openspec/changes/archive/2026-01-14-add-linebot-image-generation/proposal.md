# Change: Line Bot AI 圖片生成功能

## Why
讓 Line Bot 個人 AI 助手能夠根據用戶的文字描述生成圖片，增強 AI 互動體驗。用戶可以直接在 Line 對話中說「畫一隻貓」等指令，AI 會生成圖片並發送給用戶。

## What Changes
- 整合 nanobanana MCP Server 作為圖片生成後端（使用 Google Gemini）
- 擴展 Line Bot AI 的 prompt，加入圖片生成工具使用說明
- 擴展 `validate_nas_file_path` 支援 `nanobanana-output/` 和 `ai-images/` 路徑
- 自動建立 NAS 目錄 symlink，讓生成的圖片可透過 Line Bot 發送
- 自動處理生成的圖片，加上 FILE_MESSAGE 標記讓 Line Bot 發送
- Bot 發送的圖片記錄到 `line_files`，讓用戶可以回覆編輯
- 改進 timeout 處理：streaming 讀取 stdout，保留已完成的 tool_calls
- 加入 tool 執行時間追蹤，在前端 AI Log 顯示每個 tool 的執行時間
- 新增 AI 圖片清理排程任務（每天清理超過 1 個月的圖片）
- 優化 prompt：明確指示查找最近圖片應使用 `get_message_attachments` 而非 `search_nas_files`

## Impact
- Affected specs: `line-bot`
- Affected code:
  - `backend/src/ching_tech_os/services/linebot_ai.py` - 加入 nanobanana 工具、timeout 改進
  - `backend/src/ching_tech_os/services/linebot_agents.py` - 更新 prompt
  - `backend/src/ching_tech_os/services/claude_agent.py` - symlink、streaming、tool timing
  - `backend/src/ching_tech_os/services/mcp_server.py` - prepare_file_message 加入 nas_path
  - `backend/src/ching_tech_os/services/share.py` - 支援新路徑
  - `backend/src/ching_tech_os/services/scheduler.py` - AI 圖片清理任務
  - `frontend/js/ai-log.js` - 顯示 tool 執行時間
  - `frontend/css/ai-log.css` - tool timing 樣式
  - `backend/migrations/versions/030_*.py` - 更新資料庫 prompt
  - `.mcp.json` - nanobanana MCP 設定
