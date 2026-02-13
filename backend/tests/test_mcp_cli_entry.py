"""mcp_cli 入口測試。"""

from __future__ import annotations

import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock


def test_mcp_cli_main_entry(monkeypatch):
    run_mock = Mock()
    fake_mcp_module = ModuleType("ching_tech_os.services.mcp")
    fake_mcp_module.mcp = SimpleNamespace(run=run_mock)
    monkeypatch.setitem(sys.modules, "ching_tech_os.services.mcp", fake_mcp_module)

    runpy.run_module("ching_tech_os.mcp_cli", run_name="__main__")

    run_mock.assert_called_once()
