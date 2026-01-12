# Proposal: add-linebot-group-delete

## Summary
Line Bot 管理介面目前無法刪除群組記錄，即使群組已經離開（is_active=false）或不再需要。本提案新增群組刪除功能，讓管理者可以清理不需要的群組記錄。

## Problem Statement
- **現狀**：Line Bot 群組頁面只能查看群組、切換 AI 回應開關、綁定專案，無法刪除群組
- **影響**：
  - Bot 被踢出的群組記錄會永久保留
  - 測試群組無法清理
  - 用戶無法管理群組列表

## Proposed Solution
新增群組刪除功能：

1. **後端**：新增 `DELETE /api/linebot/groups/{id}` API
2. **前端**：在群組詳情頁新增刪除按鈕

### 刪除行為
- 刪除群組記錄（`line_groups`）
- 級聯刪除相關訊息（`line_messages`）- 資料庫已設定 ON DELETE CASCADE
- 級聯刪除相關檔案記錄（`line_files`）- 資料庫已設定 ON DELETE CASCADE
- **NAS 實體檔案不刪除**（避免誤刪，由管理員手動清理）

### 安全考量
- 需要確認對話框，避免誤刪
- 顯示將刪除的訊息數量作為警告

## Impact Analysis
- **風險等級**：低
- **影響模組**：Line Bot 管理
- **資料影響**：刪除操作不可逆，但 NAS 檔案保留

## Notes
規格中已有此需求（line-bot/spec.md 第 162-164 行、第 271-274 行），但後端 API 未實作。
