#!/usr/bin/env python3
"""
補充客戶缺少的電話和業務員

修正問題：
1. 電話沒有加到地址
2. 業務員沒有建立為聯絡人
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


def create_contact(contact_data: dict) -> dict:
    """建立聯絡人"""
    url = f"{ERPNEXT_URL}/api/resource/Contact"
    response = requests.post(url, headers=get_headers(), json={"data": contact_data})
    return response.json()


def parse_excel(excel_path: str) -> list[dict]:
    """解析 Excel 檔案"""
    df = pd.read_excel(excel_path, header=None)
    customers = []
    current_customer = None

    for i in range(5, len(df)):
        row = df.iloc[i]

        if pd.notna(row[0]) and str(row[0]).strip():
            if current_customer:
                customers.append(current_customer)

            customer_code = str(row[0]).strip()
            short_name = str(row[1]).strip() if pd.notna(row[1]) else ""
            phone = str(row[9]).strip() if pd.notna(row[9]) else ""
            sales_person = str(row[12]).strip() if pd.notna(row[12]) else ""

            current_customer = {
                "customer_code": customer_code,
                "short_name": short_name,
                "full_name": "",
                "phones": [phone] if phone else [],
                "sales_person": sales_person,
                "address": "",
            }
        elif current_customer:
            if pd.notna(row[9]) and str(row[9]).strip():
                current_customer["phones"].append(str(row[9]).strip())
            if pd.notna(row[1]) and str(row[1]).strip() and not current_customer["full_name"]:
                current_customer["full_name"] = str(row[1]).strip()
            if pd.notna(row[8]) and str(row[8]).strip():
                if not current_customer["address"]:
                    current_customer["address"] = str(row[8]).strip()

    if current_customer:
        customers.append(current_customer)

    return customers


def main():
    import argparse
    parser = argparse.ArgumentParser(description="補充客戶電話和業務員")
    parser.add_argument("excel_path", help="Excel 檔案路徑")
    parser.add_argument("--dry-run", action="store_true", help="僅測試，不實際更新")
    parser.add_argument("--limit", type=int, help="限制處理數量")
    args = parser.parse_args()

    print(f"解析 Excel: {args.excel_path}")
    customers = parse_excel(args.excel_path)
    print(f"共 {len(customers)} 家客戶\n")

    if args.limit:
        customers = customers[:args.limit]

    updated_phones = 0
    created_contacts = 0

    for i, customer in enumerate(customers):
        customer_code = customer["customer_code"]
        customer_name = customer["full_name"] or customer["short_name"]
        display_name = f"{customer_code} - {customer_name}"

        print(f"[{i+1}/{len(customers)}] {customer_code}")

        # 1. 更新地址電話
        if customer["phones"] and customer["address"]:
            address_title = f"{customer_code} 地址"
            address = get_address_by_title(address_title)

            if address and not address.get("phone"):
                phone = customer["phones"][0] if customer["phones"] else None
                fax = customer["phones"][1] if len(customer["phones"]) > 1 else None

                if args.dry_run:
                    print(f"  [DRY-RUN] 更新地址電話: {phone}, 傳真: {fax}")
                else:
                    update_address(address["name"], phone, fax)
                    print(f"  ✓ 更新地址電話: {phone}")
                    if fax:
                        print(f"  ✓ 更新傳真: {fax}")
                updated_phones += 1
            elif not address:
                # 沒有地址但有電話，跳過
                pass

        # 2. 建立業務員聯絡人（內部人員）
        if customer["sales_person"]:
            contact_data = {
                "first_name": customer["sales_person"],
                "is_internal": 1,
                "designation": "業務人員",
                "links": [{
                    "link_doctype": "Customer",
                    "link_name": display_name,
                }],
            }

            if args.dry_run:
                print(f"  [DRY-RUN] 建立業務員: {customer['sales_person']}")
            else:
                resp = create_contact(contact_data)
                if "data" in resp:
                    print(f"  ✓ 建立業務員: {customer['sales_person']}")
                    created_contacts += 1
                else:
                    err = resp.get('exc', resp.get('message', str(resp)))[:50]
                    print(f"  ✗ 建立業務員失敗: {err}")

    print(f"\n=== 完成 ===")
    print(f"更新電話: {updated_phones}")
    print(f"建立業務員: {created_contacts}")


if __name__ == "__main__":
    main()
