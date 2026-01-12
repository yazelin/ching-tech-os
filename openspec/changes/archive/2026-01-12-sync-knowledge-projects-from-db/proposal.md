# Proposal: sync-knowledge-projects-from-db

## Summary
知識庫的專案選項目前是硬編碼在程式碼中，無法顯示專案管理系統中新建立的專案。本提案修改知識庫標籤 API，讓專案選項從資料庫 `projects` 表動態載入。

## Problem Statement
- **現狀**：`/api/knowledge/tags` API 返回的專案列表是寫死的：`["rosagv", "ching-tech-os", "jaba", "jaba-line-bot", "fish-cv", "common"]`
- **位置**：`backend/src/ching_tech_os/models/knowledge.py:187`
- **影響**：
  - 知識庫篩選器的「所有專案」下拉選單無法顯示新專案
  - 知識編輯器的「專案（多選）」選項無法選擇新專案
  - 專案管理與知識庫之間的專案資料不同步

## Proposed Solution
修改 `get_all_tags()` 函數，在返回標籤時從資料庫 `projects` 表動態查詢專案名稱列表。

### 修改範圍
1. **後端 `services/knowledge.py`**：修改 `get_all_tags()` 函數，查詢資料庫取得專案列表
2. **後端 `models/knowledge.py`**：移除 `TagsResponse` 預設值中的硬編碼專案列表

### 不需變更
- 前端程式碼不需修改（已正確使用 API 返回的 `tags.projects`）
- 資料庫 schema 不需修改（`projects` 表已存在）

## Impact Analysis
- **風險等級**：低
- **影響模組**：知識庫
- **向下相容**：是（API 介面不變）

## Alternatives Considered
1. **前端直接呼叫專案 API**：增加前端複雜度，需維護兩個資料來源
2. **定期同步**：增加維護複雜度，資料可能延遲
3. **手動更新**：不切實際，容易遺漏

選擇方案 1（後端整合）因為：實作最簡單、對前端透明、資料即時同步。
