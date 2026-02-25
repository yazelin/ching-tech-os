"""research-skill check script timeout 設定測試。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_check_research_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src/ching_tech_os/skills/research-skill/scripts/check-research.py"
    )
    spec = importlib.util.spec_from_file_location("ctos_check_research_script", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stale_timeout_has_minimum_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_check_research_module()

    monkeypatch.setenv("RESEARCH_CLAUDE_TIMEOUT_SEC", "120")
    monkeypatch.setenv("RESEARCH_STALE_TIMEOUT_MINUTES", "5")

    # 2 分鐘 worker timeout → stale 至少 max(8, 2+2) = 8 分鐘
    assert module._get_stale_timeout_minutes() == 8


def test_stale_timeout_respects_larger_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_check_research_module()

    monkeypatch.setenv("RESEARCH_CLAUDE_TIMEOUT_SEC", "120")
    monkeypatch.setenv("RESEARCH_STALE_TIMEOUT_MINUTES", "15")

    assert module._get_stale_timeout_minutes() == 15


def test_stale_timeout_scales_with_large_worker_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_check_research_module()

    monkeypatch.setenv("RESEARCH_CLAUDE_TIMEOUT_SEC", "600")
    monkeypatch.setenv("RESEARCH_STALE_TIMEOUT_MINUTES", "5")

    # 10 分鐘 worker timeout → stale 至少 max(8, 10+2) = 12 分鐘
    assert module._get_stale_timeout_minutes() == 12

