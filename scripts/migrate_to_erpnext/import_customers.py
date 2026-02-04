#!/usr/bin/env python3
"""
匯入客戶資料到 ERPNext

從 Excel 檔案解析客戶資料，並使用 ERPNext REST API 匯入。
"""

import pandas as pd
import requests
import json
import re
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# 載入 .env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

ERPNEXT_URL = os.getenv("ERPNEXT_URL", "http://ct.erp")
API_KEY = os.getenv("ERPNEXT_API_KEY", "")
API_SECRET = os.getenv("ERPNEXT_API_SECRET", "")

# 客戶群組（需要先在 ERPNext 建立）
DEFAULT_GROUP = "All Customer Groups"


def get_headers():
    return {
        "Authorization": f"token {API_KEY}:{API_SECRET}",
        "Content-Type": "application/json",
    }


def customer_exists(customer_name: str) -> bool:
    """檢查客戶是否已存在"""
    url = f"{ERPNEXT_URL}/api/resource/Customer/{customer_name}"
    response = requests.get(url, headers=get_headers())
    return response.status_code == 200


def create_customer(customer_data: dict) -> dict:
    """建立客戶"""
    url = f"{ERPNEXT_URL}/api/resource/Customer"
    response = requests.post(url, headers=get_headers(), json={"data": customer_data})
    return response.json()


def create_address(address_data: dict) -> dict:
    """建立地址"""
    url = f"{ERPNEXT_URL}/api/resource/Address"
    response = requests.post(url, headers=get_headers(), json={"data": address_data})
    return response.json()


def create_contact(contact_data: dict) -> dict:
    """建立聯絡人"""
    url = f"{ERPNEXT_URL}/api/resource/Contact"
    response = requests.post(url, headers=get_headers(), json={"data": contact_data})
    return response.json()


def parse_phone(phone_str: str) -> tuple[Optional[str], Optional[str]]:
    """解析電話號碼，回傳 (電話, 手機)"""
    if not phone_str:
        return None, None

    # 手機格式：09xx-xxx-xxx 或 09xxxxxxxx
    mobile_match = re.search(r'(09\d{2}[-\s]?\d{3}[-\s]?\d{3})', phone_str)
    if mobile_match:
        mobile = mobile_match.group(1).replace("-", "").replace(" ", "")
        return None, mobile

    # 市話
    phone = phone_str.strip()
    if phone:
        return phone, None

    return None, None


def parse_contact_info(contact_str: str) -> tuple[str, Optional[str]]:
    """從聯絡人字串解析姓名和手機"""
    if not contact_str:
        return "", None

    # 嘗試匹配手機
    mobile_match = re.search(r'(09\d{2}[-\s]?\d{3}[-\s]?\d{3})', contact_str)
    mobile = None
    if mobile_match:
        mobile = mobile_match.group(1).replace("-", "").replace(" ", "")
        name = contact_str.replace(mobile_match.group(1), "").strip()
    else:
        name = contact_str.strip()

    return name, mobile


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
            tax_id = str(int(row[2])) if pd.notna(row[2]) and row[2] != "" else ""
            customer_type = str(row[3]).strip() if pd.notna(row[3]) else ""
            contact_name = str(row[4]).strip() if pd.notna(row[4]) else ""
            phone = str(row[9]).strip() if pd.notna(row[9]) else ""
            sales_person = str(row[12]).strip() if pd.notna(row[12]) else ""

            current_customer = {
                "customer_code": customer_code,
                "short_name": short_name,
                "full_name": "",
                "tax_id": tax_id,
                "customer_type": customer_type,
                "contacts": [contact_name] if contact_name else [],
                "phones": [phone] if phone else [],
                "address": "",
                "postal_code": "",
                "sales_person": sales_person,
            }
        elif current_customer:
            if pd.notna(row[4]) and str(row[4]).strip():
                current_customer["contacts"].append(str(row[4]).strip())
            if pd.notna(row[9]) and str(row[9]).strip():
                current_customer["phones"].append(str(row[9]).strip())
            if pd.notna(row[1]) and str(row[1]).strip() and not current_customer["full_name"]:
                current_customer["full_name"] = str(row[1]).strip()
            if pd.notna(row[7]) and str(row[7]).strip():
                current_customer["postal_code"] = str(int(row[7])) if isinstance(row[7], float) else str(row[7])
            if pd.notna(row[8]) and str(row[8]).strip():
                if not current_customer["address"]:
                    current_customer["address"] = str(row[8]).strip()

    if current_customer:
        customers.append(current_customer)

    return customers


def import_customer(customer: dict, dry_run: bool = False) -> dict:
    """匯入單一客戶"""
    result = {
        "customer_code": customer["customer_code"],
        "name": customer["full_name"] or customer["short_name"],
        "success": False,
        "error": None,
        "customer_id": None,
        "address_id": None,
        "contact_ids": [],
    }

    # 決定客戶名稱
    customer_name = customer["full_name"] or customer["short_name"]
    if not customer_name:
        result["error"] = "無客戶名稱"
        return result

    # 加上代碼前綴避免重複
    display_name = f"{customer['customer_code']} - {customer_name}"

    # 檢查是否已存在
    if customer_exists(display_name):
        print(f"⏭ 已存在，跳過: {display_name}")
        result["success"] = True
        result["customer_id"] = display_name
        result["error"] = "已存在"
        return result

    if dry_run:
        print(f"[DRY-RUN] 建立客戶: {display_name}")
        result["success"] = True
        return result

    # 準備客戶資料
    customer_data = {
        "customer_name": display_name,
        "customer_group": DEFAULT_GROUP,
        "customer_type": "Company",
        "territory": "Taiwan",
        "default_currency": "TWD",
    }

    # 統一編號
    if customer["tax_id"]:
        customer_data["tax_id"] = customer["tax_id"]

    try:
        # 建立客戶
        resp = create_customer(customer_data)
        if "data" in resp:
            customer_id = resp["data"]["name"]
            result["customer_id"] = customer_id
            print(f"✓ 建立客戶: {display_name}")

            # 建立地址
            if customer["address"]:
                address_data = {
                    "address_title": f"{customer['customer_code']} 地址",
                    "address_type": "Billing",
                    "address_line1": customer["address"],
                    "city": "台灣",
                    "country": "Taiwan",
                    "pincode": customer["postal_code"] if customer["postal_code"] else None,
                    "links": [{
                        "link_doctype": "Customer",
                        "link_name": customer_id,
                    }],
                }
                addr_resp = create_address(address_data)
                if "data" in addr_resp:
                    result["address_id"] = addr_resp["data"]["name"]
                    print(f"  ✓ 建立地址: {customer['address'][:30]}...")

            # 建立聯絡人
            for i, contact_str in enumerate(customer["contacts"]):
                contact_name, mobile = parse_contact_info(contact_str)
                if not contact_name:
                    continue

                # 取得對應電話
                phone = None
                if i < len(customer["phones"]):
                    phone, phone_mobile = parse_phone(customer["phones"][i])
                    if phone_mobile and not mobile:
                        mobile = phone_mobile

                contact_data = {
                    "first_name": contact_name,
                    "links": [{
                        "link_doctype": "Customer",
                        "link_name": customer_id,
                    }],
                }

                # 電話號碼
                phone_nos = []
                if phone:
                    phone_nos.append({"phone": phone, "is_primary_phone": 1})
                if mobile:
                    phone_nos.append({"phone": mobile, "is_primary_mobile_no": 1})
                if phone_nos:
                    contact_data["phone_nos"] = phone_nos

                contact_resp = create_contact(contact_data)
                if "data" in contact_resp:
                    result["contact_ids"].append(contact_resp["data"]["name"])
                    print(f"  ✓ 建立聯絡人: {contact_name}")

            result["success"] = True
        else:
            result["error"] = resp.get("message") or resp.get("exc") or str(resp)
            print(f"✗ 失敗: {display_name} - {result['error'][:50]}")

    except Exception as e:
        result["error"] = str(e)
        print(f"✗ 錯誤: {display_name} - {e}")

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="匯入客戶到 ERPNext")
    parser.add_argument("excel_path", help="Excel 檔案路徑")
    parser.add_argument("--dry-run", action="store_true", help="僅測試，不實際匯入")
    parser.add_argument("--limit", type=int, help="限制匯入數量")
    parser.add_argument("--start", type=int, default=0, help="從第幾筆開始")
    args = parser.parse_args()

    print(f"解析 Excel: {args.excel_path}")
    customers = parse_excel(args.excel_path)
    print(f"共 {len(customers)} 家客戶\n")

    # 限制範圍
    if args.start:
        customers = customers[args.start:]
    if args.limit:
        customers = customers[:args.limit]

    print(f"將匯入 {len(customers)} 家客戶")
    if args.dry_run:
        print("=== DRY RUN 模式 ===\n")

    results = []
    success_count = 0
    fail_count = 0

    for i, customer in enumerate(customers):
        print(f"\n[{i+1}/{len(customers)}] {customer['customer_code']}")
        result = import_customer(customer, dry_run=args.dry_run)
        results.append(result)
        if result["success"]:
            success_count += 1
        else:
            fail_count += 1

    print(f"\n=== 匯入完成 ===")
    print(f"成功: {success_count}")
    print(f"失敗: {fail_count}")

    if fail_count > 0:
        print("\n失敗清單:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['customer_code']}: {r['error']}")


if __name__ == "__main__":
    main()
