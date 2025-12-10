# Spec: AI 對話持久化

## ADDED Requirements

### Requirement: 資料庫 Migration 管理
系統 SHALL 使用 Alembic 管理資料庫 schema 變更。

#### Scenario: 啟動時自動 Migrate
- Given 應用程式啟動
- When 執行 start.sh
- Then 自動執行 `alembic upgrade head`
- And 資料庫 schema 更新到最新版本

#### Scenario: 新增資料表
- Given 需要新增資料表
- When 建立新的 migration 檔案
- Then 執行 `alembic upgrade head` 套用變更
- And 可用 `alembic downgrade -1` 回滾

### Requirement: 對話資料庫儲存
系統 SHALL 將 AI 對話記錄儲存在 PostgreSQL 資料庫，而非瀏覽器 localStorage。

#### Scenario: 載入對話列表
- Given 使用者已登入
- When 開啟 AI 助手
- Then 從資料庫載入該使用者的對話列表
- And 按更新時間排序（最新在上）

#### Scenario: 建立新對話
- Given 使用者點擊「新對話」
- When 系統建立對話
- Then 在資料庫建立新的 ai_chats 記錄
- And 預設標題為「新對話」
- And 使用選擇的 prompt 和 model

#### Scenario: 刪除對話
- Given 使用者點擊刪除對話按鈕
- When 確認刪除
- Then 從資料庫移除該對話記錄
- And 更新 UI 列表

### Requirement: 使用者對話隔離
系統 MUST 確保使用者只能存取自己的對話記錄。

#### Scenario: API 權限驗證
- Given 使用者 A 請求對話列表
- When API 處理請求
- Then 只回傳 user_id = A 的對話
- And 嘗試存取其他使用者對話時返回 403

### Requirement: 自主管理對話歷史
系統 SHALL 自己管理對話歷史，不依賴 Claude CLI session。

#### Scenario: 發送訊息時載入歷史
- Given 使用者在對話中發送訊息
- When 後端處理 ai_chat 事件
- Then 從資料庫載入該對話的 messages
- And 組合歷史訊息 + 新訊息成完整 prompt
- And 傳送給 Claude CLI（不使用 --session-id）

#### Scenario: 保存 AI 回應
- Given Claude CLI 回應成功
- When 後端收到回應
- Then 將使用者訊息和 AI 回應加入 messages JSONB
- And 更新 updated_at 時間戳

### Requirement: System Prompt 管理
系統 SHALL 支援多種 System Prompt 模式。

#### Scenario: 讀取 Prompt 檔案
- Given 對話使用 `prompt_name = 'code-assistant'`
- When 後端呼叫 Claude CLI
- Then 讀取 `data/prompts/code-assistant.md` 內容
- And 傳入 `--system-prompt` 參數

#### Scenario: 列出可用 Prompts
- Given 使用者開啟 AI 助手
- When 請求 GET /api/ai/prompts
- Then 回傳 data/prompts/ 目錄下的 .md 檔案列表
- And 包含 name 和 description（從檔案第一行取得）

#### Scenario: 建立對話時選擇 Prompt
- Given 使用者建立新對話
- When 選擇「程式碼助手」prompt
- Then 新對話的 prompt_name 設為 'code-assistant'

### Requirement: Token 估算與警告
系統 SHALL 估算對話 token 數量並在接近限制時警告使用者。

#### Scenario: 顯示 Token 使用量
- Given 使用者開啟對話
- When 對話載入完成
- Then 計算並顯示 token 使用量（例如 "45,000 / 200,000"）

#### Scenario: Token 超過閾值顯示警告
- Given 對話 tokens 超過 75%（150,000）
- When 對話載入或新訊息加入後
- Then 顯示警告條：「對話過長，建議壓縮」
- And 顯示「壓縮對話」按鈕

### Requirement: 對話壓縮功能
系統 SHALL 提供對話壓縮功能，由壓縮 Agent 產生摘要。

#### Scenario: 執行對話壓縮
- Given 使用者點擊「壓縮對話」按鈕
- When 系統開始壓縮
- Then 顯示「壓縮中...」狀態
- And 保留最近 10 則訊息
- And 將較舊訊息交給壓縮 Agent

#### Scenario: 壓縮完成更新對話
- Given 壓縮 Agent 產生摘要完成
- When 後端收到摘要
- Then 更新 messages：[摘要訊息] + [最近 10 則]
- And 發送 compress_complete 事件給前端
- And 前端更新 UI 並隱藏警告條
