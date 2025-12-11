# Change: 專案里程碑管理

**Status**: implemented

## Why

工業專案需要追蹤多個重要時間點，例如交機、場測、驗收等關鍵里程碑。目前專案只有開始和結束日期，無法有效管理專案期程中的各個階段性目標與進度追蹤。

## What Changes

- 新增專案里程碑（Milestones）功能
- 在「概覽」標籤頁中顯示里程碑時間軸
- 支援里程碑 CRUD 操作
- 追蹤預計日期與實際完成日期
- 顯示里程碑狀態（待處理/進行中/已完成/延遲）
- 支援自訂里程碑類型

## Impact

- Affected specs: `project-management`（新增里程碑相關需求）
- Affected code:
  - `backend/src/ching_tech_os/api/project.py` - 新增里程碑 API
  - `backend/src/ching_tech_os/services/project.py` - 新增里程碑服務層
  - `backend/src/ching_tech_os/models/project.py` - 新增里程碑模型
  - `frontend/js/project-management.js` - 新增里程碑 UI
  - `frontend/css/project-management.css` - 新增里程碑樣式
  - `backend/migrations/versions/006_create_projects.py` - 里程碑資料表（已合併）
