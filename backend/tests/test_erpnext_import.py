"""ERPNext 匯入腳本測試（scripts/erpnext_import.py）

腳本不在 `src/` 底下（它是獨立執行的維運工具），所以用 importlib 從路徑載入。
純函式（名稱正規化、合併分組、狀態對應）直接測；寫入一律經過 service 門面，
測試塞假的門面進去驗「呼叫序與參數」，不碰資料庫。

fixture 是自己捏的小樣本（三家供應商，其中一家同時是客戶；兩個聯絡人、
兩個地址、兩個物料、一個倉、兩筆 Bin、一張採購單），不是正式備份。
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "erpnext_import.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("erpnext_import", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


imp = _load_module()


# ============================================================
# 假的 service 門面
# ============================================================


class FakeNotFound(Exception):
    pass


class FakeAmbiguous(Exception):
    pass


class FakeServices:
    """記錄呼叫序與參數；回傳長得像 service 的 dict"""

    def __init__(self, resolve_party_map=None, resolve_item_map=None):
        self.calls: list[tuple[str, tuple, dict]] = []
        self.resolve_errors = (FakeNotFound, FakeAmbiguous)
        self._resolve_party_map = resolve_party_map or {}
        self._resolve_item_map = resolve_item_map or {}

    def _record(self, name, args, kwargs):
        self.calls.append((name, args, kwargs))

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]

    def of(self, name) -> list[tuple[tuple, dict]]:
        return [(a, k) for n, a, k in self.calls if n == name]

    # ── 往來對象 ──
    async def create_party(self, data, **kw):
        self._record("create_party", (data,), kw)
        return {"id": uuid4(), **data}

    async def update_party(self, party_id, data, **kw):
        self._record("update_party", (party_id, data), kw)
        return {"id": party_id, **data}

    async def add_contact(self, party_id, data, **kw):
        self._record("add_contact", (party_id, data), kw)
        return {"id": uuid4(), **data}

    async def add_address(self, party_id, data, **kw):
        self._record("add_address", (party_id, data), kw)
        return {"id": uuid4(), **data}

    # ── 物料與倉庫 ──
    async def create_item(self, data, **kw):
        self._record("create_item", (data,), kw)
        return {"id": uuid4(), **data}

    async def update_item(self, item_id, data, **kw):
        self._record("update_item", (item_id, data), kw)
        return {"id": item_id, **data}

    async def create_warehouse(self, data, **kw):
        self._record("create_warehouse", (data,), kw)
        return {"id": uuid4(), **data}

    async def update_warehouse(self, warehouse_id, data, **kw):
        self._record("update_warehouse", (warehouse_id, data), kw)
        return {"id": warehouse_id, **data}

    async def adjust_stock(self, item_id, warehouse_id, qty_delta, **kw):
        self._record("adjust_stock", (item_id, warehouse_id, qty_delta), kw)
        return {"audit_id": uuid4()}

    # ── 採購 ──
    async def create_purchase_order(self, data, **kw):
        self._record("create_purchase_order", (data,), kw)
        return {"id": uuid4(), "po_no": data.get("po_no"), **data}

    # ── 專案 ──
    async def create_project(self, data, **kw):
        self._record("create_project", (data,), kw)
        return {"id": uuid4(), **data}

    async def create_task(self, project_id, data, **kw):
        self._record("create_task", (project_id, data), kw)
        return {"id": uuid4(), **data}

    # ── 模糊解析 ──
    async def resolve_party(self, query, role=None):
        self._record("resolve_party", (query,), {"role": role})
        hit = self._resolve_party_map.get(query)
        if hit is None:
            raise FakeNotFound(query)
        return hit

    async def resolve_item(self, query):
        self._record("resolve_item", (query,), {})
        hit = self._resolve_item_map.get(query)
        if hit is None:
            raise FakeNotFound(query)
        return hit


# ============================================================
# fixture：自己捏的小樣本
# ============================================================


def _supplier(name, **extra):
    return {
        "name": name,
        "supplier_name": name,
        "supplier_group": "All Supplier Groups",
        "supplier_type": "Company",
        "country": "Taiwan",
        "doctype": "Supplier",
        **extra,
    }


def _customer(name, **extra):
    return {
        "name": name,
        "customer_name": name,
        "customer_group": "All Customer Groups",
        "customer_type": "Company",
        "territory": "All Territories",
        "doctype": "Customer",
        **extra,
    }


def _link(doctype, link_name):
    return {"link_doctype": doctype, "link_name": link_name}


@pytest.fixture
def sample() -> dict:
    """三家供應商（甲鋼鐵同時是客戶）、兩聯絡人、兩地址、兩物料、一倉、兩 Bin、一張 PO"""
    return {
        "Supplier": [
            _supplier("SM9001 - 甲鋼鐵有限公司"),
            _supplier("SM9002 - 乙工業股份有限公司"),
            _supplier("SF9003 - 丙科技股份有限公司"),
        ],
        "Customer": [
            _customer("CM9001 - 甲鋼鐵有限公司"),
        ],
        "Contact": [
            {
                "name": "測試聯絡人甲",
                "first_name": "測試聯絡人甲",
                "full_name": "測試聯絡人甲",
                "phone": "02-0000-0000",
                "mobile_no": "0900000000",
                "email_id": "a@example.com",
                "designation": "業務",
                "is_primary_contact": 1,
                "phone_nos": [],
                "email_ids": [],
                "links": [_link("Supplier", "SM9001 - 甲鋼鐵有限公司")],
            },
            {
                # 沒有 links：略過並計數
                "name": "孤兒聯絡人",
                "first_name": "孤兒聯絡人",
                "full_name": "孤兒聯絡人",
                "phone": "02-0000-0001",
                "links": [],
            },
        ],
        "Address": [
            {
                "name": "SM9001 地址-計費",
                "address_title": "SM9001 地址",
                "address_type": "Billing",
                "address_line1": "台北市中正區測試路 1 號",
                "address_line2": "",
                "city": "台北市",
                "country": "Taiwan",
                "pincode": "243",
                "is_primary_address": 1,
                "links": [_link("Supplier", "SM9001 - 甲鋼鐵有限公司")],
            },
            {
                "name": "CM9001 地址-送貨",
                "address_title": "CM9001 地址",
                "address_type": "Shipping",
                "address_line1": "台北市板橋區測試路 2 號",
                "city": "新北市",
                "country": "Taiwan",
                "is_primary_address": 0,
                "links": [_link("Customer", "CM9001 - 甲鋼鐵有限公司")],
            },
        ],
        "Item": [
            {
                "item_code": "TEST-ITEM-001",
                "item_name": "測試物料甲",
                "item_group": "測試群組甲",
                "stock_uom": "Set",
                "description": "測試規格甲",
                "is_stock_item": 1,
                "lead_time_days": 7,
                "item_defaults": [
                    {
                        "company": "測試公司有限公司",
                        "default_warehouse": "測試主倉 - 測試公司",
                        "default_supplier": "SM9002 - 乙工業股份有限公司",
                    }
                ],
            },
            {
                "item_code": "TEST-ITEM-002",
                "item_name": "測試物料乙",
                "item_group": "測試群組乙",
                "stock_uom": "Set",
                "description": "測試物料乙",
                "is_stock_item": 1,
                "lead_time_days": 0,
                "item_defaults": [
                    {"company": "測試公司有限公司", "default_warehouse": "測試主倉 - 測試公司"}
                ],
            },
        ],
        "Item Price": [
            {
                "item_code": "TEST-ITEM-001",
                "price_list": "Standard Buying",
                "buying": 1,
                "selling": 0,
                "price_list_rate": 1250.0,
                "valid_from": "2026-01-01",
            },
            {
                "item_code": "TEST-ITEM-001",
                "price_list": "Standard Selling",
                "buying": 0,
                "selling": 1,
                "price_list_rate": 2000.0,
                "valid_from": "2026-01-01",
            },
        ],
        "Warehouse": [
            {"name": "測試群組倉 - 測試公司", "warehouse_name": "測試群組倉", "is_group": 1},
            {"name": "測試主倉 - 測試公司", "warehouse_name": "測試主倉", "is_group": 0},
        ],
        "Bin": [
            {"item_code": "TEST-ITEM-001", "warehouse": "測試主倉 - 測試公司", "actual_qty": 12.0},
            {"item_code": "TEST-ITEM-002", "warehouse": "測試主倉 - 測試公司", "actual_qty": 0.0},
        ],
        "Purchase Order": [
            {
                "name": "PUR-ORD-TEST-00001",
                "docstatus": 1,
                "status": "To Receive and Bill",
                "supplier": "SM9002 - 乙工業股份有限公司",
                "transaction_date": "2026-01-09",
                "schedule_date": "2026-01-13",
                "project": "PROJ-TEST-0001",
                "items": [
                    {
                        "item_code": "TEST-ITEM-001",
                        "item_name": "測試物料甲",
                        "description": "測試規格甲",
                        "qty": 4.0,
                        "rate": 1250.0,
                        "received_qty": 1.0,
                    }
                ],
            }
        ],
        "Project": [
            {"name": "PROJ-TEST-0001", "project_name": "測試專案甲", "status": "Open",
             "expected_start_date": "2026-01-09", "notes": "line6"},
        ],
        "Task": [
            {"name": "TASK-TEST-00001", "subject": "測試任務甲", "project": "PROJ-TEST-0001",
             "status": "Completed", "description": "測試說明"},
        ],
    }


@pytest.fixture
def src(tmp_path, sample) -> Path:
    out = tmp_path / "doctypes"
    out.mkdir()
    for doctype, rows in sample.items():
        (out / f"{doctype.replace(' ', '_')}.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
        )
    return out


def empty_snapshot() -> dict:
    return imp.empty_snapshot()


# ============================================================
# 名稱正規化與合併
# ============================================================


class TestNormalize:
    def test_strips_erpnext_code_prefix(self):
        assert imp.display_name("SM9001 - 甲鋼鐵有限公司") == "甲鋼鐵有限公司"
        assert imp.display_name("CM9009-1 - 丁資訊有限公司") == "丁資訊有限公司"
        assert imp.display_name("ACMECORP") == "ACMECORP"

    def test_normalize_drops_suffix_space_and_fullwidth(self):
        assert imp.normalize_party_name("SM9001 - 甲鋼鐵有限公司") == "甲鋼鐵"
        assert imp.normalize_party_name("CM9001 - 甲鋼鐵有限公司") == "甲鋼鐵"
        # 全形轉半形＋去空白
        assert imp.normalize_party_name("ＡＢＣ 工業 股份有限公司") == "abc工業"
        # 「公司」單獨結尾也要去掉
        assert imp.normalize_party_name("大大公司") == "大大"

    def test_short_name_is_none_when_no_suffix(self):
        assert imp.short_name_of("甲鋼鐵有限公司") == "甲鋼鐵"
        assert imp.short_name_of("ACMECORP") is None


class TestBuildPartyGroups:
    def test_merges_supplier_and_customer_into_one_party(self, sample):
        groups = imp.build_party_groups(sample["Supplier"], sample["Customer"])
        by_key = {g["key"]: g for g in groups}
        assert len(groups) == 3
        merged = by_key["甲鋼鐵"]
        assert merged["is_supplier"] and merged["is_customer"]
        assert merged["name"] == "甲鋼鐵有限公司"
        assert merged["short_name"] == "甲鋼鐵"
        assert merged["source_ref"] == (
            "Supplier:SM9001 - 甲鋼鐵有限公司;Customer:CM9001 - 甲鋼鐵有限公司"
        )
        assert merged["source_tokens"] == [
            "Supplier:SM9001 - 甲鋼鐵有限公司",
            "Customer:CM9001 - 甲鋼鐵有限公司",
        ]
        # aliases 收原始名稱與 short_name
        assert "SM9001 - 甲鋼鐵有限公司" in merged["aliases"]
        assert "CM9001 - 甲鋼鐵有限公司" in merged["aliases"]
        assert "甲鋼鐵" in merged["aliases"]

    def test_supplier_only_party_is_not_customer(self, sample):
        groups = {g["key"]: g for g in imp.build_party_groups(sample["Supplier"], sample["Customer"])}
        assert groups["乙工業"]["is_supplier"] is True
        assert groups["乙工業"]["is_customer"] is False
        assert groups["乙工業"]["source_ref"] == "Supplier:SM9002 - 乙工業股份有限公司"


# ============================================================
# 匯入：往來對象
# ============================================================


@pytest.mark.asyncio
class TestImportParties:
    async def test_creates_parties_contacts_addresses_via_import(self, sample):
        svc = FakeServices()
        importer = imp.Importer(svc, empty_snapshot(), actor_user_id=7)
        await importer.import_parties(sample)

        created = svc.of("create_party")
        assert len(created) == 3
        for _args, kwargs in created:
            assert kwargs["via"] == "import"
            assert kwargs["actor_user_id"] == 7

        # 聯絡人掛到合併後的那一家；孤兒聯絡人不進
        contacts = svc.of("add_contact")
        assert len(contacts) == 1
        assert contacts[0][0][1]["name"] == "測試聯絡人甲"
        assert contacts[0][0][1]["title"] == "業務"
        assert contacts[0][0][1]["is_primary"] is True
        assert contacts[0][1]["via"] == "import"

        # 兩個地址都掛到同一家（Supplier 端與 Customer 端合併了）
        addresses = svc.of("add_address")
        assert len(addresses) == 2
        assert addresses[0][0][0] == contacts[0][0][0]
        assert addresses[1][0][0] == contacts[0][0][0]

        rep = importer.report["parties"]
        assert rep["contacts_fanout_top"] == []   # 小樣本沒有超連的聯絡人
        assert rep["created"] == 3
        assert rep["merged_groups"] == 1
        assert rep["contacts_created"] == 1
        assert rep["contacts_without_links"] == 1
        assert rep["addresses_created"] == 2

    async def test_rerun_is_idempotent(self, sample):
        """第一次跑完把結果寫回 snapshot，第二次全部 unchanged、不呼叫任何寫入"""
        svc = FakeServices()
        snapshot = empty_snapshot()
        first = imp.Importer(svc, snapshot)
        await first.import_parties(sample)
        assert first.report["parties"]["created"] == 3

        svc2 = FakeServices()
        second = imp.Importer(svc2, snapshot)
        await second.import_parties(sample)
        assert svc2.of("create_party") == []
        assert svc2.of("update_party") == []
        assert svc2.of("add_contact") == []
        assert svc2.of("add_address") == []
        assert second.report["parties"]["unchanged"] == 3
        assert second.report["parties"]["created"] == 0

    async def test_existing_party_gets_non_empty_fields_updated(self, sample):
        snapshot = empty_snapshot()
        pid = uuid4()
        snapshot["parties"]["Supplier:SM9002 - 乙工業股份有限公司"] = {
            "id": pid,
            "name": "乙工業股份有限公司",
            "short_name": None,          # 空的 → 補上
            "aliases": [],
            "is_supplier": True,
            "is_customer": False,
            "source_ref": "Supplier:SM9002 - 乙工業股份有限公司",
        }
        svc = FakeServices()
        importer = imp.Importer(svc, snapshot)
        await importer.import_parties(
            {"Supplier": [sample["Supplier"][1]], "Customer": [], "Contact": [], "Address": []}
        )
        updates = svc.of("update_party")
        assert len(updates) == 1
        (party_id, data), kwargs = updates[0]
        assert party_id == pid
        assert data["short_name"] == "乙工業"
        assert "SM9002 - 乙工業股份有限公司" in data["aliases"]
        # 沒有值的欄位不會被清成 None
        assert "name" not in data or data["name"] == "乙工業股份有限公司"
        assert kwargs["via"] == "import"


# ============================================================
# 匯入：物料、倉庫、庫存
# ============================================================


@pytest.mark.asyncio
class TestImportItemsAndStock:
    async def test_item_maps_fields_price_and_default_supplier(self, sample):
        svc = FakeServices()
        snapshot = empty_snapshot()
        supplier_id = uuid4()
        snapshot["parties"]["Supplier:SM9002 - 乙工業股份有限公司"] = {
            "id": supplier_id, "name": "乙工業股份有限公司", "short_name": "乙工業",
            "aliases": [], "is_supplier": True, "is_customer": False,
            "source_ref": "Supplier:SM9002 - 乙工業股份有限公司",
        }
        importer = imp.Importer(svc, snapshot)
        await importer.import_items(sample)

        created = {a[0]["code"]: a[0] for a, _k in svc.of("create_item")}
        bearing = created["TEST-ITEM-001"]
        assert bearing["name"] == "測試物料甲"
        assert bearing["unit"] == "Set"
        assert bearing["item_group"] == "測試群組甲"
        assert bearing["spec"] == "測試規格甲"
        assert bearing["lead_days"] == 7
        assert bearing["purchase_price"] == Decimal("1250.0")   # buying=1 才算採購價
        assert bearing["default_supplier_id"] == supplier_id
        assert bearing["source_ref"] == "Item:TEST-ITEM-001"

        # description 與 item_name 相同時不重複塞進 spec；lead_time_days=0 視為未填
        plug = created["TEST-ITEM-002"]
        assert plug["spec"] is None
        assert plug["lead_days"] is None
        assert plug["purchase_price"] is None
        assert plug["default_supplier_id"] is None
        # 完全沒用到模糊解析（source_ref 直接命中）
        assert svc.of("resolve_party") == []

    async def test_unresolvable_default_supplier_is_listed(self, sample):
        svc = FakeServices()
        importer = imp.Importer(svc, empty_snapshot())
        await importer.import_items(sample)
        assert svc.of("resolve_party")   # 落到模糊解析
        assert "SM9002 - 乙工業股份有限公司" in importer.report["unresolved"]["suppliers"]
        assert importer.report["items"]["created"] == 2

    async def test_fuzzy_resolver_hit_is_counted(self, sample):
        target = {"id": uuid4(), "name": "乙工業股份有限公司"}
        svc = FakeServices(resolve_party_map={"乙工業股份有限公司": target})
        importer = imp.Importer(svc, empty_snapshot())
        await importer.import_items(sample)
        created = {a[0]["code"]: a[0] for a, _k in svc.of("create_item")}
        assert created["TEST-ITEM-001"]["default_supplier_id"] == target["id"]
        assert importer.report["resolver"]["party_fuzzy_hit"] == 1
        assert importer.report["resolver"]["party_miss"] == 0

    async def test_warehouse_skips_groups(self, sample):
        svc = FakeServices()
        importer = imp.Importer(svc, empty_snapshot())
        await importer.import_warehouses(sample)
        created = [a[0] for a, _k in svc.of("create_warehouse")]
        assert created == [{"code": "測試主倉", "name": "測試主倉"}]
        assert importer.report["warehouses"]["created"] == 1
        assert importer.report["warehouses"]["skipped_groups"] == 1

    async def test_stock_writes_delta_and_skips_when_matching(self, sample):
        svc = FakeServices()
        snapshot = empty_snapshot()
        importer = imp.Importer(svc, snapshot)
        await importer.import_items(sample)
        await importer.import_warehouses(sample)
        await importer.import_stock(sample)

        adjusts = svc.of("adjust_stock")
        # 只有非零的那筆
        assert len(adjusts) == 1
        (item_id, warehouse_id, delta), kwargs = adjusts[0]
        assert delta == Decimal("12")
        assert kwargs["reason"] == "import"
        assert kwargs["via"] == "import"
        assert importer.report["stock"]["adjusted"] == 1
        assert importer.report["stock"]["unchanged"] == 1

        # 第二次：餘額已經對上，一筆都不寫
        svc2 = FakeServices()
        second = imp.Importer(svc2, snapshot)
        await second.import_stock(sample)
        assert svc2.of("adjust_stock") == []
        assert second.report["stock"]["unchanged"] == 2


# ============================================================
# 匯入：採購單與專案
# ============================================================


@pytest.mark.asyncio
class TestImportPurchaseOrders:
    async def _prepared(self, sample, svc):
        importer = imp.Importer(svc, empty_snapshot())
        await importer.import_parties(sample)
        await importer.import_items(sample)
        await importer.import_warehouses(sample)
        await importer.import_projects(sample)
        return importer

    async def test_keeps_erpnext_po_no_and_received_qty(self, sample):
        svc = FakeServices()
        importer = await self._prepared(sample, svc)
        await importer.import_purchase_orders(sample)

        created = svc.of("create_purchase_order")
        assert len(created) == 1
        (data,), kwargs = created[0]
        assert data["po_no"] == "PUR-ORD-TEST-00001"
        assert data["status"] == "partial"        # received_qty 1 < qty 4
        assert str(data["order_date"]) == "2026-01-09"
        assert str(data["expected_date"]) == "2026-01-13"
        assert data["project_id"] is not None
        assert len(data["lines"]) == 1
        line = data["lines"][0]
        assert line["qty"] == Decimal("4.0")
        assert line["received_qty"] == Decimal("1.0")
        assert line["unit_price"] == Decimal("1250.0")
        assert kwargs["via"] == "import"
        assert importer.report["purchase_orders"]["created"] == 1

    async def test_draft_is_skipped_cancelled_is_imported(self, sample):
        sample = dict(sample)
        sample["Purchase Order"] = [
            {**sample["Purchase Order"][0], "name": "PO-DRAFT", "docstatus": 0, "status": "Draft"},
            {**sample["Purchase Order"][0], "name": "PO-CANCEL", "docstatus": 2, "status": "Cancelled"},
            {**sample["Purchase Order"][0], "name": "PO-DONE", "docstatus": 1, "status": "Completed"},
        ]
        svc = FakeServices()
        importer = await self._prepared(sample, svc)
        await importer.import_purchase_orders(sample)
        made = {a[0]["po_no"]: a[0]["status"] for a, _k in svc.of("create_purchase_order")}
        assert made == {"PO-CANCEL": "cancelled", "PO-DONE": "received"}
        assert importer.report["purchase_orders"]["skipped_draft"] == 1

    async def test_rerun_skips_existing_po_no(self, sample):
        svc = FakeServices()
        importer = await self._prepared(sample, svc)
        await importer.import_purchase_orders(sample)
        svc2 = FakeServices()
        second = imp.Importer(svc2, importer.snapshot)
        await second.import_purchase_orders(sample)
        assert svc2.of("create_purchase_order") == []
        assert second.report["purchase_orders"]["unchanged"] == 1

    async def test_unresolvable_item_is_listed(self, sample):
        svc = FakeServices()
        importer = imp.Importer(svc, empty_snapshot())
        await importer.import_parties(sample)
        await importer.import_purchase_orders(sample)   # 沒匯物料
        assert "TEST-ITEM-001" in importer.report["unresolved"]["items"]
        assert svc.of("create_purchase_order") == []
        assert importer.report["purchase_orders"]["skipped_unresolved"] == 1


@pytest.mark.asyncio
class TestImportProjects:
    async def test_creates_projects_and_tasks_with_status_mapping(self, sample):
        svc = FakeServices()
        importer = imp.Importer(svc, empty_snapshot())
        await importer.import_projects(sample)
        (data,), _kw = svc.of("create_project")[0]
        assert data["name"] == "測試專案甲"
        assert data["status"] == "active"
        (project_id, task), _kw = svc.of("create_task")[0]
        assert task["title"] == "測試任務甲"
        assert task["status"] == "done"
        assert importer.report["projects"]["created"] == 1
        assert importer.report["projects"]["tasks_created"] == 1

    async def test_existing_project_name_is_deduped(self, sample):
        snapshot = empty_snapshot()
        existing = uuid4()
        snapshot["projects_by_name"]["測試專案甲"] = existing
        svc = FakeServices()
        importer = imp.Importer(svc, snapshot)
        await importer.import_projects(sample)
        assert svc.of("create_project") == []
        assert importer.report["projects"]["unchanged"] == 1
        # 任務仍掛到既有專案
        assert svc.of("create_task")[0][0][0] == existing


# ============================================================
# CLI 行為
# ============================================================


@pytest.mark.asyncio
class TestRunImport:
    async def test_dry_run_writes_nothing(self, src, sample):
        svc = FakeServices()
        report = await imp.run_import(
            src=src, services=svc, snapshot=empty_snapshot(), dry_run=True
        )
        assert svc.calls == []
        assert report["dry_run"] is True
        # 統計照算
        assert report["parties"]["created"] == 3
        assert report["items"]["created"] == 2
        assert report["purchase_orders"]["created"] == 1

    async def test_only_filter_runs_one_section(self, src):
        svc = FakeServices()
        report = await imp.run_import(
            src=src, services=svc, snapshot=empty_snapshot(), only=["stock"]
        )
        # stock 區塊含倉庫；沒匯物料所以 Bin 全部解析不到，一筆餘額都不寫
        assert svc.names() == ["create_warehouse", "resolve_item", "resolve_item"]
        assert report["only"] == ["stock"]
        assert report["stock"]["skipped_unresolved"] == 2

    async def test_full_run_then_rerun_is_stable(self, src):
        snapshot = empty_snapshot()
        svc = FakeServices()
        first = await imp.run_import(src=src, services=svc, snapshot=snapshot)
        svc2 = FakeServices()
        second = await imp.run_import(src=src, services=svc2, snapshot=snapshot)
        assert svc2.calls == []
        assert second["parties"]["created"] == 0
        assert second["items"]["created"] == 0
        assert second["warehouses"]["created"] == 0
        assert second["stock"]["adjusted"] == 0
        assert second["purchase_orders"]["created"] == 0
        assert second["projects"]["created"] == 0
        assert first["parties"]["created"] == 3


class TestCli:
    def test_parse_args_defaults(self):
        args = imp.parse_args(["--src", "/tmp/x"])
        assert args.src == "/tmp/x"
        assert args.dry_run is False
        assert args.only is None
        assert args.actor_user_id is None

    def test_parse_args_only_accepts_known_sections(self):
        args = imp.parse_args(["--src", "/tmp/x", "--only", "parties", "items"])
        assert args.only == ["parties", "items"]
        with pytest.raises(SystemExit):
            imp.parse_args(["--src", "/tmp/x", "--only", "nope"])

    def test_load_doctype_missing_file_returns_empty(self, tmp_path):
        assert imp.load_doctype(tmp_path, "Nope") == []

    def test_po_status_mapping(self):
        assert imp.po_status({"docstatus": 2, "status": "Cancelled"}, Decimal(0), Decimal(1)) == "cancelled"
        assert imp.po_status({"docstatus": 1, "status": "Completed"}, Decimal(1), Decimal(1)) == "received"
        assert imp.po_status({"docstatus": 1, "status": "To Receive"}, Decimal(0), Decimal(2)) == "ordered"
        assert imp.po_status({"docstatus": 1, "status": "To Bill"}, Decimal(1), Decimal(2)) == "partial"
        assert imp.po_status({"docstatus": 0, "status": "Draft"}, Decimal(0), Decimal(1)) is None

def _fanout_data(contact_extra: dict, count: int = 25) -> dict:
    suppliers = [_supplier(f"SM{i:04d} - 第{i}家有限公司") for i in range(1, count + 1)]
    return {
        "Supplier": suppliers,
        "Customer": [],
        "Contact": [
            {
                "name": "測試業務甲",
                "full_name": "測試業務甲",
                "links": [_link("Supplier", s["name"]) for s in suppliers],
                **contact_extra,
            }
        ],
        "Address": [],
    }


@pytest.mark.asyncio
async def test_high_fanout_contact_with_no_contact_details_is_skipped_as_internal():
    """掛 20 家以上又完全沒有聯絡方式＝自家業務，整筆跳過不建 party_contacts"""
    svc = FakeServices()
    importer = imp.Importer(svc, empty_snapshot())
    await importer.import_parties(_fanout_data({}))

    rep = importer.report["parties"]
    assert svc.of("add_contact") == []
    assert rep["contacts_created"] == 0
    assert rep["contacts_skipped_internal"] == 1
    assert rep["contacts_internal"] == [{"name": "測試業務甲", "parties": 25}]
    assert rep["contacts_fanout_top"] == []


@pytest.mark.asyncio
async def test_high_fanout_contact_with_phone_is_still_imported():
    """有聯絡方式的即使掛很多家也照掛，只點名"""
    svc = FakeServices()
    importer = imp.Importer(svc, empty_snapshot())
    await importer.import_parties(_fanout_data({"mobile_no": "0900000000"}))

    rep = importer.report["parties"]
    assert rep["contacts_created"] == 25
    assert rep["contacts_skipped_internal"] == 0
    assert rep["contacts_fanout_top"] == [{"name": "測試業務甲", "parties": 25}]


@pytest.mark.asyncio
async def test_internal_contact_threshold_is_configurable():
    """門檻調高到 26，同一個人就掛得進去"""
    svc = FakeServices()
    importer = imp.Importer(svc, empty_snapshot(), internal_contact_threshold=26)
    await importer.import_parties(_fanout_data({}))
    assert importer.report["parties"]["contacts_created"] == 25
    assert importer.report["parties"]["contacts_skipped_internal"] == 0


class TestSkipTestRecords:
    def test_is_test_record_looks_at_name_display_name_and_reference(self):
        assert imp.is_test_record({"name": "_MCP_TEST_假供應商"})
        assert imp.is_test_record({"name": "x", "item_name": "_MCP_TEST_假品名"})
        # 單號正常但供應商是測試資料的採購單也要濾掉
        assert imp.is_test_record(
            {"name": "PUR-ORD-TEST-00002", "supplier": "_MCP_TEST_假供應商"}
        )
        assert not imp.is_test_record({"name": "SM9001 - 甲鋼鐵有限公司"})

    def test_strip_test_records_counts_per_doctype(self):
        data = {
            "Supplier": [{"name": "_MCP_TEST_假供應商"}, {"name": "SM9002 - 乙工業"}],
            "Item": [{"name": "a", "item_code": "_MCP_TEST_假料號"}],
            "Warehouse": [{"name": "測試主倉 - 測試公司"}],
        }
        cleaned, skipped = imp.strip_test_records(data)
        assert [r["name"] for r in cleaned["Supplier"]] == ["SM9002 - 乙工業"]
        assert cleaned["Item"] == []
        assert skipped == {"Supplier": 1, "Item": 1}


@pytest.mark.asyncio
async def test_run_import_skips_test_records(tmp_path, sample):
    """整條路徑：`_MCP_TEST_` 的供應商、物料、採購單都不進資料庫"""
    sample = {k: list(v) for k, v in sample.items()}
    sample["Supplier"].append(_supplier("_MCP_TEST_假供應商"))
    sample["Item"].append(
        {"item_code": "_MCP_TEST_假料號", "item_name": "_MCP_TEST_假品名",
         "stock_uom": "Nos", "item_defaults": []}
    )
    sample["Purchase Order"].append(
        {"name": "PUR-ORD-TEST-00002", "docstatus": 2, "status": "Cancelled",
         "supplier": "_MCP_TEST_假供應商", "supplier_name": "_MCP_TEST_假供應商",
         "transaction_date": "2026-02-03", "items": [
             {"item_code": "_MCP_TEST_假料號", "qty": 10.0, "rate": 100.0}]}
    )
    out = tmp_path / "doctypes"
    out.mkdir()
    for doctype, rows in sample.items():
        (out / f"{doctype.replace(' ', '_')}.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
        )

    svc = FakeServices()
    report = await imp.run_import(src=out, services=svc, snapshot=empty_snapshot())

    assert report["skipped_test_records"] == {
        "Supplier": 1, "Item": 1, "Purchase Order": 1
    }
    assert report["parties"]["created"] == 3        # 測試供應商沒進來
    assert report["items"]["created"] == 2
    assert report["purchase_orders"]["created"] == 1
    made = [a[0]["po_no"] for a, _k in svc.of("create_purchase_order")]
    assert made == ["PUR-ORD-TEST-00001"]


# ============================================================
# 單筆失敗不中斷（M1）
# ============================================================


class _Boom(Exception):
    pass


class FlakyServices(FakeServices):
    """第 `fail_on` 次 create_party 會爆掉"""

    def __init__(self, fail_on: int = 2):
        super().__init__()
        self.fail_on = fail_on
        self._seen = 0

    async def create_party(self, data, **kw):
        self._seen += 1
        if self._seen == self.fail_on:
            raise _Boom("資料庫在這一筆爆掉")
        return await super().create_party(data, **kw)


@pytest.mark.asyncio
async def test_one_bad_record_does_not_stop_the_batch(sample):
    """一筆壞資料不該讓整批停在中間，要記進 errors 繼續跑"""
    svc = FlakyServices(fail_on=2)
    importer = imp.Importer(svc, empty_snapshot())
    await importer.import_parties(sample)

    assert importer.report["parties"]["created"] == 2   # 三家裡成功兩家
    errors = importer.report["errors"]
    assert len(errors) == 1
    assert errors[0]["doctype"] == "Supplier/Customer"
    assert "_Boom" in errors[0]["error"]


@pytest.mark.asyncio
async def test_run_import_errors_are_reported(src):
    svc = FlakyServices(fail_on=1)
    report = await imp.run_import(src=src, services=svc, snapshot=empty_snapshot())
    assert len(report["errors"]) == 1
    # 後面的區塊照樣跑完
    assert report["items"]["created"] == 2
    assert report["projects"]["created"] == 1


class _ActorConn:
    def __init__(self, found):
        self.found = found
        self.calls = []

    async def fetchval(self, sql, *args):
        self.calls.append((sql, args))
        return self.found


@pytest.mark.asyncio
class TestEnsureActor:
    async def test_none_actor_is_allowed_without_querying(self):
        conn = _ActorConn(None)
        await imp.ensure_actor(conn, None)
        assert conn.calls == []

    async def test_known_actor_passes(self):
        conn = _ActorConn(1)
        await imp.ensure_actor(conn, 7)
        assert "FROM users" in conn.calls[0][0]
        assert conn.calls[0][1] == (7,)

    async def test_unknown_actor_raises_with_a_clear_message(self):
        conn = _ActorConn(None)
        with pytest.raises(imp.ActorNotFoundError) as exc:
            await imp.ensure_actor(conn, 999)
        assert "999" in str(exc.value)
        assert "users" in str(exc.value)


# ============================================================
# load_snapshot（M2）
# ============================================================


class _SnapshotConn:
    """依 SQL 片段回固定 rows 的假 connection"""

    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows

    async def fetch(self, sql, *args):
        for fragment, rows in self.rows.items():
            if fragment in sql:
                return rows
        return []


PARTY_ID = UUID("00000000-0000-0000-0000-0000000000a1")
ITEM_ID = UUID("00000000-0000-0000-0000-0000000000b1")
WAREHOUSE_ID = UUID("00000000-0000-0000-0000-0000000000c1")
PROJECT_ID = UUID("00000000-0000-0000-0000-0000000000d1")


@pytest.mark.asyncio
async def test_load_snapshot_shapes_match_the_payloads_we_compare_against():
    """snapshot 的 key 必須跟匯入時算出來的 payload key 對得起來

    對不起來的話「重跑」會每次都判定成有變更（例如 address 的 `label` 讀成
    `address_type`、aliases 沒排序），冪等就假了。
    """
    conn = _SnapshotConn(
        {
            "FROM parties": [
                {
                    "id": PARTY_ID,
                    "name": "甲鋼鐵有限公司",
                    "short_name": "甲鋼鐵",
                    "aliases": ["SM9001 - 甲鋼鐵有限公司", "甲鋼鐵"],
                    "is_supplier": True,
                    "is_customer": True,
                    "source_ref": "Supplier:SM9001 - 甲鋼鐵有限公司;"
                    "Customer:CM9001 - 甲鋼鐵有限公司",
                }
            ],
            "FROM party_contacts": [
                {
                    "party_id": PARTY_ID,
                    "name": "測試聯絡人甲",
                    "title": "業務",
                    "phone": "02-0000-0000",
                    "mobile": "0900000000",
                    "email": "a@example.com",
                }
            ],
            "FROM party_addresses": [
                {
                    "party_id": PARTY_ID,
                    "label": "Billing",
                    "address": "台北市中正區測試路 1 號",
                    "city": "台北市",
                }
            ],
            "FROM items": [
                {
                    "id": ITEM_ID,
                    "code": "TEST-ITEM-001",
                    "name": "測試物料甲",
                    "spec": None,
                    "unit": "Set",
                    "item_group": "測試群組甲",
                    "default_supplier_id": None,
                    "purchase_price": None,
                    "lead_days": None,
                    "aliases": ["測試物料甲"],
                    "source_ref": "Item:TEST-ITEM-001",
                }
            ],
            "FROM warehouses": [
                {"id": WAREHOUSE_ID, "code": "測試主倉", "name": "測試主倉"}
            ],
            "FROM stock_balances": [
                {"item_id": ITEM_ID, "warehouse_id": WAREHOUSE_ID, "qty": "12.0000"}
            ],
            "FROM purchase_orders": [{"po_no": "PUR-ORD-TEST-00001"}],
            "FROM projects": [{"id": PROJECT_ID, "name": "測試專案甲"}],
            "FROM tasks": [{"project_id": PROJECT_ID, "title": "測試任務甲"}],
        }
    )
    snapshot = await imp.load_snapshot(conn)

    # 兩個 source token 都指到同一筆
    assert set(snapshot["parties"]) == {
        "Supplier:SM9001 - 甲鋼鐵有限公司",
        "Customer:CM9001 - 甲鋼鐵有限公司",
    }
    assert snapshot["parties"]["Supplier:SM9001 - 甲鋼鐵有限公司"]["id"] == PARTY_ID

    # contact／address 的 key 要跟 payload 算出來的一模一樣
    contact = imp.contact_payload(
        {
            "full_name": "測試聯絡人甲",
            "designation": "業務",
            "phone": "02-0000-0000",
            "mobile_no": "0900000000",
            "email_id": "a@example.com",
        }
    )
    assert imp.contact_key(contact) in snapshot["party_contacts"][PARTY_ID]
    address = imp.address_payload(
        {
            "address_type": "Billing",
            "address_line1": "台北市中正區測試路 1 號",
            "city": "台北市",
        }
    )
    assert imp.address_key(address) in snapshot["party_addresses"][PARTY_ID]

    assert snapshot["items"]["Item:TEST-ITEM-001"]["id"] == ITEM_ID
    assert snapshot["warehouses"]["測試主倉"]["id"] == WAREHOUSE_ID
    assert snapshot["balances"][(ITEM_ID, WAREHOUSE_ID)] == Decimal("12")
    assert snapshot["po_nos"] == {"PUR-ORD-TEST-00001"}
    assert snapshot["projects_by_name"] == {"測試專案甲": PROJECT_ID}
    assert snapshot["project_tasks"][PROJECT_ID] == {"測試任務甲"}


@pytest.mark.asyncio
async def test_snapshot_from_db_makes_the_second_run_a_no_op(src, sample):
    """把第一次跑的結果照 load_snapshot 的形狀重建，第二次仍然零寫入"""
    svc = FakeServices()
    first_snapshot = empty_snapshot()
    await imp.run_import(src=src, services=svc, snapshot=first_snapshot)

    # 模擬「關掉程式、重新從資料庫讀 snapshot」：只留 load_snapshot 會有的欄位
    rebuilt = empty_snapshot()
    for token, party in first_snapshot["parties"].items():
        rebuilt["parties"][token] = {
            k: party[k]
            for k in ("id", "name", "short_name", "aliases", "is_supplier",
                      "is_customer", "source_ref")
        }
    rebuilt["party_contacts"] = dict(first_snapshot["party_contacts"])
    rebuilt["party_addresses"] = dict(first_snapshot["party_addresses"])
    for token, item in first_snapshot["items"].items():
        rebuilt["items"][token] = {
            k: item[k]
            for k in ("id", "code", "name", "spec", "unit", "item_group",
                      "default_supplier_id", "purchase_price", "lead_days",
                      "aliases", "source_ref")
        }
    rebuilt["warehouses"] = {
        code: {"id": w["id"], "code": w["code"], "name": w["name"]}
        for code, w in first_snapshot["warehouses"].items()
    }
    rebuilt["balances"] = dict(first_snapshot["balances"])
    rebuilt["po_nos"] = set(first_snapshot["po_nos"])
    rebuilt["projects_by_name"] = dict(first_snapshot["projects_by_name"])
    rebuilt["project_tasks"] = dict(first_snapshot["project_tasks"])

    svc2 = FakeServices()
    second = await imp.run_import(src=src, services=svc2, snapshot=rebuilt)
    assert svc2.calls == []
    assert second["errors"] == []


# ============================================================
# L2 / L3 / L4 / L5
# ============================================================


@pytest.mark.asyncio
async def test_purchase_order_without_name_gets_its_own_bucket(sample):
    sample = dict(sample)
    sample["Purchase Order"] = [{**sample["Purchase Order"][0], "name": ""}]
    svc = FakeServices()
    importer = imp.Importer(svc, empty_snapshot())
    await importer.import_parties(sample)
    await importer.import_items(sample)
    await importer.import_purchase_orders(sample)
    assert importer.report["purchase_orders"]["skipped_no_name"] == 1
    assert importer.report["purchase_orders"]["unchanged"] == 0


class TestToDecimal:
    def test_zero_is_kept_as_zero(self):
        """行項 rate=0 是「不計價」，不是「沒填」"""
        assert imp.to_decimal(0) == Decimal("0")
        assert imp.to_decimal("0") == Decimal("0")
        assert imp.to_decimal(0.0) == Decimal("0")

    def test_blank_and_garbage_are_none(self):
        assert imp.to_decimal(None) is None
        assert imp.to_decimal("") is None
        assert imp.to_decimal("  ") is None
        assert imp.to_decimal("abc") is None

    def test_purchase_price_still_treats_zero_as_unset(self):
        rows = [
            {"item_code": "TEST-ITEM-001", "buying": 1, "price_list_rate": 0,
             "valid_from": "2026-01-01"},
            {"item_code": "TEST-ITEM-002", "buying": 1, "price_list_rate": 12.5,
             "valid_from": "2026-01-01"},
        ]
        assert imp.buying_prices(rows) == {"TEST-ITEM-002": Decimal("12.5")}


@pytest.mark.asyncio
async def test_zero_rate_line_keeps_zero_unit_price(sample):
    sample = dict(sample)
    po = {**sample["Purchase Order"][0]}
    po["items"] = [{**po["items"][0], "rate": 0.0}]
    sample["Purchase Order"] = [po]
    svc = FakeServices()
    importer = imp.Importer(svc, empty_snapshot())
    await importer.import_parties(sample)
    await importer.import_items(sample)
    await importer.import_projects(sample)
    await importer.import_purchase_orders(sample)
    (data,), _kw = svc.of("create_purchase_order")[0]
    assert data["lines"][0]["unit_price"] == Decimal("0")


@pytest.mark.asyncio
async def test_group_matching_two_existing_parties_is_reported(sample):
    """合併組的兩個 token 分別對到不同既有 party → 進 unresolved 讓人去 merge"""
    snapshot = empty_snapshot()
    a, b = uuid4(), uuid4()
    for token, pid in (
        ("Supplier:SM9001 - 甲鋼鐵有限公司", a),
        ("Customer:CM9001 - 甲鋼鐵有限公司", b),
    ):
        snapshot["parties"][token] = {
            "id": pid, "name": "甲鋼鐵有限公司", "short_name": "甲鋼鐵",
            "aliases": [], "is_supplier": True, "is_customer": True,
            "source_ref": token,
        }
    svc = FakeServices()
    importer = imp.Importer(svc, snapshot)
    await importer.import_parties(sample)

    conflicts = importer.report["unresolved"]["party_conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["name"] == "甲鋼鐵有限公司"
    assert sorted(conflicts[0]["party_ids"]) == sorted([str(a), str(b)])
    # 衝突的那一組沒有重複建立（另外兩家是新的，照建）
    created_names = [a[0]["name"] for a, _k in svc.of("create_party")]
    assert "甲鋼鐵有限公司" not in created_names


class TestMergeReview:
    def test_same_name_before_suffix_needs_no_review(self, sample):
        groups = {g["key"]: g for g in imp.build_party_groups(
            sample["Supplier"], sample["Customer"])}
        assert groups["甲鋼鐵"]["needs_review"] is False

    def test_different_name_before_suffix_needs_review(self):
        groups = imp.build_party_groups(
            [_supplier("SM9001 - 某某有限公司")],
            [_customer("CM9001 - 某某股份有限公司")],
        )
        assert len(groups) == 1
        assert groups[0]["needs_review"] is True

    @pytest.mark.asyncio
    async def test_review_list_lands_in_the_report(self):
        data = {
            "Supplier": [_supplier("SM9001 - 某某有限公司")],
            "Customer": [_customer("CM9001 - 某某股份有限公司")],
            "Contact": [],
            "Address": [],
        }
        svc = FakeServices()
        importer = imp.Importer(svc, empty_snapshot())
        await importer.import_parties(data)
        review = importer.report["merge_review"]
        assert len(review) == 1
        assert review[0]["sources"] == [
            "Supplier:SM9001 - 某某有限公司",
            "Customer:CM9001 - 某某股份有限公司",
        ]


# ============================================================
# CLI 外圍
# ============================================================


class TestCliOuter:
    def test_missing_src_directory_returns_2(self, tmp_path, capsys):
        assert imp.main(["--src", str(tmp_path / "nope")]) == 2
        assert "找不到來源目錄" in capsys.readouterr().err

    def test_write_report_round_trips(self, tmp_path):
        path = tmp_path / "r.json"
        imp.write_report(path, {"parties": {"created": 1}, "when": None})
        assert json.loads(path.read_text(encoding="utf-8"))["parties"]["created"] == 1

    @pytest.mark.asyncio
    async def test_summarize_mentions_every_bucket(self, src):
        svc = FlakyServices(fail_on=1)
        report = await imp.run_import(src=src, services=svc, snapshot=empty_snapshot())
        report["parties"]["contacts_internal"] = [{"name": "測試業務甲", "parties": 40}]
        report["parties"]["contacts_fanout_top"] = [{"name": "測試業務乙", "parties": 30}]
        report["skipped_test_records"] = {"Supplier": 1}
        report["unresolved"]["suppliers"] = ["某某有限公司"]
        report["unresolved"]["party_conflicts"] = [{"name": "某某有限公司"}]
        report["merge_review"] = [{"name": "某某有限公司", "sources": []}]
        text = imp.summarize(report)
        for fragment in (
            "parties:", "判定為內部人員", "照掛", "測試資料", "resolver:",
            "無法解析的 suppliers", "無法解析的 party_conflicts",
            "要人眼看過", "失敗（1",
        ):
            assert fragment in text


class TestBackendServices:
    def test_binds_every_function_the_importer_calls(self):
        """門面漏綁一支，真跑會在那一步才 AttributeError——這裡先擋住"""
        services = imp.BackendServices()
        for name in (
            "create_party", "update_party", "add_contact", "add_address",
            "create_item", "update_item", "create_warehouse", "update_warehouse",
            "adjust_stock", "create_purchase_order", "create_project", "create_task",
            "resolve_party", "resolve_item",
        ):
            assert callable(getattr(services, name)), name
        assert all(issubclass(e, Exception) for e in services.resolve_errors)


@pytest.fixture
def keep_event_loop():
    """`main()` 會跑 asyncio.run()，跑完會把 thread 的 event loop 清掉

    清掉之後同一個 session 裡後面用 `asyncio.get_event_loop()` 的同步測試
    （scheduler）就會 RuntimeError。這裡跑完把 loop 放回去。
    """
    policy = asyncio.get_event_loop_policy()
    try:
        loop = policy.get_event_loop()
    except RuntimeError:  # pragma: no cover - 本來就沒有 loop
        loop = None
    yield
    if loop is not None:
        asyncio.set_event_loop(loop)


class TestMainWiring:
    def test_db_name_is_exported_before_the_backend_is_imported(
        self, tmp_path, monkeypatch, keep_event_loop
    ):
        seen = {}

        async def fake_main(args):
            seen["db_name"] = os.environ.get("DB_NAME")
            seen["args"] = args
            return 0

        monkeypatch.setattr(imp, "_main", fake_main)
        monkeypatch.setenv("DB_NAME", "before")
        assert imp.main(["--src", str(tmp_path), "--db-name", "ctos_import_test"]) == 0
        assert seen["db_name"] == "ctos_import_test"

    def test_unknown_actor_becomes_exit_2_with_a_message(
        self, tmp_path, monkeypatch, capsys, keep_event_loop
    ):
        async def fake_main(_args):
            raise imp.ActorNotFoundError("--actor-user-id 999 在 users 表裡找不到")

        monkeypatch.setattr(imp, "_main", fake_main)
        assert imp.main(["--src", str(tmp_path), "--actor-user-id", "999"]) == 2
        assert "999" in capsys.readouterr().err
