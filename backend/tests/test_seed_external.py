"""seed_external 測試。"""

from __future__ import annotations

from pathlib import Path

from ching_tech_os.skills.seed_external import SEED_SKILLS, ensure_seed_skills


def test_ensure_seed_skills_creates_all_files(tmp_path: Path):
    root = tmp_path / "external-skills"

    ensure_seed_skills(root)

    for skill_name, skill_def in SEED_SKILLS.items():
        skill_dir = root / skill_name
        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()

        scripts = skill_def.get("scripts") or {}
        for filename in scripts:
            script_path = skill_dir / "scripts" / filename
            assert script_path.exists()
            assert script_path.stat().st_mode & 0o111


def test_ensure_seed_skills_keeps_existing_skill(tmp_path: Path):
    root = tmp_path / "external-skills"
    skill_dir = root / "base"
    skill_dir.mkdir(parents=True, exist_ok=True)
    custom = skill_dir / "SKILL.md"
    custom.write_text("custom", encoding="utf-8")

    ensure_seed_skills(root)

    assert custom.read_text(encoding="utf-8") == "custom"
