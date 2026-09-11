"""bot prompt／migration 032／skills／CLI 切換到往來與物料模組的驗收測試

PR 7（`.superpowers/sdd/erp-bot-switch/brief.md`）：確認 ERPNext 的痕跡從
prompt、skills、CLI 與舊桌面移除，換成 `services/mcp/erp_tools.py` 的新工具。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from ching_tech_os.services import linebot_agents

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

# 新模組的工具名稱（brief 第 1 點列的那幾支）
PARTY_TOOLS = [
    "find_party",
    "get_party",
    "create_party",
    "add_party_contact",
    "update_party_contact",
    "merge_parties",
]
INVENTORY_TOOLS = [
    "find_item",
    "get_item",
    "get_stock",
    "adjust_stock",
    "create_purchase_order",
    "receive_purchase_order",
]
ERPNEXT_MARKERS = ["mcp__erpnext__", "ERPNext", "ct.erp"]


# ============================================================
# 1. 程式碼裡的 prompt
# ============================================================


@pytest.mark.parametrize(
    "prompt_name",
    ["LINEBOT_PERSONAL_PROMPT", "LINEBOT_GROUP_PROMPT"],
)
def test_code_prompt_has_no_erpnext(prompt_name: str) -> None:
    prompt = getattr(linebot_agents, prompt_name)
    for marker in ERPNEXT_MARKERS:
        assert marker not in prompt, f"{prompt_name} 仍含 {marker}"


@pytest.mark.parametrize(
    "prompt_name",
    ["LINEBOT_PERSONAL_PROMPT", "LINEBOT_GROUP_PROMPT"],
)
def test_code_prompt_has_new_tools(prompt_name: str) -> None:
    prompt = getattr(linebot_agents, prompt_name)
    for tool in PARTY_TOOLS + INVENTORY_TOOLS:
        assert tool in prompt, f"{prompt_name} 缺少工具 {tool}"


@pytest.mark.parametrize(
    "prompt_name",
    ["LINEBOT_PERSONAL_PROMPT", "LINEBOT_GROUP_PROMPT"],
)
def test_code_prompt_points_to_new_frontend(prompt_name: str) -> None:
    """專案沒有 MCP 工具，要引導到新前端"""
    prompt = getattr(linebot_agents, prompt_name)
    assert "os.ching-tech.com/projects" in prompt


def test_code_prompt_keeps_usage_rules() -> None:
    """skills/erp/SKILL.md 的三條規矩要寫進 prompt"""
    prompt = linebot_agents.LINEBOT_PERSONAL_PROMPT
    assert "先 find 再寫" in prompt
    assert "候選" in prompt
    assert "audit_id" in prompt


# ============================================================
# 3. skills
# ============================================================


SKILLS_DIR = BACKEND_ROOT / "src" / "ching_tech_os" / "skills"


def test_inventory_skill_merged_into_erp() -> None:
    assert not (SKILLS_DIR / "inventory").exists(), "skills/inventory 應併入 skills/erp"


def test_erp_skill_covers_inventory_and_purchasing() -> None:
    text = (SKILLS_DIR / "erp" / "SKILL.md").read_text(encoding="utf-8")
    for tool in PARTY_TOOLS + INVENTORY_TOOLS:
        assert tool in text
    assert "mcp__erpnext__" not in text


def test_project_skill_has_no_erpnext_tools() -> None:
    text = (SKILLS_DIR / "project" / "SKILL.md").read_text(encoding="utf-8")
    assert "mcp__erpnext__" not in text
    assert "ct.erp" not in text
    assert "os.ching-tech.com/projects" in text


def test_script_mcp_matrix_has_no_erpnext_notes() -> None:
    import json

    matrix = json.loads((SKILLS_DIR / "script_mcp_matrix.json").read_text(encoding="utf-8"))
    names = {cap["name"]: cap for cap in matrix["capabilities"]}
    assert "inventory-management" in names
    assert names["inventory-management"]["skill"] == "erp"
    for cap in matrix["capabilities"]:
        assert "ERPNext" not in (cap.get("notes") or "")


# ============================================================
# 4. CLI
# ============================================================


@pytest.fixture(scope="module")
def cli_main():
    cli_src = str(REPO_ROOT / "cli" / "src")
    if cli_src not in sys.path:
        sys.path.insert(0, cli_src)
    import ctos_cli.main as main  # noqa: PLC0415

    return main


class _Recorder:
    """攔下 CLI 的 _api，記錄路徑與參數並回傳預先安排的資料"""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, path, **kwargs):
        self.calls.append((path, kwargs.get("params")))
        for prefix, payload in self.responses:
            if path == prefix:
                return payload
        raise AssertionError(f"CLI 打了沒安排的端點：{path}")


_ITEM_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "code": "CTOS-A1",
    "name": "測試物料",
    "spec": "10mm",
    "unit": "PCS",
    "item_group": "零件",
    "default_supplier_name": "測試供應商",
    "purchase_price": "25",
    "lead_days": 7,
    "total_qty": "12",
    "aliases": [],
    "balances": [],
    "movements": [],
}


def test_cli_erp_find_hits_items_endpoint(cli_main, monkeypatch, capsys) -> None:
    rec = _Recorder([("/api/items", {"items": [_ITEM_ROW], "total": 1})])
    monkeypatch.setattr(cli_main, "_api", rec)
    args = cli_main.build_parser().parse_args(["erp", "find", "測試"])
    args.func(args)
    assert rec.calls[0][0] == "/api/items"
    assert rec.calls[0][1]["q"] == "測試"
    assert "CTOS-A1" in capsys.readouterr().out


def test_cli_erp_item_resolves_code_then_hits_detail(cli_main, monkeypatch, capsys) -> None:
    item_id = _ITEM_ROW["id"]
    rec = _Recorder(
        [
            ("/api/items", {"items": [_ITEM_ROW], "total": 1}),
            (f"/api/items/{item_id}", _ITEM_ROW),
        ]
    )
    monkeypatch.setattr(cli_main, "_api", rec)
    args = cli_main.build_parser().parse_args(["erp", "item", "CTOS-A1"])
    args.func(args)
    assert [c[0] for c in rec.calls] == ["/api/items", f"/api/items/{item_id}"]
    assert "測試物料" in capsys.readouterr().out


def test_cli_erp_stock_hits_stock_endpoint(cli_main, monkeypatch, capsys) -> None:
    item_id = _ITEM_ROW["id"]
    rows = {
        "items": [
            {
                "item_id": item_id,
                "item_code": "CTOS-A1",
                "item_name": "測試物料",
                "warehouse_id": "22222222-2222-2222-2222-222222222222",
                "warehouse_code": "MAIN",
                "warehouse_name": "主倉",
                "qty": "12",
            }
        ],
        "total": 1,
    }
    rec = _Recorder(
        [
            ("/api/items", {"items": [_ITEM_ROW], "total": 1}),
            ("/api/stock", rows),
        ]
    )
    monkeypatch.setattr(cli_main, "_api", rec)
    args = cli_main.build_parser().parse_args(["erp", "stock", "CTOS-A1"])
    args.func(args)
    assert [c[0] for c in rec.calls] == ["/api/items", "/api/stock"]
    assert rec.calls[1][1]["item_id"] == item_id
    assert "主倉" in capsys.readouterr().out


def test_cli_erp_stock_resolves_warehouse_name(cli_main, monkeypatch) -> None:
    warehouse_id = "22222222-2222-2222-2222-222222222222"
    rec = _Recorder(
        [
            ("/api/items", {"items": [_ITEM_ROW], "total": 1}),
            (
                "/api/warehouses",
                {"items": [{"id": warehouse_id, "code": "MAIN", "name": "主倉"}], "total": 1},
            ),
            ("/api/stock", {"items": [], "total": 0}),
        ]
    )
    monkeypatch.setattr(cli_main, "_api", rec)
    args = cli_main.build_parser().parse_args(["erp", "stock", "CTOS-A1", "--warehouse", "主倉"])
    args.func(args)
    assert rec.calls[-1][1]["warehouse_id"] == warehouse_id


def test_cli_erp_bom_subcommands_removed(cli_main) -> None:
    parser = cli_main.build_parser()
    for argv in (["erp", "boms", "CTOS-A1"], ["erp", "bom", "BOM-1"]):
        with pytest.raises(SystemExit):
            parser.parse_args(argv)


def test_cli_source_has_no_erp_proxy_paths(cli_main) -> None:
    text = (REPO_ROOT / "cli" / "src" / "ctos_cli" / "main.py").read_text(encoding="utf-8")
    assert "/api/erp" not in text


# ============================================================
# 5. 舊桌面
# ============================================================


def test_legacy_desktop_has_no_erpnext_app() -> None:
    text = (REPO_ROOT / "frontend" / "js" / "desktop.js").read_text(encoding="utf-8")
    assert "erpnext" not in text
    assert "ct.erp" not in text
