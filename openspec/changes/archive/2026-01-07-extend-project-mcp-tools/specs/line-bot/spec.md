## MODIFIED Requirements

### Requirement: Line Bot Agent 整合
Line Bot SHALL 使用資料庫中的 Agent/Prompt 設定進行 AI 對話處理。

#### Scenario: 個人對話使用 linebot-personal Agent
- **WHEN** Line 用戶在個人對話中發送訊息
- **AND** 觸發 AI 處理
- **THEN** 系統從資料庫取得 `linebot-personal` Agent 設定
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容

#### Scenario: 群組對話使用 linebot-group Agent
- **WHEN** Line 用戶在群組中觸發 AI 處理
- **THEN** 系統從資料庫取得 `linebot-group` Agent 設定
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容
- **AND** 動態附加群組資訊和綁定專案資訊到 prompt

#### Scenario: Agent 不存在時的 Fallback
- **WHEN** 系統找不到對應的 Agent 設定
- **THEN** 系統使用硬編碼的預設 Prompt 作為 fallback
- **AND** 記錄警告日誌

---

## ADDED Requirements

### Requirement: 群組專案操作限制
Line Bot 在群組對話中 SHALL 根據是否綁定專案決定操作規則。

#### Scenario: 群組有綁定專案
- **WHEN** AI 處理群組對話
- **AND** 群組有綁定專案
- **THEN** system prompt 明確告知「此群組綁定專案：{專案名稱}（ID: {專案ID}）」
- **AND** AI 只能操作此綁定專案，不可操作其他專案
- **AND** 不檢查成員權限（群組內都可以操作）

#### Scenario: 群組未綁定專案
- **WHEN** AI 處理群組對話
- **AND** 群組未綁定專案
- **THEN** system prompt 說明「此群組尚未綁定專案」
- **AND** 可操作任意專案，但需檢查成員權限（與個人對話規則相同）

#### Scenario: 用戶要求操作其他專案（有綁定時）
- **WHEN** 群組已綁定專案 A
- **AND** 用戶要求操作專案 B
- **THEN** AI 應拒絕並說明「此群組只能操作綁定的專案 A」

---

### Requirement: 個人對話專案推斷與權限
Line Bot 在個人對話中 SHALL 從對話上下文推斷用戶要操作的專案，並檢查成員權限。

#### Scenario: 從對話上下文推斷專案
- **WHEN** AI 處理個人對話
- **AND** 用戶之前提到過某個專案
- **THEN** AI 從對話歷史推斷用戶要操作的專案

#### Scenario: 無法推斷時詢問
- **WHEN** 用戶請求專案相關操作
- **AND** AI 無法從對話上下文確定是哪個專案
- **THEN** AI 應詢問用戶要操作哪個專案

#### Scenario: 成員權限檢查
- **WHEN** 用戶嘗試更新專案資料
- **AND** 用戶不是該專案的成員（`project_members.user_id`）
- **THEN** 系統拒絕操作並回傳「您不是此專案的成員，無法進行此操作」

#### Scenario: 成員可操作
- **WHEN** 用戶嘗試更新專案資料
- **AND** 用戶是該專案的成員
- **THEN** 系統允許操作
