## ADDED Requirements

### Requirement: 斜線指令解析與路由
系統 SHALL 提供統一的斜線指令路由框架，支援 Line 和 Telegram 平台共用，在 AI 處理流程之前攔截並處理指令訊息。

#### Scenario: 解析斜線指令
- **WHEN** 收到以 `/` 開頭的文字訊息
- **THEN** 系統 SHALL 嘗試匹配已註冊的指令名稱或別名
- **AND** 匹配成功時提取指令名稱和參數部分
- **AND** 匹配失敗時視為一般訊息，繼續 AI 處理流程

#### Scenario: 指令路由優先於 AI 處理
- **WHEN** 訊息被解析為有效的斜線指令
- **THEN** 系統 SHALL 執行指令 handler 並回覆結果
- **AND** 不進入 `process_message_with_ai()` 流程

#### Scenario: 指令大小寫不敏感
- **WHEN** 用戶輸入 `/Reset` 或 `/DEBUG`
- **THEN** 系統 SHALL 以大小寫不敏感方式匹配指令

### Requirement: 指令註冊機制
系統 SHALL 支援透過程式碼註冊新的斜線指令，每個指令包含名稱、別名、處理函式和權限要求。

#### Scenario: 註冊指令定義
- **WHEN** 系統初始化指令路由器
- **THEN** 每個指令 SHALL 包含以下屬性：`name`（指令名稱）、`aliases`（別名列表）、`handler`（async 處理函式）、`require_bound`（是否要求已綁定）、`require_admin`（是否要求管理員）、`private_only`（是否僅限個人對話）、`platforms`（支援平台集合）

#### Scenario: 指令別名支援
- **WHEN** 指令 `reset` 註冊別名 `["新對話", "新对话", "清除對話", "清除对话", "忘記", "忘记"]`
- **THEN** 用戶輸入 `/新對話` 與輸入 `/reset` SHALL 觸發相同的 handler

### Requirement: 指令權限檢查
系統 SHALL 在執行指令前檢查用戶權限，不符合權限要求時回覆提示訊息。

#### Scenario: 未綁定用戶執行需綁定的指令
- **WHEN** 未綁定 CTOS 帳號的用戶執行 `require_bound=true` 的指令
- **THEN** 系統 SHALL 回覆「請先綁定 CTOS 帳號才能使用此指令」
- **AND** 不執行指令 handler

#### Scenario: 非管理員執行管理員指令
- **WHEN** 非管理員用戶執行 `require_admin=true` 的指令
- **THEN** 系統 SHALL 回覆「此指令僅限管理員使用」
- **AND** 不執行指令 handler

#### Scenario: 群組中執行僅限個人的指令
- **WHEN** 用戶在群組中執行 `private_only=true` 的指令
- **THEN** 系統 SHALL 靜默忽略，不回覆
- **AND** 不執行指令 handler

#### Scenario: 不支援的平台
- **WHEN** 用戶在指令不支援的平台上執行指令
- **THEN** 系統 SHALL 視為一般訊息，繼續 AI 處理流程

### Requirement: /reset 指令遷移
現有的 `/reset` 系列指令 SHALL 遷移到指令路由框架中，保持完全相同的行為。

#### Scenario: 個人對話重置
- **WHEN** 已綁定用戶在個人對話中發送 `/reset` 或其任一別名
- **THEN** 系統 SHALL 更新用戶的 `conversation_reset_at` 為當前時間
- **AND** 回覆「已清除對話歷史，開始新對話！有什麼可以幫你的嗎？」

#### Scenario: 群組中靜默忽略
- **WHEN** 用戶在群組中發送 `/reset`
- **THEN** 系統 SHALL 靜默忽略，不執行重置操作

#### Scenario: 未綁定用戶重置
- **WHEN** 未綁定用戶在個人對話中發送 `/reset`
- **AND** `BOT_UNBOUND_USER_POLICY` 為 `restricted`
- **THEN** 系統 SHALL 執行重置（受限模式也有對話歷史）
- **AND** 回覆「已清除對話歷史，開始新對話！」

### Requirement: /debug 管理員診斷指令
系統 SHALL 提供 `/debug` 指令，讓管理員透過 AI Agent 分析系統 logs，快速定位問題。

#### Scenario: 管理員執行 /debug
- **WHEN** 已綁定的管理員在個人對話中發送 `/debug [問題描述]`
- **THEN** 系統 SHALL 取得 `bot-debug` Agent 設定
- **AND** 使用 `BOT_DEBUG_MODEL` 環境變數指定的模型（預設 `sonnet`）
- **AND** 使用 debug Agent 的 system prompt
- **AND** 允許工具為 `run_skill_script`（限 `debug-skill`）
- **AND** 將 AI 診斷結果回覆給管理員

#### Scenario: 無問題描述時的預設行為
- **WHEN** 管理員發送 `/debug`（無後續文字）
- **THEN** 系統 SHALL 使用預設 prompt「分析系統目前狀態，檢查是否有異常」

#### Scenario: 非管理員執行 /debug
- **WHEN** 非管理員用戶發送 `/debug`
- **THEN** 系統 SHALL 回覆「此指令僅限管理員使用」

#### Scenario: 群組中執行 /debug
- **WHEN** 用戶在群組中發送 `/debug`
- **THEN** 系統 SHALL 靜默忽略（`private_only=true`）

### Requirement: debug-skill 診斷腳本
系統 SHALL 提供 `debug-skill`，包含多個診斷腳本供 `/debug` 指令的 AI Agent 呼叫。

#### Scenario: check-server-logs 腳本
- **WHEN** AI 呼叫 `run_skill_script(skill="debug-skill", script="check-server-logs")`
- **THEN** 腳本 SHALL 執行 `journalctl -u ching-tech-os` 取得最近的伺服器日誌
- **AND** 支援 `lines`（行數，預設 100）和 `keyword`（過濾關鍵字）參數
- **AND** 回傳日誌內容

#### Scenario: check-ai-logs 腳本
- **WHEN** AI 呼叫 `run_skill_script(skill="debug-skill", script="check-ai-logs")`
- **THEN** 腳本 SHALL 查詢 `ai_logs` 資料表的最近記錄
- **AND** 支援 `limit`（筆數，預設 20）和 `errors_only`（僅失敗記錄）參數
- **AND** 回傳格式化的 AI log 摘要

#### Scenario: check-nginx-logs 腳本
- **WHEN** AI 呼叫 `run_skill_script(skill="debug-skill", script="check-nginx-logs")`
- **THEN** 腳本 SHALL 執行 `docker logs ching-tech-os-nginx` 取得 Nginx 日誌
- **AND** 支援 `lines`（行數，預設 100）和 `type`（`access` 或 `error`，預設 `error`）參數

#### Scenario: check-db-status 腳本
- **WHEN** AI 呼叫 `run_skill_script(skill="debug-skill", script="check-db-status")`
- **THEN** 腳本 SHALL 查詢資料庫狀態資訊
- **AND** 包含：連線數、主要資料表行數、資料庫大小

#### Scenario: check-system-health 腳本
- **WHEN** AI 呼叫 `run_skill_script(skill="debug-skill", script="check-system-health")`
- **THEN** 腳本 SHALL 綜合執行所有診斷項目
- **AND** 回傳摘要報告，標記各項目的健康狀態（正常/警告/異常）

### Requirement: bot-debug Agent 預設初始化
系統 SHALL 在啟動時確保 `bot-debug` Agent 存在。

#### Scenario: 應用程式啟動時建立預設 Agent
- **WHEN** 應用程式啟動
- **AND** `bot-debug` Agent 不存在
- **THEN** 系統 SHALL 建立 `bot-debug` Agent
- **AND** 預設 model 為 `BOT_DEBUG_MODEL` 環境變數值
- **AND** 預設 system prompt 包含：CTOS 系統診斷助理角色、可用的 debug-skill scripts 說明、輸出格式（問題摘要 + 嚴重程度 + 可能原因 + 建議處理）、安全限制（僅唯讀診斷）

#### Scenario: 保留使用者修改
- **WHEN** 應用程式啟動
- **AND** `bot-debug` Agent 已存在
- **THEN** 系統 SHALL 不覆蓋現有設定
