#!/usr/bin/env python3
"""
期初庫存建立腳本
根據 CTOS 物料的 current_stock 在 ERPNext 建立 Material Receipt Stock Entry
"""
import asyncio
import json
import os
from datetime import date
from pathlib import Path

import httpx

ERPNEXT_URL = os.environ.get("ERPNEXT_URL", "http://ct.erp")
ERPNEXT_API_KEY = os.environ["ERPNEXT_API_KEY"]
ERPNEXT_API_SECRET = os.environ["ERPNEXT_API_SECRET"]

# 預設公司和倉庫（需根據實際 ERPNext 設定調整）
DEFAULT_COMPANY = "擎添工業有限公司"
DEFAULT_WAREHOUSE = "Stores - 擎添工業"


async def create_opening_stock_entry(
    client: httpx.AsyncClient,
    items_with_stock: list[dict],
    posting_date: str = None,
    dry_run: bool = False
) -> str | None:
    """
    建立期初庫存 Stock Entry (Material Receipt)

    Args:
        client: httpx AsyncClient
        items_with_stock: 物料清單，每項包含 item_code, qty, name
        posting_date: 入庫日期，預設為今天
        dry_run: 是否為模擬執行

    Returns:
        建立的 Stock Entry name，或 None（若失敗）
    """
    if not items_with_stock:
        print("沒有需要建立期初庫存的物料")
        return None

    if posting_date is None:
        posting_date = date.today().isoformat()

    # 準備 Stock Entry 資料
    stock_entry_data = {
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "purpose": "Material Receipt",
        "company": DEFAULT_COMPANY,
        "posting_date": posting_date,
        "remarks": "CTOS 資料遷移 - 期初庫存",
        "items": []
    }

    # 加入物料明細
    for item in items_with_stock:
        stock_entry_data["items"].append({
            "item_code": item["item_code"],
            "qty": item["qty"],
            "t_warehouse": DEFAULT_WAREHOUSE,  # 目標倉庫
            "basic_rate": 0,  # 期初庫存不設成本
            "allow_zero_valuation_rate": 1,
        })

    if dry_run:
        print(f"\n[DRY-RUN] 將建立 Stock Entry (Material Receipt)")
        print(f"  日期: {posting_date}")
        print(f"  公司: {DEFAULT_COMPANY}")
        print(f"  倉庫: {DEFAULT_WAREHOUSE}")
        print(f"  物料數量: {len(items_with_stock)} 項")
        print("\n  物料明細:")
        for item in items_with_stock:
            print(f"    - {item['item_code']}: {item['qty']} ({item['name']})")
        return "DRY_RUN_STOCK_ENTRY"

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Stock Entry",
            json={"data": json.dumps(stock_entry_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        stock_entry_name = result.get("data", {}).get("name")
        print(f"\n✓ 建立 Stock Entry: {stock_entry_name}")
        return stock_entry_name
    except httpx.HTTPStatusError as e:
        print(f"\n✗ 建立 Stock Entry 失敗")
        print(f"  錯誤: {e.response.text[:500]}")
        return None


async def submit_stock_entry(
    client: httpx.AsyncClient,
    stock_entry_name: str,
    dry_run: bool = False
) -> bool:
    """
    提交 Stock Entry（使其生效並更新庫存）

    Args:
        client: httpx AsyncClient
        stock_entry_name: Stock Entry 名稱
        dry_run: 是否為模擬執行

    Returns:
        是否成功
    """
    if dry_run:
        print(f"[DRY-RUN] 將提交 Stock Entry: {stock_entry_name}")
        return True

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/method/frappe.client.submit",
            json={"doc": json.dumps({
                "doctype": "Stock Entry",
                "name": stock_entry_name,
            })},
        )
        resp.raise_for_status()
        print(f"✓ Stock Entry 已提交: {stock_entry_name}")
        return True
    except httpx.HTTPStatusError as e:
        print(f"✗ Stock Entry 提交失敗: {stock_entry_name}")
        print(f"  錯誤: {e.response.text[:300]}")
        return False


async def create_opening_stock(
    items_with_stock: list[dict] = None,
    mapping_file: str = None,
    posting_date: str = None,
    auto_submit: bool = False,
    dry_run: bool = False
) -> dict:
    """
    執行期初庫存建立

    Args:
        items_with_stock: 物料清單，優先使用
        mapping_file: 映射表 JSON 檔案路徑（包含 items_with_stock）
        posting_date: 入庫日期
        auto_submit: 是否自動提交
        dry_run: 是否為模擬執行
    """
    print("=" * 50)
    print("期初庫存建立 (Stock Entry - Material Receipt)")
    print("=" * 50)

    # 讀取物料清單
    if items_with_stock is None and mapping_file:
        with open(mapping_file) as f:
            mapping_data = json.load(f)
            items_with_stock = mapping_data.get("items_with_stock", [])

    if not items_with_stock:
        print("\n沒有需要建立期初庫存的物料")
        return {"stock_entry": None}

    print(f"\n找到 {len(items_with_stock)} 筆物料需要建立期初庫存")

    # 建立 ERPNext client
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
    }

    result = {"stock_entry": None, "submitted": False}

    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        # 建立 Stock Entry
        stock_entry_name = await create_opening_stock_entry(
            client, items_with_stock, posting_date, dry_run
        )

        if stock_entry_name and not stock_entry_name.startswith("DRY_RUN"):
            result["stock_entry"] = stock_entry_name

            # 自動提交
            if auto_submit:
                submitted = await submit_stock_entry(client, stock_entry_name, dry_run)
                result["submitted"] = submitted
            else:
                print(f"\n⚠ Stock Entry 已建立但未提交，請在 ERPNext 中確認後手動提交")
                print(f"  或重新執行並加上 --auto-submit 參數")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="建立 ERPNext 期初庫存")
    parser.add_argument("--mapping-file", type=str, required=True,
                        help="物料映射表 JSON 檔案路徑（由 migrate_items.py 產生）")
    parser.add_argument("--posting-date", type=str,
                        help="入庫日期 (YYYY-MM-DD)，預設為今天")
    parser.add_argument("--auto-submit", action="store_true",
                        help="建立後自動提交 Stock Entry")
    parser.add_argument("--dry-run", action="store_true",
                        help="只顯示將執行的操作，不實際執行")
    args = parser.parse_args()

    result = asyncio.run(create_opening_stock(
        mapping_file=args.mapping_file,
        posting_date=args.posting_date,
        auto_submit=args.auto_submit,
        dry_run=args.dry_run,
    ))

    if not args.dry_run and result.get("stock_entry"):
        print(f"\n結果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
