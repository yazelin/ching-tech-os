#!/usr/bin/env python3
"""
補充供應商缺少的電話和聯絡人

修正問題：
1. 電話沒有加到地址
2. 採購人沒有建立為聯絡人
"""

import pandas as pd
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# 載入 .env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

ERPNEXT_URL = os.getenv("ERPNEXT_URL", "http://ct.erp")
API_KEY = os.getenv("ERPNEXT_API_KEY", "")
API_SECRET = os.getenv("ERPNEXT_API_SECRET", "")


def get_headers():
    return {
        "Authorization": f"token {API_KEY}:{API_SECRET}",
        "Content-Type": "application/json",
    }


def get_address_by_title(title: str) -> dict | None:
    """根據 address_title 查詢地址"""
    url = f"{ERPNEXT_URL}/api/resource/Address"
    params = {
        "filters": f'[["address_title", "=", "{title}"]]',
        "fields": '["name", "phone", "fax"]'
    }
    response = requests.get(url, headers=get_headers(), params=params)
    data = response.json()
    if data.get("data") and len(data["data"]) > 0:
        return data["data"][0]
    return None


def update_address(address_name: str, phone: str, fax: str = None) -> dict:
    """更新地址的電話"""
    url = f"{ERPNEXT_URL}/api/resource/Address/{address_name}"
    update_data = {}
    if phone:
        update_data["phone"] = phone
    if fax:
        update_data["fax"] = fax
    response = requests.put(url, headers=get_headers(), json={"data": update_data})
    return response.json()


def get_contacts_for_supplier(supplier_name: str) -> list:
    """取得供應商的聯絡人列表"""
    url = f"{ERPNEXT_URL}/api/resource/Contact"
    # 用 Dynamic Link 查詢
    params = {
        "filters": f'[["Dynamic Link", "link_name", "=", "{supplier_name}"]]',
        "fields": '["name", "first_name"]'
    }
    response = requests.get(url, headers=get_headers(), params=params)
    data = response.json()
    return data.get("data", [])


def create_contact(contact_data: dict) -> dict:
    """建立聯絡人"""
    url = f"{ERPNEXT_URL}/api/resource/Contact"
    response = requests.post(url, headers=get_headers(), json={"data": contact_data})
    return response.json()


def parse_excel(excel_path: str) -> list[dict]:
    """解析 Excel 檔案"""
    df = pd.read_excel(excel_path, header=None)
    suppliers = []
    current_supplier = None

    for i in range(5, len(df)):
        row = df.iloc[i]

        if pd.notna(row[0]) and str(row[0]).strip():
            if current_supplier:
                suppliers.append(current_supplier)

            supplier_code = str(row[0]).strip()
            short_name = str(row[1]).strip() if pd.notna(row[1]) else ""
            phone = str(row[9]).strip() if pd.notna(row[9]) else ""
            purchaser = str(row[12]).strip() if pd.notna(row[12]) else ""

            current_supplier = {
                "supplier_code": supplier_code,
                "short_name": short_name,
                "full_name": "",
                "phones": [phone] if phone else [],
                "purchaser": purchaser,
                "address": "",
            }
        elif current_supplier:
            if pd.notna(row[9]) and str(row[9]).strip():
                current_supplier["phones"].append(str(row[9]).strip())
            if pd.notna(row[1]) and str(row[1]).strip() and not current_supplier["full_name"]:
                current_supplier["full_name"] = str(row[1]).strip()
            if pd.notna(row[8]) and str(row[8]).strip():
                if not current_supplier["address"]:
                    current_supplier["address"] = str(row[8]).strip()

    if current_supplier:
        suppliers.append(current_supplier)

    return suppliers


def main():
    import argparse
    parser = argparse.ArgumentParser(description="補充供應商電話和聯絡人")
    parser.add_argument("excel_path", help="Excel 檔案路徑")
    parser.add_argument("--dry-run", action="store_true", help="僅測試，不實際更新")
    parser.add_argument("--limit", type=int, help="限制處理數量")
    args = parser.parse_args()

    print(f"解析 Excel: {args.excel_path}")
    suppliers = parse_excel(args.excel_path)
    print(f"共 {len(suppliers)} 家供應商\n")

    if args.limit:
        suppliers = suppliers[:args.limit]

    updated_phones = 0
    created_contacts = 0
    skipped = 0

    for i, supplier in enumerate(suppliers):
        supplier_code = supplier["supplier_code"]
        supplier_name = supplier["full_name"] or supplier["short_name"]
        display_name = f"{supplier_code} - {supplier_name}"

        print(f"[{i+1}/{len(suppliers)}] {supplier_code}")

        # 1. 更新地址電話
        if supplier["phones"] and supplier["address"]:
            address_title = f"{supplier_code} 地址"
            address = get_address_by_title(address_title)

            if address and not address.get("phone"):
                # 第一個電話作為主要電話，第二個作為傳真
                phone = supplier["phones"][0] if supplier["phones"] else None
                fax = supplier["phones"][1] if len(supplier["phones"]) > 1 else None

                if args.dry_run:
                    print(f"  [DRY-RUN] 更新地址電話: {phone}, 傳真: {fax}")
                else:
                    update_address(address["name"], phone, fax)
                    print(f"  ✓ 更新地址電話: {phone}")
                    if fax:
                        print(f"  ✓ 更新傳真: {fax}")
                updated_phones += 1
            elif not address:
                print(f"  ⚠ 找不到地址: {address_title}")

        # 2. 建立採購人聯絡人
        if supplier["purchaser"]:
            # 檢查是否已有此聯絡人
            existing_contacts = get_contacts_for_supplier(display_name)
            existing_names = [c["first_name"] for c in existing_contacts]

            if supplier["purchaser"] not in existing_names:
                contact_data = {
                    "first_name": supplier["purchaser"],
                    "links": [{
                        "link_doctype": "Supplier",
                        "link_name": display_name,
                    }],
                }

                if args.dry_run:
                    print(f"  [DRY-RUN] 建立聯絡人: {supplier['purchaser']}")
                else:
                    resp = create_contact(contact_data)
                    if "data" in resp:
                        print(f"  ✓ 建立聯絡人: {supplier['purchaser']}")
                        created_contacts += 1
                    else:
                        print(f"  ✗ 建立聯絡人失敗: {resp.get('message', resp)[:50]}")
            else:
                skipped += 1

    print(f"\n=== 完成 ===")
    print(f"更新電話: {updated_phones}")
    print(f"建立聯絡人: {created_contacts}")
    print(f"跳過（已存在）: {skipped}")


if __name__ == "__main__":
    main()
