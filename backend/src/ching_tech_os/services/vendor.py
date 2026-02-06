"""廠商管理服務"""

from uuid import UUID

from ..database import get_connection
from ..models.vendor import (
    VendorCreate,
    VendorUpdate,
    VendorResponse,
    VendorListItem,
    VendorListResponse,
)


from .errors import ServiceError


class VendorError(ServiceError):
    """廠商操作錯誤"""

    def __init__(self, message: str = "廠商操作錯誤"):
        super().__init__(message, "VENDOR_ERROR", 500)


class VendorNotFoundError(VendorError):
    """廠商不存在"""

    def __init__(self, message: str = "廠商不存在"):
        super().__init__(message)
        self.code = "NOT_FOUND"
        self.status_code = 404


class VendorDuplicateError(VendorError):
    """廠商編號重複"""

    def __init__(self, message: str = "廠商編號重複"):
        super().__init__(message)
        self.code = "CONFLICT"
        self.status_code = 409


async def list_vendors(
    query: str | None = None,
    active_only: bool = True,
    limit: int = 100,
) -> VendorListResponse:
    """列出廠商"""
    async with get_connection() as conn:
        sql = """
            SELECT id, erp_code, name, short_name, contact_person, phone, is_active
            FROM vendors
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if active_only:
            sql += " AND is_active = true"

        if query:
            sql += f" AND (name ILIKE ${param_idx} OR short_name ILIKE ${param_idx} OR erp_code ILIKE ${param_idx})"
            params.append(f"%{query}%")
            param_idx += 1

        sql += f" ORDER BY name LIMIT ${param_idx}"
        params.append(limit)

        rows = await conn.fetch(sql, *params)

        items = [
            VendorListItem(
                id=row["id"],
                erp_code=row["erp_code"],
                name=row["name"],
                short_name=row["short_name"],
                contact_person=row["contact_person"],
                phone=row["phone"],
                is_active=row["is_active"],
            )
            for row in rows
        ]

        # 取得總數
        count_sql = "SELECT COUNT(*) FROM vendors WHERE 1=1"
        count_params = []
        if active_only:
            count_sql += " AND is_active = true"
        if query:
            count_sql += " AND (name ILIKE $1 OR short_name ILIKE $1 OR erp_code ILIKE $1)"
            count_params.append(f"%{query}%")
        total = await conn.fetchval(count_sql, *count_params) or 0

        return VendorListResponse(items=items, total=total)


async def get_vendor(
    vendor_id: UUID,
) -> VendorResponse:
    """取得廠商詳情"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM vendors WHERE id = $1",
            vendor_id,
        )
        if not row:
            raise VendorNotFoundError(f"廠商 {vendor_id} 不存在")
        return VendorResponse(**dict(row))


async def get_vendor_by_erp_code(
    erp_code: str,
) -> VendorResponse | None:
    """依 ERP 編號取得廠商"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM vendors WHERE erp_code = $1",
            erp_code,
        )
        if not row:
            return None
        return VendorResponse(**dict(row))


async def create_vendor(
    data: VendorCreate,
    created_by: str | None = None,
) -> VendorResponse:
    """新增廠商"""
    async with get_connection() as conn:
        # 檢查 ERP 編號是否重複
        if data.erp_code:
            exists = await conn.fetchval(
                "SELECT 1 FROM vendors WHERE erp_code = $1",
                data.erp_code,
            )
            if exists:
                raise VendorDuplicateError(f"ERP 編號 {data.erp_code} 已存在")

        row = await conn.fetchrow(
            """
            INSERT INTO vendors (erp_code, name, short_name, contact_person, phone, fax, email, address, tax_id, payment_terms, notes, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            data.erp_code,
            data.name,
            data.short_name,
            data.contact_person,
            data.phone,
            data.fax,
            data.email,
            data.address,
            data.tax_id,
            data.payment_terms,
            data.notes,
            created_by,
        )
        return VendorResponse(**dict(row))


async def update_vendor(
    vendor_id: UUID,
    data: VendorUpdate,
) -> VendorResponse:
    """更新廠商"""
    async with get_connection() as conn:
        # 檢查廠商是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM vendors WHERE id = $1",
            vendor_id,
        )
        if not exists:
            raise VendorNotFoundError(f"廠商 {vendor_id} 不存在")

        # 檢查 ERP 編號是否重複（排除自己）
        if data.erp_code is not None:
            dup = await conn.fetchval(
                "SELECT 1 FROM vendors WHERE erp_code = $1 AND id != $2",
                data.erp_code,
                vendor_id,
            )
            if dup:
                raise VendorDuplicateError(f"ERP 編號 {data.erp_code} 已存在")

        # 動態建立更新語句
        updates = []
        params = []
        param_idx = 1

        for field in ["erp_code", "name", "short_name", "contact_person", "phone", "fax", "email", "address", "tax_id", "payment_terms", "notes", "is_active"]:
            value = getattr(data, field, None)
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            row = await conn.fetchrow(
                "SELECT * FROM vendors WHERE id = $1",
                vendor_id,
            )
            return VendorResponse(**dict(row))

        # updated_at 由觸發器自動更新
        params.append(vendor_id)
        sql = f"UPDATE vendors SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(sql, *params)
        return VendorResponse(**dict(row))


async def deactivate_vendor(
    vendor_id: UUID,
) -> VendorResponse:
    """停用廠商（軟刪除）"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "UPDATE vendors SET is_active = false WHERE id = $1 RETURNING *",
            vendor_id,
        )
        if not row:
            raise VendorNotFoundError(f"廠商 {vendor_id} 不存在")
        return VendorResponse(**dict(row))


async def activate_vendor(
    vendor_id: UUID,
) -> VendorResponse:
    """啟用廠商"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "UPDATE vendors SET is_active = true WHERE id = $1 RETURNING *",
            vendor_id,
        )
        if not row:
            raise VendorNotFoundError(f"廠商 {vendor_id} 不存在")
        return VendorResponse(**dict(row))
