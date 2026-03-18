## Context

CTOS 已有成熟的 extends 模組機制：`contributes.yaml` 宣告生命週期/路由/MCP server、`SkillManager` 自動掃描 `extends/*/skills/`、SKILL.md 的 `metadata.ctos.mcp_tools` 支援動態載入 MCP 工具。現有的 `his` 模組（醫療 HIS）和 `erpnext` 模組（ERP）分別展示了兩種整合模式：`his` 使用 in-process MCP 工具 + 多租戶 `clients/` 架構；`erpnext` 使用外部 MCP server 進程。

法律模組的特性：(1) 需要資料庫存儲案件/當事人資料、(2) 需要操作本機/NAS 檔案系統建立資料夾、(3) 需要呼叫外部 API（司法院裁判書系統）、(4) 需要多租戶支援（不同事務所獨立設定）。這些需求與 `his` 模組最為相似，因此採用相同的整合模式。

## Goals / Non-Goals

**Goals:**
- 以 `extends/law` git submodule 形式提供，可獨立授權、獨立版本控制
- 遵循現有 extends 模組慣例（contributes.yaml + SKILL.md + clients/），無需修改主系統核心程式碼
- 提供完整的案件生命週期管理，從建案到文書交付
- 判決檢索採可插拔架構，方便未來接入不同法學資料庫
- 多租戶支援，每間事務所有獨立的設定和 Agent prompt

**Non-Goals:**
- 不建立前端 Web App UI（第一版僅透過 Bot 和 MCP 工具操作）
- 不實作 Lawsnote API 整合（僅預留介面）
- 不實作開庭提醒推播功能（僅記錄 `next_court_date`）
- 不做案件的權限隔離（同一部署實例內所有使用者可見所有案件）
- 不做文件版本控制（檔案系統層級的版本管理由使用者自行處理）

## Decisions

### Decision 1：整合模式 — 採用 `his` 的 in-process MCP 工具模式

**選擇**：MCP 工具定義在 `core/mcp_tools.py`，透過 SKILL.md 的 `metadata.ctos.mcp_tools` 動態載入，在主系統進程內執行。

**替代方案**：
- A) 外部 MCP server（如 `erpnext` 的 `uvx` 模式）→ 需要獨立發佈 PyPI 套件，增加維護成本；且法律模組需要存取主系統的資料庫，外部進程需額外處理連線
- B) 直接在主系統 `services/mcp/` 新增工具 → 耦合主系統，無法獨立授權和版控

**理由**：法律模組需要存取主系統的 PostgreSQL 資料庫（`law_cases`、`law_parties` 表格），in-process 模式可直接使用 `ensure_db_connection()`，不需要額外的資料庫連線管理。與 `his` 模組的 `mcp_tools.py` 模式完全一致。

### Decision 2：資料庫 migration — 放在主系統的 Alembic 目錄

**選擇**：migration 檔案放在 `backend/migrations/versions/`，命名為 `0XX_add_law_tables.py`，遵循主系統的 migration 編號序列。

**替代方案**：
- A) migration 放在 `extends/law/migrations/` 內 → 主系統的 Alembic 不會掃描到 extends 目錄下的 migration，需要額外配置
- B) 用 raw SQL 腳本手動執行 → 不符合專案規範（所有 schema 變更必須使用 Alembic）

**理由**：`his` 模組的 migration 也放在主系統的 Alembic 目錄中，這是已驗證的模式。`extends/law/migrations/` 目錄仍保留 SQL 參考檔案供文件用途。

### Decision 3：案件資料夾路徑解析 — 環境變數 + config.yaml 雙層

**選擇**：
```
優先級：config.yaml 的 storage.base_path > 環境變數 LAW_DATA_PATH > 預設值
預設值：{CTOS_MOUNT_PATH}/law/{client-code}/cases
```

**替代方案**：
- A) 純環境變數 → 不支援多租戶差異化設定
- B) 純 config.yaml → 部署時需要編輯 submodule 內的檔案，不利 git 管理

**理由**：與 `his` 模組的 `CTHIS_DATA_PATH` 環境變數模式一致。config.yaml 可覆蓋預設值，環境變數作為 fallback，兼顧靈活性和易部署。

### Decision 4：司法院裁判書查詢 — HTTP 請求 + HTML 解析

**選擇**：`JudicialGovProvider` 透過 HTTP POST 向司法院裁判書查詢系統 (`judgment.judicial.gov.tw`) 發送查詢請求，解析回傳的 HTML 頁面提取判決資料。

**替代方案**：
- A) 使用 Playwright 瀏覽器自動化 → 資源消耗大，不適合高頻查詢
- B) 維護本地判決資料庫副本 → 資料量太大（數百萬筆判決），不實際

**理由**：司法院沒有公開 REST API，但其查詢頁面的 HTTP 介面可直接用 `httpx` 存取。HTML 解析雖然脆弱（網站改版會壞），但第一版可接受，且 `LegalSearchProvider` 介面設計讓未來切換到 Lawsnote API 時無需改動上層程式碼。

**風險緩解**：HTML 解析邏輯集中在 `judicial.py` 單一檔案，改版時只需修改此檔案。解析失敗時回傳明確的錯誤訊息。

### Decision 5：引用核查的判決字號解析 — 正則匹配台灣案號格式

**選擇**：`verify_citations` 工具先用正則表達式解析引用內容，判斷是判決字號還是法條：
- 判決字號格式：`{法院} {年度}年度{字別}字第{號數}號`（如「最高法院 108 年度台上字第 1234 號」）
- 法條格式：`{法律名稱}第{條號}條`（如「民法第 184 條」）

判決字號交給 `LegalSearchProvider.verify_citation()` 查詢；法條驗證第一版使用靜態法條資料庫（主要法律的條文總數對照表）。

**替代方案**：
- A) 全部交給外部 API 驗證 → 法條驗證不需要外部 API，靜態資料即可
- B) 不區分類型，統一查詢 → 效率低，且法條查詢不需要連線

**理由**：判決字號和法條的驗證方式不同，分開處理更精確。靜態法條資料庫體積小（JSON 檔案），可隨模組版本更新。

### Decision 6：文書模板設計 — Markdown + YAML frontmatter

**選擇**：每個模板檔案以 YAML frontmatter 定義 metadata，正文為 Markdown 結構化範本，AI 填入內容時遵循結構：

```markdown
---
name: civil_complaint
display_name: 民事起訴狀
category: civil
required_fields:
  - court
  - plaintiff
  - defendant
  - claims
  - facts_and_reasons
---

# 民事起訴狀

## 案號
{case_number}

## 當事人
### 原告
{plaintiff_info}

### 被告
{defendant_info}

### 訴訟代理人
{attorney_info}

## 訴之聲明
{claims}

## 事實及理由
{facts_and_reasons}

## 證據
{evidence_list}

## 附件
{attachments}
```

**替代方案**：
- A) Jinja2 模板引擎 → 過於複雜，AI 直接填入 Markdown 更自然
- B) 純文字說明（無結構） → AI 可能產出不符合法院格式的內容

**理由**：Markdown 結構模板對 AI 來說最直覺 — 模板即是 prompt 的一部分，AI 看到結構自然按結構填寫。YAML frontmatter 讓程式碼知道哪些欄位是必填的，可在產出後做基本驗證。

### Decision 7：多租戶客戶設定載入 — 遵循 `his` 模組的 `clients/` 模式

**選擇**：
```python
# 啟動時載入客戶設定
client_code = os.environ.get("LAW_CLIENT", "")
config_path = extends_law_dir / "clients" / client_code / "config.yaml"
```

每個事務所在 `clients/{firm-code}/` 下有：
- `config.yaml`：事務所設定（資料夾路徑、判決檢索 provider、功能開關）
- `agents/law-assistant.md`：事務所專屬 Agent prompt（融入事務所風格、專長領域）

**理由**：與 `his` 模組的 `HIS_CLIENT` 環境變數 + `clients/{client-code}/config.yaml` 完全一致，維護者熟悉此模式。

### Decision 8：工作流階段狀態追蹤 — 檔案系統驅動，不建額外表格

**選擇**：工作流的進度由案件資料夾中已存在的檔案決定，不在資料庫中追蹤工作流狀態。

判斷邏輯：
| 已存在檔案 | 推斷進度 |
|---|---|
| 無 | 尚未開始 |
| `00_案件總覽/證據目錄.md` | 階段 1 完成 |
| `80_AI產出/策略分析報告.md` | 階段 2 完成 |
| `80_AI產出/*草稿.md` | 階段 3 完成 |
| `80_AI產出/核查報告.md` | 階段 4 完成 |
| `10_書狀/*.docx` | 階段 5 完成 |

**替代方案**：
- A) 資料庫表格記錄工作流狀態 → 與檔案系統可能不同步，需要雙寫
- B) JSON 狀態檔案 → 額外的狀態檔案管理，容易被誤刪

**理由**：每個階段都會產出具體檔案，檔案本身就是最可靠的進度指標。不需要額外的狀態管理機制，避免檔案系統與狀態資料不同步的問題。這也讓律師可以在資料夾中直觀看到目前進度。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 司法院網站改版導致 HTML 解析失敗 | 解析邏輯集中在 `judicial.py` 單一檔案；解析失敗回傳明確錯誤；可插拔介面讓切換 provider 不影響其他功能 |
| 身分證字號加密的 key 管理 | 使用主系統的 `SECRET_KEY` 環境變數作為加密金鑰，與現有的 session 管理共用；不額外引入 key 管理機制 |
| 案件資料夾路徑中含中文字元 | Python `pathlib` 和 Linux 檔案系統原生支援 UTF-8；NAS（SMB）需確認掛載時使用 `iocharset=utf8` |
| AI 產出的法律文書品質不足 | 五階段工作流的每個階段都有人類確認門；最終交付時強制提示「僅供參考」免責聲明 |
| 證據檔案過大（高解析度掃描） | `generate_evidence_index` 僅讀取檔案 metadata（名稱、大小），不讀取檔案內容；AI 分析證據內容時由 AI 自行判斷是否需要讀取 |
| 多租戶設定衝突 | 同一 CTOS 實例同時只服務一個事務所（`LAW_CLIENT` 環境變數決定），與 `his` 模組的 `HIS_CLIENT` 相同限制 |

## Open Questions

1. **身分證字號是否需要加密？** — 目前設計使用加密儲存，但這增加了複雜度。如果部署環境已有足夠的資料庫存取控制，是否可以改為明文 + 資料庫權限管理？
2. **案件刪除策略** — 目前未設計刪除案件功能。是否需要軟刪除（標記為已歸檔）？還是案件一旦建立永不刪除？
3. **同一事務所的多位律師權限隔離** — 目前所有使用者可見所有案件。未來是否需要依承辦律師篩選可見案件？
