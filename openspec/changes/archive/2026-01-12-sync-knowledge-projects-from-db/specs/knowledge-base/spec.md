# knowledge-base Spec Delta

## MODIFIED Requirements

### Requirement: 知識庫 API
知識庫標籤 API SHALL 從專案管理系統動態載入專案列表。

#### Scenario: 取得標籤列表 API（動態專案）
- **WHEN** 前端請求 `GET /api/knowledge/tags`
- **THEN** 後端從 `projects` 資料表查詢所有專案名稱
- **AND** 返回的 `projects` 欄位包含資料庫中所有專案
- **AND** 專案列表按名稱排序
- **AND** 其他標籤欄位（types、categories、roles、levels、topics）維持原有邏輯

#### Scenario: 專案即時同步
- **WHEN** 使用者在專案管理新增專案
- **THEN** 知識庫標籤 API 立即返回新專案
- **AND** 無需重啟服務或手動同步

#### Scenario: 專案管理系統無資料時
- **WHEN** `projects` 資料表為空
- **THEN** 標籤 API 返回空的 `projects` 陣列
- **AND** 其他標籤欄位正常返回
