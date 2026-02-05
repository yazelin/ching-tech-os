## REMOVED Requirements

### Requirement: 專案管理應用程式
**Reason**: 專案管理功能遷移至 ERPNext
**Migration**: 使用新增的 ERPNext 應用程式 icon 進入 ERPNext

### Requirement: 物料管理應用程式
**Reason**: 物料管理功能遷移至 ERPNext
**Migration**: 使用新增的 ERPNext 應用程式 icon 進入 ERPNext

### Requirement: 廠商管理應用程式
**Reason**: 廠商管理功能遷移至 ERPNext（若有此 app）
**Migration**: 使用新增的 ERPNext 應用程式 icon 進入 ERPNext

---

## ADDED Requirements

### Requirement: ERPNext 應用程式入口
Web Desktop SHALL 提供 ERPNext 應用程式入口，開新視窗連至 ERPNext。

#### Scenario: 顯示 ERPNext 應用程式
- **WHEN** 使用者檢視桌面應用程式列表
- **THEN** 顯示 ERPNext 應用程式 icon
- **AND** 圖示使用 ERPNext 標誌或相關圖示

#### Scenario: 點擊 ERPNext 應用程式
- **WHEN** 使用者點擊 ERPNext 應用程式 icon
- **THEN** 開啟新瀏覽器視窗
- **AND** 導向 http://ct.erp

#### Scenario: 應用程式排列順序
- **WHEN** 使用者檢視桌面
- **THEN** ERPNext 應用程式顯示在適當位置
- **AND** 取代原本專案管理、物料管理的位置
