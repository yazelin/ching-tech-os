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
# 2. migration 032
# ============================================================


def _load_migration_032():
    path = BACKEND_ROOT / "migrations" / "versions" / "032_switch_bot_prompt_to_erp_module.py"
    assert path.is_file(), f"找不到 migration 032：{path}"
    spec = importlib.util.spec_from_file_location("migration_032", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_032_revision_chain() -> None:
    module = _load_migration_032()
    assert module.revision == "032"
    assert module.down_revision == "031"


def test_migration_032_new_sections_have_no_erpnext() -> None:
    module = _load_migration_032()
    for name, (old, new) in module.SECTIONS.items():
        for marker in ERPNEXT_MARKERS:
            assert marker not in new, f"{name} 的新段落仍含 {marker}"
        # 舊段落必須是 ERPNext 版本，downgrade 才換得回去
        assert any(marker in old for marker in ERPNEXT_MARKERS), f"{name} 的舊段落不像 ERPNext 版本"


def test_migration_032_new_sections_cover_tools() -> None:
    module = _load_migration_032()
    joined = "\n".join(new for _old, new in module.SECTIONS.values())
    for tool in PARTY_TOOLS + INVENTORY_TOOLS:
        assert tool in joined, f"migration 032 缺少工具 {tool}"
    assert "os.ching-tech.com/projects" in joined


def test_migration_032_old_sections_match_seed_data() -> None:
    """舊段落要和 seed_data.sql 的 prompt 對得起來（正式庫原文的唯一本機依據）"""
    module = _load_migration_032()
    seed = (BACKEND_ROOT / "migrations" / "versions" / "seed_data.sql").read_text(encoding="utf-8")
    # seed 是 SQL 字面值，單引號是加倍的
    for name, (old, _new) in module.SECTIONS.items():
        assert old.replace("'", "''") in seed, f"{name} 的舊段落在 seed_data.sql 找不到"


def test_migration_032_rewrite_replaces_and_reports_missing() -> None:
    module = _load_migration_032()
    content = "前言\n" + module.SECTIONS["personal_party"][0] + "\n結尾"
    rewritten, missing = module.rewrite(content, ["personal_party", "personal_inventory"])
    assert module.SECTIONS["personal_party"][1] in rewritten
    assert module.SECTIONS["personal_party"][0] not in rewritten
    # 找不到的段落只回報、不炸
    assert missing == ["personal_inventory"]


def test_migration_032_rewrite_is_reversible() -> None:
    module = _load_migration_032()
    names = list(module.SECTIONS)
    original = "\n".join(old for old, _new in module.SECTIONS.values())
    upgraded, missing = module.rewrite(original, names)
    assert missing == []
    downgraded, missing_back = module.rewrite(upgraded, names, reverse=True)
    assert missing_back == []
    assert downgraded == original


def test_migration_032_rewrite_never_raises_on_unknown_content() -> None:
    module = _load_migration_032()
    rewritten, missing = module.rewrite("完全無關的 prompt", list(module.SECTIONS))
    assert rewritten == "完全無關的 prompt"
    assert missing == list(module.SECTIONS)


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
