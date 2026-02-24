---
name: file-manager
description: NAS 共用檔案搜尋、檔案訊息與 PDF 轉圖片（script-first）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
    script_mcp_fallback:
      search_nas_files: search_nas_files
      get_nas_file_info: get_nas_file_info
      prepare_file_message: prepare_file_message
      convert_pdf_to_images: convert_pdf_to_images
---

【檔案管理（script-first）】
- 優先使用 `run_skill_script` 呼叫下列 scripts：
  - `search_nas_files`
  - `get_nas_file_info`
  - `prepare_file_message`
  - `convert_pdf_to_images`
- `input` 必須是 JSON 物件字串。

【用法範例】
- `run_skill_script(skill="file-manager", script="search_nas_files", input="{\"keywords\":\"亦達,layout\",\"file_types\":\"pdf\"}")`
- `run_skill_script(skill="file-manager", script="get_nas_file_info", input="{\"file_path\":\"shared://projects/demo.pdf\"}")`
- `run_skill_script(skill="file-manager", script="prepare_file_message", input="{\"file_path\":\"shared://projects/demo.pdf\"}")`
- `run_skill_script(skill="file-manager", script="convert_pdf_to_images", input="{\"pdf_path\":\"ctos://knowledge/demo.pdf\",\"pages\":\"1-3\"}")`
