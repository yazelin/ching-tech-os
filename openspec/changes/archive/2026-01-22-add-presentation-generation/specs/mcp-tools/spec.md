## ADDED Requirements

### Requirement: 生成簡報 MCP 工具
MCP Server SHALL 提供 `generate_presentation` 工具讓 AI 助手根據用戶需求生成 PowerPoint 簡報。

#### Scenario: 生成基本簡報
- **GIVEN** AI 助手收到用戶請求「幫我做一份介紹 AI 應用的簡報」
- **WHEN** 呼叫 `generate_presentation(topic="AI 應用")`
- **THEN** 系統使用 Claude API 生成簡報大綱
- **AND** 使用 python-pptx 建立 5 頁 PowerPoint 簡報
- **AND** 儲存至 NAS `/mnt/nas/projects/ai-presentations/`
- **AND** 回傳包含檔案路徑的成功訊息

#### Scenario: 指定頁數和風格
- **GIVEN** AI 助手有用戶的詳細需求
- **WHEN** 呼叫 `generate_presentation(topic="產品介紹", num_slides=10, style="creative")`
- **THEN** 系統生成 10 頁創意風格的簡報

#### Scenario: 停用自動配圖
- **GIVEN** 用戶不需要配圖
- **WHEN** 呼叫 `generate_presentation(topic="技術報告", include_images=false)`
- **THEN** 系統生成不含圖片的簡報

#### Scenario: 簡報包含自動配圖
- **GIVEN** 用戶需要配圖（預設行為）
- **WHEN** 呼叫 `generate_presentation(topic="旅遊分享", include_images=true)`
- **THEN** 系統從 Pexels API 根據每頁關鍵字下載配圖
- **AND** 將圖片嵌入簡報中

#### Scenario: Pexels 配圖失敗
- **GIVEN** Pexels API 無法取得圖片（網路錯誤或無結果）
- **WHEN** 呼叫 `generate_presentation(topic="某主題", include_images=true)`
- **THEN** 系統跳過配圖繼續生成簡報
- **AND** 簡報仍可正常產出（僅缺少圖片）

#### Scenario: Claude 大綱生成失敗
- **GIVEN** Claude API 回傳非預期格式或錯誤
- **WHEN** 呼叫 `generate_presentation(topic="某主題")`
- **THEN** 系統回傳錯誤訊息說明生成失敗
- **AND** 建議用戶稍後重試或調整主題描述

---

### Requirement: 簡報風格選項
`generate_presentation` 工具 SHALL 支援以下風格選項：
- `professional`（預設）：專業簡潔風格
- `casual`：輕鬆休閒風格
- `creative`：創意活潑風格
- `minimal`：極簡風格

#### Scenario: 使用專業風格
- **WHEN** 呼叫 `generate_presentation(topic="季度報告", style="professional")`
- **THEN** 簡報使用深藍色調、正式字體、簡潔版面

#### Scenario: 使用創意風格
- **WHEN** 呼叫 `generate_presentation(topic="創意提案", style="creative")`
- **THEN** 簡報使用鮮明色彩、活潑版面配置

---

### Requirement: 簡報檔案命名與儲存
系統 SHALL 將生成的簡報儲存至 NAS，並使用結構化的檔名。

#### Scenario: 檔案命名格式
- **WHEN** 生成主題為「AI 應用」的簡報
- **THEN** 檔名格式為 `AI應用_20260122_143052.pptx`（主題_日期_時間）
- **AND** 儲存路徑為 `/mnt/nas/projects/ai-presentations/`

#### Scenario: 檔名包含特殊字元
- **GIVEN** 主題包含特殊字元如「產品/服務介紹」
- **WHEN** 生成簡報
- **THEN** 系統清理檔名中的特殊字元（斜線、冒號等）
- **AND** 產出有效的檔案名稱
