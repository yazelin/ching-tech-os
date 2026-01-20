# Platform Admin UI Implementation Tasks

## Phase 1: 基礎架構

### 1.1 檔案建立
- [ ] 1.1.1 建立 `frontend/js/platform-admin.js` - 應用程式主體
- [ ] 1.1.2 建立 `frontend/css/platform-admin.css` - 樣式檔案
- [ ] 1.1.3 更新 `frontend/index.html` - 引入新檔案
- [ ] 1.1.4 更新 `frontend/login.html` - 引入新檔案

### 1.2 應用程式註冊
- [ ] 1.2.1 更新 `frontend/js/desktop.js` - 新增平台管理應用程式圖示
- [ ] 1.2.2 更新 `frontend/js/desktop.js` - openApp 加入 platform-admin case
- [ ] 1.2.3 實作權限檢查 - 僅 platform_admin 可見

## Phase 2: API 客戶端

### 2.1 API 方法
- [ ] 2.1.1 更新 `frontend/js/api-client.js` - 新增 PlatformAdminAPI 物件
- [ ] 2.1.2 實作 listTenants() 方法
- [ ] 2.1.3 實作 createTenant() 方法
- [ ] 2.1.4 實作 updateTenant() 方法
- [ ] 2.1.5 實作 suspendTenant() / activateTenant() 方法
- [ ] 2.1.6 實作 getTenantUsage() 方法
- [ ] 2.1.7 實作 listLineGroups() 方法
- [ ] 2.1.8 實作 updateLineGroupTenant() 方法

## Phase 3: 租戶管理 UI

### 3.1 租戶列表
- [ ] 3.1.1 實作租戶列表視圖 - 表格顯示所有租戶
- [ ] 3.1.2 實作狀態篩選 - active/suspended/trial
- [ ] 3.1.3 實作搜尋功能 - 依名稱/代碼搜尋
- [ ] 3.1.4 顯示使用量摘要 - 使用者數、專案數

### 3.2 建立租戶
- [ ] 3.2.1 實作建立租戶對話框
- [ ] 3.2.2 表單欄位：code、name、plan、trial_days、storage_quota
- [ ] 3.2.3 表單驗證 - code 格式檢查
- [ ] 3.2.4 建立成功後重新載入列表

### 3.3 租戶詳情
- [ ] 3.3.1 實作租戶詳情對話框/面板
- [ ] 3.3.2 顯示基本資訊 - 建立時間、狀態、方案
- [ ] 3.3.3 顯示使用量統計 - 圖表或數字
- [ ] 3.3.4 實作編輯功能 - 名稱、設定
- [ ] 3.3.5 實作停用/啟用按鈕

## Phase 4: Line 群組管理

### 4.1 群組列表
- [ ] 4.1.1 實作 Line 群組列表視圖
- [ ] 4.1.2 顯示群組名稱、目前租戶、最後活動時間
- [ ] 4.1.3 實作租戶篩選 - 依租戶過濾群組

### 4.2 變更群組租戶
- [ ] 4.2.1 實作變更租戶對話框
- [ ] 4.2.2 下拉選單選擇目標租戶
- [ ] 4.2.3 確認對話框 - 警告資料將移轉
- [ ] 4.2.4 變更成功後更新列表

## Phase 5: 整合與測試

### 5.1 整合
- [ ] 5.1.1 確保視窗管理整合 - 可拖曳、最大化
- [ ] 5.1.2 確保響應式設計 - 手機版適配
- [ ] 5.1.3 確保深色主題支援

### 5.2 測試
- [ ] 5.2.1 測試租戶 CRUD 流程
- [ ] 5.2.2 測試 Line 群組租戶變更
- [ ] 5.2.3 測試權限控制 - 非管理員無法存取
