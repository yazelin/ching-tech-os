"""SkillHub client 測試。"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import httpx

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


@pytest.mark.asyncio
async def test_load_index_variants_and_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLHUB_ENABLED", "true")
    client = SkillHubClient(base_url=str(tmp_path / "index.json"))

    client._index_source = ""
    with pytest.raises(SkillHubError, match="未提供 index 來源"):
        await client._load_index(source="")

    with pytest.raises(SkillHubError, match="Index 檔案不存在"):
        await client._load_index(source=str(tmp_path / "missing.json"))

    # items/packages 格式都可解析
    items_path = tmp_path / "items.json"
    items_path.write_text(
        json.dumps(
            {
                "items": [{"slug": "a", "version": "1", "download_url": "https://x/a.zip"}],
                "packages": [{"slug": "b", "version": "1", "download_url": "https://x/b.zip"}],
            }
        ),
        encoding="utf-8",
    )
    loaded = await client._load_index(source=str(items_path))
    assert "a" in loaded["items"]

    # 略過非物件與缺欄位
    mixed_path = tmp_path / "mixed.json"
    mixed_path.write_text(
        json.dumps(
            [
                "not-dict",
                {"slug": "missing-url", "version": "1.0.0"},
                {"slug": "ok", "version": "1.0.0", "download_url": "https://x/ok.zip"},
            ]
        ),
        encoding="utf-8",
    )
    loaded2 = await client._load_index(source=str(mixed_path))
    assert list(loaded2["items"].keys()) == ["ok"]

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("1", encoding="utf-8")
    with pytest.raises(SkillHubError, match="Index JSON 必須是物件或列表"):
        await client._load_index(source=str(invalid_path))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{invalid", encoding="utf-8")
    with pytest.raises(SkillHubError, match="解析 index JSON 失敗"):
        await client._load_index(source=str(bad_json))

    await client.close()


@pytest.mark.asyncio
async def test_load_index_http_and_error_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SKILLHUB_ENABLED", "true")
    client = SkillHubClient(base_url=str(tmp_path / "index.json"))

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    monkeypatch.setattr(
        client._client,
        "get",
        AsyncMock(return_value=_Resp([{"slug": "http-skill", "version": "1", "download_url": "https://x/s.zip"}])),
    )
    loaded = await client._load_index(source="https://example.com/index.json")
    assert "http-skill" in loaded["items"]

    req = httpx.Request("GET", "https://example.com/index.json")
    bad_resp = httpx.Response(502, request=req)
    monkeypatch.setattr(
        client._client,
        "get",
        AsyncMock(side_effect=httpx.HTTPStatusError("bad", request=req, response=bad_resp)),
    )
    with pytest.raises(SkillHubError) as exc1:
        await client._load_index(source="https://example.com/index.json")
    assert exc1.value.status_code == 502

    monkeypatch.setattr(client._client, "get", AsyncMock(side_effect=httpx.HTTPError("net down")))
    with pytest.raises(SkillHubError, match="讀取 index 失敗"):
        await client._load_index(source="https://example.com/index.json")

    await client.close()


@pytest.mark.asyncio
async def test_ensure_index_search_download_and_extract_more_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLHUB_ENABLED", "true")
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "skills": [
                    {"slug": "s1", "version": "1", "download_url": "https://x/s1.zip"},
                    {"slug": "s2", "version": "1", "download_url": "https://x/s2.zip"},
                ]
            }
        ),
        encoding="utf-8",
    )
    client = SkillHubClient(base_url=str(index_path))

    # _ensure_index
    monkeypatch.setattr(client, "_load_index", AsyncMock(return_value={"source": "x", "items": {}}))
    await client._ensure_index()
    client._load_index.assert_awaited_once()

    # search 空 query 與 limit break
    client._index = {
        "source": "x",
        "items": {
            "s1": {"slug": "s1", "title": "Skill One", "description": "demo"},
            "s2": {"slug": "s2", "title": "Skill Two", "description": "demo"},
        },
    }
    assert len(await client.search("", limit=1)) == 1
    assert len(await client.search("skill", limit=1)) == 1

    # download_zip 版本錯誤 / 缺少 url
    client._index = {
        "source": "x",
        "items": {"s1": {"slug": "s1", "version": "1.0.0", "download_url": "https://x/s1.zip"}},
    }
    with pytest.raises(SkillHubError, match="版本不存在"):
        await client.download_zip("s1", "2.0.0")

    client._index = {"source": "x", "items": {"s2": {"slug": "s2", "version": "1.0.0"}}}
    with pytest.raises(SkillHubError, match="缺少下載連結"):
        await client.download_zip("s2", "1.0.0")

    # extract_file_from_zip: download_zip 路徑、basename 比對、找不到檔案
    zip_with_skill = tmp_path / "downloaded.zip"
    _build_zip(zip_with_skill, {"folder/SKILL.md": "hello"})
    monkeypatch.setattr(client, "download_zip", AsyncMock(return_value=zip_with_skill))
    content = await client.extract_file_from_zip("s1", "1.0.0", "SKILL.md")
    assert content == "hello"
    assert zip_with_skill.exists() is False

    zip_no_match = tmp_path / "no-match.zip"
    _build_zip(zip_no_match, {"folder/OTHER.md": "x"})
    monkeypatch.setattr(client, "download_zip", AsyncMock(return_value=zip_no_match))
    assert await client.extract_file_from_zip("s1", "1.0.0", "SKILL.md") is None
    assert zip_no_match.exists() is False

    # write_meta/read_meta
    skill_dir = tmp_path / "skill-dir"
    skill_dir.mkdir(parents=True, exist_ok=True)
    SkillHubClient.write_meta(skill_dir, "slug-x", "1.2.3", owner="ct")
    meta = SkillHubClient.read_meta(skill_dir)
    assert meta is not None
    assert meta["slug"] == "slug-x"

    await client.close()


def test_get_skillhub_client_di_creates_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLHUB_ENABLED", "true")
    fake_client = object()
    monkeypatch.setattr("ching_tech_os.services.skillhub_client.SkillHubClient", lambda: fake_client)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    client = get_skillhub_client_di(request)
    assert client is fake_client
    assert request.app.state.skillhub_client is fake_client
