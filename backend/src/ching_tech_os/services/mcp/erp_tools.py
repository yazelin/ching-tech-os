"""往來與物料模組 MCP 工具（主要 API）

規格第三節。工具名稱短、動詞開頭，輸入容忍自然語言（名稱、別名、電話、統編、
料號），解析在 service 層（`services/erp.py`）。三條規矩：

1. **先 find 再寫**：寫入類工具會自己解析，但解析到多個候選時**不會猜**，
   回 `{"need_confirmation": true, "candidates": [...]}` 讓 agent 回去問人。
2. **寫入回 audit_id**：每個寫入類工具的回傳都帶 `audit_id`，agent 回覆時引用。
3. **文件擷取不呼叫模型**：`extract_*_from_document` 只把 agent 讀出來的欄位
   整理成草稿並比對重複主檔，擷取本身由 agent 完成（AI Log 才看得到過程）。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from .server import check_mcp_tool_permission, ensure_db_connection, logger, mcp
from ...models.erp import ItemUpdate, PartyAddressUpdate, PartyContactUpdate, PartyUpdate
from ...services import erp as erp_core
from ...services import erp_inventory as inventory_service
from ...services import erp_parties as party_service
from ...services import erp_purchasing as purchasing_service


# ============================================================
# 共用輔助
# ============================================================


def _clean(value: Any) -> Any:
    """UUID／Decimal／date 轉成可序列化的字串（MCP 回傳要能 JSON 化）"""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _error(message: str) -> dict:
    return {"ok": False, "error": message}


# find_party／list_parties 共用的角色枚舉（REST 端由 PartyRole 這個 Literal 鎖住，
# MCP 這邊沒有 pydantic 幫忙擋，手動比對）
_PARTY_ROLES = {"supplier", "customer", "both"}


def _fail(exc: Exception) -> dict:
    """把 service 的例外翻成工具回傳，不往外丟（agent 拿到的是資料不是 traceback）"""
    if isinstance(exc, erp_core.AmbiguousError):
        return {
            "ok": False,
            "need_confirmation": True,
            "entity": exc.entity,
            "query": exc.query,
            "candidates": _clean(exc.candidates),
            "message": str(exc),
        }
    if isinstance(exc, erp_core.NotFoundError):
        return {"ok": False, "not_found": True, "error": str(exc)}
    if isinstance(exc, erp_core.ErpError):
        return _error(str(exc))
    logger.error("ERP 工具執行失敗: %s", exc)
    return _error(f"執行失敗：{exc}")


async def _guard(tool_name: str, ctos_user_id: int | None) -> dict | None:
    """連線 ＋ 工具權限；有問題回錯誤 dict，沒問題回 None"""
    await ensure_db_connection()
    allowed, message = await check_mcp_tool_permission(tool_name, ctos_user_id)
    if not allowed:
        return _error(message)
    return None


async def _party_id_from(
    party_id: str | None, name: str | None, role: str | None = None
) -> UUID:
    """id 優先，其次用名稱解析（可能拋 Ambiguous／NotFound）"""
    if party_id:
        return UUID(party_id)
    if not name:
        raise erp_core.NotFoundError("往來對象", "")
    hit = await erp_core.resolve_party(name, role=role)
    return hit["id"]


async def _item_id_from(item_id: str | None, query: str | None) -> UUID:
    if item_id:
        return UUID(item_id)
    if not query:
        raise erp_core.NotFoundError("物料", "")
    hit = await erp_core.resolve_item(query)
    return hit["id"]


def _validated_fields(model, fields: dict) -> dict:
    """把 agent 給的 fields 過一次 Update 模型

    NOT NULL 欄位送 null、狀態值不在 Literal 裡，都在這裡就被擋下來，
    不會變成資料庫例外（回給 agent 的是「哪個欄位不行」）。

    Raises:
        InvalidOperationError: 驗證失敗（呼叫端會翻成 {"ok": false, "error": ...}）
    """
    try:
        body = model.model_validate(fields)
    except ValidationError as e:
        problems = "；".join(
            f"{'.'.join(str(x) for x in err['loc']) or '欄位'}：{err['msg']}"
            for err in e.errors()
        )
        raise erp_core.InvalidOperationError(f"欄位不合法（{problems}）") from e
    return body.model_dump(exclude_unset=True)


async def _warehouse_id_from(warehouse: str | None) -> UUID | None:
    if not warehouse:
        return None
    try:
        return UUID(warehouse)
    except ValueError:
        hit = await erp_core.resolve_warehouse(warehouse)
        return hit["id"]


# ============================================================
# 往來對象
# ============================================================


@mcp.tool()
async def find_party(
    query: str,
    role: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """模糊搜尋往來對象（供應商／客戶）

    Args:
        query: 名稱、簡稱、別名、聯絡人姓名、電話或統編
        role: supplier／customer／both，不給就三種都找
        ctos_user_id: CTOS 用戶 ID（稽核用，伺服器會自動帶）
    """
    guard = await _guard("find_party", ctos_user_id)
    if guard:
        return guard
    if role is not None and role not in _PARTY_ROLES:
        return _error(f"role 不合法：{role}（只能是 supplier／customer／both）")
    try:
        candidates = await erp_core.find_parties(query, role=role)
    except Exception as e:
        return _fail(e)
    return {"ok": True, "count": len(candidates), "candidates": _clean(candidates)}


@mcp.tool()
async def get_party(
    party_id: str | None = None,
    name: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """取得往來對象完整資料（聯絡人、地址、近期採購單、相關專案、知識庫條目數）

    Args:
        party_id: 往來對象 UUID（有就優先用）
        name: 名稱／別名／統編／電話，會做模糊解析
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("get_party", ctos_user_id)
    if guard:
        return guard
    try:
        pid = await _party_id_from(party_id, name)
        detail = await party_service.get_party_detail(pid)
    except Exception as e:
        return _fail(e)
    if detail is None:
        return {"ok": False, "not_found": True, "error": "找不到往來對象"}
    return {"ok": True, "party": _clean(detail)}


@mcp.tool()
async def create_party(
    name: str,
    short_name: str | None = None,
    is_supplier: bool = False,
    is_customer: bool = False,
    tax_id: str | None = None,
    industry: str | None = None,
    payment_terms: str | None = None,
    aliases: list[str] | None = None,
    notes: str | None = None,
    contacts: list[dict] | None = None,
    addresses: list[dict] | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """建立往來對象（建立前請先 find_party 確認沒有重複）

    Args:
        name: 公司全名
        short_name: 簡稱
        is_supplier / is_customer: 角色（可同時成立）
        tax_id: 統一編號
        industry / payment_terms / notes: 產業、付款條件、備註
        aliases: 別名清單（模糊搜尋用）
        contacts: `[{"name":..., "title":..., "phone":..., "mobile":..., "email":..., "is_primary":true}]`
        addresses: `[{"label":"公司", "address":..., "city":..., "is_primary":true}]`
        ctos_user_id: CTOS 用戶 ID（稽核的 actor）
    """
    guard = await _guard("create_party", ctos_user_id)
    if guard:
        return guard
    try:
        row = await party_service.create_party(
            {
                "name": name,
                "short_name": short_name,
                "is_supplier": is_supplier,
                "is_customer": is_customer,
                "tax_id": tax_id,
                "industry": industry,
                "payment_terms": payment_terms,
                "aliases": aliases or [],
                "notes": notes,
                "contacts": contacts or [],
                "addresses": addresses or [],
            },
            actor_user_id=ctos_user_id,
            via="mcp",
        )
    except Exception as e:
        return _fail(e)
    return {
        "ok": True,
        "party_id": str(row["id"]),
        "name": row["name"],
        "audit_id": str(row["audit_id"]),
    }


@mcp.tool()
async def update_party(
    party_id: str | None = None,
    name: str | None = None,
    fields: dict | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """更新往來對象主檔

    Args:
        party_id: 往來對象 UUID
        name: 沒有 id 時用名稱解析
        fields: 要改的欄位，例如 `{"payment_terms": "月結 60 天", "aliases": ["丙丁"]}`
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("update_party", ctos_user_id)
    if guard:
        return guard
    if not fields:
        return _error("沒有要更新的欄位")
    try:
        payload = _validated_fields(PartyUpdate, fields)
        pid = await _party_id_from(party_id, name)
        row = await party_service.update_party(
            pid, payload, actor_user_id=ctos_user_id, via="mcp"
        )
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "找不到往來對象"}
    return {
        "ok": True,
        "party_id": str(row["id"]),
        "name": row["name"],
        "audit_id": str(row["audit_id"]),
    }


@mcp.tool()
async def add_party_contact(
    party_id: str | None = None,
    party_name: str | None = None,
    name: str = "",
    title: str | None = None,
    phone: str | None = None,
    mobile: str | None = None,
    email: str | None = None,
    is_primary: bool = False,
    notes: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """新增聯絡人

    Args:
        party_id / party_name: 指定往來對象（二擇一）
        name: 聯絡人姓名（必填）
        title / phone / mobile / email / notes: 職稱、電話、手機、信箱、備註
        is_primary: 設為主要聯絡人（會把同一家原本的主要聯絡人取消）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("add_party_contact", ctos_user_id)
    if guard:
        return guard
    if not name:
        return _error("聯絡人姓名必填")
    try:
        pid = await _party_id_from(party_id, party_name)
        row = await party_service.add_contact(
            pid,
            {
                "name": name,
                "title": title,
                "phone": phone,
                "mobile": mobile,
                "email": email,
                "is_primary": is_primary,
                "notes": notes,
            },
            actor_user_id=ctos_user_id,
            via="mcp",
        )
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "找不到往來對象"}
    return {
        "ok": True,
        "contact_id": str(row["id"]),
        "party_id": str(row["party_id"]),
        "audit_id": str(row["audit_id"]),
    }


@mcp.tool()
async def add_party_address(
    party_id: str | None = None,
    party_name: str | None = None,
    address: str = "",
    label: str | None = None,
    city: str | None = None,
    is_primary: bool = False,
    ctos_user_id: int | None = None,
) -> dict:
    """新增地址

    Args:
        party_id / party_name: 指定往來對象（二擇一）
        address: 地址（必填）
        label: 公司／工廠／收貨
        city: 縣市
        is_primary: 設為主要地址
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("add_party_address", ctos_user_id)
    if guard:
        return guard
    if not address:
        return _error("地址必填")
    try:
        pid = await _party_id_from(party_id, party_name)
        row = await party_service.add_address(
            pid,
            {
                "address": address,
                "label": label,
                "city": city,
                "is_primary": is_primary,
            },
            actor_user_id=ctos_user_id,
            via="mcp",
        )
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "找不到往來對象"}
    return {
        "ok": True,
        "address_id": str(row["id"]),
        "party_id": str(row["party_id"]),
        "audit_id": str(row["audit_id"]),
    }


@mcp.tool()
async def update_party_contact(
    contact_id: str,
    party_id: str | None = None,
    party_name: str | None = None,
    fields: dict | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """更新聯絡人

    Args:
        contact_id: 聯絡人 UUID（必填）
        party_id / party_name: 指定往來對象（二擇一，用來確認聯絡人屬於哪一家）
        fields: 要改的欄位，例如 `{"phone": "03-1234567", "is_primary": true}`
            （`is_primary` 設 true 會把同一家其他聯絡人降級）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("update_party_contact", ctos_user_id)
    if guard:
        return guard
    if not fields:
        return _error("沒有要更新的欄位")
    try:
        payload = _validated_fields(PartyContactUpdate, fields)
        pid = await _party_id_from(party_id, party_name)
        row = await party_service.update_contact(
            pid, UUID(contact_id), payload, actor_user_id=ctos_user_id, via="mcp"
        )
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "找不到聯絡人"}
    return {
        "ok": True,
        "contact_id": str(row["id"]),
        "party_id": str(row["party_id"]),
        "audit_id": str(row["audit_id"]),
    }


@mcp.tool()
async def delete_party_contact(
    contact_id: str,
    party_id: str | None = None,
    party_name: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """刪除聯絡人（刪掉主要那筆不自動指派新主要）

    Args:
        contact_id: 聯絡人 UUID（必填）
        party_id / party_name: 指定往來對象（二擇一）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("delete_party_contact", ctos_user_id)
    if guard:
        return guard
    try:
        pid = await _party_id_from(party_id, party_name)
        audit_id = await party_service.delete_contact(
            pid, UUID(contact_id), actor_user_id=ctos_user_id, via="mcp"
        )
    except Exception as e:
        return _fail(e)
    if audit_id is None:
        return {"ok": False, "not_found": True, "error": "找不到聯絡人"}
    return {"ok": True, "contact_id": contact_id, "audit_id": str(audit_id)}


@mcp.tool()
async def update_party_address(
    address_id: str,
    party_id: str | None = None,
    party_name: str | None = None,
    fields: dict | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """更新地址

    Args:
        address_id: 地址 UUID（必填）
        party_id / party_name: 指定往來對象（二擇一，用來確認地址屬於哪一家）
        fields: 要改的欄位，例如 `{"city": "台北市", "is_primary": true}`
            （`is_primary` 設 true 會把同一家其他地址降級）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("update_party_address", ctos_user_id)
    if guard:
        return guard
    if not fields:
        return _error("沒有要更新的欄位")
    try:
        payload = _validated_fields(PartyAddressUpdate, fields)
        pid = await _party_id_from(party_id, party_name)
        row = await party_service.update_address(
            pid, UUID(address_id), payload, actor_user_id=ctos_user_id, via="mcp"
        )
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "找不到地址"}
    return {
        "ok": True,
        "address_id": str(row["id"]),
        "party_id": str(row["party_id"]),
        "audit_id": str(row["audit_id"]),
    }


@mcp.tool()
async def delete_party_address(
    address_id: str,
    party_id: str | None = None,
    party_name: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """刪除地址（刪掉主要那筆不自動指派新主要）

    Args:
        address_id: 地址 UUID（必填）
        party_id / party_name: 指定往來對象（二擇一）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("delete_party_address", ctos_user_id)
    if guard:
        return guard
    try:
        pid = await _party_id_from(party_id, party_name)
        audit_id = await party_service.delete_address(
            pid, UUID(address_id), actor_user_id=ctos_user_id, via="mcp"
        )
    except Exception as e:
        return _fail(e)
    if audit_id is None:
        return {"ok": False, "not_found": True, "error": "找不到地址"}
    return {"ok": True, "address_id": address_id, "audit_id": str(audit_id)}


@mcp.tool()
async def merge_parties(
    keep_id: str,
    drop_id: str,
    ctos_user_id: int | None = None,
) -> dict:
    """合併重複的往來對象：drop 的聯絡人、地址、採購單掛到 keep，drop 軟刪除

    Args:
        keep_id: 保留的往來對象 UUID
        drop_id: 要被合併掉的往來對象 UUID（名稱會變成 keep 的別名）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("merge_parties", ctos_user_id)
    if guard:
        return guard
    try:
        row = await party_service.merge_parties(
            UUID(keep_id), UUID(drop_id), actor_user_id=ctos_user_id, via="mcp"
        )
    except Exception as e:
        return _fail(e)
    return {
        "ok": True,
        "party_id": str(row["id"]),
        "name": row["name"],
        "aliases": list(row["aliases"] or []),
        "audit_id": str(row["audit_id"]),
    }


# ============================================================
# 物料
# ============================================================


@mcp.tool()
async def find_item(query: str, ctos_user_id: int | None = None) -> dict:
    """模糊搜尋物料（料號、品名、別名、規格）

    Args:
        query: 搜尋字串
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("find_item", ctos_user_id)
    if guard:
        return guard
    try:
        candidates = await erp_core.find_items(query)
    except Exception as e:
        return _fail(e)
    return {"ok": True, "count": len(candidates), "candidates": _clean(candidates)}


@mcp.tool()
async def get_item(
    item_id: str | None = None,
    code: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """取得物料主檔＋各倉餘額＋最近異動＋預設供應商

    Args:
        item_id: 物料 UUID
        code: 料號或品名（會做模糊解析）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("get_item", ctos_user_id)
    if guard:
        return guard
    try:
        iid = await _item_id_from(item_id, code)
        detail = await inventory_service.get_item_detail(iid)
    except Exception as e:
        return _fail(e)
    if detail is None:
        return {"ok": False, "not_found": True, "error": "找不到物料"}
    return {"ok": True, "item": _clean(detail)}


@mcp.tool()
async def create_item(
    code: str,
    name: str,
    spec: str | None = None,
    unit: str | None = None,
    item_group: str | None = None,
    default_supplier: str | None = None,
    purchase_price: float | None = None,
    lead_days: int | None = None,
    aliases: list[str] | None = None,
    notes: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """建立物料（建立前請先 find_item 確認沒有重複）

    Args:
        code: 料號（唯一）
        name: 品名
        spec / unit / item_group: 規格、單位、分類
        default_supplier: 預設供應商名稱或 UUID（會做模糊解析）
        purchase_price / lead_days: 採購價、交期天數
        aliases: 別名清單
        notes: 備註
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("create_item", ctos_user_id)
    if guard:
        return guard
    try:
        supplier_id = None
        if default_supplier:
            supplier_id = await _party_id_from(None, default_supplier, role="supplier")
        row = await inventory_service.create_item(
            {
                "code": code,
                "name": name,
                "spec": spec,
                "unit": unit,
                "item_group": item_group,
                "default_supplier_id": supplier_id,
                "purchase_price": (
                    Decimal(str(purchase_price)) if purchase_price is not None else None
                ),
                "lead_days": lead_days,
                "aliases": aliases or [],
                "notes": notes,
            },
            actor_user_id=ctos_user_id,
            via="mcp",
        )
    except Exception as e:
        return _fail(e)
    return {
        "ok": True,
        "item_id": str(row["id"]),
        "code": row["code"],
        "audit_id": str(row["audit_id"]),
    }


@mcp.tool()
async def update_item(
    item_id: str | None = None,
    code: str | None = None,
    fields: dict | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """更新物料主檔

    Args:
        item_id: 物料 UUID
        code: 沒有 id 時用料號／品名解析
        fields: 要改的欄位，例如 `{"purchase_price": 120, "lead_days": 14}`
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("update_item", ctos_user_id)
    if guard:
        return guard
    if not fields:
        return _error("沒有要更新的欄位")
    try:
        payload = _validated_fields(ItemUpdate, fields)
        iid = await _item_id_from(item_id, code)
        row = await inventory_service.update_item(
            iid, payload, actor_user_id=ctos_user_id, via="mcp"
        )
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "找不到物料"}
    return {
        "ok": True,
        "item_id": str(row["id"]),
        "code": row["code"],
        "audit_id": str(row["audit_id"]),
    }


# ============================================================
# 庫存
# ============================================================


@mcp.tool()
async def get_stock(
    item: str | None = None,
    warehouse: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """查庫存餘額

    Args:
        item: 料號、品名或 UUID；不給就列全部（分頁 50 筆）
        warehouse: 倉庫代碼、名稱或 UUID
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("get_stock", ctos_user_id)
    if guard:
        return guard
    try:
        item_id = await _item_id_from(None, item) if item else None
        warehouse_id = await _warehouse_id_from(warehouse)
        result = await inventory_service.get_stock(
            item_id=item_id, warehouse_id=warehouse_id
        )
    except Exception as e:
        return _fail(e)
    return {"ok": True, "total": result["total"], "rows": _clean(result["items"])}


@mcp.tool()
async def adjust_stock(
    item: str,
    warehouse: str,
    qty_delta: float,
    reason: str = "adjust",
    note: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """調整庫存（qty_delta 正數是入庫、負數是出庫）

    Args:
        item: 料號、品名或 UUID
        warehouse: 倉庫代碼、名稱或 UUID
        qty_delta: 異動數量（不可為 0）
        reason: receipt / issue / adjust / import
        note: 備註
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("adjust_stock", ctos_user_id)
    if guard:
        return guard
    try:
        item_id = await _item_id_from(None, item)
        warehouse_id = await _warehouse_id_from(warehouse)
        if warehouse_id is None:
            return _error("請指定倉別")
        result = await inventory_service.adjust_stock(
            item_id,
            warehouse_id,
            Decimal(str(qty_delta)),
            reason=reason,
            note=note,
            actor_user_id=ctos_user_id,
            via="mcp",
        )
    except Exception as e:
        return _fail(e)
    return {
        "ok": True,
        "audit_id": str(result["audit_id"]),
        "qty_after": str(result["balances"][0]["qty"]),
    }


@mcp.tool()
async def transfer_stock(
    item: str,
    from_warehouse: str,
    to_warehouse: str,
    qty: float,
    note: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """倉別調撥（同一交易寫 transfer_out 與 transfer_in）

    Args:
        item: 料號、品名或 UUID
        from_warehouse / to_warehouse: 來源倉與目的倉（代碼、名稱或 UUID）
        qty: 調撥數量（要大於 0）
        note: 備註
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("transfer_stock", ctos_user_id)
    if guard:
        return guard
    try:
        item_id = await _item_id_from(None, item)
        from_id = await _warehouse_id_from(from_warehouse)
        to_id = await _warehouse_id_from(to_warehouse)
        if from_id is None or to_id is None:
            return _error("請指定來源倉與目的倉")
        result = await inventory_service.transfer_stock(
            item_id,
            from_id,
            to_id,
            Decimal(str(qty)),
            note=note,
            actor_user_id=ctos_user_id,
            via="mcp",
        )
    except Exception as e:
        return _fail(e)
    return {
        "ok": True,
        "audit_id": str(result["audit_id"]),
        "balances": _clean(result["balances"]),
    }


# ============================================================
# 採購
# ============================================================


@mcp.tool()
async def create_purchase_order(
    supplier: str,
    lines: list[dict],
    project: str | None = None,
    expected_date: str | None = None,
    notes: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """開採購單（supplier 與 lines 的 item 都吃名稱，解析不到會回候選要你確認）

    Args:
        supplier: 供應商名稱、別名或 UUID
        lines: `[{"item": "料號或品名", "qty": 10, "unit_price": 25, "description": "..."}]`
        project: 專案名稱或 UUID（可空）
        expected_date: 預計交期 YYYY-MM-DD
        notes: 備註
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("create_purchase_order", ctos_user_id)
    if guard:
        return guard
    if not lines:
        return _error("採購單至少要一個行項")
    try:
        supplier_id = await _party_id_from(None, supplier, role="supplier")
        resolved_lines = []
        for line in lines:
            item_id = await _item_id_from(line.get("item_id"), line.get("item"))
            resolved_lines.append(
                {
                    "item_id": item_id,
                    "qty": Decimal(str(line["qty"])),
                    "unit_price": (
                        Decimal(str(line["unit_price"]))
                        if line.get("unit_price") is not None
                        else None
                    ),
                    "description": line.get("description"),
                }
            )
        project_id = await _resolve_project_id(project)
        row = await purchasing_service.create_purchase_order(
            {
                "supplier_id": supplier_id,
                "lines": resolved_lines,
                "project_id": project_id,
                "expected_date": purchasing_service.normalize_extracted_date(
                    expected_date
                ),
                "notes": notes,
            },
            actor_user_id=ctos_user_id,
            via="mcp",
        )
    except Exception as e:
        return _fail(e)
    return {
        "ok": True,
        "po_id": str(row["id"]),
        "po_no": row["po_no"],
        "status": row["status"],
        "audit_id": str(row["audit_id"]),
    }


async def _resolve_project_id(project: str | None) -> UUID | None:
    """專案吃名稱或 UUID；名稱查 projects 表（同名多筆時要求用 UUID）"""
    if not project:
        return None
    try:
        return UUID(project)
    except ValueError:
        pass
    from ...database import get_connection

    async with get_connection() as conn:
        rows = await conn.fetch(
            r"SELECT id, name, status FROM projects "
            r"WHERE name ILIKE $1 ESCAPE '\' LIMIT 4",
            erp_core.like_pattern(project),
        )
    if not rows:
        raise erp_core.NotFoundError("專案", project)
    if len(rows) > 1:
        raise erp_core.AmbiguousError("專案", project, [dict(r) for r in rows])
    return rows[0]["id"]


@mcp.tool()
async def get_purchase_order(
    po: str,
    ctos_user_id: int | None = None,
) -> dict:
    """取得採購單明細（行項的 `id` 就是收貨要用的 line_id）

    Args:
        po: 單號（PO-YYYYMM-NNN）或 UUID
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("get_purchase_order", ctos_user_id)
    if guard:
        return guard
    try:
        detail = await _load_po(po)
    except Exception as e:
        return _fail(e)
    if detail is None:
        return {"ok": False, "not_found": True, "error": f"找不到採購單：{po}"}
    return {"ok": True, "purchase_order": _clean(detail)}


async def _load_po(po: str) -> dict | None:
    """`po` 可以是 UUID 或單號；try 只包 UUID 解析，不要吞掉 service 的錯"""
    try:
        po_id = UUID(po)
    except ValueError:
        po_id = None
    if po_id is not None:
        return await purchasing_service.get_purchase_order(po_id=po_id)
    return await purchasing_service.get_purchase_order(po_no=po)


@mcp.tool()
async def list_purchase_orders(
    supplier: str | None = None,
    status: str | None = None,
    project: str | None = None,
    since: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """查採購單清單

    Args:
        supplier: 供應商名稱或 UUID
        status: draft / ordered / partial / received / cancelled
        project: 專案名稱或 UUID
        since: 起始日期 YYYY-MM-DD（比對訂購日）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("list_purchase_orders", ctos_user_id)
    if guard:
        return guard
    try:
        supplier_id = (
            await _party_id_from(None, supplier, role="supplier") if supplier else None
        )
        project_id = await _resolve_project_id(project)
        result = await purchasing_service.list_purchase_orders(
            supplier_id=supplier_id,
            status=status,
            project_id=project_id,
            since=purchasing_service.normalize_extracted_date(since),
        )
    except Exception as e:
        return _fail(e)
    return {"ok": True, "total": result["total"], "items": _clean(result["items"])}


@mcp.tool()
async def receive_purchase_order(
    po: str,
    lines: list[dict] | None = None,
    all: bool = False,
    warehouse: str | None = None,
    note: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """採購收貨入庫（更新已收量、寫庫存異動、更新單頭狀態）

    Args:
        po: 單號或 UUID
        lines: `[{"line_id": "...", "qty": 5}]`，或用 `[{"item": "料號", "qty": 5}]`
            （同一張單同一物料有兩行時會回候選要你指定 line_id）；要全收就用 all=True
        all: 收下所有行項的未收數量
        warehouse: 入庫倉（代碼、名稱或 UUID）；只有一個倉時可省略
        note: 備註
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("receive_purchase_order", ctos_user_id)
    if guard:
        return guard
    try:
        detail = await _load_po(po)
        if detail is None:
            return {"ok": False, "not_found": True, "error": f"找不到採購單：{po}"}
        resolved = []
        for line in lines or []:
            entry: dict[str, Any] = {"qty": Decimal(str(line["qty"]))}
            if line.get("line_id"):
                entry["line_id"] = UUID(str(line["line_id"]))
            else:
                entry["item_id"] = await _item_id_from(
                    line.get("item_id"), line.get("item")
                )
            resolved.append(entry)
        warehouse_id = await _warehouse_id_from(warehouse)
        result = await purchasing_service.receive_purchase_order(
            detail["id"],
            lines=resolved,
            receive_all=all,
            warehouse_id=warehouse_id,
            note=note,
            actor_user_id=ctos_user_id,
            via="mcp",
        )
    except Exception as e:
        return _fail(e)
    if result is None:
        return {"ok": False, "not_found": True, "error": f"找不到採購單：{po}"}
    return {
        "ok": True,
        "po_no": detail["po_no"],
        "status": result["status"],
        "received_lines": len(result["movements"]),
        "audit_id": str(result["audit_id"]),
    }


@mcp.tool()
async def cancel_purchase_order(
    po: str,
    reason: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """取消採購單（不是刪除；已收過貨的不能取消）

    Args:
        po: 單號或 UUID
        reason: 取消原因（寫進稽核）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("cancel_purchase_order", ctos_user_id)
    if guard:
        return guard
    try:
        detail = await _load_po(po)
        if detail is None:
            return {"ok": False, "not_found": True, "error": f"找不到採購單：{po}"}
        row = await purchasing_service.cancel_purchase_order(
            detail["id"], reason=reason, actor_user_id=ctos_user_id, via="mcp"
        )
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": f"找不到採購單：{po}"}
    return {
        "ok": True,
        "po_no": row["po_no"],
        "status": row["status"],
        "audit_id": str(row["audit_id"]),
    }


# ============================================================
# 文件擷取（工具不呼叫模型，只整理草稿與比對重複）
# ============================================================


@mcp.tool()
async def extract_party_from_document(
    file_path: str,
    name: str,
    short_name: str | None = None,
    tax_id: str | None = None,
    contact_name: str | None = None,
    contact_title: str | None = None,
    phone: str | None = None,
    mobile: str | None = None,
    email: str | None = None,
    address: str | None = None,
    is_supplier: bool = True,
    is_customer: bool = False,
    notes: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """把你從名片／文件讀出來的欄位整理成往來對象草稿，並比對可能重複的主檔

    這個工具**不會**自己讀檔或呼叫模型：請先用讀圖／convert_pdf_to_images 看內容，
    再把欄位填進來。回傳的 duplicates 不是空的時候，先問人要不要併，不要直接建。

    Args:
        file_path: 來源檔案路徑（只做紀錄）
        name: 公司名稱（必填）
        short_name / tax_id / notes: 簡稱、統編、備註
        contact_name / contact_title / phone / mobile / email: 名片上的聯絡人
        address: 地址
        is_supplier / is_customer: 角色
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("extract_party_from_document", ctos_user_id)
    if guard:
        return guard
    try:
        duplicates = await purchasing_service.match_duplicate_parties(name, tax_id)
    except Exception as e:
        return _fail(e)

    draft: dict[str, Any] = {
        "name": name,
        "short_name": short_name,
        "tax_id": tax_id,
        "is_supplier": is_supplier,
        "is_customer": is_customer,
        "notes": notes,
        "contacts": [],
        "addresses": [],
    }
    if contact_name or phone or mobile or email:
        draft["contacts"].append(
            {
                "name": contact_name or name,
                "title": contact_title,
                "phone": phone,
                "mobile": mobile,
                "email": email,
                "is_primary": True,
            }
        )
    if address:
        draft["addresses"].append({"label": "公司", "address": address, "is_primary": True})

    return {
        "ok": True,
        "source_file": file_path,
        "draft": draft,
        "duplicates": _clean(duplicates),
        "next_step": (
            "有 duplicates 就先問人要沿用哪一筆（或 merge_parties）；"
            "確認是新的再呼叫 create_party 把 draft 送出去。"
        ),
    }


@mcp.tool()
async def extract_purchase_order_from_document(
    file_path: str,
    supplier: str,
    lines: list[dict],
    expected_date: str | None = None,
    project: str | None = None,
    notes: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """把你從詢價／報價單讀出來的欄位整理成採購單草稿，並解析供應商與物料

    工具不讀檔也不呼叫模型。每個行項會回解析結果：`resolved`（唯一命中）、
    `candidates`（要人挑）或 `not_found`（要先 create_item）。

    Args:
        file_path: 來源檔案路徑（只做紀錄）
        supplier: 文件上的供應商名稱
        lines: `[{"item": "品名或料號", "qty": 10, "unit_price": 25}]`
        expected_date: 預計交期 YYYY-MM-DD
        project: 專案名稱（可空）
        notes: 備註
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("extract_purchase_order_from_document", ctos_user_id)
    if guard:
        return guard

    supplier_result: dict[str, Any] = {"query": supplier}
    try:
        hit = await erp_core.resolve_party(supplier, role="supplier")
        supplier_result["resolved"] = _clean(hit)
    except erp_core.AmbiguousError as e:
        supplier_result["candidates"] = _clean(e.candidates)
    except erp_core.NotFoundError:
        supplier_result["not_found"] = True
    except Exception as e:
        return _fail(e)

    resolved_lines = []
    for line in lines or []:
        entry: dict[str, Any] = {
            "query": line.get("item"),
            "qty": line.get("qty"),
            "unit_price": line.get("unit_price"),
            "description": line.get("description"),
        }
        try:
            hit = await erp_core.resolve_item(str(line.get("item") or ""))
            entry["resolved"] = _clean(hit)
        except erp_core.AmbiguousError as e:
            entry["candidates"] = _clean(e.candidates)
        except erp_core.NotFoundError:
            entry["not_found"] = True
        resolved_lines.append(entry)

    ready = "resolved" in supplier_result and all(
        "resolved" in line for line in resolved_lines
    )
    return {
        "ok": True,
        "source_file": file_path,
        "supplier": supplier_result,
        "lines": resolved_lines,
        "expected_date": expected_date,
        "project": project,
        "notes": notes,
        "ready_to_create": ready,
        "next_step": (
            "全部 resolved 就可以呼叫 create_purchase_order；"
            "有 candidates 要問人挑，有 not_found 要先 create_item 或 create_party。"
        ),
    }


# ============================================================
# 摘要（聚合，不是模型生成）
# ============================================================


@mcp.tool()
async def summarize_party(
    party_id: str | None = None,
    name: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """把往來對象的關聯資料（聯絡人、採購、專案、知識庫）聚合成一段上下文

    Args:
        party_id: 往來對象 UUID
        name: 名稱（會做模糊解析）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("summarize_party", ctos_user_id)
    if guard:
        return guard
    try:
        pid = await _party_id_from(party_id, name)
        result = await party_service.summarize_party(pid)
    except Exception as e:
        return _fail(e)
    if result is None:
        return {"ok": False, "not_found": True, "error": "找不到往來對象"}
    return {"ok": True, **_clean(result)}


@mcp.tool()
async def summarize_item(
    item_id: str | None = None,
    code: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """把物料的庫存、供應商、最近異動聚合成一段上下文

    Args:
        item_id: 物料 UUID
        code: 料號或品名（會做模糊解析）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("summarize_item", ctos_user_id)
    if guard:
        return guard
    try:
        iid = await _item_id_from(item_id, code)
        result = await inventory_service.summarize_item(iid)
    except Exception as e:
        return _fail(e)
    if result is None:
        return {"ok": False, "not_found": True, "error": "找不到物料"}
    return {"ok": True, **_clean(result)}
