#!/usr/bin/env python3
"""
遷移驗證腳本
比對 CTOS 與 ERPNext 的資料筆數，驗證遷移結果
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


async def get_ctos_counts(conn: asyncpg.Connection) -> dict:
    """取得 CTOS 各資料表筆數"""
    counts = {}

    # 廠商
    row = await conn.fetchrow("SELECT COUNT(*) FROM vendors WHERE is_active = true")
    counts["vendors"] = row[0]

    # 物料
    row = await conn.fetchrow("SELECT COUNT(*) FROM inventory_items")
    counts["items"] = row[0]

    # 有庫存的物料
    row = await conn.fetchrow("SELECT COUNT(*) FROM inventory_items WHERE current_stock > 0")
    counts["items_with_stock"] = row[0]

    # 專案
    row = await conn.fetchrow("SELECT COUNT(*) FROM projects")
    counts["projects"] = row[0]

    # 專案成員
    row = await conn.fetchrow("SELECT COUNT(*) FROM project_members")
    counts["members"] = row[0]

    # 里程碑
    row = await conn.fetchrow("SELECT COUNT(*) FROM project_milestones")
    counts["milestones"] = row[0]

    # 會議
    row = await conn.fetchrow("SELECT COUNT(*) FROM project_meetings")
    counts["meetings"] = row[0]

    # 附件
    row = await conn.fetchrow("SELECT COUNT(*) FROM project_attachments")
    counts["attachments"] = row[0]

    # 連結
    row = await conn.fetchrow("SELECT COUNT(*) FROM project_links")
    counts["links"] = row[0]

    return counts


async def get_erpnext_counts(client: httpx.AsyncClient) -> dict:
    """取得 ERPNext 各 DocType 筆數"""
    counts = {}

    async def get_count(doctype: str, filters: str = None) -> int:
        try:
            params = {"doctype": doctype}
            if filters:
                params["filters"] = filters
            resp = await client.get(
                f"{ERPNEXT_URL}/api/method/frappe.client.get_count",
                params=params,
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("message", 0)
        except Exception as e:
            print(f"  ⚠ 無法取得 {doctype} 筆數: {e}")
            return -1

    # Supplier
    counts["suppliers"] = await get_count("Supplier")

    # Item (只算 CTOS 遷移的，以 CTOS- 開頭)
    counts["items"] = await get_count("Item", '[["item_code","like","CTOS-%"]]')

    # Project
    counts["projects"] = await get_count("Project")

    # Task (專案相關)
    counts["tasks"] = await get_count("Task", '[["project","is","set"]]')

    # Event (會議)
    counts["events"] = await get_count("Event", '[["event_category","=","Meeting"]]')

    # Stock Entry
    counts["stock_entries"] = await get_count("Stock Entry", '[["purpose","=","Material Receipt"]]')

    return counts


async def verify_mapping(
    client: httpx.AsyncClient,
    mapping: dict,
    sample_size: int = 5
) -> dict:
    """驗證映射表中的資料是否存在於 ERPNext"""
    results = {
        "vendors": {"total": 0, "verified": 0, "failed": []},
        "items": {"total": 0, "verified": 0, "failed": []},
        "projects": {"total": 0, "verified": 0, "failed": []},
    }

    async def check_exists(doctype: str, name: str) -> bool:
        try:
            resp = await client.get(f"{ERPNEXT_URL}/api/resource/{doctype}/{name}")
            return resp.status_code == 200
        except Exception:
            return False

    # 驗證廠商
    vendors = mapping.get("vendors", {})
    results["vendors"]["total"] = len(vendors)
    sample_vendors = list(vendors.items())[:sample_size]
    for ctos_id, erpnext_name in sample_vendors:
        if await check_exists("Supplier", erpnext_name):
            results["vendors"]["verified"] += 1
        else:
            results["vendors"]["failed"].append(erpnext_name)

    # 驗證物料
    items = mapping.get("items", {})
    results["items"]["total"] = len(items)
    sample_items = list(items.items())[:sample_size]
    for ctos_id, erpnext_code in sample_items:
        if await check_exists("Item", erpnext_code):
            results["items"]["verified"] += 1
        else:
            results["items"]["failed"].append(erpnext_code)

    # 驗證專案
    projects = mapping.get("projects", {})
    results["projects"]["total"] = len(projects)
    sample_projects = list(projects.items())[:sample_size]
    for ctos_id, erpnext_name in sample_projects:
        if await check_exists("Project", erpnext_name):
            results["projects"]["verified"] += 1
        else:
            results["projects"]["failed"].append(erpnext_name)

    return results


async def run_verification(mapping_file: str = None) -> dict:
    """執行完整驗證"""
    print("=" * 60)
    print("CTOS → ERPNext 遷移驗證")
    print("=" * 60)

    # 連接 CTOS 資料庫
    conn = await asyncpg.connect(DATABASE_URL)

    # 建立 ERPNext client
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
    }

    results = {
        "ctos_counts": {},
        "erpnext_counts": {},
        "comparison": {},
        "mapping_verification": None,
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # 取得 CTOS 筆數
        print("\n取得 CTOS 資料筆數...")
        ctos_counts = await get_ctos_counts(conn)
        results["ctos_counts"] = ctos_counts

        # 取得 ERPNext 筆數
        print("取得 ERPNext 資料筆數...")
        erpnext_counts = await get_erpnext_counts(client)
        results["erpnext_counts"] = erpnext_counts

        # 比對
        print("\n" + "=" * 60)
        print("資料筆數比對")
        print("=" * 60)
        print(f"{'資料類型':<20} {'CTOS':<10} {'ERPNext':<10} {'狀態':<10}")
        print("-" * 60)

        comparisons = [
            ("廠商 → Supplier", ctos_counts["vendors"], erpnext_counts["suppliers"]),
            ("物料 → Item", ctos_counts["items"], erpnext_counts["items"]),
            ("專案 → Project", ctos_counts["projects"], erpnext_counts["projects"]),
            ("里程碑 → Task", ctos_counts["milestones"], erpnext_counts["tasks"]),
            ("會議 → Event", ctos_counts["meetings"], erpnext_counts["events"]),
        ]

        all_match = True
        for name, ctos, erpnext in comparisons:
            if erpnext < 0:
                status = "⚠ 無法取得"
                all_match = False
            elif ctos == erpnext:
                status = "✓ 一致"
            elif erpnext >= ctos:
                status = "✓ 已遷移"
            else:
                status = f"✗ 差異 {ctos - erpnext}"
                all_match = False

            print(f"{name:<20} {ctos:<10} {erpnext:<10} {status:<10}")
            results["comparison"][name] = {
                "ctos": ctos,
                "erpnext": erpnext,
                "match": ctos <= erpnext if erpnext >= 0 else None,
            }

        # 驗證映射表（如果有提供）
        if mapping_file and Path(mapping_file).exists():
            print("\n" + "=" * 60)
            print("映射表驗證（抽樣）")
            print("=" * 60)

            with open(mapping_file) as f:
                mapping = json.load(f)

            mapping_results = await verify_mapping(client, mapping)
            results["mapping_verification"] = mapping_results

            for dtype, data in mapping_results.items():
                verified = data["verified"]
                total = min(data["total"], 5)  # 抽樣數
                status = "✓" if verified == total else "✗"
                print(f"{dtype}: {verified}/{total} 筆驗證通過 {status}")
                if data["failed"]:
                    print(f"  失敗: {', '.join(data['failed'])}")

    await conn.close()

    # 總結
    print("\n" + "=" * 60)
    print("驗證結果")
    print("=" * 60)
    if all_match:
        print("✓ 所有資料筆數一致或已遷移完成")
    else:
        print("⚠ 部分資料筆數不一致，請檢查")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="驗證 CTOS → ERPNext 遷移結果")
    parser.add_argument("--mapping-file", type=str,
                        help="映射表 JSON 檔案路徑（用於抽樣驗證）")
    parser.add_argument("--json", action="store_true",
                        help="輸出 JSON 格式結果")
    args = parser.parse_args()

    result = asyncio.run(run_verification(mapping_file=args.mapping_file))

    if args.json:
        print("\n--- JSON 結果 ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
