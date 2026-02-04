#!/usr/bin/env python3
"""
廠商資料遷移腳本
將 CTOS vendors 資料遷移至 ERPNext Supplier
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
import httpx

# 載入環境變數
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

ERPNEXT_URL = os.environ.get("ERPNEXT_URL", "http://ct.erp")
ERPNEXT_API_KEY = os.environ["ERPNEXT_API_KEY"]
ERPNEXT_API_SECRET = os.environ["ERPNEXT_API_SECRET"]
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://ching_tech:ching_tech@localhost:5432/ching_tech_os")

# ID 映射表
id_mapping = {
    "vendors": {},
}


async def get_ctos_vendors(conn: asyncpg.Connection) -> list[dict]:
    """從 CTOS 讀取所有廠商資料"""
    rows = await conn.fetch("""
        SELECT id, erp_code, name, short_name, contact_person,
               phone, fax, email, address, tax_id, payment_terms, notes
        FROM vendors
        WHERE is_active = true
        ORDER BY name
    """)
    return [dict(row) for row in rows]


async def create_erpnext_supplier(client: httpx.AsyncClient, vendor: dict, dry_run: bool = False) -> str | None:
    """在 ERPNext 建立 Supplier"""
    supplier_data = {
        "supplier_name": vendor["name"],
        "supplier_group": "All Supplier Groups",
        "supplier_type": "Company",
        "country": "Taiwan",
    }

    # 如果有統編，加入 tax_id
    if vendor.get("tax_id"):
        supplier_data["tax_id"] = vendor["tax_id"]

    # 付款條件
    if vendor.get("payment_terms"):
        supplier_data["payment_terms_template"] = vendor["payment_terms"]

    if dry_run:
        print(f"  [DRY-RUN] 將建立 Supplier: {vendor['name']}")
        print(f"    資料: {json.dumps(supplier_data, ensure_ascii=False, indent=2)}")
        return f"DRY_RUN_{vendor['name']}"

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Supplier",
            json={"data": json.dumps(supplier_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        supplier_name = result.get("data", {}).get("name")
        print(f"  ✓ 建立 Supplier: {supplier_name}")
        return supplier_name
    except httpx.HTTPStatusError as e:
        print(f"  ✗ 建立 Supplier 失敗: {vendor['name']}")
        print(f"    錯誤: {e.response.text}")
        return None


async def create_erpnext_contact(
    client: httpx.AsyncClient,
    vendor: dict,
    supplier_name: str,
    dry_run: bool = False
) -> None:
    """在 ERPNext 建立 Contact（如果有聯絡人資訊）"""
    if not any([vendor.get("contact_person"), vendor.get("phone"), vendor.get("email")]):
        return

    contact_data = {
        "first_name": vendor.get("contact_person") or vendor["name"],
        "links": [{
            "link_doctype": "Supplier",
            "link_name": supplier_name,
        }],
    }

    if vendor.get("email"):
        contact_data["email_ids"] = [{
            "email_id": vendor["email"],
            "is_primary": 1,
        }]

    if vendor.get("phone"):
        contact_data["phone_nos"] = [{
            "phone": vendor["phone"],
            "is_primary_phone": 1,
        }]

    if dry_run:
        print(f"  [DRY-RUN] 將建立 Contact: {contact_data['first_name']}")
        return

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Contact",
            json={"data": json.dumps(contact_data)},
        )
        resp.raise_for_status()
        print(f"    + Contact: {contact_data['first_name']}")
    except httpx.HTTPStatusError as e:
        print(f"    ⚠ Contact 建立失敗: {e.response.text[:100]}")


async def migrate_vendors(dry_run: bool = False) -> dict:
    """執行廠商遷移"""
    print("=" * 50)
    print("廠商遷移 (vendors → Supplier)")
    print("=" * 50)

    # 連接 CTOS 資料庫
    conn = await asyncpg.connect(DATABASE_URL)

    # 建立 ERPNext client
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # 讀取 CTOS 廠商
        vendors = await get_ctos_vendors(conn)
        print(f"\n找到 {len(vendors)} 筆廠商資料\n")

        success_count = 0
        for vendor in vendors:
            print(f"\n處理: {vendor['name']} (ID: {vendor['id']})")

            # 建立 Supplier
            supplier_name = await create_erpnext_supplier(client, vendor, dry_run)

            if supplier_name:
                # 記錄 ID 映射
                id_mapping["vendors"][str(vendor["id"])] = supplier_name

                # 建立 Contact
                await create_erpnext_contact(client, vendor, supplier_name, dry_run)

                success_count += 1

        print(f"\n完成：{success_count}/{len(vendors)} 筆")

    await conn.close()
    return id_mapping


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="遷移 CTOS 廠商到 ERPNext")
    parser.add_argument("--dry-run", action="store_true", help="只顯示將執行的操作，不實際執行")
    args = parser.parse_args()

    result = asyncio.run(migrate_vendors(dry_run=args.dry_run))

    if not args.dry_run:
        # 輸出映射表
        print("\nID 映射表:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
