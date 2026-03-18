## ADDED Requirements

### Requirement: 判決檢索工具
系統 SHALL 提供 `search_judgments` MCP 工具，透過可插拔的 `LegalSearchProvider` 介面查詢判決資料。

#### Scenario: 以關鍵字搜尋判決
- **WHEN** AI 呼叫 `search_judgments(keywords="損害賠償 侵權行為", case_type="civil", limit=10)`
- **THEN** 系統透過目前啟用的 provider 搜尋，回傳判決列表（含案號、法院、日期、摘要）

#### Scenario: 限定法院和日期範圍
- **WHEN** AI 呼叫 `search_judgments(keywords="租賃", court="臺灣臺北地方法院", date_from="2024-01-01", date_to="2025-12-31")`
- **THEN** 系統回傳符合法院和日期範圍的判決列表

#### Scenario: 搜尋無結果
- **WHEN** 搜尋條件無任何匹配判決
- **THEN** 系統回傳空列表和建議（如放寬搜尋條件）

### Requirement: 判決全文取得
`LegalSearchProvider` 介面 SHALL 支援以案號取得判決全文。

#### Scenario: 以案號取得判決
- **WHEN** AI 呼叫 `search_judgments` 取得結果後，進一步以案號查詢全文
- **THEN** 系統回傳判決全文內容（純文字格式），包含案號、法院、日期、當事人、主文、事實、理由

#### Scenario: 案號不存在
- **WHEN** 查詢的案號在資料庫中不存在
- **THEN** 系統回傳「查無此案號之判決」

### Requirement: 引用核查工具
系統 SHALL 提供 `verify_citations` MCP 工具，驗證文書中引用的判決字號和法條是否真實存在。

#### Scenario: 驗證判決字號
- **WHEN** AI 呼叫 `verify_citations(citations=["最高法院 108 年度台上字第 1234 號", "民法第 184 條"])`
- **THEN** 系統逐一驗證每個引用，回傳驗證結果（存在/不存在/無法確認），對判決字號標示是否找到對應判決，對法條標示是否為有效法條

#### Scenario: 發現幻覺引用
- **WHEN** 某個判決字號在司法院系統中查無記錄
- **THEN** 系統回傳該引用為「不存在」，並建議 AI 移除或替換該引用

#### Scenario: 批次驗證
- **WHEN** `citations` 列表包含多個引用（判決字號和法條混合）
- **THEN** 系統 SHALL 並行驗證所有引用，回傳每個引用的個別結果

### Requirement: 可插拔的搜尋介面
判決檢索 SHALL 採用 `LegalSearchProvider` 抽象介面，透過 `config.yaml` 的 `legal_search.provider` 設定切換實作。

#### Scenario: 使用司法院 provider（預設）
- **WHEN** `config.yaml` 設定 `legal_search.provider: judicial` 或未設定
- **THEN** 系統使用 `JudicialGovProvider` 查詢司法院裁判書系統

#### Scenario: 切換至 Lawsnote provider
- **WHEN** `config.yaml` 設定 `legal_search.provider: lawsnote` 且 `lawsnote_api_key` 已填入
- **THEN** 系統使用 `LawsnoteProvider` 查詢 Lawsnote API

#### Scenario: Provider 不可用
- **WHEN** 設定的 provider 無法連線或 API key 無效
- **THEN** 系統回傳錯誤訊息，說明連線失敗原因

### Requirement: 司法院裁判書查詢系統整合（第一版）
`JudicialGovProvider` SHALL 實作 `LegalSearchProvider` 介面，串接司法院裁判書查詢系統取得公開判決資料。

#### Scenario: 查詢民事判決
- **WHEN** 透過 `JudicialGovProvider` 搜尋民事判決
- **THEN** 系統向司法院裁判書查詢系統發送請求，解析回傳的 HTML/JSON 資料，轉換為結構化的 `JudgmentResult` 列表

#### Scenario: 司法院系統無回應
- **WHEN** 司法院網站逾時或無法連線
- **THEN** 系統回傳錯誤訊息「司法院裁判書查詢系統目前無回應，請稍後再試」
