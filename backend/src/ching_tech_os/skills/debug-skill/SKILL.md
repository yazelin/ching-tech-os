---
name: debug-skill
description: 系統診斷工具（管理員專用），用於查詢伺服器、AI、Nginx 日誌和資料庫狀態
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    mcp_servers: ching-tech-os
    requires_app: admin
---

【系統診斷工具】
管理員專用的診斷腳本集合，透過 `run_skill_script` 呼叫：

- `check-server-logs`: 查詢 CTOS 伺服器日誌
  · input: {"lines": 50, "keyword": "error"}
  · lines: 查詢行數（預設 50）
  · keyword: 關鍵字過濾（可選）

- `check-ai-logs`: 查詢 AI 對話記錄
  · input: {"limit": 10, "errors_only": false}
  · limit: 查詢筆數（預設 10）
  · errors_only: 僅顯示失敗記錄（預設 false）

- `check-nginx-logs`: 查詢 Nginx 日誌
  · input: {"lines": 50, "type": "error"}
  · lines: 查詢行數（預設 50）
  · type: "access" 或 "error"（預設 "error"）

- `check-db-status`: 查詢資料庫狀態
  · input: {}（無參數）

- `check-system-health`: 綜合健康檢查
  · input: {}（無參數）
  · 一次檢查所有項目，回傳摘要報告
