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


def test_parse_skill_md_app_not_dict() -> None:
    """contributes.app 不是 dict 時應被忽略"""
    text = """---
name: demo
contributes:
  app: "not-a-dict"
---

body
"""
    config, _ = parse_skill_md(text, skill_name="demo")
    assert "app" not in config["contributes"]


def test_parse_skill_md_frontmatter_not_dict() -> None:
    """frontmatter 解析為非 dict 時重置為空"""
    text = """---
- item1
- item2
---

body
"""
    config, body = parse_skill_md(text, skill_name="test")
    assert config == {}
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
