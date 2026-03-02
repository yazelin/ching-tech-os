## ADDED Requirements

### Requirement: 排程管理桌面應用
系統 SHALL 提供「排程管理」桌面應用程式，以 Skill `contributes.app` 方式註冊。

#### Scenario: 應用出現在桌面
- **WHEN** 使用者登入 Web 桌面
- **THEN** 「排程管理」應用 SHALL 出現在桌面應用清單中
- **THEN** 應用圖示 SHALL 使用 `calendar-clock` 或類似的 MDI 圖示

#### Scenario: 開啟應用
- **WHEN** 使用者點擊「排程管理」應用圖示
- **THEN** SHALL 開啟排程管理視窗
- **THEN** SHALL 載入並顯示所有排程列表

#### Scenario: 僅管理員可存取
- **WHEN** 非管理員使用者嘗試開啟應用
- **THEN** SHALL 顯示權限不足的提示

### Requirement: 排程列表檢視
應用 SHALL 以表格形式顯示所有排程任務（動態 + 靜態）。

#### Scenario: 顯示排程列表
- **WHEN** 開啟排程管理應用
- **THEN** 列表 SHALL 顯示每筆排程的：名稱、觸發規則摘要、執行類型、啟用狀態、下次執行時間、最後執行結果
- **THEN** 動態排程和靜態排程 SHALL 以視覺方式區分（如標籤或分組）

#### Scenario: 狀態顏色指示
- **WHEN** 排程最後一次執行成功
- **THEN** 狀態 SHALL 顯示為綠色
- **WHEN** 排程最後一次執行失敗
- **THEN** 狀態 SHALL 顯示為紅色，並可展開查看錯誤訊息
- **WHEN** 排程尚未執行過
- **THEN** 狀態 SHALL 顯示為灰色

#### Scenario: 靜態排程唯讀
- **WHEN** 列表中顯示靜態排程（source 為 system 或 module）
- **THEN** SHALL 不提供編輯 / 刪除按鈕
- **THEN** SHALL 標示為「系統排程」供參考

### Requirement: 新增排程表單
應用 SHALL 提供 Modal 表單供使用者建立新排程。

#### Scenario: 開啟新增表單
- **WHEN** 使用者點擊「新增排程」按鈕
- **THEN** SHALL 開啟 Modal 表單

#### Scenario: 表單欄位 — 基本資訊
- **WHEN** 新增表單開啟
- **THEN** SHALL 包含：排程名稱（必填）、說明（選填）

#### Scenario: 表單欄位 — 觸發設定
- **WHEN** 使用者選擇觸發類型
- **THEN** 選擇 `cron` 時 SHALL 顯示：分鐘、小時、日、月、星期幾的輸入欄位
- **THEN** 選擇 `interval` 時 SHALL 顯示：週、天、小時、分鐘、秒的輸入欄位

#### Scenario: 表單欄位 — 執行設定（Agent 模式）
- **WHEN** 使用者選擇執行類型為 `agent`
- **THEN** SHALL 顯示 Agent 下拉選單（從 `/api/ai/agents` 載入可用 Agent 清單）
- **THEN** SHALL 顯示 prompt 文字輸入區域（多行）

#### Scenario: 表單欄位 — 執行設定（Skill Script 模式）
- **WHEN** 使用者選擇執行類型為 `skill_script`
- **THEN** SHALL 顯示 Skill 下拉選單（從系統載入可用 Skill 清單）
- **THEN** 選擇 Skill 後 SHALL 顯示該 Skill 可用的 Script 下拉選單
- **THEN** SHALL 顯示 input 文字輸入區域（選填，JSON 格式）

#### Scenario: 提交表單
- **WHEN** 使用者填寫完成並提交
- **THEN** SHALL 呼叫 POST `/api/scheduler/tasks` 建立排程
- **THEN** 成功後 SHALL 關閉 Modal 並重新載入列表
- **THEN** 失敗時 SHALL 顯示錯誤訊息

### Requirement: 編輯排程
應用 SHALL 支援編輯現有動態排程。

#### Scenario: 開啟編輯表單
- **WHEN** 使用者點擊動態排程的「編輯」按鈕
- **THEN** SHALL 開啟預填現有資料的 Modal 表單

#### Scenario: 提交編輯
- **WHEN** 使用者修改後提交
- **THEN** SHALL 呼叫 PUT `/api/scheduler/tasks/{task_id}` 更新排程
- **THEN** 成功後 SHALL 重新載入列表

### Requirement: 刪除排程
應用 SHALL 支援刪除動態排程，並要求確認。

#### Scenario: 刪除確認
- **WHEN** 使用者點擊「刪除」按鈕
- **THEN** SHALL 顯示確認對話框，包含排程名稱
- **WHEN** 使用者確認刪除
- **THEN** SHALL 呼叫 DELETE `/api/scheduler/tasks/{task_id}`
- **THEN** 成功後 SHALL 重新載入列表

### Requirement: 啟停用切換
應用 SHALL 支援快速切換排程的啟用狀態。

#### Scenario: 切換啟用狀態
- **WHEN** 使用者點擊啟用 / 停用切換按鈕
- **THEN** SHALL 呼叫 PATCH `/api/scheduler/tasks/{task_id}/toggle`
- **THEN** SHALL 即時更新 UI 上的狀態顯示

### Requirement: 手動觸發
應用 SHALL 支援手動立即執行一次排程。

#### Scenario: 手動執行
- **WHEN** 使用者點擊「立即執行」按鈕
- **THEN** SHALL 呼叫 POST `/api/scheduler/tasks/{task_id}/run`
- **THEN** SHALL 顯示「已送出執行」的提示
