#!/usr/bin/env python3
"""
物料資料遷移腳本
將 CTOS inventory_items 資料遷移至 ERPNext Item
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
import httpx

ERPNEXT_URL = os.environ.get("ERPNEXT_URL", "http://ct.erp")
ERPNEXT_API_KEY = os.environ["ERPNEXT_API_KEY"]
ERPNEXT_API_SECRET = os.environ["ERPNEXT_API_SECRET"]
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://ching_tech:ching_tech@localhost:5432/ching_tech_os")

# 預設公司和倉庫（需根據實際 ERPNext 設定調整）
DEFAULT_COMPANY = "擎添工業有限公司"
DEFAULT_WAREHOUSE = "Stores - 擎添工業"

# UOM 對應表（CTOS 單位 → ERPNext UOM）
UOM_MAPPING = {
    "個": "Nos",
    "件": "Nos",
    "組": "Set",
    "套": "Set",
    "台": "Unit",
    "支": "Nos",
    "片": "Nos",
    "張": "Nos",
    "包": "Box",
    "箱": "Box",
    "盒": "Box",
    "條": "Nos",
    "公斤": "Kg",
    "kg": "Kg",
    "公升": "Litre",
    "L": "Litre",
    "公尺": "Meter",
    "m": "Meter",
    None: "Nos",
    "": "Nos",
}

# ID 映射表
id_mapping = {
    "items": {},
}


def get_erpnext_uom(ctos_unit: str | None) -> str:
    """轉換 CTOS 單位到 ERPNext UOM"""
    if not ctos_unit:
        return "Nos"
    return UOM_MAPPING.get(ctos_unit.strip(), "Nos")


async def get_ctos_items(conn: asyncpg.Connection) -> list[dict]:
    """從 CTOS 讀取所有物料資料"""
    rows = await conn.fetch("""
        SELECT i.id, i.name, i.model, i.specification, i.unit, i.category,
               i.default_vendor, i.default_vendor_id, i.min_stock, i.current_stock,
               i.storage_location, i.notes,
               v.name as vendor_name
        FROM inventory_items i
        LEFT JOIN vendors v ON i.default_vendor_id = v.id
        ORDER BY i.name
    """)
    return [dict(row) for row in rows]


async def ensure_item_group(client: httpx.AsyncClient, category: str | None, dry_run: bool = False) -> str:
    """確保 Item Group 存在，不存在則建立"""
    if not category or category.strip() == "":
        return "All Item Groups"

    category = category.strip()

    if dry_run:
        return category

    # 檢查是否已存在
    try:
        resp = await client.get(
            f"{ERPNEXT_URL}/api/resource/Item Group/{category}",
        )
        if resp.status_code == 200:
            return category
    except Exception:
        pass

    # 建立新的 Item Group
    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Item Group",
            json={"data": json.dumps({
                "item_group_name": category,
                "parent_item_group": "All Item Groups",
            })},
        )
        resp.raise_for_status()
        print(f"    + 建立 Item Group: {category}")
        return category
    except Exception as e:
        print(f"    ⚠ Item Group 建立失敗: {category}, 使用 All Item Groups")
        return "All Item Groups"


async def create_erpnext_item(
    client: httpx.AsyncClient,
    item: dict,
    vendor_mapping: dict,
    dry_run: bool = False
) -> str | None:
    """在 ERPNext 建立 Item"""
    # 決定 item_code（優先用 model，否則用 name）
    item_code = item.get("model") or item["name"]
    # 避免重複，加上前綴
    item_code = f"CTOS-{item_code}"

    # 確保 Item Group 存在
    item_group = await ensure_item_group(client, item.get("category"), dry_run)

    item_data = {
        "item_code": item_code,
        "item_name": item["name"],
        "item_group": item_group,
        "stock_uom": get_erpnext_uom(item.get("unit")),
        "is_stock_item": 1,
        "description": item.get("specification") or item["name"],
    }

    # 安全庫存
    if item.get("min_stock"):
        item_data["safety_stock"] = float(item["min_stock"])

    # 預設倉庫
    item_data["item_defaults"] = [{
        "company": DEFAULT_COMPANY,
        "default_warehouse": DEFAULT_WAREHOUSE,
    }]

    # 預設供應商（如果有映射）
    if item.get("default_vendor_id"):
        vendor_id = str(item["default_vendor_id"])
        if vendor_id in vendor_mapping:
            item_data["item_defaults"][0]["default_supplier"] = vendor_mapping[vendor_id]

    if dry_run:
        print(f"  [DRY-RUN] 將建立 Item: {item_code}")
        print(f"    名稱: {item['name']}")
        print(f"    單位: {item_data['stock_uom']}")
        print(f"    類別: {item_group}")
        if item.get("current_stock"):
            print(f"    目前庫存: {item['current_stock']}（需建立期初 Stock Entry）")
        return f"DRY_RUN_{item_code}"

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Item",
            json={"data": json.dumps(item_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        created_item_code = result.get("data", {}).get("name")
        print(f"  ✓ 建立 Item: {created_item_code}")
        return created_item_code
    except httpx.HTTPStatusError as e:
        print(f"  ✗ 建立 Item 失敗: {item['name']}")
        print(f"    錯誤: {e.response.text[:200]}")
        return None


async def migrate_items(vendor_mapping: dict = None, dry_run: bool = False) -> dict:
    """執行物料遷移"""
    print("=" * 50)
    print("物料遷移 (inventory_items → Item)")
    print("=" * 50)

    if vendor_mapping is None:
        vendor_mapping = {}

    # 連接 CTOS 資料庫
    conn = await asyncpg.connect(DATABASE_URL)

    # 建立 ERPNext client
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # 讀取 CTOS 物料
        items = await get_ctos_items(conn)
        print(f"\n找到 {len(items)} 筆物料資料\n")

        success_count = 0
        items_with_stock = []

        for item in items:
            print(f"\n處理: {item['name']} (ID: {item['id']})")

            # 建立 Item
            item_code = await create_erpnext_item(client, item, vendor_mapping, dry_run)

            if item_code:
                # 記錄 ID 映射
                id_mapping["items"][str(item["id"])] = item_code
                success_count += 1

                # 記錄需要建立期初庫存的物料
                if item.get("current_stock") and float(item["current_stock"]) > 0:
                    items_with_stock.append({
                        "item_code": item_code,
                        "qty": float(item["current_stock"]),
                        "name": item["name"],
                    })

        print(f"\n完成：{success_count}/{len(items)} 筆")

        if items_with_stock:
            print(f"\n⚠ 有 {len(items_with_stock)} 筆物料需要建立期初庫存")
            # 保存需要建立期初庫存的清單
            id_mapping["items_with_stock"] = items_with_stock

    await conn.close()
    return id_mapping


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="遷移 CTOS 物料到 ERPNext")
    parser.add_argument("--dry-run", action="store_true", help="只顯示將執行的操作，不實際執行")
    parser.add_argument("--vendor-mapping", type=str, help="廠商映射表 JSON 檔案路徑")
    args = parser.parse_args()

    vendor_mapping = {}
    if args.vendor_mapping:
        with open(args.vendor_mapping) as f:
            mapping_data = json.load(f)
            vendor_mapping = mapping_data.get("vendors", {})

    result = asyncio.run(migrate_items(vendor_mapping=vendor_mapping, dry_run=args.dry_run))

    if not args.dry_run:
        print("\nID 映射表:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
