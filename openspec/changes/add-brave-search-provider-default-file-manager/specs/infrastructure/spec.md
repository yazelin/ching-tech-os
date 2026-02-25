## ADDED Requirements

### Requirement: Brave Search API 環境變數設定
系統設定層 SHALL 提供 Brave Search API key 設定欄位供搜尋 provider 使用。

#### Scenario: 設定層讀取 Brave API key
- **WHEN** 應用程式啟動並載入環境變數
- **THEN** 設定物件可取得 `BRAVE_SEARCH_API_KEY`
- **AND** `research-skill` 可透過設定物件或環境讀取該值

#### Scenario: 未設定 API key
- **WHEN** `BRAVE_SEARCH_API_KEY` 未設定
- **THEN** 系統不應崩潰
- **AND** research 流程可回退到既有 provider

### Requirement: .env 範例需包含 Brave 設定
專案環境變數範例檔 SHALL 包含 Brave Search API key 欄位與註解。

#### Scenario: 新部署者查看範例檔
- **WHEN** 開發者查看 `.env.example`
- **THEN** 可看到 `BRAVE_SEARCH_API_KEY=` 欄位
- **AND** 可理解該變數用途與填寫方式
