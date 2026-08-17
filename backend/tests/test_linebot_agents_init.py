"""linebot_agents 初始化流程測試。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import ching_tech_os.database as database
import ching_tech_os.services.linebot_agents as linebot_agents


class _FakeCM:
    """模擬 get_connection() 回傳的 async context manager。"""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_get_linebot_agent(monkeypatch: pytest.MonkeyPatch):
    get_agent = AsyncMock(return_value={"name": "x"})
    monkeypatch.setattr(linebot_agents.ai_manager, "get_agent_by_name", get_agent)

    await linebot_agents.get_linebot_agent(is_group=False)
    await linebot_agents.get_linebot_agent(is_group=True)

    assert get_agent.await_args_list[0].args[0] == linebot_agents.AGENT_LINEBOT_PERSONAL
    assert get_agent.await_args_list[1].args[0] == linebot_agents.AGENT_LINEBOT_GROUP


@pytest.mark.asyncio
async def test_ensure_default_linebot_agents_skip_existing(monkeypatch: pytest.MonkeyPatch):
    # 所有 agent 都已存在 → 不建立任何東西
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "get_agent_by_name",
        AsyncMock(return_value={"id": 1}),
    )
    create_prompt = AsyncMock()
    create_agent = AsyncMock()
    monkeypatch.setattr(linebot_agents.ai_manager, "create_prompt", create_prompt)
    monkeypatch.setattr(linebot_agents.ai_manager, "create_agent", create_agent)

    await linebot_agents.ensure_default_linebot_agents()

    create_prompt.assert_not_awaited()
    create_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_default_linebot_agents_create_prompt_and_agent(monkeypatch: pytest.MonkeyPatch):
    # linebot agents (2) + bot mode agents (2) + extends agents (2) = 6 個
    # 前 2 個（linebot）不存在，後 4 個（bot mode + extends）已存在
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "get_agent_by_name",
        AsyncMock(side_effect=[None, None, {"id": 3}, {"id": 4}, {"id": 5}, {"id": 6}]),
    )
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "get_prompt_by_name",
        AsyncMock(side_effect=[None, {"id": "00000000-0000-0000-0000-000000000099"}]),
    )
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "create_prompt",
        AsyncMock(return_value={"id": "00000000-0000-0000-0000-000000000011"}),
    )
    create_agent = AsyncMock()
    monkeypatch.setattr(linebot_agents.ai_manager, "create_agent", create_agent)

    await linebot_agents.ensure_default_linebot_agents()

    assert linebot_agents.ai_manager.create_prompt.await_count == 1
    assert create_agent.await_count == 2
    first_agent_payload = create_agent.await_args_list[0].args[0]
    second_agent_payload = create_agent.await_args_list[1].args[0]
    assert str(first_agent_payload.system_prompt_id) == "00000000-0000-0000-0000-000000000011"
    assert str(second_agent_payload.system_prompt_id) == "00000000-0000-0000-0000-000000000099"


# ============================================================
# _parse_agent_md：extends Agent .md 檔案解析
# ============================================================


def test_parse_agent_md_success(tmp_path: Path):
    """正常解析 frontmatter + body → agent_config。"""
    md = tmp_path / "law-assistant.md"
    md.write_text(
        "---\ndisplay_name: 法律助理\nmodel: claude-haiku\ntools:\n  - search_knowledge\n---\n你是法律助理。",
        encoding="utf-8",
    )
    config = linebot_agents._parse_agent_md(md)
    assert config is not None
    assert config["name"] == "law-assistant"
    assert config["display_name"] == "法律助理"
    assert config["model"] == "claude-haiku"
    assert config["tools"] == ["search_knowledge"]
    assert config["prompt"]["content"] == "你是法律助理。"


def test_parse_agent_md_no_frontmatter_defaults(tmp_path: Path):
    """無 frontmatter 時使用預設值，tools 空列表轉為 None。"""
    md = tmp_path / "plain.md"
    md.write_text("純 prompt 內容", encoding="utf-8")
    config = linebot_agents._parse_agent_md(md)
    assert config is not None
    assert config["display_name"] == "plain"
    assert config["model"] == "claude-sonnet"
    assert config["tools"] is None


def test_parse_agent_md_read_error(tmp_path: Path):
    """檔案不存在 → 讀取失敗 → None。"""
    assert linebot_agents._parse_agent_md(tmp_path / "not-exist.md") is None


def test_parse_agent_md_bad_yaml(tmp_path: Path):
    """frontmatter YAML 格式錯誤 → None。"""
    md = tmp_path / "bad.md"
    md.write_text("---\na: b: c\n---\nbody", encoding="utf-8")
    assert linebot_agents._parse_agent_md(md) is None


def test_parse_agent_md_empty_body(tmp_path: Path):
    """只有 frontmatter、無 prompt 內容 → None。"""
    md = tmp_path / "empty.md"
    md.write_text("---\ndisplay_name: 空\n---\n", encoding="utf-8")
    assert linebot_agents._parse_agent_md(md) is None


# ============================================================
# _seed_extends_agents：掃描 extends 目錄 seed Agent
# ============================================================


@pytest.mark.asyncio
async def test_seed_extends_agents_no_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """extends 目錄不存在 → 直接 return，不呼叫 _ensure_agents。"""
    monkeypatch.setattr(linebot_agents.settings, "extends_dir", str(tmp_path / "not-exist"))
    ensure = AsyncMock()
    monkeypatch.setattr(linebot_agents, "_ensure_agents", ensure)
    await linebot_agents._seed_extends_agents()
    ensure.assert_not_awaited()


@pytest.mark.asyncio
async def test_seed_extends_agents_scans_md(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """掃描 extends/*/clients/*/agents/*.md，跳過底線開頭與非目錄。"""
    agents_dir = tmp_path / "law" / "clients" / "acme" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "helper.md").write_text("---\nmodel: claude-haiku\n---\n助理 prompt", encoding="utf-8")
    # 底線開頭的 client 目錄應被跳過
    skipped = tmp_path / "law" / "clients" / "_template" / "agents"
    skipped.mkdir(parents=True)
    (skipped / "nope.md").write_text("不該被掃到", encoding="utf-8")
    # 沒有 clients 目錄的模組應被跳過
    (tmp_path / "other").mkdir()

    monkeypatch.setattr(linebot_agents.settings, "extends_dir", str(tmp_path))
    ensure = AsyncMock()
    monkeypatch.setattr(linebot_agents, "_ensure_agents", ensure)

    await linebot_agents._seed_extends_agents()

    ensure.assert_awaited_once()
    configs = ensure.await_args.args[0]
    assert [c["name"] for c in configs] == ["helper"]


# ============================================================
# 偏好持久化：set/get active_agent_id（DB 全 mock）
# ============================================================


AGENT_UUID = "00000000-0000-0000-0000-0000000000aa"


@pytest.mark.asyncio
async def test_set_user_and_group_active_agent(monkeypatch: pytest.MonkeyPatch):
    """設定用戶/群組偏好 Agent：帶 UUID 與清除（None）。"""
    conn = AsyncMock()
    monkeypatch.setattr(database, "get_connection", lambda: _FakeCM(conn))

    from uuid import UUID

    await linebot_agents.set_user_active_agent("bot-user-1", AGENT_UUID)
    assert conn.execute.await_args.args[1] == UUID(AGENT_UUID)
    assert conn.execute.await_args.args[2] == "bot-user-1"

    await linebot_agents.set_user_active_agent("bot-user-1", None)
    assert conn.execute.await_args.args[1] is None

    await linebot_agents.set_group_active_agent("bot-group-1", AGENT_UUID)
    assert "bot_groups" in conn.execute.await_args.args[0]
    assert conn.execute.await_args.args[2] == "bot-group-1"

    await linebot_agents.set_group_restricted_agent("bot-group-1", AGENT_UUID)
    assert "restricted_agent_id" in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_get_active_agent_ids(monkeypatch: pytest.MonkeyPatch):
    """查詢用戶/群組偏好 Agent ID：有值、無值、查無資料三種情況。"""
    conn = AsyncMock()
    monkeypatch.setattr(database, "get_connection", lambda: _FakeCM(conn))

    # 有設定偏好 → 回傳字串
    conn.fetchrow = AsyncMock(return_value={"active_agent_id": AGENT_UUID})
    assert await linebot_agents.get_user_active_agent_id("u1") == AGENT_UUID
    assert await linebot_agents.get_group_active_agent_id("g1") == AGENT_UUID

    conn.fetchrow = AsyncMock(return_value={"restricted_agent_id": AGENT_UUID})
    assert await linebot_agents.get_group_restricted_agent_id("g1") == AGENT_UUID

    # 欄位為 NULL → None
    conn.fetchrow = AsyncMock(return_value={"active_agent_id": None})
    assert await linebot_agents.get_user_active_agent_id("u1") is None

    # 查無資料列 → None
    conn.fetchrow = AsyncMock(return_value=None)
    assert await linebot_agents.get_group_active_agent_id("g1") is None
    assert await linebot_agents.get_group_restricted_agent_id("g1") is None


# ============================================================
# get_restricted_agent：受限模式 Agent fallback 鏈
# ============================================================


@pytest.mark.asyncio
async def test_get_restricted_agent_group_preference(monkeypatch: pytest.MonkeyPatch):
    """群組有設定受限 Agent 且啟用 → 直接使用。"""
    monkeypatch.setattr(
        linebot_agents, "get_group_restricted_agent_id", AsyncMock(return_value=AGENT_UUID)
    )
    agent = {"name": "custom-restricted", "is_active": True}
    monkeypatch.setattr(linebot_agents.ai_manager, "get_agent", AsyncMock(return_value=agent))

    assert await linebot_agents.get_restricted_agent("g1") == agent


@pytest.mark.asyncio
async def test_get_restricted_agent_env_default(monkeypatch: pytest.MonkeyPatch):
    """群組偏好不可用 → fallback 到環境變數指定的 Agent。"""
    monkeypatch.setattr(
        linebot_agents, "get_group_restricted_agent_id", AsyncMock(return_value=AGENT_UUID)
    )
    # 群組偏好 Agent 已停用
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "get_agent",
        AsyncMock(return_value={"name": "x", "is_active": False}),
    )
    monkeypatch.setattr(linebot_agents.settings, "bot_default_restricted_agent", "env-agent")
    env_agent = {"name": "env-agent", "is_active": True}
    monkeypatch.setattr(
        linebot_agents.ai_manager, "get_agent_by_name", AsyncMock(return_value=env_agent)
    )

    assert await linebot_agents.get_restricted_agent("g1") == env_agent


@pytest.mark.asyncio
async def test_get_restricted_agent_fallback_to_default(monkeypatch: pytest.MonkeyPatch):
    """環境變數 Agent 也不可用 → 最後 fallback 到 bot-restricted。"""
    monkeypatch.setattr(linebot_agents.settings, "bot_default_restricted_agent", "env-agent")
    default_agent = {"name": linebot_agents.AGENT_BOT_RESTRICTED, "is_active": True}
    get_by_name = AsyncMock(side_effect=[{"name": "env-agent", "is_active": False}, default_agent])
    monkeypatch.setattr(linebot_agents.ai_manager, "get_agent_by_name", get_by_name)

    # 不帶群組 → 跳過群組偏好，直接查環境變數再 fallback
    assert await linebot_agents.get_restricted_agent() == default_agent
    assert get_by_name.await_args_list[0].args[0] == "env-agent"
    assert get_by_name.await_args_list[1].args[0] == linebot_agents.AGENT_BOT_RESTRICTED


@pytest.mark.asyncio
async def test_get_restricted_agent_no_env(monkeypatch: pytest.MonkeyPatch):
    """未設定環境變數 → 直接使用 bot-restricted。"""
    monkeypatch.setattr(linebot_agents.settings, "bot_default_restricted_agent", "")
    default_agent = {"name": linebot_agents.AGENT_BOT_RESTRICTED, "is_active": True}
    get_by_name = AsyncMock(return_value=default_agent)
    monkeypatch.setattr(linebot_agents.ai_manager, "get_agent_by_name", get_by_name)

    assert await linebot_agents.get_restricted_agent() == default_agent
    get_by_name.assert_awaited_once_with(linebot_agents.AGENT_BOT_RESTRICTED)


# ============================================================
# get_linebot_agent：偏好覆蓋路由
# ============================================================


@pytest.mark.asyncio
async def test_get_linebot_agent_group_preference(monkeypatch: pytest.MonkeyPatch):
    """群組有偏好 Agent 且啟用 → 使用偏好。"""
    monkeypatch.setattr(
        linebot_agents, "get_group_active_agent_id", AsyncMock(return_value=AGENT_UUID)
    )
    agent = {"name": "pref-agent", "is_active": True}
    monkeypatch.setattr(linebot_agents.ai_manager, "get_agent", AsyncMock(return_value=agent))
    get_by_name = AsyncMock()
    monkeypatch.setattr(linebot_agents.ai_manager, "get_agent_by_name", get_by_name)

    result = await linebot_agents.get_linebot_agent(is_group=True, bot_group_id="g1")
    assert result == agent
    get_by_name.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_linebot_agent_user_preference_inactive(monkeypatch: pytest.MonkeyPatch):
    """個人偏好 Agent 已停用 → fallback 到預設 linebot-personal。"""
    monkeypatch.setattr(
        linebot_agents, "get_user_active_agent_id", AsyncMock(return_value=AGENT_UUID)
    )
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "get_agent",
        AsyncMock(return_value={"name": "pref", "is_active": False}),
    )
    default_agent = {"name": linebot_agents.AGENT_LINEBOT_PERSONAL, "is_active": True}
    get_by_name = AsyncMock(return_value=default_agent)
    monkeypatch.setattr(linebot_agents.ai_manager, "get_agent_by_name", get_by_name)

    result = await linebot_agents.get_linebot_agent(is_group=False, bot_user_id="u1")
    assert result == default_agent
    get_by_name.assert_awaited_once_with(linebot_agents.AGENT_LINEBOT_PERSONAL)
