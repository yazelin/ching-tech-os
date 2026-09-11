"""往來對象服務（parties / party_contacts / party_addresses）

asyncpg raw SQL，資料表見 migration 030。寫入一律包交易，並在同一交易裡寫
`erp_audit`（`erp.audit()`），回傳的 dict 帶 `audit_id` 讓 agent 引用。
軟刪除：`deleted_at` 非空的不進清單、不進解析、明細回 None。
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from ..database import get_connection
from .erp import (
    InvalidOperationError,
    audit,
    build_diff,
    like_pattern,
)

logger = logging.getLogger(__name__)

# 允許建立時寫入的主檔欄位
_PARTY_FIELDS = (
    "name",
    "short_name",
    "aliases",
    "is_supplier",
    "is_customer",
    "tax_id",
    "industry",
    "payment_terms",
    "notes",
    "source_ref",
)

# 允許更新的主檔欄位（與建立相同，id／時間戳不給改）
_PARTY_UPDATE_FIELDS = _PARTY_FIELDS

_CONTACT_FIELDS = ("name", "title", "phone", "mobile", "email", "is_primary", "notes")
_ADDRESS_FIELDS = ("label", "address", "city", "is_primary")


# ============================================================
# 清單
# ============================================================


async def list_parties(
    q: str | None = None,
    role: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """往來對象清單（搜尋名稱／簡稱／別名／統編，可依供應商／客戶篩選）"""
    offset = (max(page, 1) - 1) * page_size
    pattern = like_pattern(q) if q else None
    where = r"""
        WHERE p.deleted_at IS NULL
          AND (
            $1::text IS NULL
            OR ($1 = 'supplier' AND p.is_supplier)
            OR ($1 = 'customer' AND p.is_customer)
          )
          AND (
            $2::text IS NULL
            OR p.name ILIKE $2 ESCAPE '\'
            OR COALESCE(p.short_name, '') ILIKE $2 ESCAPE '\'
            OR COALESCE(p.tax_id, '') ILIKE $2 ESCAPE '\'
            OR EXISTS (
                SELECT 1 FROM unnest(p.aliases) AS a WHERE a ILIKE $2 ESCAPE '\'
            )
          )
    """
    async with get_connection() as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM parties p {where}", role, pattern
        )
        rows = await conn.fetch(
            f"""
            SELECT
                p.id, p.name, p.short_name, p.is_supplier, p.is_customer,
                p.tax_id, p.industry, p.created_at, p.updated_at,
                (
                    SELECT c.name FROM party_contacts c
                    WHERE c.party_id = p.id
                    ORDER BY c.is_primary DESC, c.created_at
                    LIMIT 1
                ) AS primary_contact,
                (
                    SELECT COALESCE(c.phone, c.mobile) FROM party_contacts c
                    WHERE c.party_id = p.id
                    ORDER BY c.is_primary DESC, c.created_at
                    LIMIT 1
                ) AS primary_phone
            FROM parties p
            {where}
            ORDER BY p.updated_at DESC
            LIMIT $3 OFFSET $4
            """,
            role,
            pattern,
            page_size,
            offset,
        )
    return {"items": [dict(r) for r in rows], "total": int(total or 0)}


# ============================================================
# 明細
# ============================================================


async def get_party_detail(party_id: UUID) -> dict[str, Any] | None:
    """明細：主檔＋聯絡人＋地址＋近期採購單＋相關專案＋知識庫條目數"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, short_name, aliases, is_supplier, is_customer,
                   tax_id, industry, payment_terms, notes, source_ref,
                   created_by, created_at, updated_at
            FROM parties
            WHERE id = $1 AND deleted_at IS NULL
            """,
            party_id,
        )
        if row is None:
            return None

        contacts = await conn.fetch(
            """
            SELECT id, party_id, name, title, phone, mobile, email, is_primary,
                   notes, created_at, updated_at
            FROM party_contacts
            WHERE party_id = $1
            ORDER BY is_primary DESC, created_at
            """,
            party_id,
        )
        addresses = await conn.fetch(
            """
            SELECT id, party_id, label, address, city, is_primary,
                   created_at, updated_at
            FROM party_addresses
            WHERE party_id = $1
            ORDER BY is_primary DESC, created_at
            """,
            party_id,
        )
        purchase_orders = await conn.fetch(
            """
            SELECT po.id, po.po_no, po.status, po.order_date, po.expected_date,
                   (
                       SELECT COALESCE(
                           SUM(l.qty * COALESCE(l.unit_price, 0)), 0
                       )
                       FROM purchase_order_lines l WHERE l.po_id = po.id
                   ) AS total_amount
            FROM purchase_orders po
            WHERE po.supplier_id = $1
            ORDER BY po.created_at DESC
            LIMIT 10
            """,
            party_id,
        )
        projects = await conn.fetch(
            """
            SELECT DISTINCT pr.id, pr.name, pr.status
            FROM purchase_orders po
            JOIN projects pr ON pr.id = po.project_id
            WHERE po.supplier_id = $1
            ORDER BY pr.name
            """,
            party_id,
        )

    detail = dict(row)
    detail["contacts"] = [dict(r) for r in contacts]
    detail["addresses"] = [dict(r) for r in addresses]
    detail["purchase_orders"] = [dict(r) for r in purchase_orders]
    detail["projects"] = [dict(r) for r in projects]
    detail["knowledge_count"] = count_party_knowledge(detail["name"])
    return detail


def count_party_knowledge(name: str) -> int:
    """知識庫提到這家公司的條目數（走既有的全文檢索，不另開 index）"""
    try:
        from .knowledge import search_knowledge

        return search_knowledge(query=name).total
    except Exception as e:  # pragma: no cover - 知識庫不可用時不擋明細
        logger.warning("計算往來對象知識條目數失敗: %s", e)
        return 0


# ============================================================
# 建立／更新／軟刪除
# ============================================================


def _pick(data: dict, fields: tuple[str, ...]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in fields}


async def create_party(
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any]:
    """建立往來對象（可一次帶聯絡人與地址），回傳主檔＋audit_id"""
    async with get_connection() as conn, conn.transaction():
        row = await conn.fetchrow(
            """
            INSERT INTO parties
                (name, short_name, aliases, is_supplier, is_customer, tax_id,
                 industry, payment_terms, notes, source_ref, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            data["name"],
            data.get("short_name"),
            list(data.get("aliases") or []),
            bool(data.get("is_supplier", False)),
            bool(data.get("is_customer", False)),
            data.get("tax_id"),
            data.get("industry"),
            data.get("payment_terms"),
            data.get("notes"),
            data.get("source_ref"),
            actor_user_id,
        )
        for contact in data.get("contacts") or []:
            await _insert_contact(conn, row["id"], contact, actor_user_id)
        for address in data.get("addresses") or []:
            await _insert_address(conn, row["id"], address, actor_user_id)

        audit_id = await audit(
            conn,
            "party",
            row["id"],
            "create",
            build_diff(None, _pick(dict(row), _PARTY_FIELDS)),
            actor_user_id,
            via,
            agent_name,
        )

    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def update_party(
    party_id: UUID,
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """更新主檔（只更新有給的欄位），回傳主檔＋audit_id；找不到回 None"""
    fields = _pick(data, _PARTY_UPDATE_FIELDS)
    async with get_connection() as conn, conn.transaction():
        before = await conn.fetchrow(
            "SELECT * FROM parties WHERE id = $1 AND deleted_at IS NULL", party_id
        )
        if before is None:
            return None
        if fields:
            names = list(fields.keys())
            assignments = ", ".join(f"{n} = ${i + 2}" for i, n in enumerate(names))
            row = await conn.fetchrow(
                f"""
                UPDATE parties
                SET {assignments}, updated_at = NOW()
                WHERE id = $1 AND deleted_at IS NULL
                RETURNING *
                """,
                party_id,
                *[fields[n] for n in names],
            )
        else:
            row = before
        audit_id = await audit(
            conn,
            "party",
            party_id,
            "update",
            build_diff(_pick(dict(before), _PARTY_FIELDS), _pick(dict(row), _PARTY_FIELDS)),
            actor_user_id,
            via,
            agent_name,
        )

    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def delete_party(
    party_id: UUID,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> UUID | None:
    """軟刪除；已刪或不存在回 None"""
    async with get_connection() as conn, conn.transaction():
        row = await conn.fetchrow(
            """
            UPDATE parties
            SET deleted_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id, name
            """,
            party_id,
        )
        if row is None:
            return None
        return await audit(
            conn,
            "party",
            party_id,
            "delete",
            {"name": row["name"]},
            actor_user_id,
            via,
            agent_name,
        )


# ============================================================
# 聯絡人與地址
# ============================================================


async def _insert_contact(conn, party_id: UUID, data: dict, actor_user_id: int | None):
    """同一家只留一個主要聯絡人：設 is_primary 時先把其他的取消"""
    if data.get("is_primary"):
        await conn.execute(
            "UPDATE party_contacts SET is_primary = false WHERE party_id = $1",
            party_id,
        )
    return await conn.fetchrow(
        """
        INSERT INTO party_contacts
            (party_id, name, title, phone, mobile, email, is_primary, notes,
             created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
        """,
        party_id,
        data["name"],
        data.get("title"),
        data.get("phone"),
        data.get("mobile"),
        data.get("email"),
        bool(data.get("is_primary", False)),
        data.get("notes"),
        actor_user_id,
    )


async def _insert_address(conn, party_id: UUID, data: dict, actor_user_id: int | None):
    if data.get("is_primary"):
        await conn.execute(
            "UPDATE party_addresses SET is_primary = false WHERE party_id = $1",
            party_id,
        )
    return await conn.fetchrow(
        """
        INSERT INTO party_addresses
            (party_id, label, address, city, is_primary, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        party_id,
        data.get("label"),
        data["address"],
        data.get("city"),
        bool(data.get("is_primary", False)),
        actor_user_id,
    )


async def add_contact(
    party_id: UUID,
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """新增聯絡人；往來對象不存在（或已軟刪除）回 None"""
    async with get_connection() as conn, conn.transaction():
        if not await _party_alive(conn, party_id):
            return None
        row = await _insert_contact(conn, party_id, _pick(data, _CONTACT_FIELDS), actor_user_id)
        audit_id = await audit(
            conn,
            "party_contact",
            row["id"],
            "create",
            {"party_id": str(party_id), **build_diff(None, _pick(dict(row), _CONTACT_FIELDS))},
            actor_user_id,
            via,
            agent_name,
        )
    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def add_address(
    party_id: UUID,
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """新增地址；往來對象不存在（或已軟刪除）回 None"""
    async with get_connection() as conn, conn.transaction():
        if not await _party_alive(conn, party_id):
            return None
        row = await _insert_address(conn, party_id, _pick(data, _ADDRESS_FIELDS), actor_user_id)
        audit_id = await audit(
            conn,
            "party_address",
            row["id"],
            "create",
            {"party_id": str(party_id), **build_diff(None, _pick(dict(row), _ADDRESS_FIELDS))},
            actor_user_id,
            via,
            agent_name,
        )
    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def _party_alive(conn, party_id: UUID) -> bool:
    found = await conn.fetchval(
        "SELECT 1 FROM parties WHERE id = $1 AND deleted_at IS NULL", party_id
    )
    return found is not None


# ============================================================
# 合併重複主檔
# ============================================================


async def merge_parties(
    keep_id: UUID,
    drop_id: UUID,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any]:
    """把 drop 的聯絡人、地址、採購單、預設供應商掛到 keep，drop 軟刪除

    drop 的名稱與別名併進 keep 的 aliases，之後用舊名字也找得到。

    Raises:
        InvalidOperationError: keep 與 drop 相同，或其中一筆不存在
    """
    if keep_id == drop_id:
        raise InvalidOperationError("不能把同一筆往來對象合併到自己")

    async with get_connection() as conn, conn.transaction():
        keep = await conn.fetchrow(
            "SELECT * FROM parties WHERE id = $1 AND deleted_at IS NULL", keep_id
        )
        drop = await conn.fetchrow(
            "SELECT * FROM parties WHERE id = $1 AND deleted_at IS NULL", drop_id
        )
        if keep is None or drop is None:
            raise InvalidOperationError("要合併的往來對象不存在或已刪除")

        await conn.execute(
            "UPDATE party_contacts SET party_id = $1 WHERE party_id = $2",
            keep_id,
            drop_id,
        )
        await conn.execute(
            "UPDATE party_addresses SET party_id = $1 WHERE party_id = $2",
            keep_id,
            drop_id,
        )
        await conn.execute(
            "UPDATE purchase_orders SET supplier_id = $1 WHERE supplier_id = $2",
            keep_id,
            drop_id,
        )
        await conn.execute(
            """
            UPDATE items SET default_supplier_id = $1 WHERE default_supplier_id = $2
            """,
            keep_id,
            drop_id,
        )

        merged_aliases = _merge_aliases(keep, drop)
        row = await conn.fetchrow(
            """
            UPDATE parties
            SET aliases = $2,
                is_supplier = parties.is_supplier OR $3,
                is_customer = parties.is_customer OR $4,
                tax_id = COALESCE(parties.tax_id, $5),
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            keep_id,
            merged_aliases,
            drop["is_supplier"],
            drop["is_customer"],
            drop["tax_id"],
        )
        await conn.execute(
            """
            UPDATE parties
            SET deleted_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            drop_id,
        )
        audit_id = await audit(
            conn,
            "party",
            keep_id,
            "merge",
            {
                "kept": {"id": str(keep_id), "name": keep["name"]},
                "dropped": {"id": str(drop_id), "name": drop["name"]},
                "aliases": merged_aliases,
            },
            actor_user_id,
            via,
            agent_name,
        )

    result = dict(row)
    result["audit_id"] = audit_id
    return result


def _merge_aliases(keep, drop) -> list[str]:
    """keep 的別名 ＋ drop 的名稱／簡稱／別名，去重且保持順序"""
    merged: list[str] = []
    for value in [
        *(keep["aliases"] or []),
        drop["name"],
        drop["short_name"],
        *(drop["aliases"] or []),
    ]:
        if value and value != keep["name"] and value not in merged:
            merged.append(value)
    return merged


# ============================================================
# 摘要（聚合，不是模型生成）
# ============================================================


async def summarize_party(party_id: UUID) -> dict[str, Any] | None:
    """把往來對象的關聯資料組成一段給 agent 的上下文"""
    detail = await get_party_detail(party_id)
    if detail is None:
        return None

    roles = []
    if detail["is_supplier"]:
        roles.append("供應商")
    if detail["is_customer"]:
        roles.append("客戶")

    lines = [
        f"【{detail['name']}】{'／'.join(roles) or '未標角色'}",
    ]
    if detail.get("tax_id"):
        lines.append(f"統編：{detail['tax_id']}")
    if detail.get("payment_terms"):
        lines.append(f"付款條件：{detail['payment_terms']}")
    if detail["contacts"]:
        primary = detail["contacts"][0]
        phone = primary.get("phone") or primary.get("mobile") or "無電話"
        lines.append(f"主要聯絡人：{primary['name']}（{phone}）")
    if detail["addresses"]:
        lines.append(f"地址：{detail['addresses'][0]['address']}")
    if detail["purchase_orders"]:
        recent = "、".join(
            f"{po['po_no']}（{po['status']}）" for po in detail["purchase_orders"][:5]
        )
        lines.append(f"近期採購單：{recent}")
    else:
        lines.append("近期採購單：無")
    if detail["projects"]:
        lines.append(
            "相關專案：" + "、".join(p["name"] for p in detail["projects"][:5])
        )
    lines.append(f"知識庫條目數：{detail['knowledge_count']}")

    return {
        "party_id": detail["id"],
        "name": detail["name"],
        "summary": "\n".join(lines),
        "contact_count": len(detail["contacts"]),
        "purchase_order_count": len(detail["purchase_orders"]),
        "project_count": len(detail["projects"]),
        "knowledge_count": detail["knowledge_count"],
    }
