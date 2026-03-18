## ADDED Requirements

### Requirement: 建立當事人
系統 SHALL 提供 `create_party` MCP 工具，建立當事人記錄，支援自然人和法人兩種類型。

#### Scenario: 建立自然人
- **WHEN** AI 呼叫 `create_party(name="王小明", party_type="natural_person", phone="0912345678")`
- **THEN** 系統在 `law_parties` 表格新增一筆記錄，回傳當事人 ID

#### Scenario: 建立法人
- **WHEN** AI 呼叫 `create_party(name="某某股份有限公司", party_type="legal_entity", id_number="12345678")`
- **THEN** 系統在 `law_parties` 表格新增一筆記錄，`id_number` 以加密方式儲存

#### Scenario: 姓名重複
- **WHEN** `name` 與現有當事人相同
- **THEN** 系統 SHALL 仍建立新記錄（允許同名），但在回傳訊息中提示已有同名當事人

### Requirement: 查詢當事人
系統 SHALL 提供 `get_party` 和 `list_parties` MCP 工具，支援精確查詢和模糊搜尋。

#### Scenario: 以 ID 查詢
- **WHEN** AI 呼叫 `get_party(party_id=1)`
- **THEN** 系統回傳當事人完整資訊，包含關聯的所有案件清單（含角色）

#### Scenario: 以姓名模糊搜尋
- **WHEN** AI 呼叫 `get_party(name="王")`
- **THEN** 系統回傳所有姓名包含「王」的當事人列表

#### Scenario: 列出所有法人
- **WHEN** AI 呼叫 `list_parties(party_type="legal_entity")`
- **THEN** 系統回傳所有法人類型的當事人列表

### Requirement: 關聯當事人到案件
系統 SHALL 提供 `link_party_to_case` MCP 工具，將當事人以特定角色關聯到案件。

#### Scenario: 成功關聯
- **WHEN** AI 呼叫 `link_party_to_case(case_id=1, party_id=2, role="defendant")`
- **THEN** 系統在 `law_case_parties` 表格新增關聯記錄

#### Scenario: 重複關聯
- **WHEN** 同一當事人以同一角色已關聯到同一案件
- **THEN** 系統回傳提示「該當事人已以此角色關聯到此案件」，不建立重複記錄

#### Scenario: 同一當事人不同角色
- **WHEN** 同一當事人需以不同角色關聯到同一案件（如同時為原告和證人）
- **THEN** 系統 SHALL 允許建立，因為 UNIQUE 約束是 (case_id, party_id, role) 的組合

### Requirement: 當事人 DB 表格
系統 SHALL 透過 Alembic migration 建立 `law_parties` 和 `law_case_parties` 表格。`law_parties` 包含姓名、身分證/統編（加密）、類型、聯絡方式等欄位。`law_case_parties` 為案件與當事人的多對多關聯表。

#### Scenario: Migration 執行
- **WHEN** 執行 `uv run alembic upgrade head`
- **THEN** 資料庫中建立 `law_parties` 和 `law_case_parties` 表格，含 UNIQUE(case_id, party_id, role) 約束和外鍵關聯

### Requirement: 身分證字號加密儲存
系統 SHALL 對 `law_parties.id_number` 欄位進行加密後再寫入資料庫，查詢時解密顯示。

#### Scenario: 儲存含身分證字號的當事人
- **WHEN** 建立當事人並提供 `id_number="A123456789"`
- **THEN** 資料庫中儲存的值為加密後的密文，透過 `get_party` 查詢時回傳明文
