---
name: printer
description: 列印功能
requires_app: printer
tools:
  - prepare_print_file
  - mcp__printer__print_file
  - mcp__printer__list_printers
  - mcp__printer__printer_status
  - mcp__printer__cancel_job
  - mcp__printer__print_test_page
mcp_servers:
  - printer
  - ching-tech-os
---

【列印功能】
列印分兩步驟，先轉換路徑再列印：

步驟 1 - 準備檔案（ching-tech-os 工具）：
- prepare_print_file: 將虛擬路徑轉換為絕對路徑，Office 文件自動轉 PDF
  · file_path: 檔案路徑（必填）
    - 虛擬路徑：ctos://knowledge/attachments/report.pdf、shared://projects/...
    - 絕對路徑：/mnt/nas/ctos/...
  · 回傳：可列印的絕對路徑

步驟 2 - 實際列印（printer-mcp 工具）：
- mcp__printer__print_file: 將檔案送至印表機列印
  · file_path: 步驟 1 回傳的絕對路徑（必填）
  · printer: 印表機名稱（可選，預設使用系統預設）
  · copies: 份數（可選，預設 1）
  · page_size: 紙張大小（可選，A3/A4/A5/B4/B5/Letter/Legal）
  · orientation: 方向（可選，portrait/landscape）
  · color_mode: 色彩模式（可選，gray/color，預設 gray。除非用戶要求彩色列印，否則一律用 gray）
- mcp__printer__list_printers: 查詢可用印表機
- mcp__printer__printer_status: 查詢印表機狀態
- mcp__printer__cancel_job: 取消列印工作

⚠️ 重要：不要跳過步驟 1 直接呼叫 printer-mcp！
  虛擬路徑（ctos://、shared://）必須先經過 prepare_print_file 轉換。
  只有當你已經有絕對路徑（/mnt/nas/...）時才能直接用 printer-mcp。

【支援的檔案格式】
- 直接列印：PDF、純文字（.txt, .log, .csv）、圖片（PNG, JPG, JPEG, GIF, BMP, TIFF, WebP）
- 自動轉 PDF：Office 文件（.docx, .xlsx, .pptx, .doc, .xls, .ppt, .odt, .ods, .odp）

【列印使用情境】
1. 用戶說「把知識庫的報告印出來」
   → search_knowledge("報告") 找到檔案路徑
   → prepare_print_file(file_path="ctos://knowledge/...")
   → mcp__printer__print_file(file_path="回傳的絕對路徑")
2. 用戶說「印 3 份 A3 橫式」
   → prepare_print_file(file_path=...)
   → mcp__printer__print_file(file_path=..., copies=3, page_size="A3", orientation="landscape")
3. 用戶說「列出印表機」
   → mcp__printer__list_printers()（不需要步驟 1）
