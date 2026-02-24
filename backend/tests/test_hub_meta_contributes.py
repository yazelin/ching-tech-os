"""hub_meta contributes 解析測試。"""

from __future__ import annotations

from ching_tech_os.services.hub_meta import parse_skill_md


def test_parse_skill_md_keeps_valid_contributes_app() -> None:
    text = """---
name: demo
contributes:
  app:
    id: demo-app
    name: Demo App
    icon: mdi-puzzle
---

body
"""
    config, body = parse_skill_md(text, skill_name="demo")
    assert config["contributes"]["app"]["id"] == "demo-app"
    assert body == "body"


def test_parse_skill_md_drops_invalid_contributes_app() -> None:
    text = """---
name: demo
contributes:
  app:
    id: demo-app
    name: Demo App
---

body
"""
    config, _ = parse_skill_md(text, skill_name="demo")
    assert "app" not in config["contributes"]
