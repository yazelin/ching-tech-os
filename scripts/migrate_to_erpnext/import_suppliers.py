#!/usr/bin/env python3
"""
匯入供應商資料到 ERPNext

從 Excel 檔案解析供應商資料，並使用 ERPNext REST API 匯入。
"""

import pandas as pd
import requests
import json
import re
import sys
from typing import Optional
from pathlib import Path

# ERPNext 設定（從 .env 讀取）
import os
from dotenv import load_dotenv

# 載入 .env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

ERPNEXT_URL = os.getenv("ERPNEXT_URL", "http://ct.erp")
API_KEY = os.getenv("ERPNEXT_API_KEY", "")
API_SECRET = os.getenv("ERPNEXT_API_SECRET", "")

# 類型對應
TYPE_TO_GROUP = {
    "自動化元件": "自動化元件",
    "修理": "Services",
    "金屬生產": "金屬生產",
    "文具": "文具",
    "軟體": "Services",
    "旅行社": "旅行社",
}

DEFAULT_GROUP = "Services"


def get_headers():
    return {
        "Authorization": f"token {API_KEY}:{API_SECRET}",
        "Content-Type": "application/json",
    }


def supplier_exists(supplier_name: str) -> bool:
    """檢查供應商是否已存在"""
    url = f"{ERPNEXT_URL}/api/resource/Supplier/{supplier_name}"
    response = requests.get(url, headers=get_headers())
    return response.status_code == 200


def create_supplier(supplier_data: dict) -> dict:
    """建立供應商"""
    url = f"{ERPNEXT_URL}/api/resource/Supplier"
    response = requests.post(url, headers=get_headers(), json={"data": supplier_data})
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
        # 移除手機號碼，剩下的是姓名
        name = contact_str.replace(mobile_match.group(1), "").strip()
    else:
        name = contact_str.strip()

    return name, mobile


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
            tax_id = str(int(row[2])) if pd.notna(row[2]) and row[2] != "" else ""
            supplier_type = str(row[3]).strip() if pd.notna(row[3]) else ""
            contact_name = str(row[4]).strip() if pd.notna(row[4]) else ""
            phone = str(row[9]).strip() if pd.notna(row[9]) else ""

            current_supplier = {
                "supplier_code": supplier_code,
                "short_name": short_name,
                "full_name": "",
                "tax_id": tax_id,
                "supplier_type": supplier_type,
                "contacts": [contact_name] if contact_name else [],
                "phones": [phone] if phone else [],
                "address": "",
                "postal_code": "",
            }
        elif current_supplier:
            if pd.notna(row[4]) and str(row[4]).strip():
                current_supplier["contacts"].append(str(row[4]).strip())
            if pd.notna(row[9]) and str(row[9]).strip():
                current_supplier["phones"].append(str(row[9]).strip())
            if pd.notna(row[1]) and str(row[1]).strip() and not current_supplier["full_name"]:
                current_supplier["full_name"] = str(row[1]).strip()
            if pd.notna(row[7]) and str(row[7]).strip():
                current_supplier["postal_code"] = str(int(row[7])) if isinstance(row[7], float) else str(row[7])
            if pd.notna(row[8]) and str(row[8]).strip():
                if not current_supplier["address"]:
                    current_supplier["address"] = str(row[8]).strip()

    if current_supplier:
        suppliers.append(current_supplier)

    return suppliers


def import_supplier(supplier: dict, dry_run: bool = False) -> dict:
    """匯入單一供應商"""
    result = {
        "supplier_code": supplier["supplier_code"],
        "name": supplier["full_name"] or supplier["short_name"],
        "success": False,
        "error": None,
        "supplier_id": None,
        "address_id": None,
        "contact_ids": [],
    }

    # 決定供應商名稱
    supplier_name = supplier["full_name"] or supplier["short_name"]
    if not supplier_name:
        result["error"] = "無供應商名稱"
        return result

    # 加上代碼前綴避免重複
    display_name = f"{supplier['supplier_code']} - {supplier_name}"

    # 決定供應商群組
    supplier_group = TYPE_TO_GROUP.get(supplier["supplier_type"], DEFAULT_GROUP)

    # 準備供應商資料
    supplier_data = {
        "supplier_name": display_name,
        "supplier_group": supplier_group,
        "supplier_type": "Company",
        "country": "Taiwan",
        "default_currency": "TWD",
    }

    # 統一編號
    if supplier["tax_id"]:
        supplier_data["tax_id"] = supplier["tax_id"]

    # 檢查是否已存在
    if supplier_exists(display_name):
        print(f"⏭ 已存在，跳過: {display_name}")
        result["success"] = True
        result["supplier_id"] = display_name
        result["error"] = "已存在"
        return result

    if dry_run:
        print(f"[DRY-RUN] 建立供應商: {display_name}")
        result["success"] = True
        return result

    try:
        # 建立供應商
        resp = create_supplier(supplier_data)
        if "data" in resp:
            supplier_id = resp["data"]["name"]
            result["supplier_id"] = supplier_id
            print(f"✓ 建立供應商: {display_name}")

            # 建立地址
            if supplier["address"]:
                address_data = {
                    "address_title": f"{supplier['supplier_code']} 地址",
                    "address_type": "Billing",
                    "address_line1": supplier["address"],
                    "city": "台灣",
                    "country": "Taiwan",
                    "pincode": supplier["postal_code"] if supplier["postal_code"] else None,
                    "links": [{
                        "link_doctype": "Supplier",
                        "link_name": supplier_id,
                    }],
                }
                addr_resp = create_address(address_data)
                if "data" in addr_resp:
                    result["address_id"] = addr_resp["data"]["name"]
                    print(f"  ✓ 建立地址: {supplier['address'][:30]}...")

            # 建立聯絡人
            for i, contact_str in enumerate(supplier["contacts"]):
                contact_name, mobile = parse_contact_info(contact_str)
                if not contact_name:
                    continue

                # 取得對應電話
                phone = None
                if i < len(supplier["phones"]):
                    phone, phone_mobile = parse_phone(supplier["phones"][i])
                    if phone_mobile and not mobile:
                        mobile = phone_mobile

                contact_data = {
                    "first_name": contact_name,
                    "links": [{
                        "link_doctype": "Supplier",
                        "link_name": supplier_id,
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
    parser = argparse.ArgumentParser(description="匯入供應商到 ERPNext")
    parser.add_argument("excel_path", help="Excel 檔案路徑")
    parser.add_argument("--dry-run", action="store_true", help="僅測試，不實際匯入")
    parser.add_argument("--limit", type=int, help="限制匯入數量")
    parser.add_argument("--start", type=int, default=0, help="從第幾筆開始")
    args = parser.parse_args()

    print(f"解析 Excel: {args.excel_path}")
    suppliers = parse_excel(args.excel_path)
    print(f"共 {len(suppliers)} 家供應商\n")

    # 限制範圍
    if args.start:
        suppliers = suppliers[args.start:]
    if args.limit:
        suppliers = suppliers[:args.limit]

    print(f"將匯入 {len(suppliers)} 家供應商")
    if args.dry_run:
        print("=== DRY RUN 模式 ===\n")

    results = []
    success_count = 0
    fail_count = 0

    for i, supplier in enumerate(suppliers):
        print(f"\n[{i+1}/{len(suppliers)}] {supplier['supplier_code']}")
        result = import_supplier(supplier, dry_run=args.dry_run)
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
                print(f"  - {r['supplier_code']}: {r['error']}")


if __name__ == "__main__":
    main()
