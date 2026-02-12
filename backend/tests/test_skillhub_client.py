"""SkillHub client 測試。"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from ching_tech_os.services.skillhub_client import (
    SkillHubClient,
    SkillHubDisabledError,
    SkillHubError,
    get_skillhub_client_di,
    skillhub_enabled,
    validate_slug,
)


def _build_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_feature_flag_and_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLHUB_ENABLED", raising=False)
    assert skillhub_enabled() is False
    with pytest.raises(SkillHubDisabledError):
        SkillHubClient(base_url="x")

    monkeypatch.setenv("SKILLHUB_ENABLED", "true")
    assert skillhub_enabled() is True
    assert validate_slug("skill-a") is True
    assert validate_slug("Skill-A") is False


@pytest.mark.asyncio
async def test_load_index_search_and_get_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLHUB_ENABLED", "true")
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "slug": "demo-skill",
                        "version": "1.0.0",
                        "download_url": "https://example.com/demo.zip",
                        "sha256": "abc",
                        "name": "Demo Skill",
                        "description": "for test",
                        "author": "ct",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    client = SkillHubClient(base_url=str(index_path))

    loaded = await client._load_index()
    assert "demo-skill" in loaded["items"]

    results = await client.search("demo")
    assert results[0]["slug"] == "demo-skill"

    detail = await client.get_skill("demo-skill")
    assert detail["skill"]["slug"] == "demo-skill"
    assert detail["latestVersion"]["version"] == "1.0.0"

    with pytest.raises(SkillHubError):
        await client.get_skill("missing")

    await client.close()


@pytest.mark.asyncio
async def test_download_extract_and_file_from_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLHUB_ENABLED", "true")
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            [
                {
                    "slug": "demo",
                    "version": "1.0.0",
                    "download_url": "https://example.com/demo.zip",
                    "sha256": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    client = SkillHubClient(base_url=str(index_path))
    await client._load_index()

    zip_path = tmp_path / "demo.zip"
    _build_zip(zip_path, {"folder/SKILL.md": "# demo"})

    async def _fake_download_to_temp(_url: str) -> Path:
        return zip_path

    monkeypatch.setattr(client, "_download_to_temp", _fake_download_to_temp)
    result = await client.download_and_extract("demo", "1.0.0", tmp_path / "out")
    assert result["slug"] == "demo"
    assert (tmp_path / "out" / "folder" / "SKILL.md").exists()

    # extract_file_from_zip with zip_data
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("SKILL.md", "hello")
    content = await client.extract_file_from_zip("demo", "1.0.0", "SKILL.md", zip_data=buf.getvalue())
    assert content == "hello"

    await client.close()


def test_sha256_and_safe_extract(tmp_path: Path) -> None:
    # 檢查 _verify_sha256
    zip_path = tmp_path / "x.zip"
    zip_path.write_bytes(b"abc")

    # 無 expected 時直接略過
    SkillHubClient._verify_sha256(zip_path, None)

    with pytest.raises(SkillHubError, match="SHA256 不符"):
        SkillHubClient._verify_sha256(zip_path, "deadbeef")

    # safe extract 正常
    safe_zip = tmp_path / "safe.zip"
    _build_zip(safe_zip, {"ok.txt": "ok"})
    out_dir = tmp_path / "extract"
    SkillHubClient._safe_extract_zip(safe_zip, out_dir)
    assert (out_dir / "ok.txt").exists()

    # zip slip
    slip_zip = tmp_path / "slip.zip"
    _build_zip(slip_zip, {"../evil.txt": "evil"})
    with pytest.raises(SkillHubError, match="Zip slip"):
        SkillHubClient._safe_extract_zip(slip_zip, tmp_path / "extract2")


def test_get_skillhub_client_di(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLHUB_ENABLED", "true")
    fake_client = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(skillhub_client=fake_client)))
    assert get_skillhub_client_di(request) is fake_client
