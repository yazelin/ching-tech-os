## 1. Git Repo 與模組骨架

- [x] 1.1 建立 `ching-tech-law` GitHub repo（private），初始化 README.md
- [x] 1.2 在主專案新增 git submodule：`git submodule add <repo-url> extends/law`
- [x] 1.3 建立模組目錄結構：`core/`、`core/services/`、`core/services/legal_search/`、`templates/`、`clients/_template/`、`skills/`、`migrations/`
- [x] 1.4 建立 `contributes.yaml`，宣告 MCP 工具載入路徑（`core/mcp_tools.py`）
- [x] 1.5 建立 `SKILL.md` 模組主宣告（metadata.ctos.mcp_tools 指向 `core/mcp_tools.py`）
- [x] 1.6 建立 `clients/_template/config.yaml` 事務所設定範本
- [x] 1.7 建立 `clients/_template/README.md` 部署檢查清單
- [x] 1.8 建立 `clients/_template/agents/law-assistant.md` Agent prompt 範本

## 2. 資料庫 Migration

- [x] 2.1 建立 Alembic migration 檔案 `backend/migrations/versions/018_add_law_tables.py`，包含 `law_parties`、`law_cases`、`law_case_parties` 三張表格
- [x] 2.2 在 `law_case_parties` 加入 UNIQUE(case_id, party_id, role) 約束和外鍵
- [x] 2.3 執行 `uv run alembic upgrade head` 驗證 migration 成功
- [x] 2.4 在 `extends/law/migrations/law_tables.sql` 放置 SQL 參考檔案（文件用途）

## 3. Pydantic 資料模型

- [x] 3.1 建立 `core/models.py`：定義 `Case`、`Party`、`CaseParty`、`CaseCreate`、`PartyCreate` 等 Pydantic model
- [x] 3.2 建立 `core/models.py`：定義 `JudgmentResult`、`JudgmentDetail`、`CitationVerification` 判決檢索相關 model
- [x] 3.3 建立 `core/models.py`：定義 `FirmConfig` 客戶設定 model（對應 config.yaml）

## 4. 案件管理服務

- [x] 4.1 建立 `core/services/case_service.py`：實作 `create_case()` — 寫入 DB + 建立 8 層資料夾結構
- [x] 4.2 實作 `get_case()` — 以 case_id 或 case_number 查詢，含關聯當事人清單
- [x] 4.3 實作 `list_cases()` — 支援 status、case_type、lawyer_name 篩選
- [x] 4.4 實作 `update_case()` — 更新指定欄位 + updated_at 時間戳
- [x] 4.5 實作資料夾路徑解析邏輯：config.yaml > LAW_DATA_PATH 環境變數 > 預設值

## 5. 當事人管理服務

- [x] 5.1 建立 `core/services/party_service.py`：實作 `create_party()` — 含 id_number 加密儲存
- [x] 5.2 實作 `get_party()` — 支援 party_id 精確查詢和 name 模糊搜尋，含關聯案件清單
- [x] 5.3 實作 `list_parties()` — 支援 party_type 篩選
- [x] 5.4 實作 `link_party_to_case()` — 含 UNIQUE 約束重複檢查
- [x] 5.5 實作 id_number 加密/解密工具函式（使用主系統 SECRET_KEY）

## 6. 證據管理服務

- [x] 6.1 建立 `core/services/evidence_service.py`：實作 `generate_evidence_index()` — 掃描 `20_證據/` 資料夾
- [x] 6.2 實作證據編號解析邏輯：辨識已有編號的檔案名稱（甲證/乙證/丙證）
- [x] 6.3 實作自動編號：依案件角色決定前綴，未編號檔案依排列順序指派
- [x] 6.4 實作證據目錄 Markdown 輸出：表格格式含編號、檔名、類型、大小，存入 `00_案件總覽/證據目錄.md`

## 7. 法律文書模板

- [x] 7.1 建立 `templates/civil_complaint.md` 民事起訴狀模板（含 YAML frontmatter + 結構化 Markdown）
- [x] 7.2 建立 `templates/civil_defense.md` 民事答辯狀模板
- [x] 7.3 建立 `templates/preparatory_brief.md` 準備書狀模板
- [x] 7.4 建立 `templates/appeal.md` 上訴狀模板
- [x] 7.5 建立 `templates/petition.md` 聲請狀模板
- [x] 7.6 建立 `templates/criminal_complaint.md` 刑事告訴狀模板
- [x] 7.7 建立 `templates/criminal_defense.md` 刑事答辯狀模板
- [x] 7.8 建立 `templates/certified_letter.md` 存證信函模板
- [x] 7.9 建立 `templates/lawyer_letter.md` 律師函模板
- [x] 7.10 建立 `templates/legal_opinion.md` 法律意見書模板

## 8. 文書撰寫服務

- [x] 8.1 建立 `core/services/document_service.py`：實作模板載入邏輯（讀取 YAML frontmatter + Markdown 正文）
- [x] 8.2 實作 `draft_legal_document()` — 載入模板、填入案件資料、回傳結構化內容供 AI 撰寫
- [x] 8.3 實作文書類型列表查詢（掃描 templates/ 目錄的 frontmatter）

## 9. 判決檢索服務

- [x] 9.1 建立 `core/services/legal_search/__init__.py`：定義 `LegalSearchProvider` ABC（search、get_judgment、verify_citation 三個抽象方法）
- [x] 9.2 建立 `core/services/legal_search/judicial.py`：實作 `JudicialGovProvider`，透過 HTTP POST 查詢司法院裁判書系統
- [x] 9.3 實作司法院 HTML 回應解析：提取案號、法院、日期、摘要、全文
- [x] 9.4 實作 `verify_citation()` — 判決字號正則解析 + 查詢驗證
- [x] 9.5 建立法條驗證靜態資料庫（JSON 檔案，主要法律的條文總數對照表）
- [x] 9.6 建立 `core/services/legal_search/lawsnote.py`：預留 `LawsnoteProvider` 骨架（raise NotImplementedError）
- [x] 9.7 實作 provider 工廠函式：依 config.yaml 的 `legal_search.provider` 設定選擇實作

## 10. MCP 工具註冊

- [x] 10.1 建立 `core/mcp_tools.py`：註冊 `create_case` 工具
- [x] 10.2 註冊 `get_case`、`list_cases`、`update_case` 工具
- [x] 10.3 註冊 `create_party`、`get_party`、`list_parties`、`link_party_to_case` 工具
- [x] 10.4 註冊 `generate_evidence_index` 工具
- [x] 10.5 註冊 `draft_legal_document` 工具
- [x] 10.6 註冊 `search_judgments`、`verify_citations` 工具

## 11. CTOS Skills

- [x] 11.1 建立 `skills/case-mgmt/SKILL.md`：案件管理 Skill（allowed-tools 含案件和當事人 MCP 工具）
- [x] 11.2 建立 `skills/evidence-mgmt/SKILL.md`：證據整理 Skill
- [x] 11.3 建立 `skills/legal-writing/SKILL.md`：法律文書撰寫 Skill（含 10 種文書類型說明和使用範例）
- [x] 11.4 建立 `skills/legal-search/SKILL.md`：判決檢索與事實核查 Skill
- [x] 11.5 建立 `skills/case-workflow/SKILL.md`：五階段工作流 SOP Skill（含階段判斷邏輯和人類確認門指引）

## 12. 多租戶設定與整合

- [x] 12.1 實作客戶設定載入邏輯：讀取 `LAW_CLIENT` 環境變數 → 載入 `clients/{firm-code}/config.yaml`
- [x] 12.2 實作 `FirmConfig` 驗證和預設值填充
- [x] 12.3 確認 `contributes.yaml` 被主系統正確掃描和載入
- [x] 12.4 確認 Skills 被 SkillManager 正確掃描和載入
- [x] 12.5 確認 MCP 工具被正確註冊並可透過 Bot 呼叫

## 13. 測試與驗證

- [x] 13.1 手動測試：建立案件 → 驗證資料夾結構正確建立
- [x] 13.2 手動測試：建立當事人 → 關聯到案件 → 查詢驗證
- [x] 13.3 手動測試：放入測試證據檔案 → 產出證據目錄
- [x] 13.4 手動測試：draft_legal_document 載入模板 → AI 撰寫 → md2doc 輸出 Word
- [x] 13.5 手動測試：search_judgments 查詢司法院 → 驗證回傳結果
- [x] 13.6 手動測試：verify_citations 驗證真實/虛構判決字號
- [x] 13.7 端對端測試：透過 Line Bot 觸發 case-workflow Skill，走完五階段工作流
