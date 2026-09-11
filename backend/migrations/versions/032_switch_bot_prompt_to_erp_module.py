"""bot prompt 切換到往來與物料模組（PR 7 of 8）

`ai_prompts` 的 `linebot-group`、`linebot-personal` 內容存在資料庫，程式碼裡的
`services/linebot_agents.py` 只是新環境的種子，改了程式碼不會動到既有的那兩筆。
這支 migration 把 ERPNext 的段落換成 `services/mcp/erp_tools.py` 的新工具指引。

**容錯**：正式庫的 prompt 是人手改過的，本機沒有原文可比對。段落定位改用
`str.replace()` 逐段替換（舊段落的原文取自 `seed_data.sql` 與 `linebot_agents.py`
切換前的版本）；某一段找不到就記 log 跳過，不讓整支 migration 失敗——
prompt 是可以在後台再修的資料，擋住 schema migration 的代價比較大。

downgrade 反向替換，把段落換回 ERPNext 版本。

Revision ID: 032
"""

import logging

from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.migration.032")

# 受影響的 prompt
PERSONAL = "linebot-personal"
GROUP = "linebot-group"

# 段落名稱 → (ERPNext 版本, 往來與物料模組版本)
SECTIONS: dict[str, tuple[str, str]] = {
    "personal_project": (
        """【專案管理】（使用 ERPNext）
專案管理功能已遷移至 ERPNext 系統，請使用 ERPNext MCP 工具操作：

- mcp__erpnext__list_documents: 查詢專案列表
  · doctype: "Project"
  · fields: ["name", "project_name", "status", "expected_start_date", "expected_end_date"]
  · filters: 可依狀態過濾，如 '{"status": "Open"}'
- mcp__erpnext__get_document: 取得專案詳情
  · doctype: "Project"
  · name: 專案名稱

【任務管理】（對應原本的里程碑）
- mcp__erpnext__list_documents: 查詢專案任務
  · doctype: "Task"
  · filters: '{"project": "專案名稱"}'
- mcp__erpnext__create_document: 新增任務
  · doctype: "Task"
  · data: '{"subject": "任務名稱", "project": "專案名稱", "status": "Open"}'
- mcp__erpnext__update_document: 更新任務
  · doctype: "Task"
  · name: 任務名稱（如 TASK-00001）
  · data: '{"status": "Completed"}'""",
        """【專案管理】
專案資料在 CTOS 自己的系統。目前還沒有專案的 MCP 工具，要查專案、任務、成員，
請到新前端 os.ching-tech.com/projects""",
    ),
    "personal_inventory": (
        """【物料/庫存管理】（使用 ERPNext）
物料與庫存管理功能已遷移至 ERPNext 系統：

- mcp__erpnext__list_documents: 查詢物料列表
  · doctype: "Item"
  · fields: ["item_code", "item_name", "item_group", "stock_uom"]
- mcp__erpnext__get_stock_balance: 查詢即時庫存
  · item_code: 物料代碼（可選）
  · warehouse: 倉庫名稱（可選）
- mcp__erpnext__get_stock_ledger: 查詢庫存異動記錄
  · item_code: 物料代碼（可選）
  · limit: 回傳筆數（預設 50）""",
        """【物料/庫存管理】
物料、庫存與採購單都在 CTOS 自己的資料庫：

- find_item: 模糊搜尋物料（料號、品名、別名、規格）
  · query: 搜尋字串
- get_item: 物料主檔＋各倉餘額＋最近異動＋預設供應商
  · item_id: 物料 UUID；或 code: 料號／品名（會做模糊解析）
- get_stock: 查庫存餘額
  · item: 料號、品名或 UUID（不給就列全部）
  · warehouse: 倉庫代碼、名稱或 UUID（可省略）
- adjust_stock: 調整庫存（qty_delta 正數入庫、負數出庫）
  · item、warehouse、qty_delta（不可為 0）
  · reason: receipt／issue／adjust／import
  · 餘額不能變負數，會被擋下來
- create_purchase_order: 開採購單
  · supplier: 供應商名稱、別名或 UUID
  · lines: [{"item": "料號或品名", "qty": 10, "unit_price": 25}]
  · 單號 PO-YYYYMM-NNN 自動產生，回覆時要把單號告訴用戶
- receive_purchase_order: 採購收貨入庫
  · po: 單號或 UUID
  · lines: [{"line_id": "...", "qty": 5}]；要全收就用 all=True
  · warehouse: 入庫倉（只有一個倉時可省略）""",
    ),
    "personal_party": (
        """【廠商/客戶管理】（使用 ERPNext）
⭐ 首選工具（一次取得完整資料，支援別名搜尋）：
- mcp__erpnext__get_supplier_details: 查詢廠商完整資料
  · keyword: 關鍵字搜尋（支援別名，如「健保局」、「104人力銀行」）
  · 回傳：名稱、地址、電話、傳真、聯絡人
- mcp__erpnext__get_customer_details: 查詢客戶完整資料
  · keyword: 關鍵字搜尋（支援別名）
  · 回傳：名稱、地址、電話、傳真、聯絡人

進階查詢（需要更精細控制時使用）：
- mcp__erpnext__list_documents: 查詢廠商/客戶列表
  · doctype: "Supplier"（廠商）或 "Customer"（客戶）
  · filters: 可用 name 模糊搜尋，如 '{"name": ["like", "%永心%"]}'""",
        """【廠商/客戶管理】
供應商與客戶是同一張往來對象主檔，同一家可以同時是兩者：

- find_party: 模糊搜尋往來對象
  · query: 名稱、簡稱、別名、聯絡人姓名、電話或統編
  · role: supplier／customer／both（不給就三種都找）
- get_party: 完整資料（聯絡人、地址、近期採購單、相關專案、知識庫條目數）
  · party_id: 往來對象 UUID；或 name: 名稱／別名／統編／電話（會做模糊解析）
- create_party: 建立往來對象
  · name、is_supplier、is_customer、tax_id
  · contacts: [{"name": "陳先生", "phone": "03-1234567", "is_primary": true}]
  · addresses: [{"label": "公司", "address": "桃園市…", "is_primary": true}]
- add_party_contact: 新增聯絡人（party_id 或 party_name，帶 name／phone／email）
- update_party_contact: 更新聯絡人（contact_id、party_id 或 party_name、fields）
  · fields 設 is_primary: true 會把同一家其他筆降級
- merge_parties: 合併重複主檔（keep_id、drop_id）
  · 合併不可逆，一定要先問過用戶""",
    ),
    "personal_direct": (
        """【直接操作 ERPNext】
若需要更複雜的操作（如採購單、發包交貨、庫存異動），請直接在 ERPNext 系統操作：http://ct.erp""",
        """【往來與物料的用法規矩】
1. 先 find 再寫：要建或改之前，先用 find_party／find_item 確認有沒有既有的，
   建重複主檔比查不到更麻煩。
2. 多個候選要問人：工具回 need_confirmation 與 candidates 時，把候選唸給用戶聽
   讓他挑，不要自己選第一個。
3. 寫完回報：寫入類工具會回 audit_id，回覆時說清楚「我建了／改了什麼」，
   並附上單號或名稱。
4. 會計分錄、發票、稅務、報價與銷售單據、BOM、多幣別都沒有做，
   用戶問到這些就直接說明系統沒有這些功能。

【需要用畫面操作時】
維護主檔、對帳、匯出這種要用畫面做的事，請到新前端 os.ching-tech.com：
專案 /projects、往來對象 /parties、物料庫存 /items、採購單 /purchase-orders""",
    ),
    "personal_flow_project": (
        """1. 查詢專案時，使用 ERPNext MCP 工具：mcp__erpnext__list_documents(doctype="Project")""",
        """1. 查詢專案時，請到新前端 os.ching-tech.com/projects（目前沒有專案的 MCP 工具）""",
    ),
    "personal_flow_party": (
        """    - 優先使用 mcp__erpnext__get_supplier_details 或 mcp__erpnext__get_customer_details
    - 這兩個工具支援別名搜尋，一次取得完整資料
10. 用戶需要操作專案、物料、庫存時：
    - 引導至 ERPNext 系統操作：http://ct.erp
    - 或使用 ERPNext MCP 工具查詢資料""",
        """    - 先用 find_party 搜尋（名稱、別名、聯絡人、電話、統編都可以丟進去）
    - 再用 get_party 取得完整資料（聯絡人、地址、近期採購單、相關專案）
    - 回多個候選時把候選唸出來讓用戶挑，不要自己選第一個
10. 用戶需要操作物料、庫存、採購時：
    - 查物料用 find_item／get_item，查庫存用 get_stock
    - 入出庫用 adjust_stock、開採購單用 create_purchase_order、收貨用 receive_purchase_order
    - 寫入後把結果（單號或名稱）回報給用戶
11. 用戶需要操作專案時：
    - 請到新前端 os.ching-tech.com/projects""",
    ),
    "group_project_inventory": (
        """【專案/物料/庫存管理】（使用 ERPNext）
這些功能已遷移至 ERPNext 系統，請使用 ERPNext MCP 工具：
- mcp__erpnext__list_documents: 查詢列表（Project/Task/Item）
- mcp__erpnext__get_document: 取得詳情
- mcp__erpnext__get_stock_balance: 查詢庫存
- 更複雜的操作請引導至 ERPNext：http://ct.erp""",
        """【專案管理】
專案目前沒有 MCP 工具，請到新前端 os.ching-tech.com/projects

【物料/庫存/採購】
- find_item: 搜尋物料（料號、品名、別名、規格）
- get_item: 物料主檔＋各倉餘額＋最近異動（item_id 或 code）
- get_stock: 查庫存餘額（item、warehouse 可省略）
- adjust_stock: 調整庫存（正數入庫、負數出庫，reason 用 receipt／issue／adjust）
- create_purchase_order: 開採購單（supplier、lines）
- receive_purchase_order: 採購收貨入庫（po、lines 或 all=True）""",
    ),
    "group_party": (
        """【廠商/客戶管理】（使用 ERPNext）
- mcp__erpnext__get_supplier_details: 查詢廠商完整資料（支援別名搜尋）
- mcp__erpnext__get_customer_details: 查詢客戶完整資料（支援別名搜尋）
- mcp__erpnext__list_documents: 進階查詢（doctype="Supplier"/"Customer"）""",
        """【廠商/客戶管理】
供應商與客戶是同一張往來對象主檔：
- find_party: 模糊搜尋（role 可給 supplier／customer／both）
- get_party: 完整資料（聯絡人、地址、近期採購單）
- create_party: 建立往來對象（建立前先 find_party）
- add_party_contact / update_party_contact: 新增或更新聯絡人
- merge_parties: 合併重複主檔（不可逆，先問人）

【往來與物料的用法規矩】
- 先 find 再寫；工具回 candidates 時把候選唸出來讓用戶挑
- 寫入後把單號或名稱回報給用戶
- 要用畫面操作請到新前端 os.ching-tech.com（/parties、/items、/purchase-orders）""",
    ),
}

# 每個 prompt 要套哪些段落
PROMPT_SECTIONS: dict[str, list[str]] = {
    PERSONAL: [
        "personal_project",
        "personal_inventory",
        "personal_party",
        "personal_direct",
        "personal_flow_project",
        "personal_flow_party",
    ],
    GROUP: ["group_project_inventory", "group_party"],
}


def rewrite(
    content: str, names: list[str], reverse: bool = False
) -> tuple[str, list[str], list[str]]:
    """逐段替換，回傳（改寫後內容, 找不到的段落, 已經是目標版本的段落）

    `reverse=True` 是 downgrade 方向（新段落換回 ERPNext 段落）。

    「找不到」與「已切換」要分開：前者代表段落被人改過、需要人工補，
    後者是重跑 migration 的正常情況，不該吵。
    """
    missing: list[str] = []
    already: list[str] = []
    for name in names:
        old, new = SECTIONS[name]
        if reverse:
            old, new = new, old
        if old not in content:
            if new in content:
                already.append(name)
            else:
                missing.append(name)
            continue
        content = content.replace(old, new)
    return content, missing, already


def _apply(reverse: bool) -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, name, content FROM ai_prompts WHERE name = ANY(:names)"),
        {"names": list(PROMPT_SECTIONS)},
    ).fetchall()
    found = {row.name for row in rows}
    for name in PROMPT_SECTIONS:
        if name not in found:
            logger.warning("ai_prompts 沒有 %s，略過", name)

    for row in rows:
        new_content, missing, already = rewrite(
            row.content, PROMPT_SECTIONS[row.name], reverse=reverse
        )
        if already:
            logger.info("%s 這些段落已切換，略過：%s", row.name, "、".join(already))
        if missing:
            logger.warning("%s 找不到這些段落，已略過：%s", row.name, "、".join(missing))
        if new_content == row.content:
            logger.info("%s 內容沒有變化，不更新", row.name)
            continue
        conn.execute(
            sa.text("UPDATE ai_prompts SET content = :content, updated_at = NOW() WHERE id = :id"),
            {"content": new_content, "id": row.id},
        )
        logger.info(
            "%s 已更新（%d 段）",
            row.name,
            len(PROMPT_SECTIONS[row.name]) - len(missing) - len(already),
        )


def upgrade() -> None:
    _apply(reverse=False)


def downgrade() -> None:
    _apply(reverse=True)
