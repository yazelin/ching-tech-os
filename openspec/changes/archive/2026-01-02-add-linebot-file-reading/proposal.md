# Proposal: add-linebot-file-reading

## Summary

讓 Line Bot AI 能夠讀取用戶上傳的文字檔案和 PDF（如 .txt、.md、.pdf 等），目前只有圖片會被複製到 `/tmp` 供 AI 讀取。

## Problem

目前 Line Bot AI 處理流程：
- 圖片：下載到 NAS → 複製到 `/tmp/linebot-images/` → AI 可用 Read 工具讀取
- 檔案（.txt、.pdf 等）：下載到 NAS → **沒有複製到 /tmp** → AI 無法讀取

用戶上傳 .txt 或 .pdf 檔案後，AI 無法存取該檔案內容。

## Solution

1. 新增 `/tmp/linebot-files/` 目錄處理非圖片檔案
2. 新增 `ensure_temp_file()` 函數，從 NAS 複製檔案到暫存
3. 修改對話歷史組合邏輯，包含檔案路徑資訊
4. 支援回覆舊檔案訊息（類似回覆圖片）
5. 擴展 scheduler 清理 `/tmp/linebot-files/`

## Scope

### In Scope
- 支援文字類檔案：`.txt`、`.md`、`.json`、`.csv`、`.log`、`.xml`、`.yaml`、`.yml`
- 支援 PDF：`.pdf`（Claude Read 工具原生支援）
- 檔案暫存機制（類似圖片暫存）
- 對話歷史包含檔案資訊
- 回覆舊檔案訊息時讀取該檔案
- Scheduler 清理暫存檔案

### Out of Scope
- Office 文件（.docx、.pptx、.xlsx）需要額外工具轉換，本次不實作
- 大檔案處理（超過 5MB 的檔案暫不支援讀取）

## Affected Capabilities
- `line-bot`

## Status
Complete
