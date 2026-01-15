# Tasks: Line Bot AI 圖片生成功能

## 1. 環境設定
- [x] 1.1 在 `.mcp.json` 加入 nanobanana MCP Server 設定
- [x] 1.2 將 `.mcp.json` 加入 `.gitignore`（避免 API key 外洩）
- [x] 1.3 建立 `.mcp.json.example` 範本
- [x] 1.4 更新 `.env.example` 加入 nanobanana 相關說明

## 2. 後端整合
- [x] 2.1 在 `claude_agent.py` 自動建立 NAS 目錄和 symlink
  - `/tmp/ching-tech-os-cli/nanobanana-output` → `/mnt/nas/ctos/linebot/files/ai-images`
- [x] 2.2 在 `linebot_ai.py` 加入 `mcp__nanobanana__generate_image` 工具
- [x] 2.3 在 `linebot_agents.py` 更新 prompt 加入圖片生成說明
- [x] 2.4 擴展 `share.py` 的 `validate_nas_file_path` 支援：
  - `nanobanana-output/` 路徑
  - `ai-images/` 路徑
  - `ctos_mount_path` 路徑

## 3. 自動處理機制
- [x] 3.1 實作 `extract_generated_images_from_tool_calls` 從 tool_calls 提取生成圖片
- [x] 3.2 實作 `auto_prepare_generated_images` 自動呼叫 prepare_file_message
- [x] 3.3 整合到 `process_message_with_ai` 主流程

## 4. 測試驗證
- [x] 4.1 測試 AI 能正確呼叫 `generate_image` 生成圖片
- [x] 4.2 測試自動處理機制能正確補上 FILE_MESSAGE 標記
- [x] 4.3 確認用戶能在 Line 對話中收到圖片

## 5. 文件更新
- [x] 5.1 更新 `CLAUDE.md` 加入 AI logs 查詢方式
- [x] 5.2 更新 `docs/linebot.md` 加入圖片生成功能說明

## 6. 圖片記錄與找回機制
- [x] 6.1 Bot 發送的圖片記錄到 `line_files`（讓用戶可以回覆編輯）
  - 在 `mcp_server.py` 的 `prepare_file_message` 加入 `nas_path`
  - 在 `linebot_ai.py` 發送圖片後呼叫 `save_file_record`
- [x] 6.2 刪除 `get_recent_ai_images` 工具（設計問題：無法區分用戶）
- [x] 6.3 更新 prompt 改用 `get_message_attachments` 來找回圖片
- [x] 6.4 統一路徑格式為 `ai-images/xxx.jpg`

## 7. Timeout 處理改進
- [x] 7.1 Timeout 從 180 秒延長到 300 秒
- [x] 7.2 改成 streaming 讀取 stdout，timeout 時保留已完成的 tool_calls
- [x] 7.3 加入 tool 執行時間記錄和診斷資訊
- [x] 7.4 Timeout 但有生成圖片時，仍嘗試發送給用戶
- [x] 7.5 修復 buffer limit 問題（64KB → 10MB）

## 8. 排程任務
- [x] 8.1 新增 `cleanup_ai_images` 排程任務
  - 每天凌晨 4:30 執行
  - 清理超過 1 個月的 AI 生成圖片

## 9. Tool 執行時間顯示
- [x] 9.1 在 `ClaudeResponse` 加入 `tool_timings` 欄位
- [x] 9.2 在 `_parse_stream_json_with_timing` 追蹤每個 tool 的執行時間
- [x] 9.3 在 `linebot_ai.py` 將 timing 存入 `parsed_response`
- [x] 9.4 在前端 AI Log 執行流程中顯示每個 tool 的執行時間
- [x] 9.5 修復 `.ai-log-flow-icon` 的 SVG 大小問題

## 10. Prompt 優化
- [x] 10.1 在 `search_nas_files` 說明加入警告：查找最近圖片請用 `get_message_attachments`
- [x] 10.2 在 `get_message_attachments` 說明加入：用於查找最近的圖片，比 search_nas_files 更快
- [x] 10.3 建立 migration 030 同步資料庫 prompt
