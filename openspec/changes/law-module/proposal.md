## Why

律師事務所在 AI 工作流上有明確且高價值的應用場景（參考 kb-063 市井律師 BOB 的實戰分享）：案件資料整理、證據編號、訴狀撰寫、判決檢索、事實核查。目前這些工作流需要律師手動串接多個 AI 平台（Claude Desktop + Gemini + Perplexity），操作繁瑣且成本高（月費合計 US$550+）。

CTOS 已具備 AI Agent、MCP 工具、知識庫、Bot 整合、文件輸出（md2doc）等基礎設施，只需新增法律領域的專業模組，即可為律師事務所提供一站式 AI 工作流平台。此模組以 `extends/law` git submodule 形式提供，方便獨立授權與部署。

## What Changes

- 新增 `extends/law` git submodule，提供律師事務所專用的 AI 工作流模組
- 新增 DB 表格：`law_cases`（案件）、`law_parties`（當事人）、`law_case_parties`（關聯表）
- 新增 MCP 工具：案件管理、當事人管理、證據目錄產出、法律文書撰寫、判決檢索、引用核查
- 新增 5 個 CTOS Skills：案件管理、法律文書撰寫（10 種文書模板）、判決檢索、證據整理、五階段工作流 SOP
- 新增多租戶客戶設定（`clients/{firm-code}/`），支援不同事務所獨立部署
- 判決檢索採可插拔介面設計，第一版串接司法院裁判書查詢系統，預留 Lawsnote API 擴充
- 多模型協作全程在 CTOS 內部透過 API 完成（Claude extended thinking / Gemini），不需操作外部瀏覽器

## Capabilities

### New Capabilities

- `law-case-management`：案件生命週期管理 — 建立案件自動建資料夾結構、案件狀態追蹤、開庭日提醒
- `law-party-management`：當事人獨立管理 — 自然人/法人 CRUD、案件關聯、歷史案件查詢
- `law-evidence-management`：證據整理自動化 — 掃描證據資料夾、自動編號（甲證/乙證）、產出證據目錄
- `law-legal-writing`：法律文書撰寫 — 10 種文書 Markdown 結構模板、AI 依模板生成草稿、md2doc 輸出 Word
- `law-legal-search`：判決檢索與事實核查 — 可插拔搜尋介面、司法院裁判書查詢、引用核查（驗證判決字號/法條是否存在）
- `law-case-workflow`：五階段工作流 SOP — 案件總覽→策略分析→文書撰寫→事實核查→組裝交付

### Modified Capabilities

- `mcp-tools`：註冊法律模組的 MCP 工具
- `skills`：SkillManager 自動掃描 `extends/law/skills/`

## Impact

- **extends/law/**（新增）：
  - `contributes.yaml`：模組宣告（MCP 工具載入）
  - `SKILL.md`：模組主 SKILL 宣告
  - `core/models.py`：Pydantic 資料模型（Case、Party、Evidence、LegalDocument）
  - `core/mcp_tools.py`：MCP 工具定義（9 個工具）
  - `core/services/case_service.py`：案件管理服務（CRUD + 資料夾建立）
  - `core/services/party_service.py`：當事人管理服務
  - `core/services/evidence_service.py`：證據編號與目錄產出
  - `core/services/document_service.py`：文書產出（模板套用 + md2doc）
  - `core/services/legal_search/`：判決檢索可插拔介面
  - `core/services/legal_search/judicial.py`：司法院裁判書查詢（第一版）
  - `core/services/legal_search/lawsnote.py`：Lawsnote API（預留）
  - `core/templates/`：10 種法律文書 Markdown 結構模板
  - `skills/case-mgmt/SKILL.md`：案件管理 Skill
  - `skills/legal-writing/SKILL.md`：法律文書撰寫 Skill
  - `skills/legal-search/SKILL.md`：判決檢索 Skill
  - `skills/evidence-mgmt/SKILL.md`：證據整理 Skill
  - `skills/case-workflow/SKILL.md`：五階段工作流 Skill
  - `clients/_template/`：新客戶部署範本
  - `migrations/`：DB migration SQL

- **backend/migrations/versions/**：
  - Alembic migration 新增 `law_cases`、`law_parties`、`law_case_parties` 表格

- **不動的部分**：
  - 既有的知識庫、NAS 檔案管理、md2doc、Bot AI 流程不需修改
  - 模組透過 `contributes.yaml` 和 SkillManager 自動整合，不需改 `main.py`

## 架構設計

### 目錄結構

```
extends/law/
├── contributes.yaml
├── SKILL.md
├── README.md
│
├── core/
│   ├── __init__.py
│   ├── models.py                    # Pydantic 資料模型
│   ├── mcp_tools.py                 # MCP 工具定義
│   └── services/
│       ├── __init__.py
│       ├── case_service.py          # 案件管理
│       ├── party_service.py         # 當事人管理
│       ├── evidence_service.py      # 證據編號/目錄
│       ├── document_service.py      # 文書產出
│       └── legal_search/            # 判決檢索（可插拔）
│           ├── __init__.py          # LegalSearchProvider ABC
│           ├── judicial.py          # 司法院裁判書（v1）
│           └── lawsnote.py          # Lawsnote（預留）
│
├── templates/                       # 法律文書 Markdown 模板
│   ├── civil_complaint.md           # 民事起訴狀
│   ├── civil_defense.md             # 民事答辯狀
│   ├── preparatory_brief.md         # 準備書狀
│   ├── appeal.md                    # 上訴狀
│   ├── petition.md                  # 聲請狀
│   ├── criminal_complaint.md        # 刑事告訴狀
│   ├── criminal_defense.md          # 刑事答辯狀
│   ├── certified_letter.md          # 存證信函
│   ├── lawyer_letter.md             # 律師函
│   └── legal_opinion.md             # 法律意見書
│
├── clients/
│   ├── _template/
│   │   ├── config.yaml              # 事務所設定範本
│   │   ├── README.md                # 部署檢查清單
│   │   └── agents/
│   │       └── law-assistant.md     # Agent prompt 範本
│   └── {firm-code}/                 # 各事務所獨立設定
│
├── skills/
│   ├── case-mgmt/SKILL.md
│   ├── legal-writing/SKILL.md
│   ├── legal-search/SKILL.md
│   ├── evidence-mgmt/SKILL.md
│   └── case-workflow/SKILL.md
│
└── migrations/
    └── law_tables.sql
```

### DB Schema

**`law_parties`（當事人）**

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | SERIAL PK | 自動編號 |
| name | VARCHAR(100) NOT NULL | 姓名/公司名 |
| id_number | VARCHAR(20) | 身分證/統編（加密儲存） |
| party_type | VARCHAR(20) | natural_person / legal_entity |
| phone | VARCHAR(30) | 聯絡電話 |
| email | VARCHAR(100) | Email |
| address | TEXT | 地址 |
| notes | TEXT | 備註 |
| created_at | TIMESTAMPTZ | 建立時間 |
| updated_at | TIMESTAMPTZ | 更新時間 |

**`law_cases`（案件）**

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | SERIAL PK | 自動編號 |
| case_number | VARCHAR(50) | 案號（如 113年度訴字第1234號） |
| case_name | VARCHAR(200) NOT NULL | 案件名稱 |
| case_type | VARCHAR(20) NOT NULL | civil / criminal / administrative / family |
| court | VARCHAR(50) | 管轄法院 |
| role | VARCHAR(20) | plaintiff / defendant / third_party |
| status | VARCHAR(20) DEFAULT 'active' | active / closed / appealing |
| lawyer_name | VARCHAR(50) | 承辦律師 |
| folder_path | TEXT | 案件資料夾絕對路徑 |
| next_court_date | DATE | 下次開庭日 |
| notes | TEXT | 備註 |
| created_at | TIMESTAMPTZ | 建立時間 |
| updated_at | TIMESTAMPTZ | 更新時間 |

**`law_case_parties`（案件-當事人關聯）**

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | SERIAL PK | 自動編號 |
| case_id | INTEGER FK → law_cases | 案件 |
| party_id | INTEGER FK → law_parties | 當事人 |
| role | VARCHAR(20) NOT NULL | plaintiff / defendant / third_party / witness |
| created_at | TIMESTAMPTZ | 建立時間 |

UNIQUE(case_id, party_id, role)

### 案件資料夾結構

建立案件時自動建立以下資料夾（路徑可在 `config.yaml` 設定）：

```
{base_path}/{case_id}_{case_name}/
├── 00_案件總覽/        # 案件摘要、爭點清單
├── 10_書狀/           # 起訴狀、答辯狀、準備書狀
├── 20_證據/           # 原告證據（甲證1, 甲證2...）
├── 30_對造/           # 被告書狀、證據
├── 40_裁判/           # 法院裁定、判決
├── 50_法規/           # 相關法條、函釋
├── 80_AI產出/         # AI 分析報告、草稿
└── 90_操作紀錄/       # AI 對話紀錄、工作日誌
```

### MCP 工具清單

| 工具 | 說明 | 參數 |
|------|------|------|
| `create_case` | 建立案件 + 自動建資料夾 | case_name, case_type, court, role, client_name, opponent_name |
| `get_case` | 查詢案件詳情 | case_id 或 case_number |
| `list_cases` | 案件列表（可篩選） | status, case_type, lawyer_name |
| `update_case` | 更新案件資訊 | case_id, 欲更新欄位 |
| `create_party` | 建立當事人 | name, party_type, phone, email, address |
| `get_party` | 查詢當事人 | party_id 或 name（模糊搜尋） |
| `list_parties` | 當事人列表 | party_type |
| `link_party_to_case` | 關聯當事人到案件 | case_id, party_id, role |
| `generate_evidence_index` | 掃描證據資料夾，產出證據目錄 | case_id |
| `draft_legal_document` | 依模板撰寫法律文書 | case_id, document_type, additional_instructions |
| `search_judgments` | 判決檢索 | keywords, court, date_range, case_type |
| `verify_citations` | 核查引用的判決字號/法條 | citations (list) |

### 判決檢索可插拔介面

```python
class LegalSearchProvider(ABC):
    """判決檢索提供者介面"""

    @abstractmethod
    async def search(
        self, keywords: str,
        court: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        case_type: str | None = None,
        limit: int = 10,
    ) -> list[JudgmentResult]: ...

    @abstractmethod
    async def get_judgment(self, case_number: str) -> JudgmentDetail | None:
        """以案號取得判決全文"""

    @abstractmethod
    async def verify_citation(self, citation: str) -> CitationVerification:
        """驗證判決字號或法條是否存在"""

class JudicialGovProvider(LegalSearchProvider):
    """司法院裁判書查詢系統（第一版）"""

class LawsnoteProvider(LegalSearchProvider):
    """Lawsnote API（預留）"""
```

透過 `config.yaml` 的 `legal_search.provider` 設定切換：

```yaml
legal_search:
  provider: judicial    # judicial / lawsnote
  # lawsnote_api_key: ""  # Lawsnote 付費 API key
```

### 五階段工作流 SOP（case-workflow Skill）

參考 kb-063 的極限工作流，在 CTOS 內部完成全程：

```
階段 1：案件總覽與事實整理
  └─ 工具：create_case → generate_evidence_index
  └─ AI 產出：事實摘要、爭點清單、證據對照表 → 存入 00_案件總覽/
  └─ 🔒 人類確認門：確認事實摘要、指定工作方向

階段 2：策略分析
  └─ AI extended thinking 分析爭點、攻防策略
  └─ 工具：search_judgments 查詢相關判決
  └─ AI 產出：策略分析報告 → 存入 80_AI產出/
  └─ 🔒 人類確認門：選擇策略方向

階段 3：文書撰寫
  └─ 工具：draft_legal_document（依模板撰寫）
  └─ AI 產出：文書草稿（Markdown） → 存入 80_AI產出/
  └─ 🔒 人類確認門：審閱草稿

階段 4：事實核查
  └─ 工具：verify_citations 核查判決引用、法條引用
  └─ 交叉比對文書與原始證據
  └─ AI 產出：核查報告 → 存入 80_AI產出/

階段 5：組裝與交付
  └─ md2doc 輸出 Word 文件
  └─ 最終文件 → 存入 10_書狀/
  └─ 🔒 人類確認門：律師最終審閱
```

### 客戶設定範本（config.yaml）

```yaml
# 事務所基本資訊
firm:
  name: ""              # 事務所名稱
  code: ""              # 事務所代碼（kebab-case）

# 案件資料夾設定
storage:
  base_path: ""         # 案件資料夾根路徑（如 /mnt/nas/ctos/law/{firm-code}/cases）
  folder_template: "{case_id}_{case_name}"  # 資料夾命名格式

# 判決檢索設定
legal_search:
  provider: judicial    # judicial / lawsnote
  # lawsnote_api_key: ""

# AI 模型偏好
ai:
  writing_model: opus   # 文書撰寫使用的模型
  analysis_model: opus  # 策略分析使用的模型
  extended_thinking: true  # 啟用深度思考

# Agent 設定
agents:
  default: ""           # 預設 Agent prompt

# 功能開關
features:
  case_management: true
  legal_writing: true
  legal_search: true
  evidence_management: true
  case_workflow: true
```

### 整合方式

- **contributes.yaml**：宣告 MCP 工具載入路徑（`core/mcp_tools.py`），類似 `his` 模組
- **Skills**：由 SkillManager 自動掃描 `extends/law/skills/`
- **DB migration**：在主系統 `backend/migrations/versions/` 新增 Alembic migration
- **環境變數**：`LAW_CLIENT`（客戶代碼）、`LAW_DATA_PATH`（資料夾根路徑）
