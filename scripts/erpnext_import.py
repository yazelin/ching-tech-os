#!/usr/bin/env python3
"""把 ERPNext 備份的 doctype JSON 匯進往來與物料模組（規格第六節）。

來源是 `scripts/erpnext_export.py` 產出的 `<備份日期>/doctypes/*.json`
（正式機每日備份在 `/mnt/nas/ctos/erpnext-backup/`）。

寫入一律經過 `services/erp*.py` 與 `services/project.py` 的函式，不繞過去直接
INSERT，所以每一筆都會留 `erp_audit`，`via="import"`、`actor_user_id` 是
`--actor-user-id` 指定的執行者。

**冪等**：以 `source_ref` 當 key（`Supplier:<name>`、`Customer:<name>`、
`Item:<item_code>`、`PO:<name>`），已存在就只更新有值且真的變了的欄位。
倉庫與專案的資料表沒有 `source_ref` 欄位，改用 `code`／專案名稱當 key
（兩者都是唯一鍵，且由來源名稱決定，所以重跑一樣收斂）。
庫存重跑做的是「目標餘額 − 現有餘額」的差額調整，差為 0 就不寫。

用法：
  erpnext_import.py --src /mnt/nas/ctos/erpnext-backup/20260912/doctypes --dry-run
  erpnext_import.py --src ./doctypes --db-name ctos_import_test --actor-user-id 1
  erpnext_import.py --src ./doctypes --only parties items
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("erpnext_import")

# 會讀的 doctype（檔名是 doctype 名稱把空白換成底線）
DOCTYPES = (
    "Supplier",
    "Customer",
    "Contact",
    "Address",
    "Item",
    "Item Price",
    "Warehouse",
    "Bin",
    "Purchase Order",
    "Project",
    "Task",
)

# `--only` 可選的區塊，也是預設的執行順序（採購單要等往來對象、物料、專案都在）
SECTIONS = ("parties", "items", "stock", "projects", "purchase_orders")

# 一個 Contact 掛到超過這麼多家就算「掛很多家」：沒有任何聯絡方式的視為擎添自家
# 人員整筆跳過（`--internal-contact-threshold` 可調），有聯絡方式的照掛但點名。
DEFAULT_INTERNAL_CONTACT_THRESHOLD = 20

# ERPNext 裡 MCP 測試留下的假資料，前綴長這樣
TEST_RECORD_PREFIX = "_MCP_TEST_"

# 判斷測試資料時要看的欄位（主鍵與各 doctype 的顯示名稱、以及指到主檔的參照）
TEST_RECORD_FIELDS = (
    "name",
    "supplier_name",
    "customer_name",
    "supplier",
    "item_code",
    "item_name",
    "full_name",
    "address_title",
    "warehouse_name",
    "project_name",
    "subject",
)

# ERPNext 主鍵前面那段流水碼，例如 `SM9001 - `、`CF9002-1 - `
CODE_PREFIX_RE = re.compile(r"^[A-Za-z]{1,4}\d{2,}(?:-\d+)?\s*-\s*")

# 公司尾綴；反覆剝到剝不動為止（「股份有限公司」剝完不會再留「公司」）
COMPANY_SUFFIX_RE = re.compile(r"(股份有限公司|有限公司|公司)$")

# ERPNext 專案／任務狀態對到本模組的狀態集合
PROJECT_STATUS = {
    "Open": "active",
    "Completed": "completed",
    "Cancelled": "cancelled",
}
TASK_STATUS = {
    "Open": "todo",
    "Overdue": "todo",
    "Working": "doing",
    "Pending Review": "doing",
    "Template": "todo",
    "Completed": "done",
    "Cancelled": "done",
}


# ============================================================
# 名稱正規化
# ============================================================


def _text(value: Any) -> str:
    return (value or "").strip() if isinstance(value, str) else ""


def display_name(raw: str) -> str:
    """去掉 ERPNext 的流水碼前綴，留給人看的名字"""
    return CODE_PREFIX_RE.sub("", _text(raw)).strip()


def strip_company_suffix(name: str) -> str:
    """反覆剝掉公司尾綴"""
    current = _text(name)
    while True:
        stripped = COMPANY_SUFFIX_RE.sub("", current).strip()
        if stripped == current or not stripped:
            return current if not stripped else stripped
        current = stripped


def short_name_of(name: str) -> str | None:
    """剝掉公司尾綴的簡稱；沒東西可剝就回 None（不重複存一份一樣的）"""
    short = strip_company_suffix(name)
    return short if short and short != _text(name) else None


def fold_party_name(raw: str) -> str:
    """去前綴 → 全形轉半形 → 去空白 → 小寫（**還沒**去公司尾綴）"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", display_name(raw))).casefold()


def normalize_party_name(raw: str) -> str:
    """合併用的 key：`fold_party_name()` 再去公司尾綴"""
    return strip_company_suffix(fold_party_name(raw))


# ============================================================
# 讀檔與小工具
# ============================================================


def load_doctype(src: Path, doctype: str) -> list[dict]:
    """讀一個 doctype 的 JSON；檔案不在就當空的（備份可能沒匯那個 doctype）"""
    path = Path(src) / f"{doctype.replace(' ', '_')}.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else [data]


def load_all(src: Path) -> dict[str, list[dict]]:
    return {doctype: load_doctype(src, doctype) for doctype in DOCTYPES}


def to_decimal(value: Any) -> Decimal | None:
    """數字欄位轉 Decimal；只有空的與壞掉的回 None

    **0 會保留成 `Decimal("0")`**：採購單行項的 `rate` 是 0 代表「這行不計價」，
    不是「沒填」，清成 NULL 會讓金額對不起來。要把 0 當沒填的只有
    `purchase_price`（`buying_prices()` 自己擋）與 `lead_days`。
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def to_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def dedupe(values: list[str]) -> list[str]:
    """去空白、去重、排序（排序是為了讓重跑比得出「沒變」）"""
    return sorted({v for v in (_text(x) for x in values) if v})


def is_test_record(row: dict) -> bool:
    """`_MCP_TEST_` 開頭的都是 MCP 測試留下的假資料，不匯

    看主鍵與顯示名稱，也看指到主檔的參照欄位——測試留下的採購單 `name`
    是正常單號，但它的 `supplier` 是 `_MCP_TEST_...`，整張單都是測試用的。
    """
    return any(
        _text(row.get(field)).startswith(TEST_RECORD_PREFIX)
        for field in TEST_RECORD_FIELDS
    )


def strip_test_records(data: dict[str, list[dict]]) -> tuple[dict, dict[str, int]]:
    """把每個 doctype 的測試資料濾掉，回傳（過濾後的資料, 每個 doctype 略過幾筆）"""
    cleaned: dict[str, list[dict]] = {}
    skipped: dict[str, int] = {}
    for doctype, rows in data.items():
        kept = [row for row in rows if not is_test_record(row)]
        cleaned[doctype] = kept
        if len(kept) != len(rows):
            skipped[doctype] = len(rows) - len(kept)
    return cleaned, skipped


def po_status(po: dict, received: Decimal, total: Decimal) -> str | None:
    """ERPNext 的採購單狀態對到本模組；草稿（docstatus=0）回 None 代表不匯"""
    status = _text(po.get("status"))
    if po.get("docstatus") == 2 or status == "Cancelled":
        return "cancelled"
    if status in ("Completed", "Closed"):
        return "received"
    if po.get("docstatus") == 0:
        return None
    if total > 0 and received >= total:
        return "received"
    if received > 0:
        return "partial"
    return "ordered"


# ============================================================
# 合併往來對象
# ============================================================


def build_party_groups(suppliers: list[dict], customers: list[dict]) -> list[dict]:
    """Supplier 與 Customer 正規化後同名的併成一組（一筆 party）"""
    groups: dict[str, dict] = {}
    sources = (
        ("Supplier", suppliers or [], "supplier_name"),
        ("Customer", customers or [], "customer_name"),
    )
    for role, rows, name_field in sources:
        for row in rows:
            raw = _text(row.get("name")) or _text(row.get(name_field))
            if not raw:
                continue
            key = normalize_party_name(raw)
            if not key:
                continue
            group = groups.setdefault(
                key,
                {
                    "key": key,
                    "name": "",
                    "source_tokens": [],
                    "alias_pool": [],
                    "variants": [],
                    "is_supplier": False,
                    "is_customer": False,
                },
            )
            group["source_tokens"].append(f"{role}:{raw}")
            group["variants"].append(fold_party_name(raw))
            group["alias_pool"] += [raw, _text(row.get(name_field)), display_name(raw)]
            if role == "Supplier":
                group["is_supplier"] = True
                # 供應商名優先當主名（採購單、Item Default 都是用供應商端的名字）
                if not group["name"] or not group["_from_supplier"]:
                    group["name"] = display_name(raw)
                group["_from_supplier"] = True
            else:
                group["is_customer"] = True
                if not group["name"]:
                    group["name"] = display_name(raw)
            group.setdefault("_from_supplier", role == "Supplier")

    result = []
    for group in groups.values():
        short = short_name_of(group["name"])
        aliases = dedupe(group["alias_pool"] + ([short] if short else []))
        # 去尾綴之前名稱就不同的（「某某有限公司」對上「某某股份有限公司」），
        # 有可能是兩家不同的法人被併在一起，列進 merge_review 讓人眼看過
        variants = sorted(set(group["variants"]))
        result.append(
            {
                "key": group["key"],
                "name": group["name"],
                "short_name": short,
                "aliases": [a for a in aliases if a != group["name"]],
                "is_supplier": group["is_supplier"],
                "is_customer": group["is_customer"],
                "source_tokens": group["source_tokens"],
                "source_ref": ";".join(group["source_tokens"]),
                "needs_review": len(variants) > 1,
            }
        )
    return result


def contact_payload(contact: dict) -> dict | None:
    """Contact → party_contacts 欄位；沒有名字的略過"""
    name = (
        _text(contact.get("full_name"))
        or " ".join(
            p for p in (_text(contact.get("first_name")), _text(contact.get("last_name"))) if p
        ).strip()
        or _text(contact.get("name"))
    )
    if not name:
        return None
    phone = _text(contact.get("phone"))
    mobile = _text(contact.get("mobile_no"))
    for row in contact.get("phone_nos") or []:
        number = _text(row.get("phone"))
        if not number:
            continue
        if row.get("is_primary_mobile_no") and not mobile:
            mobile = number
        elif not phone:
            phone = number
    email = _text(contact.get("email_id"))
    if not email:
        for row in contact.get("email_ids") or []:
            email = _text(row.get("email_id"))
            if email:
                break
    return {
        "name": name,
        "title": _text(contact.get("designation")) or None,
        "phone": phone or None,
        "mobile": mobile or None,
        "email": email or None,
        "is_primary": bool(contact.get("is_primary_contact")),
    }


def address_payload(address: dict) -> dict | None:
    """Address → party_addresses 欄位；沒有地址本文的略過"""
    lines = [_text(address.get("address_line1")), _text(address.get("address_line2"))]
    text = " ".join(p for p in lines if p).strip()
    if not text:
        return None
    return {
        "label": _text(address.get("address_type")) or None,
        "address": text,
        "city": _text(address.get("city")) or None,
        "is_primary": bool(address.get("is_primary_address")),
    }


def link_tokens(row: dict) -> list[str]:
    """Dynamic Link 子表 → `Supplier:<name>` / `Customer:<name>` token"""
    tokens = []
    for link in row.get("links") or []:
        doctype = _text(link.get("link_doctype"))
        link_name = _text(link.get("link_name"))
        if doctype in ("Supplier", "Customer") and link_name:
            tokens.append(f"{doctype}:{link_name}")
    return tokens


# ============================================================
# 既有狀態
# ============================================================


def empty_snapshot() -> dict[str, Any]:
    """匯入前的資料庫狀態；`load_snapshot()` 從真的資料庫填，測試直接給空的"""
    return {
        "parties": {},           # source token -> party 記錄
        "party_contacts": {},    # party_id -> set[聯絡人 key]
        "party_addresses": {},   # party_id -> set[地址 key]
        "items": {},             # `Item:<code>` -> item 記錄
        "warehouses": {},        # code -> 倉庫記錄
        "balances": {},          # (item_id, warehouse_id) -> Decimal
        "po_nos": set(),         # 已存在的採購單號
        "projects_by_name": {},  # 專案名稱 -> id
        "project_tasks": {},     # project_id -> set[任務標題]
    }


async def load_snapshot(conn) -> dict[str, Any]:
    """把既有狀態一次讀進記憶體（只讀，不寫）"""
    snapshot = empty_snapshot()

    for row in await conn.fetch(
        """
        SELECT id, name, short_name, aliases, is_supplier, is_customer, source_ref
        FROM parties
        WHERE deleted_at IS NULL AND source_ref IS NOT NULL
        """
    ):
        record = dict(row)
        record["aliases"] = list(record["aliases"] or [])
        for token in (record["source_ref"] or "").split(";"):
            if token:
                snapshot["parties"][token] = record

    for row in await conn.fetch(
        "SELECT party_id, name, title, phone, mobile, email FROM party_contacts"
    ):
        snapshot["party_contacts"].setdefault(row["party_id"], set()).add(
            contact_key(dict(row))
        )
    for row in await conn.fetch(
        "SELECT party_id, label, address, city FROM party_addresses"
    ):
        snapshot["party_addresses"].setdefault(row["party_id"], set()).add(
            address_key(dict(row))
        )

    for row in await conn.fetch(
        """
        SELECT id, code, name, spec, unit, item_group, default_supplier_id,
               purchase_price, lead_days, aliases, source_ref
        FROM items
        WHERE deleted_at IS NULL
        """
    ):
        record = dict(row)
        record["aliases"] = list(record["aliases"] or [])
        snapshot["items"][record["source_ref"] or f"Item:{record['code']}"] = record

    for row in await conn.fetch(
        "SELECT id, code, name FROM warehouses WHERE deleted_at IS NULL"
    ):
        snapshot["warehouses"][row["code"]] = dict(row)

    for row in await conn.fetch(
        "SELECT item_id, warehouse_id, qty FROM stock_balances"
    ):
        snapshot["balances"][(row["item_id"], row["warehouse_id"])] = Decimal(row["qty"])

    for row in await conn.fetch("SELECT po_no FROM purchase_orders"):
        snapshot["po_nos"].add(row["po_no"])

    for row in await conn.fetch("SELECT id, name FROM projects"):
        snapshot["projects_by_name"][row["name"]] = row["id"]
    for row in await conn.fetch("SELECT project_id, title FROM tasks"):
        snapshot["project_tasks"].setdefault(row["project_id"], set()).add(row["title"])

    return snapshot


def contact_key(data: dict) -> tuple:
    return (
        _text(data.get("name")),
        _text(data.get("phone")),
        _text(data.get("mobile")),
        _text(data.get("email")),
    )


def address_key(data: dict) -> tuple:
    return (_text(data.get("label")), _text(data.get("address")), _text(data.get("city")))


# ============================================================
# 匯入
# ============================================================


def empty_report() -> dict[str, Any]:
    return {
        "parties": {
            "created": 0, "updated": 0, "unchanged": 0, "merged_groups": 0,
            "contacts_created": 0, "contacts_unchanged": 0, "contacts_without_links": 0,
            "contacts_skipped_empty": 0, "contacts_skipped_internal": 0,
            "contacts_internal": [], "contacts_fanout_top": [],
            "addresses_created": 0, "addresses_unchanged": 0,
            "addresses_without_links": 0, "addresses_skipped_empty": 0,
        },
        "items": {"created": 0, "updated": 0, "unchanged": 0, "skipped_no_code": 0},
        "warehouses": {"created": 0, "updated": 0, "unchanged": 0, "skipped_groups": 0},
        "stock": {"adjusted": 0, "unchanged": 0, "skipped_unresolved": 0},
        "projects": {
            "created": 0, "unchanged": 0,
            "tasks_created": 0, "tasks_unchanged": 0, "tasks_without_project": 0,
        },
        "purchase_orders": {
            "created": 0, "unchanged": 0, "skipped_draft": 0,
            "skipped_unresolved": 0, "skipped_no_lines": 0, "skipped_no_name": 0,
        },
        "resolver": {
            "party_exact_hit": 0, "party_fuzzy_hit": 0, "party_miss": 0,
            "item_exact_hit": 0, "item_fuzzy_hit": 0, "item_miss": 0,
        },
        "unresolved": {
            "suppliers": [], "items": [], "warehouses": [], "projects": [],
            # 同一組合併目標對到兩筆以上既有 party（要人去 merge_parties）
            "party_conflicts": [],
        },
        "skipped_test_records": {},
        # 去尾綴之前名稱就不同的合併組，要人眼看過
        "merge_review": [],
        # 單筆失敗不中斷整批；每一筆都記在這裡，最後 exit code 非 0
        "errors": [],
    }


class Importer:
    """一次匯入的狀態機：吃 service 門面與 snapshot，邊寫邊更新 snapshot

    每個 `import_*` 都只認 snapshot，不自己去查資料庫，所以重跑第二次讀到的
    是同一份既有狀態，統計就會全部落在 unchanged。
    """

    def __init__(
        self,
        services,
        snapshot: dict,
        actor_user_id: int | None = None,
        dry_run: bool = False,
        internal_contact_threshold: int = DEFAULT_INTERNAL_CONTACT_THRESHOLD,
    ) -> None:
        self.services = services
        self.snapshot = snapshot
        self.actor_user_id = actor_user_id
        self.dry_run = dry_run
        self.internal_contact_threshold = internal_contact_threshold
        self.report = empty_report()

    # ── 寫入門面 ──

    async def _write(self, name: str, *args, **kwargs) -> dict:
        """dry-run 只回一個假 id，讓後面的步驟還能接得下去

        沒指定 `actor_user_id` / `via` 的寫入一律補上稽核參數
        （`create_task` 這種不吃稽核參數的要自己傳 `audit=False`）。
        """
        if kwargs.pop("audit", True):
            kwargs.setdefault("actor_user_id", self.actor_user_id)
            kwargs.setdefault("via", "import")
        if self.dry_run:
            return {"id": uuid4()}
        return await getattr(self.services, name)(*args, **kwargs)

    def _note(self, bucket: str, value: str) -> None:
        target = self.report["unresolved"][bucket]
        if value not in target:
            target.append(value)

    async def _guard(self, doctype: str, name: str, coro_fn, *args, **kwargs) -> bool:
        """跑一筆；失敗就記進 `errors` 繼續跑下一筆，回傳有沒有成功

        一筆壞資料不該讓整批停在中間（停在中間才是最難收拾的狀態：
        資料庫已經寫了一半）。所有 errors 會讓行程的 exit code 變 1。
        """
        try:
            await coro_fn(*args, **kwargs)
            return True
        except Exception as exc:  # noqa: BLE001 - 故意吃掉，記錄後繼續
            logger.warning("匯入 %s「%s」失敗：%s", doctype, name, exc)
            self.report["errors"].append(
                {
                    "doctype": doctype,
                    "name": name,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return False

    # ── 往來對象 ──

    async def import_parties(self, data: dict) -> None:
        groups = build_party_groups(data.get("Supplier") or [], data.get("Customer") or [])
        report = self.report["parties"]
        report["merged_groups"] = sum(
            1 for g in groups if g["is_supplier"] and g["is_customer"]
        )

        for group in groups:
            if group["needs_review"]:
                self.report["merge_review"].append(
                    {"name": group["name"], "sources": group["source_tokens"]}
                )
            await self._guard("Supplier/Customer", group["name"], self._party_one, group)

        await self._import_links(
            data.get("Contact") or [], contact_payload, contact_key,
            "party_contacts", "add_contact", "contacts",
        )
        await self._import_links(
            data.get("Address") or [], address_payload, address_key,
            "party_addresses", "add_address", "addresses",
        )

    async def _party_one(self, group: dict) -> None:
        report = self.report["parties"]
        payload = {
            "name": group["name"],
            "short_name": group["short_name"],
            "aliases": group["aliases"],
            "is_supplier": group["is_supplier"],
            "is_customer": group["is_customer"],
            "source_ref": group["source_ref"],
        }
        # 這一組的來源 token 可能分別對到不同的既有 party（上一次匯入時
        # 兩家還沒併在一起）。這種要人去跑 merge_parties，腳本不自己猜：
        # 先更新第一筆，把衝突記進 unresolved 讓人看。
        matched = []
        for token in group["source_tokens"]:
            party = self.snapshot["parties"].get(token)
            if party is not None and party["id"] not in [m["id"] for m in matched]:
                matched.append(party)
        if len(matched) > 1:
            self.report["unresolved"]["party_conflicts"].append(
                {
                    "name": group["name"],
                    "source_ref": group["source_ref"],
                    "party_ids": [str(m["id"]) for m in matched],
                }
            )

        existing = matched[0] if matched else None
        if existing is None:
            row = await self._write("create_party", payload)
            record = {**payload, "id": row["id"]}
            report["created"] += 1
        else:
            changes = party_changes(existing, payload)
            if changes:
                await self._write(
                    "update_party", existing["id"], changes
                )
                record = {**existing, **changes}
                report["updated"] += 1
            else:
                record = existing
                report["unchanged"] += 1
        for token in group["source_tokens"]:
            self.snapshot["parties"][token] = record

    async def _import_links(
        self, rows, to_payload, to_key, bucket, writer, label
    ) -> None:
        """Contact 與 Address 共用：依 Dynamic Link 掛到 party，重複的不再建"""
        report = self.report["parties"]
        for row in rows:
            targets = []
            for token in link_tokens(row):
                party = self.snapshot["parties"].get(token)
                if party is not None and party["id"] not in [t["id"] for t in targets]:
                    targets.append(party)
            if not targets:
                report[f"{label}_without_links"] += 1
                continue
            payload = to_payload(row)
            if payload is None:
                report[f"{label}_skipped_empty"] += 1
                continue
            if label == "contacts" and len(targets) >= self.internal_contact_threshold:
                # ERPNext 把擎添自家業務也掛成往來對象的 Contact，一個人可以掛幾百家。
                # 完全沒有聯絡方式的，就是內部人員而不是廠商窗口：整筆跳過。
                # 不跳過的話這些名字會進 party_contacts.name 的 trgm 索引，
                # 用人名去 resolve_party 會一次跳出幾百個候選（實測是 AmbiguousError）。
                if not any(payload.get(f) for f in ("phone", "mobile", "email")):
                    report["contacts_skipped_internal"] += 1
                    report["contacts_internal"].append(
                        {"name": _text(row.get("name")) or payload["name"],
                         "parties": len(targets)}
                    )
                    continue
                # 有聯絡方式的照掛，只點名讓執行的人看見
                report["contacts_fanout_top"].append(
                    {"name": payload["name"], "parties": len(targets)}
                )
            key = to_key(payload)
            for party in targets:
                seen = self.snapshot[bucket].setdefault(party["id"], set())
                if key in seen:
                    report[f"{label}_unchanged"] += 1
                    continue
                ok = await self._guard(
                    "Contact" if label == "contacts" else "Address",
                    f"{payload['name'] if label == 'contacts' else payload['address']}"
                    f" → {party['name']}",
                    self._write, writer, party["id"], payload,
                )
                if not ok:
                    continue
                seen.add(key)
                report[f"{label}_created"] += 1

    # ── 物料 ──

    async def import_items(self, data: dict) -> None:
        prices = buying_prices(data.get("Item Price") or [])
        report = self.report["items"]
        for row in data.get("Item") or []:
            code = _text(row.get("item_code")) or _text(row.get("name"))
            if not code:
                report["skipped_no_code"] += 1
                continue
            await self._guard("Item", code, self._item_one, row, code, prices)

    async def _item_one(self, row: dict, code: str, prices: dict) -> None:
        report = self.report["items"]
        name = _text(row.get("item_name")) or code
        spec = _text(row.get("description"))
        payload = {
            "code": code,
            "name": name,
            "spec": spec if spec and spec != name else None,
            "unit": _text(row.get("stock_uom")) or None,
            "item_group": _text(row.get("item_group")) or None,
            "default_supplier_id": await self._item_default_supplier(row),
            "purchase_price": prices.get(code),
            # 前置期 0 天不是有意義的值，當成沒填
            "lead_days": int(row["lead_time_days"]) if row.get("lead_time_days") else None,
            "aliases": [a for a in dedupe([name]) if a != code],
            "source_ref": f"Item:{code}",
        }
        token = payload["source_ref"]
        existing = self.snapshot["items"].get(token)
        if existing is None:
            written = await self._write("create_item", payload)
            self.snapshot["items"][token] = {**payload, "id": written["id"]}
            report["created"] += 1
            return
        changes = item_changes(existing, payload)
        if changes:
            await self._write("update_item", existing["id"], changes)
            self.snapshot["items"][token] = {**existing, **changes}
            report["updated"] += 1
        else:
            report["unchanged"] += 1

    async def _item_default_supplier(self, row: dict):
        """Item Default 的預設供應商 → party id；解析不到記進 unresolved"""
        raw = ""
        for default in row.get("item_defaults") or []:
            raw = _text(default.get("default_supplier"))
            if raw:
                break
        if not raw:
            return None
        party = await self._resolve_party(raw)
        return party["id"] if party else None

    async def _resolve_party(self, raw: str):
        """先用 source_ref 精確命中，落空才走 service 的模糊解析"""
        resolver = self.report["resolver"]
        party = self.snapshot["parties"].get(f"Supplier:{raw}") or self.snapshot[
            "parties"
        ].get(f"Customer:{raw}")
        if party is not None:
            resolver["party_exact_hit"] += 1
            return party
        try:
            found = await self.services.resolve_party(display_name(raw), role="supplier")
        except self.services.resolve_errors:
            resolver["party_miss"] += 1
            self._note("suppliers", raw)
            return None
        resolver["party_fuzzy_hit"] += 1
        return found

    async def _resolve_item(self, code: str):
        resolver = self.report["resolver"]
        item = self.snapshot["items"].get(f"Item:{code}")
        if item is not None:
            resolver["item_exact_hit"] += 1
            return item
        try:
            found = await self.services.resolve_item(code)
        except self.services.resolve_errors:
            resolver["item_miss"] += 1
            self._note("items", code)
            return None
        resolver["item_fuzzy_hit"] += 1
        return found

    # ── 倉庫 ──

    async def import_warehouses(self, data: dict) -> None:
        report = self.report["warehouses"]
        for row in data.get("Warehouse") or []:
            if row.get("is_group"):
                report["skipped_groups"] += 1
                continue
            code = warehouse_code(row)
            if not code:
                continue
            await self._guard("Warehouse", code, self._warehouse_one, code)

    async def _warehouse_one(self, code: str) -> None:
            report = self.report["warehouses"]
            payload = {"code": code, "name": code}
            existing = self.snapshot["warehouses"].get(code)
            if existing is None:
                written = await self._write(
                    "create_warehouse", payload
                )
                self.snapshot["warehouses"][code] = {**payload, "id": written["id"]}
                report["created"] += 1
            elif _text(existing.get("name")) != payload["name"]:
                await self._write(
                    "update_warehouse", existing["id"], {"name": payload["name"]},
                )
                self.snapshot["warehouses"][code] = {**existing, "name": payload["name"]}
                report["updated"] += 1
            else:
                report["unchanged"] += 1

    # ── 庫存 ──

    async def import_stock(self, data: dict) -> None:
        """Bin 的 actual_qty 當目標餘額，只補「目標 − 現有」的差額"""
        report = self.report["stock"]
        erp_warehouses = {
            _text(w.get("name")): warehouse_code(w)
            for w in data.get("Warehouse") or []
            if not w.get("is_group")
        }
        for row in data.get("Bin") or []:
            code = _text(row.get("item_code"))
            await self._guard("Bin", code, self._bin_one, row, code, erp_warehouses)

    async def _bin_one(self, row: dict, code: str, erp_warehouses: dict) -> None:
        report = self.report["stock"]
        item = await self._resolve_item(code) if code else None
        if item is None:
            report["skipped_unresolved"] += 1
            return
        warehouse = self.snapshot["warehouses"].get(
            erp_warehouses.get(_text(row.get("warehouse")), "")
        )
        if warehouse is None:
            self._note("warehouses", _text(row.get("warehouse")))
            report["skipped_unresolved"] += 1
            return
        target = Decimal(str(row.get("actual_qty") or 0))
        slot = (item["id"], warehouse["id"])
        delta = target - self.snapshot["balances"].get(slot, Decimal(0))
        if delta == 0:
            report["unchanged"] += 1
            return
        await self._write(
            "adjust_stock",
            item["id"],
            warehouse["id"],
            delta,
            reason="import",
            note=f"ERPNext Bin 初始餘額：{code} @ {_text(row.get('warehouse'))}",
        )
        self.snapshot["balances"][slot] = target
        report["adjusted"] += 1

    # ── 專案與任務 ──

    async def import_projects(self, data: dict) -> None:
        report = self.report["projects"]
        erp_projects: dict[str, Any] = {}
        for row in data.get("Project") or []:
            name = _text(row.get("project_name")) or _text(row.get("name"))
            if not name:
                continue
            await self._guard("Project", name, self._project_one, row, name, erp_projects)

        for row in data.get("Task") or []:
            project_id = erp_projects.get(_text(row.get("project")))
            title = _text(row.get("subject")) or _text(row.get("name"))
            if project_id is None or not title:
                report["tasks_without_project"] += 1
                continue
            seen = self.snapshot["project_tasks"].setdefault(project_id, set())
            if title in seen:
                report["tasks_unchanged"] += 1
                continue
            ok = await self._guard(
                "Task",
                title,
                self._write,
                "create_task",
                project_id,
                {
                    "title": title,
                    "description": _text(row.get("description")) or None,
                    "status": TASK_STATUS.get(_text(row.get("status")), "todo"),
                    "due_date": to_date(row.get("exp_end_date")),
                },
                audit=False,
            )
            if not ok:
                continue
            seen.add(title)
            report["tasks_created"] += 1

    async def _project_one(self, row: dict, name: str, erp_projects: dict) -> None:
        report = self.report["projects"]
        existing = self.snapshot["projects_by_name"].get(name)
        if existing is None:
            written = await self._write(
                "create_project",
                {
                    "name": name,
                    "status": PROJECT_STATUS.get(_text(row.get("status")), "active"),
                    "start_date": to_date(row.get("expected_start_date")),
                    "end_date": to_date(row.get("expected_end_date")),
                    "description": _text(row.get("notes")) or None,
                },
                created_by=self.actor_user_id,
                audit=False,
            )
            project_id = written["id"]
            self.snapshot["projects_by_name"][name] = project_id
            report["created"] += 1
        else:
            project_id = existing
            report["unchanged"] += 1
        erp_projects[_text(row.get("name"))] = project_id

    # ── 採購單 ──

    async def import_purchase_orders(self, data: dict) -> None:
        report = self.report["purchase_orders"]
        erp_projects = {
            _text(p.get("name")): self.snapshot["projects_by_name"].get(
                _text(p.get("project_name")) or _text(p.get("name"))
            )
            for p in data.get("Project") or []
        }
        for row in data.get("Purchase Order") or []:
            po_no = _text(row.get("name"))
            if not po_no:
                # 沒有單號的不能匯（po_no 是 NOT NULL 也是冪等 key），單獨計數
                report["skipped_no_name"] += 1
                continue
            if po_no in self.snapshot["po_nos"]:
                report["unchanged"] += 1
                continue
            await self._guard("Purchase Order", po_no, self._po_one, row, po_no, erp_projects)

    async def _po_one(self, row: dict, po_no: str, erp_projects: dict) -> None:
        report = self.report["purchase_orders"]
        raw_lines = row.get("items") or []
        total = sum((Decimal(str(x.get("qty") or 0)) for x in raw_lines), Decimal(0))
        received = sum(
            (Decimal(str(x.get("received_qty") or 0)) for x in raw_lines), Decimal(0)
        )
        status = po_status(row, received, total)
        if status is None:
            report["skipped_draft"] += 1
            return

        supplier = await self._resolve_party(_text(row.get("supplier")))
        if supplier is None:
            report["skipped_unresolved"] += 1
            return

        lines, unresolved = [], False
        for index, raw_line in enumerate(raw_lines):
            qty = Decimal(str(raw_line.get("qty") or 0))
            if qty <= 0:
                continue
            item = await self._resolve_item(_text(raw_line.get("item_code")))
            if item is None:
                unresolved = True
                break
            description = _text(raw_line.get("description")) or _text(
                raw_line.get("item_name")
            )
            lines.append(
                {
                    "item_id": item["id"],
                    "description": description or None,
                    "qty": qty,
                    # rate 是 0 就存 0（代表不計價），不要清成 NULL
                    "unit_price": to_decimal(raw_line.get("rate")),
                    "received_qty": min(
                        Decimal(str(raw_line.get("received_qty") or 0)), qty
                    ),
                    "sort_order": index,
                }
            )
        if unresolved:
            report["skipped_unresolved"] += 1
            return
        if not lines:
            report["skipped_no_lines"] += 1
            return

        await self._write(
            "create_purchase_order",
            {
                "po_no": po_no,
                "supplier_id": supplier["id"],
                "project_id": erp_projects.get(_text(row.get("project"))),
                "status": status,
                "order_date": to_date(row.get("transaction_date")),
                "expected_date": to_date(row.get("schedule_date")),
                "notes": f"ERPNext {po_no}",
                "lines": lines,
            },
        )
        self.snapshot["po_nos"].add(po_no)
        report["created"] += 1


def warehouse_code(row: dict) -> str:
    """倉庫代碼用 ERPNext 的 warehouse_name（`<倉名> - <公司名>` 的前半）"""
    return _text(row.get("warehouse_name")) or _text(row.get("name"))


def buying_prices(rows: list[dict]) -> dict[str, Decimal]:
    """Item Price 裡 buying=1 的採購價，同料號取 valid_from 最新的那筆"""
    best: dict[str, tuple[str, Decimal]] = {}
    for row in rows:
        if not row.get("buying"):
            continue
        code = _text(row.get("item_code"))
        rate = to_decimal(row.get("price_list_rate"))
        # 採購價 0 等於沒填價（ERPNext 建物料時的預設值），不要寫進主檔
        if not code or rate is None or rate == 0:
            continue
        valid_from = _text(row.get("valid_from"))
        current = best.get(code)
        if current is None or valid_from >= current[0]:
            best[code] = (valid_from, rate)
    return {code: rate for code, (_valid, rate) in best.items()}


def party_changes(existing: dict, payload: dict) -> dict:
    """只更新「有值且真的不一樣」的欄位；布林旗標只加不減"""
    changes: dict[str, Any] = {}
    for field in ("name", "short_name", "source_ref"):
        value = payload.get(field)
        if value and value != existing.get(field):
            changes[field] = value
    for flag in ("is_supplier", "is_customer"):
        if payload.get(flag) and not existing.get(flag):
            changes[flag] = True
    merged = dedupe(list(existing.get("aliases") or []) + list(payload.get("aliases") or []))
    if merged != list(existing.get("aliases") or []):
        changes["aliases"] = merged
    return changes


def item_changes(existing: dict, payload: dict) -> dict:
    changes: dict[str, Any] = {}
    for field in ("name", "spec", "unit", "item_group", "lead_days", "source_ref"):
        value = payload.get(field)
        if value not in (None, "") and value != existing.get(field):
            changes[field] = value
    for field in ("default_supplier_id", "purchase_price"):
        value = payload.get(field)
        if value is None:
            continue
        current = existing.get(field)
        if field == "purchase_price" and current is not None:
            current = Decimal(str(current))
        if value != current:
            changes[field] = value
    merged = dedupe(list(existing.get("aliases") or []) + list(payload.get("aliases") or []))
    if merged != list(existing.get("aliases") or []):
        changes["aliases"] = merged
    return changes


# ============================================================
# 一次匯入
# ============================================================


async def run_import(
    src: Path,
    services,
    snapshot: dict,
    actor_user_id: int | None = None,
    dry_run: bool = False,
    only: list[str] | None = None,
    internal_contact_threshold: int = DEFAULT_INTERNAL_CONTACT_THRESHOLD,
    importer: "Importer | None" = None,
) -> dict[str, Any]:
    """跑一次匯入，回傳 import-report 的內容

    呼叫端可以先自己建 `Importer` 傳進來——這樣就算中途整個炸掉，
    呼叫端手上還有那個 importer 的 `report`，可以把已經做到的部分寫出去。
    """
    data, skipped_tests = strip_test_records(load_all(Path(src)))
    if importer is None:
        importer = Importer(
            services,
            snapshot,
            actor_user_id=actor_user_id,
            dry_run=dry_run,
            internal_contact_threshold=internal_contact_threshold,
        )
    importer.report["skipped_test_records"] = skipped_tests
    sections = [s for s in SECTIONS if only is None or s in only]

    started = datetime.now(timezone.utc)
    # metadata 先寫進去：載入之後才爆掉的話，殘報告至少看得出是哪一次跑、
    # 來源有幾筆。（載入來源本身就失敗的話連這裡都到不了，殘報告只有空桶。）
    importer.report.update(
        {
            "src": str(src),
            "dry_run": dry_run,
            "only": sections,
            "actor_user_id": actor_user_id,
            "internal_contact_threshold": internal_contact_threshold,
            "started_at": started.isoformat(),
            "finished_at": None,
            "source_counts": {k: len(v) for k, v in data.items()},
        }
    )
    for section in sections:
        if section == "parties":
            await importer.import_parties(data)
        elif section == "items":
            await importer.import_items(data)
        elif section == "stock":
            await importer.import_warehouses(data)
            await importer.import_stock(data)
        elif section == "projects":
            await importer.import_projects(data)
        elif section == "purchase_orders":
            await importer.import_purchase_orders(data)

    importer.report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return importer.report


class ActorNotFoundError(Exception):
    """`--actor-user-id` 指到不存在的使用者"""


async def ensure_actor(conn, actor_user_id: int | None) -> None:
    """`--actor-user-id` 一定要對得上 users，否則稽核的 actor 會是假的

    不擋的話 `created_by` 的外鍵會在第一筆寫入時才炸，那時候已經開始寫了。
    """
    if actor_user_id is None:
        return
    found = await conn.fetchval("SELECT 1 FROM users WHERE id = $1", actor_user_id)
    if not found:
        raise ActorNotFoundError(
            f"--actor-user-id {actor_user_id} 在 users 表裡找不到；"
            "請用真的使用者 id，或不要帶這個參數（稽核的 actor 會是 NULL）"
        )


class BackendServices:
    """真跑時的門面：綁到後端 service 函式（所以稽核會記 via=import）"""

    def __init__(self) -> None:
        from ching_tech_os.services import (  # noqa: PLC0415
            erp,
            erp_inventory,
            erp_parties,
            erp_purchasing,
            project,
        )

        self.resolve_errors = (erp.NotFoundError, erp.AmbiguousError)
        self.resolve_party = erp.resolve_party
        self.resolve_item = erp.resolve_item
        self.create_party = erp_parties.create_party
        self.update_party = erp_parties.update_party
        self.add_contact = erp_parties.add_contact
        self.add_address = erp_parties.add_address
        self.create_item = erp_inventory.create_item
        self.update_item = erp_inventory.update_item
        self.create_warehouse = erp_inventory.create_warehouse
        self.update_warehouse = erp_inventory.update_warehouse
        self.adjust_stock = erp_inventory.adjust_stock
        self.create_purchase_order = erp_purchasing.create_purchase_order
        self.create_project = project.create_project
        self.create_task = project.create_task


# ============================================================
# CLI
# ============================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--src", required=True, help="ERPNext 備份的 doctypes 目錄")
    parser.add_argument(
        "--dry-run", action="store_true", help="只印統計不寫入（仍會讀資料庫比對）"
    )
    parser.add_argument(
        "--only", nargs="+", choices=list(SECTIONS), help="只跑這些區塊"
    )
    parser.add_argument(
        "--db-name", help="覆寫 DB_NAME（其餘連線參數照 config.py 的 env 取法）"
    )
    parser.add_argument(
        "--actor-user-id", type=int, help="稽核的 actor_user_id（預設 NULL）"
    )
    parser.add_argument(
        "--internal-contact-threshold",
        type=int,
        default=DEFAULT_INTERNAL_CONTACT_THRESHOLD,
        help="Contact 掛到幾家以上且完全沒有聯絡方式就視為內部人員跳過"
        f"（預設 {DEFAULT_INTERNAL_CONTACT_THRESHOLD}）",
    )
    parser.add_argument(
        "--report", default="import-report.json", help="匯入報告輸出路徑"
    )
    return parser.parse_args(argv)


def summarize(report: dict) -> str:
    lines = [f"來源：{report['src']}（dry-run={report['dry_run']}）"]
    for section in ("parties", "items", "warehouses", "stock", "projects", "purchase_orders"):
        stats = ", ".join(
            f"{k}={v}" for k, v in report[section].items() if v and not isinstance(v, list)
        )
        lines.append(f"  {section}: {stats or '無異動'}")
    threshold = report.get("internal_contact_threshold", DEFAULT_INTERNAL_CONTACT_THRESHOLD)

    def _top(rows):
        return ", ".join(
            f"{x['name']}({x['parties']})"
            for x in sorted(rows, key=lambda x: -x["parties"])[:5]
        )

    internal = report["parties"]["contacts_internal"]
    if internal:
        lines.append(
            f"  判定為內部人員而跳過的聯絡人（{len(internal)}，掛 {threshold} 家以上"
            f"且無聯絡方式）：{_top(internal)}"
        )
    fanout = report["parties"]["contacts_fanout_top"]
    if fanout:
        lines.append(
            f"  掛在 {threshold} 家以上但有聯絡方式（照掛，{len(fanout)}）：{_top(fanout)}"
        )
    tests = report.get("skipped_test_records") or {}
    if tests:
        lines.append(
            f"  略過的 {TEST_RECORD_PREFIX} 測試資料（{sum(tests.values())}）："
            + ", ".join(f"{k}={v}" for k, v in tests.items())
        )
    resolver = ", ".join(f"{k}={v}" for k, v in report["resolver"].items() if v)
    lines.append(f"  resolver: {resolver or '未使用'}")
    for bucket, values in report["unresolved"].items():
        if not values:
            continue
        shown = ", ".join(
            v if isinstance(v, str) else v.get("name", str(v)) for v in values[:10]
        )
        lines.append(f"  無法解析的 {bucket}（{len(values)}）：{shown}")
    review = report.get("merge_review") or []
    if review:
        lines.append(
            f"  合併後要人眼看過的（{len(review)}）："
            + ", ".join(x["name"] for x in review[:10])
        )
    errors = report.get("errors") or []
    if errors:
        lines.append(f"  失敗（{len(errors)}，已跳過繼續跑）：")
        for err in errors[:10]:
            lines.append(f"    {err['doctype']}「{err['name']}」→ {err['error']}")
    return "\n".join(lines)


async def _main(args: argparse.Namespace) -> int:
    from ching_tech_os.database import (  # noqa: PLC0415
        close_db_pool,
        get_connection,
        init_db_pool,
    )

    await init_db_pool()
    importer: Importer | None = None
    try:
        async with get_connection() as conn:
            await ensure_actor(conn, args.actor_user_id)
            snapshot = await load_snapshot(conn)
        importer = Importer(
            BackendServices(),
            snapshot,
            actor_user_id=args.actor_user_id,
            dry_run=args.dry_run,
            internal_contact_threshold=args.internal_contact_threshold,
        )
        await run_import(
            src=Path(args.src),
            services=importer.services,
            snapshot=snapshot,
            actor_user_id=args.actor_user_id,
            dry_run=args.dry_run,
            only=args.only,
            internal_contact_threshold=args.internal_contact_threshold,
            importer=importer,
        )
    finally:
        await close_db_pool()
        # 區塊跑到一半爆掉時，把各桶的計數寫出來——不然就不知道資料庫被寫了多少。
        # 注意：`load_all()` 之前就爆掉（找不到檔、JSON 壞掉）時報告只有空桶，
        # 但那種情況本來也還沒開始寫資料庫。
        if importer is not None:
            write_report(Path(args.report), importer.report)

    report = importer.report
    print(summarize(report))
    print(f"報告：{args.report}")
    if report["errors"]:
        print(f"有 {len(report['errors'])} 筆失敗，見報告的 errors", file=sys.stderr)
        return 1
    return 0


def write_report(path: Path, report: dict) -> None:
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.db_name:
        # config.py 的 settings 是 import 時建立的單例，所以要在 import 之前設好
        os.environ["DB_NAME"] = args.db_name
    src = Path(args.src)
    if not src.is_dir():
        print(f"找不到來源目錄：{src}", file=sys.stderr)
        return 2
    try:
        return asyncio.run(_main(args))
    except ActorNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
