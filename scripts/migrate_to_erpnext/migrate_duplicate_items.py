#!/usr/bin/env python3
"""
遷移重複型號的物料（加後綴）
"""
import asyncio
import json
import os

import asyncpg
import httpx

ERPNEXT_URL = os.environ.get("ERPNEXT_URL", "http://ct.erp")
ERPNEXT_API_KEY = os.environ["ERPNEXT_API_KEY"]
ERPNEXT_API_SECRET = os.environ["ERPNEXT_API_SECRET"]
DATABASE_URL = os.environ.get("DATABASE_URL")

MAPPING_FILE = os.path.join(os.path.dirname(__file__), "id_mapping.json")

DEFAULT_COMPANY = "擎添工業有限公司"
DEFAULT_WAREHOUSE = "Stores - 擎添工業"

# UOM 對應表
UOM_MAPPING = {
    "個": "Nos", "件": "Nos", "組": "Set", "套": "Set",
    "台": "Unit", "支": "Nos", "片": "Nos", "張": "Nos",
    "包": "Box", "箱": "Box", "盒": "Box", "條": "Nos",
    "公斤": "Kg", "kg": "Kg", "公升": "Litre", "L": "Litre",
    "公尺": "Meter", "m": "Meter", None: "Nos", "": "Nos",
}


def get_erpnext_uom(ctos_unit: str | None) -> str:
    if not ctos_unit:
        return "Nos"
    return UOM_MAPPING.get(ctos_unit.strip(), "Nos")


async def get_existing_item_codes(client: httpx.AsyncClient) -> set[str]:
    """取得 ERPNext 已存在的 Item Code"""
    try:
        resp = await client.get(
            f"{ERPNEXT_URL}/api/resource/Item",
            params={
                "filters": json.dumps([["item_code", "like", "CTOS-%"]]),
                "fields": json.dumps(["item_code"]),
                "limit_page_length": 0,
            }
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return {item["item_code"] for item in data}
    except Exception as e:
        print(f"取得 Item 列表失敗: {e}")
        return set()


async def ensure_item_group(client: httpx.AsyncClient, category: str | None) -> str:
    """確保 Item Group 存在"""
    if not category or category.strip() == "":
        return "All Item Groups"

    category = category.strip()

    # 檢查是否存在
    try:
        resp = await client.get(f"{ERPNEXT_URL}/api/resource/Item Group/{category}")
        if resp.status_code == 200:
            return category
    except Exception:
        pass

    # 建立
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
    except Exception:
        return "All Item Groups"


async def create_item_with_suffix(
    client: httpx.AsyncClient,
    item: dict,
    suffix: int,
    existing_codes: set[str],
) -> str | None:
    """建立帶後綴的 Item"""
    base_code = item.get("model") or item["name"]
    item_code = f"CTOS-{base_code}-{suffix}"

    # 確保不重複
    while item_code in existing_codes:
        suffix += 1
        item_code = f"CTOS-{base_code}-{suffix}"

    item_group = await ensure_item_group(client, item.get("category"))

    item_data = {
        "item_code": item_code,
        "item_name": item["name"],
        "item_group": item_group,
        "stock_uom": get_erpnext_uom(item.get("unit")),
        "is_stock_item": 1,
        "description": item.get("specification") or item["name"],
    }

    if item.get("min_stock"):
        item_data["safety_stock"] = float(item["min_stock"])

    item_data["item_defaults"] = [{
        "company": DEFAULT_COMPANY,
        "default_warehouse": DEFAULT_WAREHOUSE,
    }]

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Item",
            json={"data": json.dumps(item_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        created_code = result.get("data", {}).get("name")
        print(f"  ✓ 建立 Item: {created_code} ({item['name']})")
        return created_code
    except httpx.HTTPStatusError as e:
        print(f"  ✗ 建立失敗: {item['name']}")
        print(f"    錯誤: {e.response.text[:150]}")
        return None


async def migrate_duplicates():
    """遷移重複型號的物料"""
    print("=" * 50)
    print("遷移重複型號物料（加後綴）")
    print("=" * 50)

    # 讀取現有映射
    with open(MAPPING_FILE) as f:
        mapping = json.load(f)

    existing_item_ids = set(mapping.get("items", {}).keys())

    # 連接資料庫
    conn = await asyncpg.connect(DATABASE_URL)

    # 建立 ERPNext client
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
    }

    new_items = {}

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # 取得已存在的 Item Code
        existing_codes = await get_existing_item_codes(client)
        print(f"\nERPNext 已有 {len(existing_codes)} 個 CTOS Item")

        # 查詢所有物料
        rows = await conn.fetch("""
            SELECT id, name, model, specification, unit, category,
                   min_stock, current_stock, storage_location
            FROM inventory_items
            ORDER BY model, name
        """)

        # 找出未遷移的物料
        unmigrated = []
        for row in rows:
            item_id = str(row["id"])
            if item_id not in existing_item_ids:
                unmigrated.append(dict(row))

        print(f"找到 {len(unmigrated)} 筆未遷移物料\n")

        # 追蹤每個型號已使用的後綴
        model_suffix = {}

        for item in unmigrated:
            model = item.get("model") or item["name"]

            # 決定後綴
            if model not in model_suffix:
                model_suffix[model] = 2  # 從 2 開始（1 是原本的）

            suffix = model_suffix[model]

            item_code = await create_item_with_suffix(
                client, item, suffix, existing_codes
            )

            if item_code:
                new_items[str(item["id"])] = item_code
                existing_codes.add(item_code)
                model_suffix[model] = suffix + 1

    await conn.close()

    # 更新映射表
    if new_items:
        mapping["items"].update(new_items)
        with open(MAPPING_FILE, "w") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 映射表已更新: {MAPPING_FILE}")

    print("\n" + "=" * 50)
    print(f"新增 Item: {len(new_items)} 個")

    # 列出有庫存的新物料（需要建立 Stock Entry）
    items_with_stock = []
    conn = await asyncpg.connect(DATABASE_URL)
    for item_id, item_code in new_items.items():
        row = await conn.fetchrow(
            "SELECT current_stock FROM inventory_items WHERE id = $1",
            item_id
        )
        if row and row["current_stock"] and float(row["current_stock"]) > 0:
            items_with_stock.append({
                "item_code": item_code,
                "qty": float(row["current_stock"]),
            })
    await conn.close()

    if items_with_stock:
        print(f"\n⚠ 有 {len(items_with_stock)} 個新物料有庫存，需要建立 Stock Entry：")
        for item in items_with_stock:
            print(f"  - {item['item_code']}: {item['qty']}")

    return new_items, items_with_stock


if __name__ == "__main__":
    new_items, items_with_stock = asyncio.run(migrate_duplicates())
