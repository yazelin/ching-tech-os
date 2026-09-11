"""bot prompt／migration 033／skill 切換到專案 MCP 工具的驗收測試（PR 7b）

PR 7（`test_erp_bot_switch.py`）把專案段落改成「請到新前端」，這一支確認它再
換成 `services/mcp/project_tools.py` 的工具指引，且 033 可逆。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from ching_tech_os.services import linebot_agents

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
SKILLS_DIR = BACKEND_ROOT / "src" / "ching_tech_os" / "skills"

# brief 第 1 點列的九支
PROJECT_TOOLS = [
    "find_project",
    "get_project",
    "list_overdue_milestones",
    "list_tasks",
    "create_task",
    "update_task",
    "create_milestone",
    "complete_milestone",
    "add_project_member",
]

# 切換前的講法（PR 7 的過渡文字）
OLD_MARKERS = ["沒有專案的 MCP 工具", "專案目前沒有 MCP 工具", "還沒有專案的 MCP 工具"]


def _load_migration_033():
    path = (
        BACKEND_ROOT
        / "migrations"
        / "versions"
        / "033_switch_bot_prompt_to_project_tools.py"
    )
    assert path.is_file(), f"找不到 migration 033：{path}"
    spec = importlib.util.spec_from_file_location("migration_033", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_migration_032():
    from tests.test_erp_bot_switch import _load_migration_032 as loader

    return loader()


# ============================================================
# 1. 程式碼裡的 prompt
# ============================================================


@pytest.mark.parametrize(
    "prompt_name", ["LINEBOT_PERSONAL_PROMPT", "LINEBOT_GROUP_PROMPT"]
)
def test_code_prompt_has_project_tools(prompt_name: str) -> None:
    prompt = getattr(linebot_agents, prompt_name)
    for tool in PROJECT_TOOLS:
        assert tool in prompt, f"{prompt_name} 缺少工具 {tool}"


@pytest.mark.parametrize(
    "prompt_name", ["LINEBOT_PERSONAL_PROMPT", "LINEBOT_GROUP_PROMPT"]
)
def test_code_prompt_drops_no_tool_wording(prompt_name: str) -> None:
    prompt = getattr(linebot_agents, prompt_name)
    for marker in OLD_MARKERS:
        assert marker not in prompt, f"{prompt_name} 仍寫著「{marker}」"


@pytest.mark.parametrize(
    "prompt_name", ["LINEBOT_PERSONAL_PROMPT", "LINEBOT_GROUP_PROMPT"]
)
def test_code_prompt_keeps_web_for_creating_projects(prompt_name: str) -> None:
    """建立專案不開放給 bot，這條路要留在 prompt 裡"""
    prompt = getattr(linebot_agents, prompt_name)
    assert "os.ching-tech.com/projects" in prompt
    assert "開新專案" in prompt or "建立專案不開放給 bot" in prompt


def test_code_prompt_states_member_rule() -> None:
    prompt = linebot_agents.LINEBOT_PERSONAL_PROMPT
    assert "只有專案成員能編輯" in prompt
    assert "候選" in prompt


# ============================================================
# 2. migration 033
# ============================================================


def test_migration_033_revision_chain() -> None:
    module = _load_migration_033()
    assert module.revision == "033"
    assert module.down_revision == "032"


def test_migration_033_old_sections_come_from_migration_032() -> None:
    """033 的舊段落必須是 032 換上去的文字，兩支才接得起來"""
    module = _load_migration_033()
    previous = _load_migration_032()
    produced = "\n".join(new for _old, new in previous.SECTIONS.values())
    for name, (old, _new) in module.SECTIONS.items():
        assert old in produced, f"{name} 的舊段落不是 032 產出的文字"


def test_migration_033_new_sections_cover_tools() -> None:
    module = _load_migration_033()
    joined = "\n".join(new for _old, new in module.SECTIONS.values())
    for tool in PROJECT_TOOLS:
        assert tool in joined, f"migration 033 缺少工具 {tool}"
    assert "os.ching-tech.com/projects" in joined
    for marker in OLD_MARKERS:
        assert marker not in joined


def test_migration_033_new_sections_match_linebot_agents_verbatim() -> None:
    """migration 的新段落要和 linebot_agents.py 的對應段落逐字相等

    兩份文字是分開維護的（migration 必須自足），這條擋的是只改一邊。
    """
    module = _load_migration_033()
    prompts = {
        module.PERSONAL: linebot_agents.LINEBOT_PERSONAL_PROMPT,
        module.GROUP: linebot_agents.LINEBOT_GROUP_PROMPT,
    }
    for prompt_name, names in module.PROMPT_SECTIONS.items():
        for name in names:
            assert module.SECTIONS[name][1] in prompts[prompt_name], (
                f"{name} 的新段落和 linebot_agents.py 的 {prompt_name} 對不起來"
            )


def test_migration_033_rewrite_replaces_and_reports_missing() -> None:
    module = _load_migration_033()
    content = "前言\n" + module.SECTIONS["personal_project"][0] + "\n結尾"
    rewritten, missing, already = module.rewrite(
        content, ["personal_project", "group_project"]
    )
    assert module.SECTIONS["personal_project"][1] in rewritten
    assert module.SECTIONS["personal_project"][0] not in rewritten
    assert missing == ["group_project"]
    assert already == []


def test_migration_033_rewrite_is_reversible() -> None:
    module = _load_migration_033()
    names = list(module.SECTIONS)
    original = "\n".join(old for old, _new in module.SECTIONS.values())
    upgraded, missing, already = module.rewrite(original, names)
    assert missing == [] and already == []
    downgraded, missing_back, already_back = module.rewrite(upgraded, names, reverse=True)
    assert missing_back == [] and already_back == []
    assert downgraded == original


def test_migration_033_rewrite_never_raises_on_unknown_content() -> None:
    module = _load_migration_033()
    rewritten, missing, already = module.rewrite("完全無關的 prompt", list(module.SECTIONS))
    assert rewritten == "完全無關的 prompt"
    assert missing == list(module.SECTIONS)
    assert already == []


def test_migration_033_rewrite_reports_already_switched() -> None:
    module = _load_migration_033()
    content = module.SECTIONS["group_project"][1]
    rewritten, missing, already = module.rewrite(content, ["group_project"])
    assert rewritten == content
    assert missing == []
    assert already == ["group_project"]


# ---- _apply（假連線，不碰真資料庫）----


class _FakeRow:
    def __init__(self, id_, name, content):
        self.id = id_
        self.name = name
        self.content = content


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    """只認得 SELECT 與 UPDATE 兩種語句，記錄所有 UPDATE"""

    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def execute(self, statement, params=None):
        sql = str(statement)
        if sql.strip().upper().startswith("SELECT"):
            return _FakeResult(self.rows)
        self.updates.append(params)
        return _FakeResult([])


class _FakeOp:
    def __init__(self, conn):
        self._conn = conn

    def get_bind(self):
        return self._conn


def _run_apply(module, rows, reverse=False):
    conn = _FakeConn(rows)
    original = module.op
    module.op = _FakeOp(conn)
    try:
        module._apply(reverse=reverse)
    finally:
        module.op = original
    return conn


def test_migration_033_apply_skips_when_prompt_row_missing(caplog) -> None:
    module = _load_migration_033()
    with caplog.at_level("WARNING"):
        conn = _run_apply(module, [])
    assert conn.updates == []
    assert "linebot-personal" in caplog.text
    assert "linebot-group" in caplog.text


def test_migration_033_apply_updates_content() -> None:
    module = _load_migration_033()
    original = "\n".join(
        module.SECTIONS[name][0] for name in module.PROMPT_SECTIONS[module.PERSONAL]
    )
    rows = [_FakeRow("id-1", module.PERSONAL, original)]
    conn = _run_apply(module, rows)
    assert len(conn.updates) == 1
    assert conn.updates[0]["id"] == "id-1"
    written = conn.updates[0]["content"]
    assert "find_project" in written
    assert "沒有專案的 MCP 工具" not in written


def test_migration_033_apply_downgrade_restores_web_wording() -> None:
    module = _load_migration_033()
    switched = "\n".join(
        module.SECTIONS[name][1] for name in module.PROMPT_SECTIONS[module.GROUP]
    )
    rows = [_FakeRow("id-2", module.GROUP, switched)]
    conn = _run_apply(module, rows, reverse=True)
    assert len(conn.updates) == 1
    assert "專案目前沒有 MCP 工具" in conn.updates[0]["content"]


def test_migration_033_apply_does_not_update_when_already_switched(caplog) -> None:
    """已經切換過的內容不再下 UPDATE（不動 updated_at），且只記 info 不記 warning"""
    module = _load_migration_033()
    switched = "\n".join(
        module.SECTIONS[name][1] for name in module.PROMPT_SECTIONS[module.GROUP]
    )
    rows = [_FakeRow("id-2", module.GROUP, switched)]
    with caplog.at_level("INFO"):
        conn = _run_apply(module, rows)
    assert conn.updates == []
    assert "已切換" in caplog.text
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert not [w for w in warnings if module.GROUP in w]


# ============================================================
# 3. skill 與對照表
# ============================================================


def test_project_skill_documents_tools() -> None:
    text = (SKILLS_DIR / "project" / "SKILL.md").read_text(encoding="utf-8")
    for tool in PROJECT_TOOLS:
        assert tool in text, f"skills/project 缺少 {tool}"
    assert "只有專案成員能編輯" in text
    assert "need_confirmation" in text
    # 建立專案仍然只在網頁
    assert "os.ching-tech.com/projects" in text
    for marker in OLD_MARKERS:
        assert marker not in text


def test_script_mcp_matrix_marks_project_as_mcp_only() -> None:
    matrix = json.loads((SKILLS_DIR / "script_mcp_matrix.json").read_text(encoding="utf-8"))
    names = {cap["name"]: cap for cap in matrix["capabilities"]}
    cap = names["project-management"]
    assert cap["skill"] == "project"
    assert "沒有 MCP 工具" not in (cap.get("notes") or "")


@pytest.mark.asyncio
async def test_project_skill_loads_for_project_user() -> None:
    from ching_tech_os.skills import get_skill_manager

    sm = get_skill_manager()
    skills = await sm.get_skills_for_user({"project-management": True}, role="user")
    assert "project" in {s.name for s in skills}


# ============================================================
# 4. 文件
# ============================================================


def test_docs_list_project_tools() -> None:
    text = (REPO_ROOT / "docs" / "mcp-server.md").read_text(encoding="utf-8")
    assert "project_tools.py" in text
    for tool in PROJECT_TOOLS:
        assert f"`{tool}`" in text, f"docs/mcp-server.md 缺少 {tool}"
